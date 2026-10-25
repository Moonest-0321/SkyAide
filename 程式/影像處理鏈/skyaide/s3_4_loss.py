"""S3-4 損失區間：給範圍，不給單一數字（表 34、圖 25、圖 v8 S3-4）。
半經驗損傷函數（小樣本也能用）與 LightGBM 分位數迴歸（第 10、50、90 百分位）堆疊，
再以保形分位數迴歸（CQR）用校準場的核定結果放寬或收窄區間，使覆蓋率達宣稱的 80%。
每作物均方根誤差 > 10 個百分點者，該作物的損失區間只作參考，案件歸 B。"""
import numpy as np
import lightgbm as lgb

from .common import fig, show, parcel_map

CROPS = ["水稻", "香蕉", "麻竹筍", "木瓜", "竹（山坡）"]
FEATS = ["flood", "lodge_mod", "lodge_sev", "buried", "veg_anom", "veg_z", "cloud_post", "hr_lodge", "irrigation",
         "eff_ha", "slope", "semi"] + [f"crop_{c}" for c in CROPS]
FEAT_ZH = dict(flood="淹水比例", lodge_mod="倒伏中度比例", lodge_sev="倒伏嚴重比例", buried="埋沒比例", veg_anom="NDVI 比去年同期多降",
               veg_z="植生標準分數", cloud_post="災後雲遮比例", hr_lodge="高解析倒伏比例", irrigation="疑似灌溉", eff_ha="面積",
               slope="坡度", semi="半經驗損傷函數")


def semi_empirical(crop, f):
    """半經驗損傷函數：取各訊號換算的損失最大者（%）。"""
    fw = {"水稻": 0.95, "木瓜": 0.85, "香蕉": 0.80, "麻竹筍": 0.70, "竹（山坡）": 0.60}.get(crop, 0.8)
    lod = f.get("hr_lodge")
    lod_loss = 0.9 * lod if lod is not None else 0.45 * f["lodge_mod"] + 0.85 * f["lodge_sev"]
    radar = max(fw * f["flood"], lod_loss, 0.95 * f["buried"])
    veg = -f["veg_anom"] * 1.2 if f.get("veg_anom") is not None and f["veg_anom"] < 0 else 0.0
    base = radar if radar > 0.05 else veg
    return float(np.clip(100 * base + 3, 0, 100))


def feature_rows(ctx):
    rows = []
    for pid, p in ctx["parcels"].items():
        if p["kind"] != "farm":
            continue
        f = ctx["feat"][pid]
        crop = p["declared"]["crop"]
        r = dict(id=pid, crop=crop, flood=f["flood"], lodge_mod=f["lodge_mod"], lodge_sev=f["lodge_sev"], buried=f["buried"],
                 veg_anom=f.get("veg_anom"), veg_z=f.get("veg_z"), cloud_post=f["cloud_post"], hr_lodge=f.get("hr_lodge"),
                 irrigation=float(f["irrigation"]), eff_ha=p["eff_ha"], slope=p["slope"], semi=semi_empirical(crop, f))
        for c in CROPS:
            r[f"crop_{c}"] = float(crop == c)
        rows.append(r)
    return rows


def _X(rows):
    return np.array([[np.nan if r[k] is None else r[k] for k in FEATS] for r in rows], dtype=float)


def run(ctx, st):
    P = ctx["params"]["loss"]
    rows = feature_rows(ctx)
    tr, ca = ctx.get("train_rows", []), ctx.get("calib_rows", [])
    qs = P["quantiles"]
    models = {}
    if len(tr) >= 50:
        for q in qs:
            m = lgb.LGBMRegressor(objective="quantile", alpha=q, verbose=-1, random_state=0, **P["lgbm"])
            m.fit(_X(tr), np.array([r["y"] for r in tr]))
            models[q] = m
    st.check("LightGBM 分位數模型", bool(models), f"以 {len(tr)} 筆過去核定損失率訓練" if models else "訓練資料不足，只用半經驗損傷函數",
             severity="warn", action="區間只作參考")

    def predict(rs):
        X = _X(rs)
        if models:
            Q = np.column_stack([models[q].predict(X) for q in qs])
        else:
            semi = np.array([r["semi"] for r in rs]); Q = np.column_stack([semi - 15, semi, semi + 15])
        Q = np.sort(np.clip(Q, 0, 100), axis=1)
        return Q

    # 保形校準（CQR）：上下兩側分開，各側目標 1 − (1 − 覆蓋率) / 2；
    # 依「有無受損訊號」分組校準（Mondrian），避免沒有訊號的田被有部分受損的田撐寬
    grp = lambda r: "有受損訊號" if r["semi"] >= 10 else "無受損訊號"
    adj = {}
    rmse_by = {}
    if ca:
        Qc = predict(ca); yc = np.array([r["y"] for r in ca]); gc = np.array([grp(r) for r in ca])
        cov_before = float(np.mean((yc >= Qc[:, 0]) & (yc <= Qc[:, 2])))
        side = 1 - (1 - P["coverage_target"]) / 2

        def cal(m):
            n = int(m.sum()); level = min(1.0, np.ceil((n + 1) * side) / n)
            return float(np.quantile(Qc[m, 0] - yc[m], level)), float(np.quantile(yc[m] - Qc[m, 2], level))
        adj["全部"] = cal(np.ones(len(yc), bool))
        rows_adj = []
        for g in ("有受損訊號", "無受損訊號"):
            m = gc == g
            adj[g] = cal(m) if m.sum() >= 20 else adj["全部"]
            rows_adj.append([g, int(m.sum()), round(-adj[g][0], 2), round(adj[g][1], 2)])
        lo_adj = np.array([adj[g][0] for g in gc]); hi_adj = np.array([adj[g][1] for g in gc])
        cov_after = float(np.mean((yc >= Qc[:, 0] - lo_adj) & (yc <= Qc[:, 2] + hi_adj)))
        st.metric("校準前覆蓋率", round(cov_before * 100, 1), "%", target="80%")
        st.metric("校準後覆蓋率", round(cov_after * 100, 1), "%", target="100 件時 72%–88%", ok=70 <= cov_after * 100 <= 92)
        st.table("保形校準調整（分組）", ["組別", "校準件數", "下限調整", "上限調整"], rows_adj, note="單位：個百分點；負值往下放寬、正值往上放寬")
        for c in CROPS:
            m = np.array([r["crop"] == c for r in ca])
            if m.sum() >= 5:
                rmse_by[c] = float(np.sqrt(np.mean((Qc[m, 1] - yc[m]) ** 2)))
        st.table("各作物損失中間值的均方根誤差（校準場）", ["作物", "件數", "均方根誤差", "使用方式"],
                 [[c, int(sum(r["crop"] == c for r in ca)), round(v, 1), "可支撐 A" if v <= P["rmse_max"] else "只作參考，案件歸 B"] for c, v in rmse_by.items()],
                 note=f"目標 ≤ {P['rmse_max']} 個百分點（表 70）")
    ctx["loss_ref_only"] = {c: v > P["rmse_max"] for c, v in rmse_by.items()}

    Q = predict(rows) if rows else np.zeros((0, 3))
    for i, r in enumerate(rows):
        a = adj.get(grp(r), adj.get("全部", (0.0, 0.0)))
        Q[i, 0] = np.clip(Q[i, 0] - a[0], 0, 100); Q[i, 2] = np.clip(Q[i, 2] + a[1], 0, 100)
    contrib = models[0.5].predict(_X(rows), pred_contrib=True) if models and rows else None
    out = {}
    for i, r in enumerate(rows):
        q10, q50, q90 = (round(float(v), 1) for v in Q[i])
        p20 = float(np.interp(20, [q10, q50, q90] if q90 > q10 else [q10, q10 + 0.1, q10 + 0.2], [0.1, 0.5, 0.9], left=0.0, right=1.0))
        top = []
        if contrib is not None:
            c = contrib[i][:-1]
            for k in np.argsort(-np.abs(c))[:3]:
                v = r[FEATS[k]]
                top.append(f"{FEAT_ZH.get(FEATS[k], FEATS[k])} {'—' if v is None else round(v, 3)}（{'+' if c[k] >= 0 else '−'}{abs(c[k]):.1f}）")
        out[r["id"]] = dict(p10=q10, p50=q50, p90=q90, p_ge20=round(1 - p20, 3), semi=round(r["semi"], 1), top=top)
    ctx["loss"] = out
    st.count(估計坵塊=len(out))

    truth = ctx.get("truth")
    if truth and out:
        y = np.array([truth[k]["loss"] for k in out]); q = np.array([[v["p10"], v["p50"], v["p90"]] for v in out.values()])
        st.metric("（模擬對答案）本場覆蓋率", round(float(np.mean((y >= q[:, 0]) & (y <= q[:, 2]))) * 100, 1), "%")
        st.metric("（模擬對答案）中間值均方根誤差", round(float(np.sqrt(np.mean((q[:, 1] - y) ** 2))), 1), "個百分點")

    if ctx.get("quiet"):
        return
    for pid, v in out.items():
        ctx["mon"].parcel(pid, "S3-4", v)
    if models:
        imp = models[0.5].booster_.feature_importance("gain")
        order = np.argsort(imp)[::-1][:10]
        f = fig(11, 3.8)
        ax = f.add_subplot(1, 2, 1)
        ax.barh([FEAT_ZH.get(FEATS[k], FEATS[k].replace("crop_", "作物：")) for k in order][::-1], imp[order][::-1], color="#2f6fdb")
        ax.set_title("中間值模型的特徵重要度（gain）", fontsize=10)
        ax = f.add_subplot(1, 2, 2)
        idx = np.argsort(Q[:, 1])
        ax.fill_between(range(len(idx)), Q[idx, 0], Q[idx, 2], color="#8fa9dd", alpha=0.6, label="第 10–90 百分位")
        ax.plot(range(len(idx)), Q[idx, 1], color="#15213b", lw=1, label="中間值")
        if truth:
            ax.scatter(range(len(idx)), [truth[rows[i]["id"]]["loss"] for i in idx], s=6, color="#c0392b", label="（模擬）真實損失", zorder=3)
        ax.axhline(20, color="k", ls="--", lw=0.8); ax.axhline(40, color="#1d6b43", ls=":", lw=0.8); ax.axhline(10, color="#5b3f9e", ls=":", lw=0.8)
        ax.set_title("本場每塊田的損失區間（依中間值排序）", fontsize=10); ax.set_ylabel("%"); ax.legend(fontsize=7, loc="upper left")
        st.image("損失模型", f, "虛線為 20% 門檻；綠點線 40%（A 達標下限）、紫點線 10%（A 未達標上限）。")
    lab = ctx["label"]
    f = fig(10, 3.6)
    show(f.add_subplot(1, 2, 1), parcel_map(lab, {k: v["p50"] for k, v in out.items()}), "損失中間值（%）", cmap="YlOrRd", vmin=0, vmax=100)
    show(f.add_subplot(1, 2, 2), parcel_map(lab, {k: v["p90"] - v["p10"] for k, v in out.items()}), "區間寬度（個百分點）", cmap="viridis", vmin=0, vmax=60)
    st.image("損失區間地圖", f, "")
