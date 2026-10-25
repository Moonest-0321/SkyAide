"""S3-2 坵塊化：從一格 10 米變成一塊田（表 31 坵塊化、表 32）。
對位與排除：與地籍套疊檢查偏移；災前即為水面者不做淹水判讀；非農地以農地範圍排除。
坵塊向內縮 10 米（圖解地籍區 20 米）取統計；內縮後少於 5 格改用熱區高解析影像，沒有則「影像條件」不通過。
每坵塊、每日期一列：各項數值、雲與補值旗標。"""
import numpy as np
from scipy import ndimage as ndi

from .common import otsu, fig, show


def inset_label(label, px):
    out = label.copy()
    for _ in range(px):
        mx = ndi.maximum_filter(out, 3); mn = ndi.minimum_filter(out, 3)
        out = np.where(mx == mn, out, 0)
    return out


def _nanmean(a):
    a = a[np.isfinite(a)]
    return float(a.mean()) if a.size else None


def run(ctx, st):
    P = ctx["params"]["parcel"]
    prods = ctx["products"]
    R = ctx["pre"]
    cad = next(x for p, x in prods.values() if p["kind"] == "CADASTRE")
    farm = next(x for p, x in prods.values() if p["kind"] == "LANDUSE")["farmland"].astype(bool)
    dec = next(x for p, x in prods.values() if p["kind"] == "DECLARE")
    lab = cad["label"]
    attrs = cad["attrs"]

    # 災前即為水面（河、魚塭、埤塘）：災前平均 VV 低於 Otsu 門檻
    pre_mean = np.nanmean(R["vv_pre"], axis=0)
    thr = min(otsu(pre_mean), ctx["params"]["flood"]["otsu_max_db"])
    perm_water = pre_mean < thr
    R["perm_water"] = perm_water

    in1 = inset_label(lab, P["inset_px"])
    in2 = inset_label(lab, P["inset_px_graphic"])
    nd_pre = R["opt"]["pre"]["ndvi"] if "pre" in R["opt"] else None
    parcels = {}
    pix = {}
    excluded = 0
    for pid, a in attrs.items():
        pid = int(pid)
        d = dec.get(pid)
        full = lab == pid
        if not full.any():
            continue
        farm_frac = float(farm[full].mean())
        if d is None or farm_frac < 0.5:
            excluded += 1
            continue                                   # 非農地（建物、防風林）不判讀
        kind = "pond" if d["crop"] == "魚塭" else "farm"
        ins = (in2 if a["graphic"] else in1) == pid
        n_ins = int(ins.sum())
        use = ins if n_ins else full
        # 對位檢查：內縮後的像素若混入鄰田（NDVI 明顯不同的比例過高），視為對位不確定
        mix = None
        if nd_pre is not None and kind == "farm":
            v = nd_pre[use]; v = v[np.isfinite(v)]
            if v.size >= 4:
                mix = float(np.mean(np.abs(v - np.median(v)) > P["misreg_ndvi_diff"]))
        misreg = mix is not None and mix > P["misreg_mix_frac"]
        rec = dict(id=pid, land_no=a["land_no"], kind=kind, graphic=bool(a["graphic"]), reg_ha=a["reg_ha"],
                   eff_ha=round(float(a["reg_ha"]) * farm_frac, 4),          # 有效種植面積：登記面積扣除非農地（農路、建物、水塘）
                   n_full=int(full.sum()), n_inset=n_ins, needs_hr=n_ins < P["min_sentinel_px"],
                   mix_frac=mix, misreg=misreg, perm_water_frac=float(perm_water[use].mean()),
                   shadow_frac=float((R["shadow"] | R["layover"])[use].mean()),
                   slope=float(np.nanmean(R["slope"][full])),
                   declared=d, center=[float(x) for x in np.argwhere(full).mean(0)])
        # 時序表：每日期一列
        rows = []
        for i, pid_s1 in enumerate(ctx["s1_pre"] + [ctx["s1_post"]]):
            vv = R["vv_pre"][i] if i < len(ctx["s1_pre"]) else R["vv_post"]
            vh = R["vh_pre"][i] if i < len(ctx["s1_pre"]) else R["vh_post"]
            day = prods[pid_s1][0]["day"]
            rows.append(dict(src="S1", day=day, vv=_nanmean(vv[use]), vh=_nanmean(vh[use]),
                             radar_valid=float(np.isfinite(vv[use]).mean())))
        for role, o in R["opt"].items():
            day = prods[ctx["s2"][role]][0]["day"]
            cf = float(o["clear"][use].mean())
            rows.append(dict(src="S2", role=role, day=day, ndvi=_nanmean(o["ndvi"][use]), ndre=_nanmean(o["ndre"][use]),
                             mndwi=_nanmean(o["mndwi"][use]), clear=cf, flag="雲遮" if cf < 0.5 else ""))
        rec["coh_pre"] = _nanmean(R["coh_pre"][use]); rec["coh_post"] = _nanmean(R["coh_post"][use])
        rec["table"] = rows
        parcels[pid] = rec
        pix[pid] = np.flatnonzero(use)
    ctx["parcels"] = parcels
    ctx["pix"] = pix
    ctx["label"] = lab
    farm_p = [p for p in parcels.values() if p["kind"] == "farm"]
    n_small = sum(p["needs_hr"] for p in farm_p)
    n_mis = sum(p["misreg"] for p in farm_p)
    st.count(坵塊=len(parcels), 農田=len(farm_p), 魚塭=len(parcels) - len(farm_p), 非農地排除=excluded)
    st.metric("內縮後少於 5 格（改用高解析或列 C）", n_small, "筆")
    st.metric("對位不確定", n_mis, "筆")
    st.metric("災前即為水面的像素", round(float(perm_water.mean()) * 100, 1), "%", note="不做淹水判讀")
    st.check("非農地以農地範圍排除", True, f"排除 {excluded} 筆（建物、防風林）", severity="info")
    st.check("對位檢查", True, f"{n_mis} 筆內縮後混入鄰田比例 > {P['misreg_mix_frac']:.0%}，標為對位不確定", severity="info")

    truth = ctx.get("truth")
    if truth:
        tp = sum(1 for p in farm_p if p["misreg"] and any(truth[p["id"]]["misreg"]))
        actual = sum(1 for p in farm_p if any(truth[p["id"]]["misreg"]))
        st.metric("（模擬對答案）真實偏移被標出", f"{tp}/{actual}", "", note="地籍偏移但鄰田作物相同時，影像上看不出來")

    if ctx.get("quiet"):
        return
    for p in parcels.values():
        ctx["mon"].parcel(p["id"], "S3-2", dict(land_no=p["land_no"], kind=p["kind"], reg_ha=p["reg_ha"], eff_ha=p["eff_ha"],
                                                n_inset=p["n_inset"], needs_hr=p["needs_hr"], misreg=p["misreg"],
                                                mix_frac=p["mix_frac"], graphic=p["graphic"], shadow_frac=p["shadow_frac"],
                                                table=p["table"]))
    f = fig(12, 3.8)
    kinds = np.zeros(lab.shape)
    for p in parcels.values():
        kinds.flat[pix[p["id"]]] = 1 if p["kind"] == "farm" else 2
        if p["misreg"]:
            kinds.flat[pix[p["id"]]] = 3
        if p["needs_hr"]:
            kinds[lab == p["id"]] = 4
    show(f.add_subplot(1, 3, 1), lab % 17, "地籍坵塊", cmap="tab20", cbar=False)
    show(f.add_subplot(1, 3, 2), kinds, "內縮後：1 農田 2 魚塭 3 對位不確定 4 太小", cmap="viridis", vmin=0, vmax=4)
    show(f.add_subplot(1, 3, 3), perm_water.astype(float), "災前即為水面（不判淹水）", cmap="Blues", vmin=0, vmax=1)
    st.image("坵塊化", f, "每塊田向內縮 10 米（圖解地籍 20 米）後取統計；黃色為內縮後不足 5 格的小田。")
    st.table("坵塊時序表（前 8 筆農田）", ["坵塊", "地號", "內縮格數", "災前 VV", "災後 VV", "災後 NDVI", "災後清晰"],
             [[p["id"], p["land_no"], p["n_inset"], p["table"][len(ctx["s1_pre"]) - 1]["vv"], p["table"][len(ctx["s1_pre"])]["vv"],
               next((r["ndvi"] for r in p["table"] if r.get("role") == "post"), None),
               next((r["clear"] for r in p["table"] if r.get("role") == "post"), None)] for p in farm_p[:8]])
