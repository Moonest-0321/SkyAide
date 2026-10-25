"""S4 案件分級：先看證據，再看損失（表 17、表 39、表 18、表 42、表 70、圖 v8 S4）。
① 證據檢核（可信度五項，含長時間對照 L1–L4）：任一項未通過 → C 缺失並附原因碼，即使損失看起來很明顯也一樣。
② 證據完整者看損失區間：下限 ≥ 40% A 達標；上限 ≤ 10% A 未達標；跨過 20% B 邊緣。
判讀元件未達使用門檻時（例如 Sentinel 倒伏尚無與現勘比對的精確度），用它判出的案件一律歸 B 或 C。
未申請的田不列入分級：衛星看到明顯受損者主動通知可以申請。R1–R5 申請交叉檢核與分級並列。"""
from collections import Counter

from .common import fig, show, parcel_map

GRADES = {"A_MET": "A 達標", "A_NOT_MET": "A 未達標", "B": "B 邊緣", "C": "C 缺失"}


def five_checks(p, f, ctx):
    crop = p["declared"]["crop"]
    ck = {}
    # 影像條件
    r = []
    if p["needs_hr"] and f.get("hr_lodge") is None:
        r.append("像素不足")
    if p["misreg"]:
        r.append("對位不確定")
    if crop == "竹（山坡）" and f.get("hr_lodge") is None:
        r.append("樹冠遮蔽或網室")
    if p["shadow_frac"] > 0.3:
        r.append("雷達陰影")
    ck["imagery"] = dict(pass_=not r, reasons=r, detail=f"內縮後 {p['n_inset']} 格" + ("；高解析已補" if f.get("hr_lodge") is not None else ""))
    # 觀測完整
    radar_strong = f["flood"] >= 0.5 or f["buried"] >= 0.5 or f.get("hr_lodge") is not None
    clear = 1 - f["cloud_post"]
    ok = clear >= 0.5 or radar_strong
    ck["completeness"] = dict(pass_=ok, reasons=[] if ok else ["雲遮"], detail=f"光學清晰 {clear:.0%}" + ("；雷達訊號可單獨判定" if radar_strong else ""))
    # 多源一致
    r = []
    if f["irrigation"]:
        r.append("疑似灌溉")
    radar_damage = f["flood"] > 0.2 or (f["lodge_mod"] + f["lodge_sev"]) > 0.2 or f["buried"] > 0.2 or (f.get("hr_lodge") or 0) > 0.2
    if f.get("veg_z") is not None and clear >= 0.5 and not radar_strong:
        optical_damage = f["veg_z"] < -3 or (f.get("veg_anom") or 0) <= -0.2
        if radar_damage != optical_damage:
            r.append("來源不一致")
    ck["consistency"] = dict(pass_=not r, reasons=r, detail="雷達" + ("有" if radar_damage else "無") + "受損訊號" +
                             (f"；植生分數 {f['veg_z']:.1f}" if f.get("veg_z") is not None else "；光學不可用"))
    # 申報一致
    crop_ok = ctx.get("crop_ok", {}).get(crop, False)
    pred = f.get("crop_pred")
    h = f.get("hist") or {}
    if crop_ok and pred is not None:
        ok = pred == crop
        detail = f"衛星判釋 {pred}（機率 {f.get('crop_prob', 0):.2f}）"
    else:
        ok = bool(h.get("L1", True))
        detail = "作物判釋未達使用門檻，以申報為準，只查物候"
    ck["declaration"] = dict(pass_=ok, reasons=[] if ok else ["作物不符"], detail=detail)
    # 生產事實（含 L1–L4）
    r = []
    if h.get("pre6_mean") is not None and h["pre6_mean"] < 0.3 and crop != "水稻":
        r.append("災前未見作物生長")
    for k, name in (("L1", "L1 耕作物候"), ("L2", "L2 作物年齡"), ("L3", "L3 損失時點"), ("L4", "L4 前次災損後恢復")):
        if h and h.get(k) is False:
            r.append(name)
    ck["production"] = dict(pass_=not r, reasons=r, detail="長時間對照 " + ("全過" if not r else "未過：" + "、".join(r)),
                            longterm={k: h.get(k) for k in ("L1", "L2", "L3", "L4")})
    failed = [k for k, v in ck.items() if not v["pass_"]]
    cred = "高" if not failed else ("低" if "production" in failed or len(failed) >= 2 else "中")
    return ck, cred


def r_checks(p, f, ctx, photos, hist_hashes):
    G = ctx["params"]["grade"]
    d = p["declared"]
    out = {}
    out["R1"] = dict(status="待確認" if p["misreg"] else "一致", note="地籍與影像對位" + ("不確定" if p["misreg"] else "可靠"))
    pred = f.get("crop_pred")
    out["R2"] = dict(status="一致" if (pred is None or pred == d["crop"]) else "待補件", note=f"申報 {d['crop']}，衛星 {pred or '—'}")
    diff = (d["declared_ha"] - p["eff_ha"]) / max(p["eff_ha"], 1e-6) if d.get("declared_ha") else 0
    out["R3"] = dict(status="待確認" if diff > G["area_mismatch"] else "一致", note=f"申報 {d.get('declared_ha')} 公頃、有效種植 {p['eff_ha']} 公頃（差 {diff:+.0%}）")
    out["R4"] = dict(status="一致" if d.get("right_valid", True) else "待補件", note="使用權文件" + ("有效" if d.get("right_valid", True) else "已過期"))
    dup = []
    if d.get("dup_with"):
        dup.append(f"與坵塊 {d['dup_with']} 重複申請")
    ph = photos.get(p["id"]) or photos.get(str(p["id"]))
    if ph:
        dist = min(bin(ph["dhash"] ^ h).count("1") for h in hist_hashes) if hist_hashes else 64
        if dist <= G["photo_dhash_max_bits"]:
            dup.append(f"App 照片與歷次案件相似（差 {dist} 位元）")
        if ph["mode"] != "App 即時拍攝":
            dup.append("照片為相簿匯入")
    out["R5"] = dict(status="待確認" if dup else "一致", note="；".join(dup) or "無重複")
    return out


def _pond(p, f):
    """魚塭（表 36）：以放養申報證明在養；池水流失且無收成申報判 A 達標；只有間接訊號列 C。"""
    d = p["declared"]
    ck = dict(stock=dict(pass_=bool(d.get("stocking")), reasons=[] if d.get("stocking") else ["無放養申報"], detail="放養申報" + ("有" if d.get("stocking") else "無")))
    if not d.get("stocking"):
        return "C", ["無放養申報"], "低", ck
    if f.get("water_loss") and not d.get("harvest"):
        return "A_MET", [], "高", ck
    reasons = []
    if f.get("outage_days", 0) > 0:
        reasons.append(f"僅有間接訊號（停電 {f['outage_days']} 天）")
    if f.get("region_overflow", 0) > 0.3:
        reasons.append("僅有間接訊號（區域溢淹）")
    return "C", reasons or ["未見訊號，需到場"], "中", ck


def run(ctx, st):
    G = ctx["params"]["grade"]
    parcels, feats, loss = ctx["parcels"], ctx["feat"], ctx.get("loss", {})
    prods = ctx["products"]
    app = next((x for p, x in prods.values() if p["kind"] == "APP_PHOTO"), dict(photos={}, history_hashes=[]))
    cats = {c["crop"]: c for c in ctx["source"].categories()["items"]}
    ref_only = ctx.get("loss_ref_only", {})
    cases, notify = {}, []
    for pid, p in parcels.items():
        f = feats[pid]
        d = p["declared"]
        cat = cats.get(d["crop"], {})
        if p["kind"] == "pond":
            if d["applied"]:
                g, reasons, cred, ck = _pond(p, f)
                cases[pid] = dict(id=pid, land_no=p["land_no"], crop="魚塭", category=cat.get("id"), level=cat.get("level"), grade=g,
                                  reasons=reasons, credibility=cred, checks=ck, interval=None, r=None, area_ha=p["eff_ha"],
                                  pond=dict(water_pre=f.get("water_pre"), water_post=f.get("water_post"), outage_days=f.get("outage_days")))
            continue
        L = loss.get(pid)
        ck, cred = five_checks(p, f, ctx)
        reasons = [r for v in ck.values() for r in v["reasons"]]
        if not d["applied"]:
            if L and cred == "高" and L["p10"] >= G["a_met_lower_min"]:
                notify.append(dict(id=pid, land_no=p["land_no"], crop=d["crop"], interval=[L["p10"], L["p50"], L["p90"]]))
            continue
        why = []
        if cred != "高":
            g = "C"
        elif L is None:
            g, why = "C", ["損失區間未產出"]
        elif L["p10"] >= G["a_met_lower_min"]:
            g = "A_MET"
        elif L["p90"] <= G["a_not_met_upper_max"]:
            g = "A_NOT_MET"
        else:
            g = "B"
        if g == "A_MET":
            lodge_only = f["flood"] < 0.3 and f["buried"] < 0.3 and (f["lodge_mod"] + f["lodge_sev"]) >= 0.2 and f.get("hr_lodge") is None
            if lodge_only:
                g, why = "B", ["倒伏（Sentinel）不單獨支撐 A 級"]
        if g in ("A_MET", "A_NOT_MET") and ref_only.get(d["crop"]):
            g, why = "B", [f"{d['crop']}損失模型均方根誤差未達標，區間只作參考"]
        rc = r_checks(p, f, ctx, app["photos"], app["history_hashes"])
        if rc["R3"]["status"] != "一致":
            g = "C"; reasons.append("面積不符")
        cases[pid] = dict(id=pid, land_no=p["land_no"], crop=d["crop"], category=cat.get("id"), level=cat.get("level"),
                          grade=g, reasons=reasons, notes=why, credibility=cred, checks=ck, r=rc, area_ha=p["eff_ha"],
                          interval=[L["p10"], L["p50"], L["p90"]] if L else None, p_ge20=L["p_ge20"] if L else None,
                          top=L["top"] if L else [], applicant=d.get("applicant"), baseline_locked=d.get("baseline_locked"),
                          declared_ha=d.get("declared_ha"))
    ctx["cases"] = cases
    ctx["notify_unapplied"] = notify
    cnt = {g: sum(c["grade"] == g for c in cases.values()) for g in GRADES}
    st.count(申請案件=len(cases), **{GRADES[g]: n for g, n in cnt.items()}, 未申請但明顯受損=len(notify))
    n = max(len(cases), 1)
    st.metric("直接判定率（A 級占申請）", round((cnt["A_MET"] + cnt["A_NOT_MET"]) / n * 100, 1), "%", target="乙等門檻 ≥ 50%")
    st.metric("C 缺失比例", round(cnt["C"] / n * 100, 1), "%")
    rc_counter = Counter(r for c in cases.values() if c["grade"] == "C" for r in c["reasons"])
    st.table("C 缺失原因碼分布", ["原因碼", "件數"], [[k, v] for k, v in rc_counter.most_common()])
    notes = Counter(x for c in cases.values() for x in c.get("notes", []))
    st.table("判讀元件未達門檻而改判 B", ["原因", "件數"], [[k, v] for k, v in notes.most_common()])
    by_cat = {}
    for c in cases.values():
        by_cat.setdefault((c["crop"], c["level"]), Counter())[c["grade"]] += 1
    st.table("各類別分級", ["類別", "等級", "A 達標", "A 未達標", "B 邊緣", "C 缺失"],
             [[k[0], k[1]] + [v.get(g, 0) for g in GRADES] for k, v in sorted(by_cat.items())])
    rtab = Counter((k, v["status"]) for c in cases.values() if c.get("r") for k, v in c["r"].items() if v["status"] != "一致")
    st.table("R1–R5 申請交叉檢核（不一致者）", ["規則", "結果", "件數"], [[k[0], k[1], v] for k, v in sorted(rtab.items())])
    st.check("可信度非「高」一律列 C", all(c["grade"] == "C" for c in cases.values() if c["credibility"] != "高"), "", severity="info")

    truth = ctx.get("truth")
    if truth:
        T = G["threshold"]
        wrong_met = [c for c in cases.values() if c["grade"] == "A_MET" and truth[c["id"]]["loss"] < T]
        wrong_not = [c for c in cases.values() if c["grade"] == "A_NOT_MET" and truth[c["id"]]["loss"] >= T]
        st.metric("（模擬對答案）A 達標判錯", f"{len(wrong_met)}/{cnt['A_MET']}")
        st.metric("（模擬對答案）A 未達標判錯", f"{len(wrong_not)}/{cnt['A_NOT_MET']}")
        claims = [c for c in cases.values() if truth[c["id"]]["claim"]]
        st.table("（模擬對答案）不實申請是否被擋下", ["坵塊", "不實類型", "分級", "原因碼"],
                 [[c["id"], truth[c["id"]]["claim"], GRADES[c["grade"]], "、".join(c["reasons"] + c.get("notes", [])) or "—"] for c in claims])

    if ctx.get("quiet"):
        return
    for pid, c in cases.items():
        ctx["mon"].parcel(pid, "S4", c)
    for x in notify:
        ctx["mon"].parcel(x["id"], "S4", dict(grade=None, note="未申請，不列入分級；衛星看到明顯受損，主動通知", interval=x["interval"]))
    lab = ctx["label"]
    code = {"A_MET": 1, "A_NOT_MET": 2, "B": 3, "C": 4}
    f = fig(11, 4)
    show(f.add_subplot(1, 2, 1), parcel_map(lab, {k: code[c["grade"]] for k, c in cases.items()}), "分級：1 A 達標 2 A 未達標 3 B 邊緣 4 C 缺失", cmap="Set1", vmin=1, vmax=9)
    show(f.add_subplot(1, 2, 2), parcel_map(lab, {k: {"高": 3, "中": 2, "低": 1}[c["credibility"]] for k, c in cases.items()}), "可信度：3 高 2 中 1 低", cmap="RdYlGn", vmin=1, vmax=3)
    st.image("分級結果", f, "只有申請的田列入分級；空白為未申請、非農地或水面。")
