"""
天相星 SkyAide｜長時間對照防偽檢核（模擬）

衛星每 5–6 天經過一次，系統平時就替每塊田累積多年紀錄。這份紀錄申請人改不了，
可以拿來檢查申報內容在「時間上」是否說得通。本程式模擬 3 年、每 6 天一筆的植生時序
（約 35% 被雲遮），比較只看災前 6 期（約 36 天）與看 3 年長期紀錄，能抓到哪些不實申請。

四種不實申請（各 40 筆）：
  F1 新植冒充成樹：申報成齡果樹受損，紀錄顯示 7 個月前還是裸地
  F2 災前已收割：水稻在颱風前 10–20 天已收割，仍申報颱風損失
  F3 前次災損未恢復：上一場災害（75 天前）受損後未補植，再次申請
  F4 長期未耕作：雜草休耕地（植生指數約 0.4）申報水稻
誠實申請 400 筆：各作物正常物候、颱風後受損、合法新植香蕉、前次受災後已補植者再受災等。

四項長期檢核（不通過者列 C 並附原因，交公所確認，不直接否決）：
  L1 耕作物候：過去 12 個月是否有該作物應有的生長週期
  L2 作物年齡：多年生作物自最近一次裸地起算的年數，是否符合申報
  L3 損失時點：植生下降發生在災前還是災後
  L4 前次災損後恢復：有前次申請者，兩次災害之間是否恢復或補植

執行：python longterm_check.py
"""
import json
import os

import numpy as np

rng = np.random.default_rng(2026)
DAY = np.arange(0, 3 * 365)
E = 2 * 365 + 187          # 第 3 年 7 月 6 日（丹娜絲登陸日）
E1 = E - 75                # 前一場災害
OBS = np.arange(3, 3 * 365, 6)
ANALYSIS = E + 12          # 災後 12 天出分級
OBS = OBS[OBS <= ANALYSIS]
MIN_AGE = {"果樹": 730, "竹": 730, "香蕉": 270}
PERENNIAL = set(MIN_AGE)


def rice(j1=0, j2=0):
    v = np.full(DAY.size, 0.25)
    for y in range(3):
        for tr, hv in ((85 + j1, 200 + j1), (225 + j2, 330 + j2)):
            a, b = y * 365 + tr, y * 365 + hv
            idx = (DAY >= a) & (DAY < b)
            x = (DAY[idx] - a) / (b - a)
            # 插秧後上升，抽穗（x≈0.55）達高峰，成熟期緩降至 0.6，收割後回到裸田
            v[idx] = np.where(x < 0.55, 0.25 + 0.62 * np.sin(np.pi / 2 * x / 0.55), 0.87 - 0.27 * (x - 0.55) / 0.42)
    return v


def perennial(kind):
    base = {"香蕉": 0.80, "果樹": 0.66, "竹": 0.72}[kind]
    amp = {"香蕉": 0.02, "果樹": 0.06, "竹": 0.03}[kind]
    return base + amp * np.sin(2 * np.pi * DAY / 365 + rng.uniform(0, 6.28))


def damage(v, day, depth, recover_to=None, recover_days=60):
    v = v.copy()
    idx = DAY >= day
    v[idx] = np.minimum(v[idx], v[idx] - depth + 0 * DAY[idx])
    v[idx] = np.maximum(v[idx], 0.18)
    if recover_to is not None:
        r = (DAY >= day + 15) & (DAY < day + 15 + recover_days)
        v[r] = v[r] + (recover_to - v[r]) * (DAY[r] - day - 15) / recover_days
        v[DAY >= day + 15 + recover_days] = np.maximum(v[DAY >= day + 15 + recover_days], recover_to)
    return v


def observe(v):
    y = v[OBS] + rng.normal(0, 0.035, OBS.size)
    y[rng.random(OBS.size) < 0.35] = np.nan
    return y


cases = []


def add(label, declared, v, claim_hist=None):
    cases.append(dict(label=label, declared=declared, obs=observe(v), hist=claim_hist or []))


# ------------------------------------------------------------------ 誠實申請
for _ in range(400):
    kind = rng.choice(["水稻", "香蕉", "果樹", "竹"], p=[0.4, 0.2, 0.25, 0.15])
    v = rice(int(rng.integers(-8, 9)), int(rng.integers(-8, 9))) if kind == "水稻" else perennial(kind)
    hist = []
    r = rng.random()
    if kind == "香蕉" and r < 0.25:                                  # 合法新植香蕉：10–14 個月前種下
        t0 = E - int(rng.integers(300, 420))
        v[DAY < t0] = 0.2
        g = (DAY >= t0) & (DAY < t0 + 150)
        v[g] = 0.2 + (0.8 - 0.2) * (DAY[g] - t0) / 150
    if rng.random() < 0.2:                                           # 前次受災、已補植或恢復
        v = damage(v, E1, 0.35, recover_to=(None if kind == "水稻" else 0.62), recover_days=50)
        if kind == "水稻":                                            # 補植：第二期提早
            a = E1 + 20
            g = (DAY >= a) & (DAY < E)
            v[g] = 0.25 + 0.55 * np.clip((DAY[g] - a) / 60, 0, 1)
        hist = [E1]
    if rng.random() < 0.85:                                          # 這次颱風受損（多數申請者確實受損）
        v = damage(v, E + int(rng.integers(0, 3)), rng.uniform(0.25, 0.5))
    add("誠實", kind, v, hist)

# ------------------------------------------------------------------ 不實申請
for _ in range(40):                                                  # F1 新植冒充成樹
    v = np.full(DAY.size, 0.2)
    t0 = E - int(rng.integers(150, 260))
    g = DAY >= t0
    v[g] = 0.2 + 0.35 * np.clip((DAY[g] - t0) / 120, 0, 1)
    add("F1 新植冒充成樹", "果樹", damage(v, E + 1, 0.15))
for _ in range(40):                                                  # F2 災前已收割
    j = int(rng.integers(-8, 9))
    v = rice(j, 0)
    h = E - int(rng.integers(10, 21))
    v[(DAY >= h) & (DAY < E + 30)] = 0.25
    add("F2 災前已收割", "水稻", v)
for _ in range(40):                                                  # F3 前次災損未恢復
    kind = rng.choice(["水稻", "果樹", "香蕉"])
    v = rice() if kind == "水稻" else perennial(kind)
    v = damage(v, E1, 0.45)
    v[DAY >= E1 + 5] = np.minimum(v[DAY >= E1 + 5], 0.3)
    add("F3 前次災損未恢復", kind, v, [E1])
for _ in range(40):                                                  # F4 長期未耕作（雜草）
    w = np.cumsum(rng.normal(0, 0.01, DAY.size))
    v = 0.40 + 0.06 * np.sin(2 * np.pi * DAY / 365) + (w - np.convolve(w, np.ones(120) / 120, "same"))
    add("F4 長期未耕作", "水稻", np.clip(v, 0.2, 0.6))


# ------------------------------------------------------------------ 檢核
def window(y, a, b):
    m = (OBS >= a) & (OBS < b) & np.isfinite(y)
    return y[m]


def smooth(y):
    out = np.full(y.size, np.nan)
    fin = np.where(np.isfinite(y))[0]
    for k, i in enumerate(fin):
        out[i] = np.median(y[fin[max(0, k - 1):k + 2]])
    return out


def checks(c):
    y, decl = c["obs"], c["declared"]
    s = smooth(y)
    flags = []
    last12 = window(s, E - 365, E)
    # L1 耕作物候
    if decl == "水稻":
        if len(last12) < 8 or np.nanpercentile(last12, 90) < 0.68 or np.nanpercentile(last12, 90) - np.nanpercentile(last12, 10) < 0.3:
            flags.append("L1 過去 12 個月未見水稻生長週期")
    elif len(last12) and np.nanmedian(last12) < 0.5:
        flags.append("L1 過去 12 個月植生偏低，不符多年生作物")
    # L2 作物年齡
    if decl in PERENNIAL:
        low = OBS[(s < 0.25) & (OBS < E)]
        age = E - low.max() if low.size else E
        if age < MIN_AGE[decl]:
            flags.append(f"L2 最近一次裸地距今約 {age // 30} 個月，短於{decl}應有的種植年數")
    # L3 損失時點：今年災前的下降幅度，扣掉這塊田前兩年同一時段的正常下降（如成熟期）
    pre = window(y, E - 60, E - 30)
    last = window(y, E - 18, E)
    if len(pre) and len(last):
        drop = np.median(pre) - np.median(last)
        normal = []
        for k in (1, 2):
            a, b = window(y, E - 365 * k - 60, E - 365 * k - 30), window(y, E - 365 * k - 18, E - 365 * k)
            if len(a) and len(b):
                normal.append(np.median(a) - np.median(b))
        if drop - (np.median(normal) if normal else 0) >= 0.25:
            flags.append("L3 植生下降發生在災前（較往年同期多降）")
    # L4 前次災損後恢復
    for e1 in c["hist"]:
        between = window(s, e1 + 30, E - 5)
        if len(between) and np.nanmax(between) < 0.5:
            flags.append("L4 前次災損後未見恢復或補植")
    return flags


def short_check(c):
    """只看災前 6 期（v7 原有的生產事實檢核）。"""
    y = c["obs"][(OBS < E)][-6:]
    y = y[np.isfinite(y)]
    return ["災前 6 期未見作物"] if len(y) and y.mean() < 0.30 else []


res = {}
for c in cases:
    c["flags"] = checks(c)
    c["short"] = short_check(c)
    d = res.setdefault(c["label"], dict(件數=0, 長期標出=0, 短期標出=0, 原因={}))
    d["件數"] += 1
    d["長期標出"] += int(bool(c["flags"]))
    d["短期標出"] += int(bool(c["short"]))
    for f in c["flags"]:
        key = f.split(" ")[0]
        d["原因"][key] = d["原因"].get(key, 0) + 1
for d in res.values():
    d["長期標出率"] = round(d["長期標出"] / d["件數"], 3)
    d["短期標出率"] = round(d["短期標出"] / d["件數"], 3)

out = dict(設定=dict(紀錄長度="3 年", 觀測間隔="6 天", 雲遮比例=0.35, 誠實申請=400, 每類不實申請=40,
                    分析時間="災後 12 天"), 結果=res)
os.makedirs("sop_output", exist_ok=True)
json.dump(out, open("sop_output/longterm_results.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for k, d in res.items():
    print(f"{k:10s} 件數 {d['件數']:3d}｜長期標出 {d['長期標出率']:.0%}｜只看災前 6 期 {d['短期標出率']:.0%}｜{d['原因']}")
