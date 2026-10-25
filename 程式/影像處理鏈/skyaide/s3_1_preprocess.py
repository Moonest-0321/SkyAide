"""S3-1 前處理：把影像變成可比較的數值（表 31）。
雷達：輻射地形正規化、Lee 濾波、換算 dB、VH／VV；以地形模型標出雷達陰影與疊置區。
光學：Cloud Score+ 逐像素去雲（門檻 0.60），計算 NDVI、NDRE、NDWI、MNDWI；雲遮像素不得作為災後證據。
夜間燈光：以災前 30 天中位數為基準。"""
import numpy as np

from .common import to_db, lee_filter, enl, fig, show


def terrain(dem, px, inc_deg, P):
    gy, gx = np.gradient(dem, px)
    slope_range = -gx                         # 朝西觀測：地面往東升高 → 面向雷達
    theta = np.radians(inc_deg)
    local = theta - np.arctan(slope_range)
    gain = np.clip(np.cos(local) / np.cos(theta), 0.05, 6)
    shadow = np.arctan(-slope_range) > (np.pi / 2 - theta) * P["shadow_factor"]
    layover = np.arctan(slope_range) > theta * P["layover_factor"]
    slope_deg = np.degrees(np.arctan(np.hypot(gx, gy)))
    return gain, shadow, layover, slope_deg


def run(ctx, st):
    P = ctx["params"]["preprocess"]
    prods = ctx["products"]
    ev = ctx["event"]
    dem_p, dem = next((p, x) for p, x in prods.values() if p["kind"] == "DEM")
    gain, shadow, layover, slope = terrain(dem["dem"], ev["pixel_m"], dem_p["meta"]["incidence_deg"], P)
    st.check("精密軌道、熱雜訊去除、輻射校正為 σ⁰", True, "由來源 GRD 產品完成（模擬資料視為已完成）", severity="info")

    def prep(pid):
        _, x = prods[pid]
        vv = x["vv"] / gain; vh = x["vh"] / gain               # 輻射地形正規化
        vv_f = lee_filter(vv, P["lee_window"], P["lee_looks"]); vh_f = lee_filter(vh, P["lee_window"], P["lee_looks"])
        vv_db, vh_db = to_db(vv_f), to_db(vh_f)
        vv_db[shadow | layover] = np.nan; vh_db[shadow | layover] = np.nan
        return vv_db, vh_db, x["vv"], vv_f

    pre = [prep(pid) for pid in ctx["s1_pre"]]
    post = prep(ctx["s1_post"])
    R = dict(vv_pre=np.stack([p[0] for p in pre]), vh_pre=np.stack([p[1] for p in pre]),
             vv_post=post[0], vh_post=post[1], shadow=shadow, layover=layover, slope=slope, gain=gain)
    R["ratio_post"] = R["vh_post"] - R["vv_post"]
    coh = sorted([(p, x) for p, x in prods.values() if p["kind"] == "S1_COH"], key=lambda t: t[0]["day"])
    R["coh_pre"], R["coh_post"] = coh[0][1]["coh"], coh[-1][1]["coh"]

    # Lee 濾波效果：均勻區的等效視數
    lab = next(x for p, x in prods.values() if p["kind"] == "CADASTRE")["label"]
    big = np.bincount(lab.ravel()); pid_big = int(np.argmax(big[1:]) + 1)
    homo = lab == pid_big
    enl_before, enl_after = enl(post[2], homo), enl(post[3], homo)
    st.metric("斑點濾波前等效視數", round(enl_before, 1), "")
    st.metric("斑點濾波後等效視數", round(enl_after, 1), "", ok=enl_after > enl_before * 2, note="越大代表斑點越少")
    st.check("Lee 濾波有效降低斑點", enl_after > enl_before * 2, f"等效視數 {enl_before:.1f} → {enl_after:.1f}", severity="warn")
    sh = float((shadow | layover).mean())
    st.metric("雷達陰影與疊置面積", round(sh * 100, 1), "%")
    st.check("陰影疊置區已標出並排除", True, f"{sh * 100:.1f}% 像素不參與雷達判讀", severity="info")

    # 光學
    thr = P["cloud_score_threshold"]
    opt = {}
    for role, pid in ctx["s2"].items():
        _, x = prods[pid]
        clear = x["cs"] >= thr
        def idx(a, b):
            v = (a - b) / np.maximum(a + b, 1e-6)
            return np.where(clear, v, np.nan)
        opt[role] = dict(clear=clear, ndvi=idx(x["B8"], x["B4"]), ndre=idx(x["B8"], x["B5"]),
                         ndwi=idx(x["B3"], x["B8"]), mndwi=idx(x["B3"], x["B11"]))
        st.metric(f"光學清晰比例（{role}）", round(float(clear.mean()) * 100, 1), "%")
    R["opt"] = opt
    if "post" in opt:
        cf = float(opt["post"]["clear"].mean())
        st.check("災後光學可用", cf >= 0.5, f"清晰 {cf * 100:.0f}%；雲遮像素不作災後證據，雷達先判", action="光學有雲時不等待", severity="info")

    # 夜間燈光
    vi = next(((p, x) for p, x in prods.values() if p["kind"] == "VIIRS"), None)
    if vi:
        p, x = vi
        days, rad = x["days"], x["rad"]
        Pp = ctx["params"]["pond"]
        base = np.nanmedian(rad[(days < 0) & (days >= -Pp["baseline_days"])], axis=0)
        out = rad < Pp["outage_ratio"] * base
        R["viirs"] = dict(days=days, rad=rad, base=base, outage=out, cell=p["meta"]["cell_px"])
        nan_days = [int(d) for d, r in zip(days, rad) if np.all(np.isnan(r))]
        st.check("夜間燈光有效觀測", len(nan_days) <= 2, f"雲遮無觀測日：{nan_days or '無'}", severity="info")

    ctx["pre"] = R
    st.count(雷達期數=len(pre) + 1, 光學期數=len(opt))

    if ctx.get("quiet"):
        return
    _, raw = prods[ctx["s1_post"]]
    f = fig(12, 3.6)
    show(f.add_subplot(1, 4, 1), to_db(raw["vv"]), "原始 VV（未正規化）", vmin=-25, vmax=0)
    show(f.add_subplot(1, 4, 2), to_db(raw["vv"] / gain), "地形正規化後", vmin=-25, vmax=0)
    show(f.add_subplot(1, 4, 3), R["vv_post"], "Lee 濾波後（陰影疊置已遮）", vmin=-25, vmax=0)
    m = np.zeros(shadow.shape); m[shadow] = 1; m[layover] = 2
    show(f.add_subplot(1, 4, 4), m, "陰影（1）、疊置（2）", cmap="magma", vmin=0, vmax=2)
    st.image("雷達前處理", f, "右上山坡的亮暗差異在地形正規化後消除；陰影與疊置區不參與判讀。")
    if "post" in opt:
        f = fig(12, 3.6)
        show(f.add_subplot(1, 4, 1), opt["pre"]["ndvi"], "災前 NDVI", cmap="RdYlGn", vmin=-0.2, vmax=0.9)
        show(f.add_subplot(1, 4, 2), opt["post"]["ndvi"], "災後 NDVI（雲已去除）", cmap="RdYlGn", vmin=-0.2, vmax=0.9)
        show(f.add_subplot(1, 4, 3), opt["post"]["clear"].astype(float), "災後清晰像素", cmap="gray", vmin=0, vmax=1)
        show(f.add_subplot(1, 4, 4), opt["post"]["mndwi"], "災後 MNDWI（水體）", cmap="Blues", vmin=-0.5, vmax=0.8)
        st.image("光學前處理", f, f"Cloud Score+ 門檻 {thr}；白色為清晰像素。")
