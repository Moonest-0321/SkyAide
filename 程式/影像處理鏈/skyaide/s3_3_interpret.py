"""S3-3 影像判讀：每塊田回答四個問題，加上作物與魚塭（表 34、圖 v8 S3-3）。
  變成水了嗎　淹水三法投票：Otsu（上限 −15 dB）、比災前最近兩期暗 3 dB、低於自身災前時序 3 個標準差；至少兩法同意；插秧灌水期稻田標「疑似灌溉」
  倒了嗎　　　VH 與災前最近兩期相差 2.5 dB 以上；隱馬可夫隨機場（ICM）三級：無、中度、嚴重；已判淹水不重複計算
  地表換掉了嗎 同調性降到 0.5 以下且比災前少 0.3 以上；水面排除
  植物變少了嗎 NDVI 下降扣掉自身去年同期的變化，再與同作物鄰田（雷達無異常者）比，中位數與 MAD 標準分數
  種的是什麼　 災前一年時序特徵 → 分類器（準備期以過去災害標註訓練）；插秧前雷達下降 2 dB 以上才判水稻
  還在養嗎　　 年度 VH 中位數＋Otsu＋形狀過濾找魚塭；池水面積少一半以上為池水流失；夜間燈光低於災前 30 天中位數一半計停電天數
熱區高解析影像：小田與倒伏候選在此下單，回傳後於 S1 補登，再用於判讀。"""
import numpy as np
from scipy import ndimage as ndi

from .common import otsu, fig, show, parcel_map
from . import s1_ingest

CROPS = ["水稻", "香蕉", "麻竹筍", "木瓜", "竹（山坡）"]


# ---------------------------------------------------------------- 像素層級
def flood_vote(R, P):
    vv_pre, vv_post = R["vv_pre"], R["vv_post"]
    thr = min(otsu(vv_post), P["otsu_max_db"])
    m1 = vv_post < thr
    m2 = (vv_post - np.nanmean(vv_pre[-2:], axis=0)) < P["change_db"]
    mu = np.nanmean(vv_pre, axis=0); sd = np.maximum(np.nanstd(vv_pre, axis=0), 0.5)
    m3 = (vv_post - mu) / sd < P["anomaly_z"]
    ok = ~R["perm_water"] & np.isfinite(vv_post)
    votes = (m1.astype(int) + m2 + m3) * ok
    return votes >= P["min_votes"], dict(otsu=m1 & ok, change=m2 & ok, anomaly=m3 & ok, votes=votes, thr=thr)


def lodging_mrf(R, flood, P):
    r = R["vh_post"] - np.nanmean(R["vh_pre"][-2:], axis=0)
    a = np.abs(r)
    valid = np.isfinite(a) & ~flood & ~R["perm_water"]
    a = np.where(valid, a, 0)
    mu = np.array([0.8, (P["moderate_db"] + P["severe_db"]) / 2, P["severe_db"] + 1.5]); sd = np.array([0.9, 0.9, 1.5])
    nll = np.stack([0.5 * ((a - mu[k]) / sd[k]) ** 2 + np.log(sd[k]) for k in range(3)])
    cls = np.where(a >= P["severe_db"], 2, np.where(a >= P["moderate_db"], 1, 0))
    kern = np.array([[0, 1, 0], [1, 0, 1], [0, 1, 0]])
    for _ in range(P["mrf_iter"]):
        same = np.stack([ndi.convolve((cls == k).astype(float), kern, mode="nearest") for k in range(3)])
        energy = nll + P["mrf_beta"] * (4 - same)
        cls = np.argmin(energy, axis=0)
    cls[~valid] = 0
    return cls, r


def burial(R, flood, P):
    return (R["coh_post"] < P["coh_post_max"]) & ((R["coh_pre"] - R["coh_post"]) > P["coh_drop_min"]) & ~flood & ~R["perm_water"]


# ---------------------------------------------------------------- 作物判釋特徵
def crop_features(h):
    """災前一年 NDVI 時序（內插雲遮）與 VH 時序的特徵：均值、年／半年諧波、極值、VH 下降次數。"""
    d = h["nd_days"]; v = h["ndvi"].astype(float)
    m = d >= -365
    d, v = d[m], v[m]
    ok = np.isfinite(v)
    if ok.sum() < 6:
        return None
    vi = np.interp(d, d[ok], v[ok])
    t = 2 * np.pi * d / 365.0
    X = np.column_stack([np.ones_like(t), np.cos(t), np.sin(t), np.cos(2 * t), np.sin(2 * t)])
    coef, *_ = np.linalg.lstsq(X, vi, rcond=None)
    vh = h["vh"].astype(float)
    med = ndi.median_filter(vh, 5, mode="nearest")
    drops = int(np.sum((med - vh) >= 2.0))
    return [coef[0], np.hypot(coef[1], coef[2]), np.hypot(coef[3], coef[4]), vi.max(), vi.min(), vi.std(),
            vh.mean(), vh.std(), vh.min(), drops]


def history_growth(h, crop):
    """生產事實與長時間對照 L1–L4 的指標（構想書表 42）。"""
    d = h["nd_days"]; v = h["ndvi"].astype(float)
    ok = np.isfinite(v)
    out = {}
    last6 = v[ok & (d >= -40)]
    out["pre6_mean"] = float(np.nanmean(last6)) if last6.size else None
    yr = v[ok & (d >= -365)]
    if crop == "水稻":
        out["L1"] = bool(yr.size and np.nanmax(yr) >= 0.6 and np.nanmin(yr) <= 0.35)        # 有升降週期
    else:
        out["L1"] = bool(yr.size and np.nanmedian(yr) >= 0.5)
    need = {"香蕉": 0.75, "麻竹筍": 2.0, "木瓜": 0.6, "竹（山坡）": 2.0}.get(crop)
    if need:
        bare = d[ok & (v < 0.25)]
        years = (-bare.max() / 365.0) if bare.size else 3.0
        out["L2"] = bool(years >= need)
        out["L2_years"] = round(float(years), 2)
    else:
        out["L2"] = True
    # L3：災前 15 天的下降幅度，扣掉前兩年同一時段（逐日內插對齊）的正常變化；取前兩年較大者，避免誤標誠實申請
    def drop(shift):
        dd = np.arange(-45, 1) - shift
        sel = ok & (d >= dd[0] - 12) & (d <= dd[-1] + 12)
        if sel.sum() < 3:
            return np.nan
        s_ = np.interp(dd, d[sel], v[sel])
        return float(s_[:30].mean() - s_[30:].mean())
    drop_now = drop(0)
    past = [x for x in (drop(365), drop(730)) if np.isfinite(x)]
    excess = drop_now - max(past) if past and np.isfinite(drop_now) else np.nan
    out["L3_excess"] = None if not np.isfinite(excess) else round(float(excess), 3)
    out["L3"] = not (np.isfinite(excess) and excess > 0.2)
    def win(lo, hi):
        s = v[ok & (d >= lo) & (d < hi)]
        return float(np.nanmean(s)) if s.size else np.nan
    # L4：前次災害（約 300 天前）後是否恢復
    before = win(-420, -320); after = win(-200, -40)
    out["L4"] = not (np.isfinite(before) and np.isfinite(after) and after < 0.7 * before)
    return out


# ---------------------------------------------------------------- 主流程
def run(ctx, st):
    PF, PL, PB, PV = (ctx["params"][k] for k in ("flood", "lodging", "burial", "vegetation"))
    R = ctx["pre"]
    parcels, pix = ctx["parcels"], ctx["pix"]
    prods = ctx["products"]
    hist = next(x for p, x in prods.values() if p["kind"] == "HISTORY")

    flood, fd = flood_vote(R, PF)
    lod_cls, vh_ratio = lodging_mrf(R, flood, PL)
    bur = burial(R, flood, PB)
    st.metric("淹水 Otsu 門檻", round(fd["thr"], 2), "dB", note=f"上限 {PF['otsu_max_db']} dB")
    st.metric("淹水像素", round(float(flood.mean()) * 100, 2), "%")
    st.metric("倒伏中度／嚴重像素", f"{(lod_cls == 1).mean() * 100:.2f}% ／ {(lod_cls == 2).mean() * 100:.2f}%")
    st.metric("埋沒像素", round(float(bur.mean()) * 100, 2), "%")

    model = ctx.get("crop_model")
    feats = {}
    for pid, p in parcels.items():
        ix = pix[pid]
        f = dict(flood=float(flood.flat[ix].mean()), lodge_mod=float((lod_cls.flat[ix] == 1).mean()),
                 lodge_sev=float((lod_cls.flat[ix] == 2).mean()), buried=float(bur.flat[ix].mean()),
                 vh_ratio=float(np.nanmean(vh_ratio.flat[ix])) if np.isfinite(vh_ratio.flat[ix]).any() else None,
                 votes_mean=float(fd["votes"].flat[ix].mean()))
        tab = {r.get("role"): r for r in p["table"] if r["src"] == "S2"}
        pre, post, lyp, lyq = (tab.get(k, {}) for k in ("pre", "post", "ly_pre", "ly_post"))
        f["cloud_post"] = 1 - post.get("clear", 0.0)
        f["d_this"] = (post["ndvi"] - pre["ndvi"]) if post.get("ndvi") is not None and pre.get("ndvi") is not None and post.get("clear", 0) >= 0.5 else None
        f["d_ly"] = (lyq["ndvi"] - lyp["ndvi"]) if lyq.get("ndvi") is not None and lyp.get("ndvi") is not None else None
        f["veg_anom"] = (f["d_this"] - (f["d_ly"] or 0.0)) if f["d_this"] is not None else None
        s1 = [r for r in p["table"] if r["src"] == "S1"]
        f["vv_last_pre"] = s1[-2]["vv"]
        h = hist.get(pid)
        f["hist"] = history_growth(h, p["declared"]["crop"]) if h and p["kind"] == "farm" else None
        # 作物判釋
        if p["kind"] == "farm" and h:
            x = crop_features(h)
            if x is not None and model is not None:
                pr = model.predict_proba([x])[0]
                k = int(np.argmax(pr))
                f["crop_pred"] = str(model.classes_[k]); f["crop_prob"] = float(pr[k])
                f["rice_drops"] = x[-1]
                if f["crop_pred"] == "水稻" and x[-1] < 1:          # 沒有插秧前下降 2 dB，不判水稻
                    order = np.argsort(pr)[::-1]
                    f["crop_pred"] = str(model.classes_[order[1]]); f["crop_prob"] = float(pr[order[1]])
        # 疑似灌溉：申報或判釋為水稻，且災前最後一期已像水面
        rice = p["declared"]["crop"] == "水稻" or f.get("crop_pred") == "水稻"
        f["irrigation"] = bool(rice and f["vv_last_pre"] is not None and f["vv_last_pre"] < PF["transplant_dark_db"])
        feats[pid] = f

    # 植生：同作物鄰田（雷達無異常）比的穩健標準分數
    lab = ctx["label"]
    centers = {pid: np.array(p["center"]) for pid, p in parcels.items()}
    for pid, f in feats.items():
        if f["veg_anom"] is None:
            f["veg_z"] = None; continue
        crop = parcels[pid]["declared"]["crop"]
        ref = [g["veg_anom"] for q, g in feats.items() if q != pid and g["veg_anom"] is not None
               and parcels[q]["declared"]["crop"] == crop and max(g["flood"], g["lodge_mod"] + g["lodge_sev"], g["buried"]) < 0.1
               and np.linalg.norm(centers[q] - centers[pid]) * ctx["event"]["pixel_m"] <= PV["neighbors_radius_m"]][:PV["neighbors_max"]]
        if len(ref) < 3:
            f["veg_z"] = None; continue
        med = np.median(ref); mad = max(1.4826 * np.median(np.abs(np.array(ref) - med)), 0.02)
        f["veg_z"] = float((f["veg_anom"] - med) / mad)
        f["veg_drop"] = bool(f["veg_anom"] <= -PV["drop_vs_last_year"] and parcels[pid]["eff_ha"] >= PV["min_area_ha"])

    # 魚塭：年度 VH 中位數找水面、形狀過濾；池水流失、停電天數
    PP = ctx["params"]["pond"]
    vh_med = np.nanmedian(R["vh_pre"], axis=0)
    water = vh_med < min(otsu(vh_med), -20)
    comp, n = ndi.label(water)
    pond_mask = np.zeros_like(water)
    for sl, k in zip(ndi.find_objects(comp), range(1, n + 1)):
        reg = comp[sl] == k
        area = reg.sum() * ctx["event"]["pixel_m"] ** 2 / 1e4
        if area >= 0.1 and reg.mean() >= PP["min_rectangularity"]:
            pond_mask[sl] |= reg
    vi = R.get("viirs")
    for pid, p in parcels.items():
        if p["kind"] != "pond":
            continue
        ix = pix[pid]; f = feats[pid]
        f["pond_detected"] = float(pond_mask.flat[ix].mean())
        pre_w = float((np.nanmean(R["vv_pre"], axis=0).flat[ix] < -17).mean())
        post_w = float((R["vv_post"].flat[ix] < -17).mean())
        f["water_pre"], f["water_post"] = pre_w, post_w
        f["water_loss"] = bool(pre_w > 0.5 and post_w < PP["water_loss_ratio"] * pre_w)
        days = 0
        if vi:
            r, c = (np.array(p["center"]) // vi["cell"]).astype(int)
            seq = [(d, o) for d, o, x in zip(vi["days"], vi["outage"][:, r, c], vi["rad"][:, r, c]) if d >= 0]
            for d, o in seq:
                if np.isnan(vi["rad"][list(vi["days"]).index(d), r, c]):
                    continue
                if o:
                    days += 1
                else:
                    break
        f["outage_days"] = days
        f["region_overflow"] = float(flood.flat[ix].mean())

    # 熱區高解析影像下單：小田、Sentinel 倒伏候選（倒伏不能單靠 Sentinel 判 A）
    hr_cand = [pid for pid, p in parcels.items() if p["kind"] == "farm" and p["declared"]["applied"] and
               (p["needs_hr"] or (feats[pid]["lodge_mod"] + feats[pid]["lodge_sev"] >= 0.3 and feats[pid]["flood"] < 0.3))]
    hr = {}
    if hr_cand:
        new, failed = ctx["source"].order_hr(hr_cand)
        for prod in new:
            payload = ctx["source"].load(prod)
            if s1_ingest.register(ctx, st, prod, payload, late=True):
                hr.update({int(k): v for k, v in payload["results"].items()})
        st.check("熱區高解析影像取像", not failed, f"下單 {len(hr_cand)} 塊，回傳 {len(hr)} 塊，取像失敗（雲）{len(failed)} 塊",
                 action="失敗者「影像條件」或「觀測完整」不通過，列 C 並派無人機", severity="info")
    for pid, v in hr.items():
        feats[pid]["hr_lodge"] = v["lodge_frac"]; feats[pid]["hr_canopy_visible"] = v["canopy_visible"]
    ctx["hr_ordered"] = hr_cand

    ctx["feat"] = feats
    ctx["maps"] = dict(flood=flood, lod=lod_cls, bur=bur, vh_ratio=vh_ratio, fd=fd, pond=pond_mask)
    n_irr = sum(f["irrigation"] for f in feats.values())
    st.metric("疑似灌溉（插秧灌水期稻田）", n_irr, "塊", note="不以積水單獨判 A，列 C")
    st.count(判讀坵塊=len(feats), 高解析下單=len(hr_cand), 高解析回傳=len(hr))

    truth = ctx.get("truth")
    if truth:
        farm = [pid for pid, p in parcels.items() if p["kind"] == "farm" and "crop_pred" in feats[pid]]
        acc = np.mean([feats[pid]["crop_pred"] == truth[pid]["crop"] for pid in farm]) if farm else None
        st.metric("（模擬對答案）作物判釋準確率", round(float(acc) * 100, 1) if acc is not None else None, "%")
        fl_t = ctx["source"].dmg == 1 if hasattr(ctx["source"], "dmg") else np.isin(lab, [k for k, t in truth.items() if t["damage"] == "淹水"])
        inter = (flood & fl_t).sum(); union = (flood | fl_t).sum()
        st.metric("（模擬對答案）淹水 IoU", round(float(inter / max(union, 1)), 3))

    if ctx.get("quiet"):
        return
    for pid, f in feats.items():
        ctx["mon"].parcel(pid, "S3-3", {k: v for k, v in f.items()})
        h = hist.get(pid)
        if h is not None:
            ctx["mon"].series(pid, dict(nd_days=h["nd_days"], ndvi=h["ndvi"], vh_days=h["vh_days"], vh=h["vh"]))
    f = fig(13, 3.4)
    show(f.add_subplot(1, 4, 1), fd["otsu"].astype(float), f"① Otsu（{fd['thr']:.1f} dB）", cmap="Blues", vmin=0, vmax=1, cbar=False)
    show(f.add_subplot(1, 4, 2), fd["change"].astype(float), "② 比災前暗 3 dB", cmap="Blues", vmin=0, vmax=1, cbar=False)
    show(f.add_subplot(1, 4, 3), fd["anomaly"].astype(float), "③ 低於自身時序 3σ", cmap="Blues", vmin=0, vmax=1, cbar=False)
    show(f.add_subplot(1, 4, 4), flood.astype(float), "至少兩法同意＝淹水", cmap="Blues", vmin=0, vmax=1, cbar=False)
    st.image("淹水三法投票", f, "災前即為水面者已排除。")
    f = fig(13, 3.6)
    show(f.add_subplot(1, 3, 1), vh_ratio, "VH 災後－災前（dB）", cmap="RdBu", vmin=-8, vmax=8)
    show(f.add_subplot(1, 3, 2), lod_cls.astype(float), "倒伏三級（ICM 平滑）", cmap="YlOrRd", vmin=0, vmax=2)
    show(f.add_subplot(1, 3, 3), bur.astype(float), "埋沒、流失（同調性）", cmap="Oranges", vmin=0, vmax=1, cbar=False)
    st.image("倒伏與埋沒", f, "倒伏：0 無、1 中度、2 嚴重。")
    f = fig(13, 3.6)
    show(f.add_subplot(1, 3, 1), parcel_map(lab, {k: v["veg_z"] for k, v in feats.items() if v["veg_z"] is not None}), "植生標準分數（相對同作物鄰田）", cmap="RdYlGn", vmin=-6, vmax=3)
    cm = {c: i + 1 for i, c in enumerate(CROPS)}
    show(f.add_subplot(1, 3, 2), parcel_map(lab, {k: cm.get(v.get("crop_pred"), 0) for k, v in feats.items()}), "作物判釋：1 水稻 2 香蕉 3 麻竹筍 4 木瓜 5 山坡竹", cmap="tab10", vmin=0, vmax=9)
    po = parcel_map(lab, {k: v.get("outage_days", 0) for k, v in feats.items() if parcels[k]["kind"] == "pond"})
    show(f.add_subplot(1, 3, 3), po, "魚塭停電天數", cmap="Purples", vmin=0, vmax=5)
    st.image("植生、作物、魚塭", f, "植生分數越負代表比同作物鄰田掉得越多（已扣去年同期）。")
