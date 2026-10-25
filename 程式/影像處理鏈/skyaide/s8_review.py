"""S8 災後檢討與評等（表 37 S8、表 66、表 67、圖 v8 S7–S8）。
逐類別計算 A 達標精確度、A 未達標精確度、判定正確率、直接判定率、B 邊緣確認率，一律以 95% 單側信賴下界判斷；
決定下一場的等級（下界未達 95% 即降一等、連續場次歸零；類別不得高於整體）。另做偏差與缺失分析、區間覆蓋率、作業日誌查驗。"""
import os
from collections import Counter

import numpy as np

from .common import cp_lower, fig
from . import ledger as ledger_mod

ORDER = {"丙": 0, "乙": 1, "甲": 2}
NAME = {0: "丙", 1: "乙", 2: "甲"}


def run(ctx, st):
    P = ctx["params"]["levels"]
    T = ctx["params"]["grade"]["threshold"]
    lo, hi = ctx["params"]["grade"]["b_confirm_range"]
    cases, back, levels = ctx["cases"], ctx["backfill"], ctx["levels"]
    meta = {c["id"]: c for c in ctx["source"].categories()["items"]}
    overall = ctx["source"].categories()["overall"]
    rows, nxt = [], {}
    for cid, lv in levels.items():
        cs = [c for c in cases.values() if c["category"] == cid]
        if not cs:
            continue
        sv = [c for c in cs if c["id"] in back]
        am = [c for c in sv if c["grade"] == "A_MET"]; an = [c for c in sv if c["grade"] == "A_NOT_MET"]; bb = [c for c in sv if c["grade"] == "B"]
        k_am = sum(back[c["id"]]["survey_loss"] >= T for c in am); k_an = sum(back[c["id"]]["survey_loss"] < T for c in an)
        k_b = sum(lo <= back[c["id"]]["survey_loss"] <= hi for c in bb)
        # 同一類別、同一模型版本的樣本跨場合併計算（prior 為前幾場累積）
        pr = meta.get(cid, {}).get("prior", {})
        pa, pn, pb = pr.get("a_met", (0, 0)), pr.get("a_not_met", (0, 0)), pr.get("b", (0, 0))
        K_am, N_am = k_am + pa[0], len(am) + pa[1]; K_an, N_an = k_an + pn[0], len(an) + pn[1]; K_b, N_b = k_b + pb[0], len(bb) + pb[1]
        lb_am, lb_an = cp_lower(K_am, N_am), cp_lower(K_an, N_an)
        lb_acc = cp_lower(K_am + K_an, N_am + N_an)
        lb_b = cp_lower(K_b, N_b)
        direct = sum(c["grade"] in ("A_MET", "A_NOT_MET") for c in cs) / len(cs)
        cov = [c for c in sv if c["interval"]]
        coverage = np.mean([c["interval"][0] <= back[c["id"]]["survey_loss"] <= c["interval"][2] for c in cov]) if cov else None
        streak = meta.get(cid, {}).get("streak", 0); gov = meta.get(cid, {}).get("gov_approved", lv == "甲")
        meets = all(x is not None for x in (lb_am, lb_an, lb_acc, lb_b)) and lb_am >= P["a_precision_lb"] and lb_an >= P["a_precision_lb"] \
            and lb_acc >= P["accuracy_lb"] and direct >= P["direct_rate"] and lb_b >= P["b_confirm_lb"]
        cur = ORDER[lv]
        if lb_am is None or lb_an is None:
            new, why = cur, "樣本不足：同一類別、同一模型版本的抽查結果跨場合併計算，或提高抽查比例"
        elif cur >= 1 and (lb_am < P["a_precision_lb"] or lb_an < P["a_precision_lb"]):
            new, why, streak = cur - 1, "A 精確度下界低於 95%，下一場降一等，連續場次歸零", 0
        elif meets:
            streak += 1
            new = 1 if cur == 0 else (2 if cur == 1 and streak >= P["streak_for_a"] and gov else cur)
            why = "達標" + (f"；連續 {streak} 場" if cur >= 1 else "，升為乙等")
        else:
            new, why, streak = cur, "未全數達標，連續場次歸零", 0
        new = min(new, ORDER[overall])
        nxt[cid] = NAME[new]
        f = lambda v: None if v is None else round(v * 100, 1)
        rows.append([meta.get(cid, {}).get("crop", cid), lv, len(cs), len(sv), f"{k_am}/{len(am)}（累計 {K_am}/{N_am}）", f(lb_am),
                     f"{k_an}/{len(an)}（累計 {K_an}/{N_an}）", f(lb_an), f(lb_acc), round(direct * 100, 1), f"{k_b}/{len(bb)}（累計 {K_b}/{N_b}）",
                     f(lb_b), f(coverage), NAME[new], why])
    st.table("逐類別評等（回填樣本＋前幾場累計）",
             ["類別", "本場", "案件", "回填", "A 達標對", "下界%", "A 未達標對", "下界%", "判定正確率下界%", "直接判定率%",
              "B 確認", "下界%", "區間覆蓋%", "下一場", "說明"], rows,
             note="下界為 95% 單側 Clopper–Pearson；升等條件見表 67。甲等只有抽查的 A 與 B、C 有標準答案。累計為同一類別、同一模型版本前幾場的樣本（模擬）。")
    ctx["next_levels"] = nxt

    # 偏差與缺失分析
    sv = [c for c in cases.values() if c["id"] in back]
    svi = [c for c in sv if c["interval"]]
    sys_dmg = sum(c["interval"][1] >= T for c in svi); real_dmg = sum(back[c["id"]]["survey_loss"] >= T for c in svi)
    bias = (sys_dmg - real_dmg) / max(real_dmg, 1)
    st.metric("區域偏差（回填樣本中系統中間值 ≥ 20% 與現勘受損筆數之差）", round(bias * 100, 1), "%", target="±20% 以內", ok=abs(bias) <= 0.2)
    st.table("C 缺失最常缺的資料", ["原因碼", "件數"], Counter(r for c in cases.values() if c["grade"] == "C" for r in c["reasons"]).most_common(8))
    wrong = [c for c in sv if (c["grade"] == "A_MET" and back[c["id"]]["survey_loss"] < T) or (c["grade"] == "A_NOT_MET" and back[c["id"]]["survey_loss"] >= T)]
    st.table("判錯的 A 級（需檢討）", ["坵塊", "作物", "分級", "區間", "現勘損失"],
             [[c["id"], c["crop"], c["grade"], c["interval"], back[c["id"]]["survey_loss"]] for c in wrong])
    st.check("A 級沒有判錯", not wrong, f"{len(wrong)} 件判錯", action="納入重新訓練與保形重校；相關類別依下界降等", severity="warn")

    # 作業日誌（雜湊鏈）查驗
    ok, at = ledger_mod.verify_file(os.path.join(ctx["run_dir"], "ledger.jsonl"))
    st.check("作業日誌雜湊鏈完整", ok, "前面每一步的紀錄未被改動" if ok else f"第 {at + 1} 筆起鏈結斷開", severity="warn")

    truth = ctx.get("truth")
    if truth:
        allc = list(cases.values())
        am = [c for c in allc if c["grade"] == "A_MET"]; an = [c for c in allc if c["grade"] == "A_NOT_MET"]
        st.metric("（模擬全知）A 達標精確度", round(np.mean([truth[c["id"]]["loss"] >= T for c in am]) * 100, 1) if am else None, "%")
        st.metric("（模擬全知）A 未達標精確度", round(np.mean([truth[c["id"]]["loss"] < T for c in an]) * 100, 1) if an else None, "%")

    if ctx.get("quiet"):
        return
    pairs = [(c["interval"][1], back[c["id"]]["survey_loss"], c["grade"]) for c in sv if c["interval"]]
    if pairs:
        f = fig(5.6, 4.6); ax = f.add_subplot(1, 1, 1)
        col = {"A_MET": "#1d6b43", "A_NOT_MET": "#5b3f9e", "B": "#d9822b", "C": "#a63a12"}
        for g in col:
            xs = [p for p in pairs if p[2] == g]
            if xs:
                ax.scatter([x[0] for x in xs], [x[1] for x in xs], s=14, color=col[g], label={"A_MET": "A 達標", "A_NOT_MET": "A 未達標", "B": "B 邊緣", "C": "C 缺失"}[g])
        ax.plot([0, 100], [0, 100], color="#999", lw=0.8); ax.axhline(T, color="k", ls="--", lw=0.8); ax.axvline(T, color="k", ls="--", lw=0.8)
        ax.set_xlabel("系統損失中間值（%）"); ax.set_ylabel("現勘損失（%）"); ax.legend(fontsize=8); ax.set_title("回填樣本：系統估計與現勘", fontsize=10)
        st.image("系統與現勘比對", f, "虛線為 20% 門檻；左上與右下象限是判錯邊的案件。")
    st.count(類別=len(rows), 回填=len(back), 判錯A=len(wrong))
