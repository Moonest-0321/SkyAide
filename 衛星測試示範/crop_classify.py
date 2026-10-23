"""
作物判釋（粗分 5 類）：只用颱風前一整年的 Sentinel-1 雷達
==============================================================

類別：0 水體（海、河）　1 魚塭／鹽田　2 水稻　3 其他作物（旱作、果樹、休耕等）　4 建地／道路

做法（不需要人工標註，全部是看得懂的規則）：
  1. 扣掉每期影像的整體亮度跳動（全區陸地的中位數）
  2. 每個像素算三個數字：
       VV 中位數      ：一年的典型亮度。建地很亮、水面很暗
       VH 第 80 百分位：一年中「較亮的時候」有多亮。作物長高時 VH 會變亮；魚塭水面一年到頭都暗
       插秧期落差     ：插秧期（二期作 7–8 月、一期作 1–3 月）VH 最低點，比之後 1–2 個月低多少。
                        水稻插秧前田裡灌水，雷達先變很暗，稻子長高再變亮，形成 V 字
  3. 依序套規則（先符合的先算）：
       建地／道路：VV 中位數 > −4 dB
       水體      ：水面（VH 第 80 百分位 < −19.5 dB，或 VH 中位數 < −20 dB），且和研究區西邊的海連成一片
       魚塭／鹽田：其餘的水面
       水稻      ：任一期插秧期落差 < −3.5 dB，且 VH 第 80 百分位 > −17 dB
       其他作物  ：剩下的
  4. 平滑：每個像素看周圍 7×7（約 70 公尺見方），取多數類別，去掉零星雜點。
     魚塭是一格格池子夾著堤岸，周圍只要有 40% 是池子就算魚塭區（堤岸本身很亮，會把多數拉走）

限制：沒有官方標註可以比對，只是粗分。之後有了國土利用調查或公所回填的作物資料，
      再改用隨機森林、時序 Transformer（構想書中的作法）。

執行：python fetch_s1_year.py 之後 python crop_classify.py
"""
import json
import os

import numpy as np
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "real_data")
OUT = os.path.join(HERE, "output_crop")
os.makedirs(OUT, exist_ok=True)

CLASSES = ["水體", "魚塭／鹽田", "水稻", "其他作物", "建地／道路"]
HA = 15330 / 1600 * 16600 / 1600 / 1e4          # 每像素公頃數

BUILT_VV = -4.0          # 建地：VV 中位數高於此值
DARK_VH80 = -19.5        # 水面：VH 第 80 百分位低於此值
RICE_DIP = -3.5          # 水稻：插秧期落差低於此值
RICE_VH80 = -17.0        # 水稻：生長高峰的 VH 要高於此值
SMOOTH = 7               # 平滑視窗（像素）

d = np.load(os.path.join(DATA, "s1_year.npz"))
vv = d["vv"].astype("float32")
vh = d["vh"].astype("float32")
dates = [str(s) for s in d["dates"]]
T, H, W = vh.shape

# ---------- 1. 扣掉每期整體亮度跳動 ----------
land = np.median(vv, 0) > -14
offsets = {}
for name, arr in (("VV", vv), ("VH", vh)):
    off = np.array([np.median(arr[t][land]) for t in range(T)])
    off -= off.mean()
    arr -= off[:, None, None]
    offsets[name] = [round(float(x), 2) for x in off]

# ---------- 2. 三個數字 ----------
idx = lambda a, b: [i for i, s in enumerate(dates) if a <= s <= b]
dip2 = vh[idx("2024-07-01", "2024-08-31")].min(0) - np.median(vh[idx("2024-09-10", "2024-10-31")], 0)
dip1 = vh[idx("2025-01-01", "2025-03-31")].min(0) - np.median(vh[idx("2025-04-01", "2025-05-31")], 0)
dip = np.minimum(dip1, dip2)
vv_med = np.median(vv, 0)
vh_p80 = np.percentile(vh, 80, axis=0)
vh_med = np.median(vh, 0)

# ---------- 3. 規則 ----------
pred = np.full((H, W), 3, np.uint8)                       # 預設：其他作物
dark = (vh_p80 < DARK_VH80) | (vh_med < -20)
lab, _ = ndi.label(dark)
sea_ids = np.unique(lab[:, :5][lab[:, :5] > 0])          # 和西邊界相連的暗區＝海、河口、河道
sea = np.isin(lab, sea_ids)
pred[(dip < RICE_DIP) & (vh_p80 > RICE_VH80)] = 2
pred[dark] = 1
pred[sea] = 0
pred[vv_med > BUILT_VV] = 4

# ---------- 4. 平滑 ----------
score = np.stack([ndi.uniform_filter((pred == c).astype(np.float32), SMOOTH) for c in range(len(CLASSES))])
crop = score.argmax(0).astype(np.uint8)
pond_zone = (score[1] >= 0.4) & (crop != 0)
crop[pond_zone] = 1

area = {CLASSES[c]: round(float((crop == c).sum() * HA)) for c in range(len(CLASSES))}
stats = {
    "影像期數": T, "期間": f"{dates[0]} ～ {dates[-1]}",
    "門檻": {"建地VV": BUILT_VV, "水面VH80": DARK_VH80, "水稻插秧落差": RICE_DIP, "水稻VH80": RICE_VH80},
    "各期整體亮度偏移_dB": offsets,
    "各類面積_公頃": area,
    "水稻占農地比例（水稻＋其他作物）": round(area["水稻"] / (area["水稻"] + area["其他作物"]), 3),
}
json.dump(stats, open(os.path.join(OUT, "crop_stats.json"), "w"), ensure_ascii=False, indent=2)
np.savez_compressed(os.path.join(OUT, "crop_map.npz"), crop=crop, pixel_pred=pred,
                    dip1=dip1.astype("float16"), dip2=dip2.astype("float16"),
                    vv_med=vv_med.astype("float16"), vh_p80=vh_p80.astype("float16"))
for k in ("期間", "各類面積_公頃", "水稻占農地比例（水稻＋其他作物）"):
    print(k, stats[k])
