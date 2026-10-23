"""
作物判釋 v2：魚塭照 Ottinger 等人（2022）、陸地用 Presto 預訓練模型
=====================================================================

和 v1（crop_classify.py，純規則）的差別：
  - 水面與魚塭：照 Ottinger et al. (2022) Remote Sensing 14(1):153 的流程
      全年 VH 中位數 → Otsu 自動門檻 → 切成一個個水面物件 → 依形狀篩選
      （論文沒有公布形狀門檻數值，這裡的數值是本研究自訂，見 POND_*）
      和研究區西邊的海連在一起、或細長的水面（河道）＝天然水體，其餘像池子的＝魚塭／鹽田
  - 陸地（水稻、其他作物、建地）：
      NASA Harvest 的開源預訓練模型 Presto（Tseng et al., 2023；MIT 授權；
      也是歐洲太空總署 WorldCereal 的骨幹）把每個像素 12 個月的雷達值轉成 128 維特徵，
      再用「作物曆規則挑出的典型樣本」訓練一個邏輯斯迴歸分類器，推到全部陸地。
      只用 Sentinel-1（VV、VH），Presto 其他輸入（光學、氣象、地形）以遮罩略過。
  - 為了在 2 核 CPU 上幾分鐘內跑完，陸地分類在 20 米解析度進行，再放大回 10 米。

類別：0 水體　1 魚塭／鹽田　2 水稻（有插秧訊號）　3 其他作物　4 建地／道路　5 可能是水稻
  「可能是水稻」：Presto 分類器判為水稻、但時序上看不到插秧灌水的 V 字，先不算進水稻
  魚塭區：周圍 25% 以上是池子的地方，堤岸和放水中的池子一併算魚塭／鹽田
限制：沒有官方標註可比對，只是粗分；典型樣本來自規則，不是人工標註。

執行：python fetch_s1_year.py 之後 python crop_classify_v2.py（約 5–8 分鐘）
需要：numpy scipy scikit-learn scikit-image torch einops
"""
import json
import os
import sys
import time

import numpy as np
from scipy import ndimage as ndi
from skimage.filters import threshold_otsu
from skimage.measure import label, regionprops
from skimage.segmentation import expand_labels
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "third_party"))
import torch                                   # noqa: E402
import single_file_presto as presto            # noqa: E402

DATA = os.path.join(HERE, "real_data")
OUT = os.path.join(HERE, "output_crop")
os.makedirs(OUT, exist_ok=True)

CLASSES = ["水體", "魚塭／鹽田", "水稻", "其他作物", "建地／道路", "可能是水稻"]
HA = 15330 / 1600 * 16600 / 1600 / 1e4
LAT0, LON0, DLAT, DLON = 23.40, 120.10, 0.15, 0.15

# 魚塭形狀篩選（本研究自訂；論文用緊實度、凸包比等指標但未公布數值）
POND_MIN_HA, POND_MAX_HA = 0.05, 200.0    # 面積（大型鹽田、滯洪池也算進來）
POND_ERODE = 2                            # 先內縮 2 像素，把濾波後糊在一起的相鄰池子分開
POND_SOLIDITY = 0.75                      # 面積 ÷ 凸包面積：池子方正，接近 1；河道彎曲細長，偏低
POND_ELONG = 6.0                          # 長軸 ÷ 短軸：超過視為細長水道

# 典型樣本規則（同 v1，但更嚴格，只挑很確定的）
RICE_DIP, RICE_VH80 = -4.0, -16.5
BUILT_VV = -3.0
N_SAMPLE = 3000

t0 = time.time()
d = np.load(os.path.join(DATA, "s1_year.npz"))
vv = d["vv"].astype("float32")
vh = d["vh"].astype("float32")
dates = [str(s) for s in d["dates"]]
T, H, W = vh.shape

# ---------- 扣掉每期整體亮度跳動 ----------
land0 = np.median(vv, 0) > -14
for arr in (vv, vh):
    off = np.array([np.median(arr[t][land0]) for t in range(T)])
    arr -= (off - off.mean())[:, None, None]

# ========== 1. 水面與魚塭：Ottinger et al. (2022) ==========
vh_med = np.median(vh, 0)                                 # 全年 VH 中位數
otsu_thr = float(threshold_otsu(vh_med[np.isfinite(vh_med)]))
water = vh_med < otsu_thr
water = ndi.binary_opening(water, iterations=1)           # 去掉單點雜訊
core = ndi.binary_erosion(water, iterations=POND_ERODE)   # 內縮，切開相鄰池子
lab = expand_labels(label(core, connectivity=1), distance=POND_ERODE + 1)
lab[~water] = 0                                           # 長回原大小，但不超出水面
sea_ids = set(np.unique(lab[:, :5])) - {0}               # 和西邊界相連＝海（含河口、河道）
pond = np.zeros((H, W), bool)
natural = np.zeros((H, W), bool)
n_pond_obj = 0
for r in regionprops(lab):
    sl = r.slice
    m = lab[sl] == r.label
    a_ha = r.area * HA
    elong = r.axis_major_length / max(r.axis_minor_length, 1)
    if r.label in sea_ids or a_ha > POND_MAX_HA or elong > POND_ELONG or r.solidity < POND_SOLIDITY:
        natural[sl][m] = True
    elif a_ha >= POND_MIN_HA:
        pond[sl][m] = True
        n_pond_obj += 1
print(f"[1] Otsu 門檻 {otsu_thr:.1f} dB；魚塭物件 {n_pond_obj} 個；{time.time() - t0:.0f} 秒")

# ========== 2. 典型樣本（陸地）==========
idx = lambda a, b: [i for i, s in enumerate(dates) if a <= s <= b]
dip2 = vh[idx("2024-07-01", "2024-08-31")].min(0) - np.median(vh[idx("2024-09-10", "2024-10-31")], 0)
dip1 = vh[idx("2025-01-01", "2025-03-31")].min(0) - np.median(vh[idx("2025-04-01", "2025-05-31")], 0)
vv_med = np.median(vv, 0)
vh_p80 = np.percentile(vh, 80, axis=0)
vh_std = vh.std(0)
land = ~(water | ndi.binary_dilation(water, iterations=1))
typical = {
    2: land & (np.minimum(dip1, dip2) < RICE_DIP) & (vh_p80 > RICE_VH80) & (vv_med > -14) & (vv_med < -6),
    3: land & (vv_med > -11) & (vv_med < -5) & (vh_p80 > RICE_VH80) & (dip1 > -1.5) & (dip2 > -1.5) & (vh_std < 1.0),
    4: land & (vv_med > BUILT_VV),
}

# ========== 3. Presto 特徵（20 米）==========
def down2(a):                     # 2×2 平均 → 20 米
    return a.reshape(*a.shape[:-2], a.shape[-2] // 2, 2, a.shape[-1] // 2, 2).mean((-3, -1))

months = [f"{y}-{m:02d}" for y, m in [(2024, m) for m in range(7, 13)] + [(2025, m) for m in range(1, 7)]]
mvv = np.stack([vv[[i for i, s in enumerate(dates) if s.startswith(mo)]].mean(0) for mo in months])
mvh = np.stack([vh[[i for i, s in enumerate(dates) if s.startswith(mo)]].mean(0) for mo in months])
mvv2, mvh2 = down2(mvv), down2(mvh)                       # (12, 800, 800)
h2, w2 = mvv2.shape[1:]
n_px = h2 * w2
NB = 17                                                   # Presto 正規化後的波段數；S1 是前兩個
x_all = np.zeros((n_px, 12, NB), np.float32)
x_all[:, :, 0] = ((mvv2.reshape(12, -1).T) + 25) / 25     # Presto 對 S1 的正規化：(dB + 25) / 25
x_all[:, :, 1] = ((mvh2.reshape(12, -1).T) + 25) / 25
mask = np.ones((12, NB), np.float32); mask[:, 0:2] = 0     # 只有 S1，其他波段遮掉
yy, xx = np.mgrid[0:h2, 0:w2]
latlon = np.stack([LAT0 - (yy.ravel() + 0.5) / h2 * DLAT, LON0 + (xx.ravel() + 0.5) / w2 * DLON], 1).astype(np.float32)

EMB_CACHE = os.path.join(OUT, "presto_emb_20m.npy")
if os.path.exists(EMB_CACHE) and os.path.getmtime(EMB_CACHE) > os.path.getmtime(os.path.join(DATA, "s1_year.npz")):
    emb = np.load(EMB_CACHE).astype(np.float32)               # 已算過就直接讀
else:
    torch.set_num_threads(os.cpu_count() or 2)
    model = presto.Presto.construct()
    model.load_state_dict(torch.load(os.path.join(HERE, "third_party", "presto_default_model.pt"),
                                     map_location="cpu", weights_only=True))
    enc = model.encoder.eval()
    emb = np.zeros((n_px, 128), np.float32)
    B = 8192
    mask_t = torch.from_numpy(mask).expand(B, 12, NB)
    dw = torch.full((B, 12), 9, dtype=torch.long)
    with torch.no_grad():
        for s in range(0, n_px, B):
            e = min(s + B, n_px); nb = e - s
            out = enc(torch.from_numpy(x_all[s:e]), dynamic_world=dw[:nb], latlons=torch.from_numpy(latlon[s:e]),
                      mask=mask_t[:nb], month=6, eval_task=True)        # 第一個月是 7 月（0＝1 月）
            emb[s:e] = out.numpy()
print(f"[3] Presto 特徵 {emb.shape}；{time.time() - t0:.0f} 秒")

# ========== 4. 分類器：典型樣本 → 邏輯斯迴歸 ==========
rng = np.random.default_rng(0)
Xs, ys = [], []
counts = {}
for c, m in typical.items():
    m2 = down2(m.astype(np.float32)) > 0.99                    # 20 米格子裡 4 個像素都典型
    ids = np.flatnonzero(m2.ravel())
    counts[CLASSES[c]] = int(len(ids))
    pick = rng.choice(ids, size=min(N_SAMPLE, len(ids)), replace=False)
    Xs.append(emb[pick]); ys.append(np.full(len(pick), c))
X, y = np.concatenate(Xs), np.concatenate(ys)
perm = rng.permutation(len(y)); half = len(y) // 2
scaler = StandardScaler().fit(X)
clf = LogisticRegression(max_iter=2000, C=0.5)
clf.fit(scaler.transform(X[perm[:half]]), y[perm[:half]])
agree = float((clf.predict(scaler.transform(X[perm[half:]])) == y[perm[half:]]).mean())
clf.fit(scaler.transform(X), y)
land_pred2 = clf.predict(scaler.transform(emb)).reshape(h2, w2).astype(np.uint8)
land_pred = np.kron(land_pred2, np.ones((2, 2), np.uint8))   # 放大回 10 米
print(f"[4] 典型樣本 {counts}；分類器與規則一致 {agree:.3f}；{time.time() - t0:.0f} 秒")

# ========== 5. 組合與平滑 ==========
pred = land_pred.copy()
no_v = (pred == 2) & (np.minimum(dip1, dip2) > -2.0)     # 判為水稻但沒有插秧 V 字
pred[no_v] = 5
pred[pond] = 1
pred[natural] = 0
score = np.stack([ndi.uniform_filter((pred == c).astype(np.float32), 5) for c in range(len(CLASSES))])
crop = score.argmax(0).astype(np.uint8)
crop[pond & (score[1] >= 0.3)] = 1          # 魚塭物件本身優先
# 魚塭區：周圍 9×9（約 90 公尺見方）有 25% 以上是池子，就算魚塭區（堤岸、放水中的池子），不判成作物
pond_zone = ndi.uniform_filter(pond.astype(np.float32), 9) >= 0.25
crop[pond_zone & np.isin(crop, [2, 3, 5])] = 1
crop[natural] = 0

crop[(water & ~pond & ~natural)] = 0      # 太小的水面碎片當水體
area = {CLASSES[c]: round(float((crop == c).sum() * HA)) for c in range(len(CLASSES))}
v1 = json.load(open(os.path.join(OUT, "crop_stats.json"), encoding="utf-8"))["各類面積_公頃"] \
    if os.path.exists(os.path.join(OUT, "crop_stats.json")) else None
stats = {
    "方法": "水面/魚塭：Ottinger et al. 2022（全年 VH 中位數＋Otsu＋形狀篩選）；陸地：Presto 預訓練特徵＋邏輯斯迴歸",
    "期間": f"{dates[0]} ～ {dates[-1]}（{T} 期，合成 12 個月）",
    "Otsu門檻_dB": round(otsu_thr, 2),
    "魚塭形狀門檻（自訂）": {"面積公頃": [POND_MIN_HA, POND_MAX_HA], "凸包比": POND_SOLIDITY, "長短軸比上限": POND_ELONG},
    "魚塭物件數": n_pond_obj,
    "典型樣本數（20米格）": counts,
    "分類器與規則一致的比例（不是準確度）": round(agree, 3),
    "各類面積_公頃": area,
    "v1規則版各類面積_公頃": v1,
    "水稻占農地比例（只算有插秧訊號）": round(area["水稻"] / max(1, area["水稻"] + area["其他作物"] + area["可能是水稻"]), 3),
}
json.dump(stats, open(os.path.join(OUT, "crop_stats_v2.json"), "w"), ensure_ascii=False, indent=2)
np.save(EMB_CACHE, emb.astype(np.float16))
np.savez_compressed(os.path.join(OUT, "crop_map_v2.npz"), crop=crop, land_pred=land_pred, pond=pond,
                    natural=natural, vh_med=vh_med.astype("float16"))
print(f"完成，{time.time() - t0:.0f} 秒")
for k in ("Otsu門檻_dB", "魚塭物件數", "各類面積_公頃", "v1規則版各類面積_公頃", "水稻占農地比例（只算有插秧訊號）"):
    print(k, stats[k])
