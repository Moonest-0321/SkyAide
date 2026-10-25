"""S1 資料輸入：登錄與檢核（表 37 S1、圖 v8 S1）。
每個檔案記錄來源、產品編號與 SHA-256，比對官方檢查碼；檢查有效像素率、數值範圍、網格一致；
災前影像距災害 ≤ 10 日。未通過：停止計算，補件或改用其他日期影像。"""
from datetime import datetime

import numpy as np

from .common import sha256_payload, to_db, fig, show

RANGES = {"S1_GRD": (0, 50), "S1_COH": (0, 1), "S2_L2A": (0, 1.2), "DEM": (-50, 4000), "VIIRS": (0, 500)}


def _arrays(payload):
    if isinstance(payload, dict):
        return {k: v for k, v in payload.items() if isinstance(v, np.ndarray) and v.ndim >= 2}
    return {}


def register(ctx, st, product, payload, late=False):
    """登錄一筆產品：雜湊、比對官方檢查碼、有效像素、數值範圍、網格。回傳是否可用。"""
    P = ctx["params"]["s1"]
    shape = tuple(ctx["event"]["shape"])
    h = sha256_payload(payload)
    ok_ck = h == product["official_checksum"]
    arrs = _arrays(payload)
    valid = min([float(np.isfinite(a).mean()) for a in arrs.values()] or [1.0])
    lo, hi = RANGES.get(product["kind"], (-np.inf, np.inf))
    in_range = all(np.nanmin(a) >= lo and np.nanmax(a) <= hi for k, a in arrs.items() if k not in ("days",)) if arrs else True
    grid = all(a.shape[-2:] == shape for a in arrs.values() if product["kind"] not in ("VIIRS",)) if arrs else True
    usable = ok_ck and grid and in_range and (valid >= P["valid_pixel_min"] or product["kind"] in ("VIIRS", "S2_L2A"))
    rec = dict(id=product["id"], kind=product["kind"], sensor=product["sensor"], datetime=product["datetime"],
               day=product.get("day"), sha256=h, official=product["official_checksum"], checksum_ok=ok_ck,
               valid_ratio=round(valid, 4), in_range=bool(in_range), grid_ok=bool(grid), usable=bool(usable), late=late)
    ctx["manifest"].append(rec)
    if usable:
        ctx["products"][product["id"]] = (product, payload)
    else:
        why = [] if ok_ck else ["檢查碼不符"]
        why += [] if grid else ["網格不一致"]
        why += [] if in_range else ["數值超出範圍"]
        st.warn(f"{product['kind']} {product['id']} 不採用：{'、'.join(why) or '有效像素不足'}")
    return usable


def run(ctx, st):
    src = ctx["source"]
    P = ctx["params"]["s1"]
    ctx["manifest"] = []
    ctx["products"] = {}
    cat = src.catalog()
    st.log(f"資料來源 {src.name}：{len(cat)} 筆產品")
    for prod in cat:
        register(ctx, st, prod, src.load(prod))
    man = ctx["manifest"]
    bad = [m for m in man if not m["checksum_ok"]]
    st.check("比對官方檢查碼", not bad, f"{len(man) - len(bad)}/{len(man)} 筆相符" + (f"；不符：{', '.join(m['id'] for m in bad)}" if bad else ""),
             action="不符的產品不採用，改用其他日期影像", severity="warn", basis="表 37 S1")
    st.check("網格一致", all(m["grid_ok"] for m in man), "所有影像與事件網格相同", severity="stop")

    # 雷達：災前影像新鮮度與期數
    usable = {pid: p for pid, (p, _) in ctx["products"].items()}
    s1_pre = sorted([p for p in usable.values() if p["kind"] == "S1_GRD" and p["day"] < 0], key=lambda p: p["day"])
    s1_post = [p for p in usable.values() if p["kind"] == "S1_GRD" and p["day"] >= 0]
    fresh = -s1_pre[-1]["day"] if s1_pre else 999
    st.check("災前雷達影像距災害 ≤ 10 日", fresh <= P["pre_image_max_days"], f"最近一期災前雷達距災害 {fresh} 日",
             action="停止計算，補件或改用其他日期影像", severity="stop", basis="表 37 S1、表 71")
    st.check(f"災前雷達至少 {P['min_pre_s1_scenes']} 期（時序異常法需要）", len(s1_pre) >= P["min_pre_s1_scenes"],
             f"可用 {len(s1_pre)} 期", action="停止計算", severity="stop")
    if len(s1_pre) < 6:
        st.warn(f"災前雷達只剩 {len(s1_pre)} 期（原規格 6 期），時序異常法以 {len(s1_pre)} 期計算")
    st.check("災後雷達已到站", bool(s1_post), f"{len(s1_post)} 期", action="等待到站", severity="stop")
    s2 = {p["meta"]["role"]: p for p in usable.values() if p["kind"] == "S2_L2A"}
    s2_fresh = -s2["pre"]["day"] if "pre" in s2 else 999
    st.check("災前光學影像距災害 ≤ 10 日", s2_fresh <= P["pre_image_max_days"], f"{s2_fresh} 日",
             action="光學只作參考", severity="warn")
    st.check("去年同期光學基準", "ly_pre" in s2 and "ly_post" in s2, "去年同期災前、災後各一期", severity="warn",
             action="植生只比鄰田，不比自身往年")
    for k in ("CADASTRE", "LANDUSE", "DECLARE", "HISTORY", "DEM", "S1_COH", "VIIRS", "APP_PHOTO"):
        have = any(p["kind"] == k for p in usable.values())
        st.check(f"{k} 已登錄", have, "", severity="stop" if k in ("CADASTRE", "DECLARE", "DEM") else "warn")

    ctx["s1_pre"] = [p["id"] for p in s1_pre]
    ctx["s1_post"] = s1_post[-1]["id"]
    ctx["s2"] = {k: v["id"] for k, v in s2.items()}
    st.count(登錄=len(man), 採用=len(usable), 不採用=len(man) - len(usable))
    st.metric("災前雷達新鮮度", fresh, "日", target="≤ 10", ok=fresh <= 10)
    st.metric("雷達到站時間", ctx["event"]["radar_arrival"])
    st.table("輸入清單（來源、產品編號、取得時間、SHA-256）",
             ["種類", "產品編號", "日期", "SHA-256（前 16 碼）", "檢查碼", "有效像素", "採用"],
             [[m["kind"], m["id"], m["datetime"][:16], m["sha256"][:16], "相符" if m["checksum_ok"] else "不符",
               m["valid_ratio"], "是" if m["usable"] else "否"] for m in man])

    # 監看圖：災後原始雷達與光學
    if not ctx.get("quiet"):
        _, post = ctx["products"][ctx["s1_post"]]
        f = fig(11, 3.6)
        show(f.add_subplot(1, 3, 1), to_db(post["vv"]), "災後 VV（原始 σ⁰，dB）", vmin=-25, vmax=0)
        if "post" in s2:
            _, o = ctx["products"][s2["post"]["id"]]
            rgb = np.dstack([o["B4"], o["B3"], o["B3"] * 0.9]) * 4
            ax = f.add_subplot(1, 3, 2); ax.imshow(np.clip(rgb, 0, 1)); ax.set_title("災後光學（含雲）", fontsize=10); ax.axis("off")
            show(f.add_subplot(1, 3, 3), o["cs"], "Cloud Score+ 清晰度", cmap="viridis", vmin=0, vmax=1)
        st.image("災後原始影像", f, "雷達不受雲影響；光學有雲，清晰度低於門檻的像素在前處理去除。")
    import json, hashlib
    st.d["outputs_hash"] = hashlib.sha256(json.dumps([m["sha256"] for m in man]).encode()).hexdigest()
    ctx["manifest_hash"] = st.d["outputs_hash"]
