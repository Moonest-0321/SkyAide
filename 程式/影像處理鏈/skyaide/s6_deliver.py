"""S5–S6 交付公所：交付方式由類別的系統等級決定（表 19、圖 v8 S5–S6）。
丙　收集期：結果不交公所使用，存為訓練與驗證資料；公所全部依現行方式現勘。
乙　考察期：A／B／C 與存證報告作為參考資料，可依分級排定現勘順序。
甲　參與判定：A 達標書面審核（系統自動申報）、A 未達標通知；B 到場；C 補件或到場。
類別不得高於整體等級。輸出分級清冊、B、C 清單、自動申報清單與縣府副本。"""
import csv
import os
from collections import Counter

GR = {"A_MET": "A 達標", "A_NOT_MET": "A 未達標", "B": "B 邊緣", "C": "C 缺失"}
ORDER = {"丙": 0, "乙": 1, "甲": 2}


def _w(path, header, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)


def run(ctx, st):
    cats = ctx["source"].categories()
    overall = cats["overall"]
    levels = {}
    for c in cats["items"]:
        lv = c["level"]
        if ORDER[lv] > ORDER[overall]:
            st.warn(f"{c['crop']} 等級 {lv} 高於整體 {overall}，降為 {overall}")
            lv = overall
        levels[c["id"]] = lv
    st.check("類別不得高於整體等級", True, f"整體 {overall} 等", severity="info")
    d = os.path.join(ctx["run_dir"], "deliver"); os.makedirs(d, exist_ok=True)
    roster, bc, auto, train = [], [], [], []
    for pid, c in sorted(ctx["cases"].items()):
        lv = levels.get(c["category"], c["level"])
        iv = c["interval"] or [None, None, None]
        rep = ctx["reports"].get(pid, {})
        row = [pid, c["land_no"], c["crop"], lv, GR[c["grade"]], "、".join(c["reasons"] + c.get("notes", [])), iv[0], iv[1], iv[2], rep.get("verify_code")]
        if lv == "丙":
            train.append(row); continue
        roster.append(row + ["參考資料" if lv == "乙" else "參與判定"])
        if lv == "甲" and c["grade"] in ("A_MET", "A_NOT_MET"):
            auto.append([pid, c["land_no"], c["crop"], GR[c["grade"]], iv[1], c["area_ha"], rep.get("verify_code"),
                         "書面審核（自動申報）" if c["grade"] == "A_MET" else "勘查期內送達未達標通知"])
        if c["grade"] in ("B", "C"):
            bc.append([pid, c["land_no"], c["crop"], lv, GR[c["grade"]], "、".join(c["reasons"]) or "損失率是否達 20%"])
    head = ["坵塊", "地號", "作物", "等級", "分級", "原因碼", "第10百分位", "中間值", "第90百分位", "查驗碼"]
    _w(os.path.join(d, "分級清冊.csv"), head + ["用途"], roster)
    _w(os.path.join(d, "自動申報清單.csv"), ["坵塊", "地號", "作物", "分級", "受災率（中間值）", "面積", "查驗碼", "處理"], auto)
    _w(os.path.join(d, "BC清單.csv"), ["坵塊", "地號", "作物", "等級", "分級", "要確認的項目"], bc)
    _w(os.path.join(d, "縣府副本_分級清冊.csv"), head + ["用途"], roster)
    _w(os.path.join(d, "丙等_訓練資料.csv"), head, train)
    ctx["levels"] = levels
    st.count(交公所=len(roster), 自動申報=len(auto), B_C清單=len(bc), 丙等不交公所=len(train))
    by = Counter(levels.get(c["category"], c["level"]) for c in ctx["cases"].values())
    st.table("交付方式", ["等級", "案件數", "交付"], [["甲", by.get("甲", 0), "參與判定：A 自動申報、A 未達標通知、B 到場、C 補件或到場"],
                                              ["乙", by.get("乙", 0), "參考資料：依分級排定現勘順序，全部依現行規定勘查"],
                                              ["丙", by.get("丙", 0), "不交公所：存為訓練與驗證資料"]])
    st.table("輸出檔案", ["檔案", "筆數"], [["deliver/分級清冊.csv", len(roster)], ["deliver/自動申報清單.csv", len(auto)],
                                       ["deliver/BC清單.csv", len(bc)], ["deliver/縣府副本_分級清冊.csv", len(roster)], ["deliver/丙等_訓練資料.csv", len(train)]])
    sla = ctx["params"]["sla_hours"]
    import time
    st.metric("出件時間（本次運算）", round(time.time() - ctx["mon"]._t0, 1) if ctx.get("mon") else None, "秒", target=f"雷達到站後 {sla} 小時內")
