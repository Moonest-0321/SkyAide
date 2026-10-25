"""
天相星 SkyAide｜可信度驗證：可信度等級是否對應實際誤差？區間經現勘回填校準後覆蓋率是否達標？

  1. 以 10 個模擬工況（seed 200–209）計算每筆坵塊的可信度等級，比較各等級的
     損失中間值誤差、區間覆蓋率與 A／B 判反件數。
  2. 保形校準（conformalized quantile regression, Romano et al. 2019）：
     前 5 個工況當作「已回填現勘結果的災害」，算出區間需要放寬或收窄多少，
     再套用到後 5 個工況，比較校準前後的覆蓋率與區間寬度。

執行：python credibility_eval.py
"""

import json
import math
import os

import numpy as np

import skyaide_demo as s
import sop_pipeline as sp

OUT = sp.OUT
os.makedirs(OUT, exist_ok=True)


def scene_rows(seed):
    sc = s.simulate_scene(seed)
    _, rows = s.analyse(sc)
    for r, p in zip(rows, sc.parcels):
        r["true_loss"], r["crop"] = p["true_loss"], p["crop"]
    s.classify_parcels(rows)
    for r in rows:
        r["pre_ndvi_mean"] = float(np.mean([r[f"nd{k}"] for k in range(s.N_PRE)]))
        r["producing"] = r["pre_ndvi_mean"] >= sp.BARE_NDVI
        r["seed"] = seed
    sp.apply_credibility(rows)
    return rows


allrows = {seed: scene_rows(seed) for seed in range(200, 210)}
flat = [r for rs in allrows.values() for r in rs]

# ---------------------------------------------------------------- 1. 各可信度等級的實際誤差
by_level = {}
for lv in "高中低":
    rs = [r for r in flat if r["cred"] == lv]
    if not rs:
        continue
    err = np.array([abs(r["q50"] - r["true_loss"]) for r in rs])
    cover = np.mean([r["q10"] <= r["true_loss"] <= r["q90"] for r in rs])
    wrong_side = sum((r["q50"] >= 0.2) != (r["true_loss"] >= 0.2) for r in rs)
    by_level[lv] = dict(坵塊數=len(rs), 占比=round(len(rs) / len(flat), 3),
                        中間值平均誤差_百分點=round(float(err.mean() * 100), 1),
                        誤差大於15個百分點比例=round(float((err > 0.15).mean()), 3),
                        區間覆蓋率=round(float(cover), 3),
                        中間值落在門檻錯邊=int(wrong_side), 錯邊比例=round(wrong_side / len(rs), 3),
                        A件數=sum(r["grade"] == "A" for r in rs), B件數=sum(r["grade"] == "B" for r in rs))
fail_counts = {}
for r in flat:
    for k in r["cred_fails"]:
        fail_counts[k] = fail_counts.get(k, 0) + 1

# ---------------------------------------------------------------- 2. 保形校準
ALPHA = 0.20   # 目標覆蓋率 80%
cal = [r for seed in range(200, 205) for r in allrows[seed]]
test = [r for seed in range(205, 210) for r in allrows[seed]]
scores = np.array([max(r["q10"] - r["true_loss"], r["true_loss"] - r["q90"]) for r in cal])
n = len(scores)
k = math.ceil((n + 1) * (1 - ALPHA))
Q = float(np.sort(scores)[min(k, n) - 1])


def cover_width(rs, q):
    lo = np.array([max(0, r["q10"] - q) for r in rs])
    hi = np.array([min(1, r["q90"] + q) for r in rs])
    y = np.array([r["true_loss"] for r in rs])
    return float(np.mean((lo <= y) & (y <= hi))), float(np.mean(hi - lo))


before = cover_width(test, 0.0)
after = cover_width(test, Q)
# 若規則把區間訂得太窄（壓力測試）：把所有區間半寬縮成一半，再看校準能否拉回
narrow = []
for r in test:
    m, hw_lo, hw_hi = r["q50"], r["q50"] - r["q10"], r["q90"] - r["q50"]
    narrow.append(dict(q10=m - hw_lo / 2, q90=m + hw_hi / 2, true_loss=r["true_loss"]))
cal_n = []
for r in cal:
    m, hw_lo, hw_hi = r["q50"], r["q50"] - r["q10"], r["q90"] - r["q50"]
    cal_n.append(dict(q10=m - hw_lo / 2, q90=m + hw_hi / 2, true_loss=r["true_loss"]))
sn = np.sort([max(r["q10"] - r["true_loss"], r["true_loss"] - r["q90"]) for r in cal_n])
Qn = float(sn[min(math.ceil((len(sn) + 1) * (1 - ALPHA)), len(sn)) - 1])
nb, na = cover_width(narrow, 0.0), cover_width(narrow, Qn)

result = dict(
    工況數=10, 坵塊數=len(flat), 各可信度等級=by_level, 未通過檢核次數=fail_counts,
    保形校準=dict(目標覆蓋率=1 - ALPHA, 校準工況="seed 200–204", 測試工況="seed 205–209",
              校準坵塊數=len(cal), 測試坵塊數=len(test),
              原規則=dict(調整量_百分點=round(Q * 100, 1), 校準前覆蓋率=round(before[0], 3), 校準前平均寬度=round(before[1], 3),
                       校準後覆蓋率=round(after[0], 3), 校準後平均寬度=round(after[1], 3)),
              區間過窄壓力測試=dict(調整量_百分點=round(Qn * 100, 1), 校準前覆蓋率=round(nb[0], 3), 校準前平均寬度=round(nb[1], 3),
                            校準後覆蓋率=round(na[0], 3), 校準後平均寬度=round(na[1], 3))),
)
with open(os.path.join(OUT, "credibility_eval.json"), "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=1)
print(json.dumps(result, ensure_ascii=False, indent=1))
