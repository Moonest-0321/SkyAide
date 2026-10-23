"""產生《演算法原理白話說明》用的圖（用丹娜絲真實 Sentinel-1 資料＋模擬資料）。"""
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import skyaide_demo as sky

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output_explain")
os.makedirs(OUT, exist_ok=True)
for f in ["Noto Sans CJK TC", "PingFang TC", "Heiti TC", "Microsoft JhengHei"]:
    try:
        from matplotlib import font_manager
        font_manager.findfont(f, fallback_to_default=False)
        plt.rcParams["font.family"] = f
        break
    except Exception:
        continue
plt.rcParams["axes.unicode_minus"] = False
credit = "真實資料：Contains modified Copernicus Sentinel data 2025, processed by Microsoft Planetary Computer"

d = np.load(os.path.join(HERE, "real_data", "danas_s1.npz"))
pre_lin = [np.nan_to_num(d[f"pre{i}_vv"], nan=1e-4) for i in range(6)]
post_lin = np.nan_to_num(d["post_vv"], nan=1e-4)
pre_db = sky.to_db(np.stack([sky.lee_filter(x) for x in pre_lin]))
post_db = sky.to_db(sky.lee_filter(post_lin))
flood = np.load(os.path.join(HERE, "output_real", "flood_mask.npy"))

# ---------- 圖 E1：斑點雜訊與 Lee 濾波（布袋附近一小塊，約 1.5 公里） ----------
y0, x0, n = 880, 560, 150
raw = sky.to_db(post_lin)[y0:y0 + n, x0:x0 + n]
flt = post_db[y0:y0 + n, x0:x0 + n]
fig, axs = plt.subplots(1, 3, figsize=(15, 5))
axs[0].imshow(raw, cmap="gray", vmin=-22, vmax=-2)
axs[0].set_title("原始雷達影像（dB）：顆粒很粗")
axs[1].imshow(flt, cmap="gray", vmin=-22, vmax=-2)
axs[1].set_title("Lee 濾波後：田塊內變平滑，邊界還在")
row = n // 2
axs[2].plot(raw[row], color="#bbb", lw=1, label="原始")
axs[2].plot(flt[row], color="#1565c0", lw=1.8, label="濾波後")
axs[2].set_title("同一條橫線上的數值")
axs[2].set_xlabel("像素（每格約 10 米）")
axs[2].set_ylabel("VV（dB）")
axs[2].legend()
for ax in axs[:2]:
    ax.axhline(row, color="#e53935", lw=0.8)
    ax.set_xticks([]); ax.set_yticks([])
fig.suptitle("圖 E1　雷達的斑點雜訊與 Lee 濾波（丹娜絲災後 7/10，布袋附近約 1.5 公里見方）", fontsize=12)
fig.text(0.5, -0.01, credit, ha="center", fontsize=8, color="gray")
fig.tight_layout()
fig.savefig(os.path.join(OUT, "figE1_lee.png"), dpi=120, bbox_inches="tight")
plt.close(fig)

# ---------- 圖 E2：Otsu 直方圖 ----------
vals = post_db[np.isfinite(post_db)].ravel()
thr = sky.otsu(vals)
fig, ax = plt.subplots(figsize=(10, 4.8))
ax.hist(vals, bins=200, range=(-30, 5), color="#90a4ae")
ax.axvline(thr, color="#e53935", lw=2, label=f"Otsu 自動門檻 {thr:.1f} dB")
ax.axvline(-15, color="#1565c0", lw=2, ls="--", label="採用的上限 −15 dB")
ax.text(-24.5, ax.get_ylim()[1] * 0.85, "水面\n（海、魚塭、河）", ha="center", fontsize=10)
ax.text(-6, ax.get_ylim()[1] * 0.85, "陸地\n（田、房子、路）", ha="center", fontsize=10)
ax.set_xlabel("災後 VV（dB）")
ax.set_ylabel("像素數")
ax.set_title("圖 E2　整張影像的亮度分布：兩座山，Otsu 在兩座山之間切一刀")
ax.legend(loc="upper left", bbox_to_anchor=(0.30, 1.0))
fig.text(0.5, -0.02, credit, ha="center", fontsize=8, color="gray")
fig.tight_layout()
fig.savefig(os.path.join(OUT, "figE2_otsu.png"), dpi=120, bbox_inches="tight")
plt.close(fig)

# ---------- 圖 E3：一個像素的時間序列 ----------
ys, xs = np.where(flood)
k = len(ys) // 3
fy, fx = ys[k], xs[k]                                    # 一個被判為淹水的像素
land = (~flood) & (pre_db.mean(0) > -12) & (pre_db.std(0) < 0.8)
ly, lx = [a[len(a) // 2] for a in np.where(land)]        # 一個沒事的像素
dates = ["6/04", "6/10", "6/16", "6/22", "6/28", "7/04", "7/10\n災後"]
fig, axs = plt.subplots(1, 2, figsize=(14, 4.8), sharey=True)
for ax, (py, px), name in [(axs[0], (ly, lx), "沒事的田"), (axs[1], (fy, fx), "被判為淹水的田")]:
    series = np.append(pre_db[:, py, px], post_db[py, px])
    m, s = pre_db[:, py, px].mean(), max(pre_db[:, py, px].std(), 0.5)
    last2 = pre_db[-2:, py, px].mean()
    ax.fill_between([-0.3, 6.3], m - 3 * s, m + 3 * s, color="#e3f2fd", label="災前平均 ± 3 個標準差（法 3）")
    ax.axhline(m, color="#64b5f6", lw=1)
    ax.axhline(last2 - 3, color="#fb8c00", ls="--", lw=1.5, label="比災前最近兩期暗 3 dB（法 2）")
    ax.axhline(-15, color="#e53935", ls=":", lw=1.5, label="水面門檻 −15 dB（法 1）")
    ax.plot(range(6), series[:6], "o-", color="#455a64", label="災前 6 期")
    ax.plot(6, series[6], "s", ms=11, color="#d32f2f" if name != "沒事的田" else "#2e7d32", label="災後")
    ax.set_xticks(range(7)); ax.set_xticklabels(dates)
    ax.set_title(f"{name}：災後 {series[6]:.1f} dB")
    ax.set_ylim(-26, -2)
axs[0].set_ylabel("VV（dB）")
axs[1].legend(loc="lower left", fontsize=8.5)
fig.suptitle("圖 E3　同一個像素 7 次拍攝的亮度：沒事的田在框框內，淹水的田掉出去", fontsize=12)
fig.text(0.5, -0.02, credit, ha="center", fontsize=8, color="gray")
fig.tight_layout()
fig.savefig(os.path.join(OUT, "figE3_timeseries.png"), dpi=120, bbox_inches="tight")
plt.close(fig)

# ---------- 圖 E4：NDVI 相對分數（模擬資料） ----------
sc = sky.simulate_scene(42)
maps, rows = sky.analyse(sc)
sky.classify_parcels(rows)
rice = [r for r in rows if r["pred_crop"] == 0 and np.isfinite(r["dndvi"])]
ref = [r["dndvi"] for r in rice if max(r["flood_frac"], r["lodge_frac"], r["buried_frac"]) < 0.1]
dmg = [r for r in rice if max(r["flood_frac"], r["lodge_frac"], r["buried_frac"]) >= 0.1]
med = np.median(ref)
mad = max(1.4826 * np.median(np.abs(np.array(ref) - med)), 0.02)
fig, ax = plt.subplots(figsize=(10, 4.6))
ax.scatter(ref, np.zeros(len(ref)) + np.random.default_rng(1).uniform(-0.15, 0.15, len(ref)),
           color="#66bb6a", s=40, label="參考組：雷達看起來沒事的水稻田")
ax.scatter([r["dndvi"] for r in dmg], np.ones(len(dmg)) + np.random.default_rng(2).uniform(-0.15, 0.15, len(dmg)),
           color="#e53935", s=40, label="雷達有看到變化的水稻田")
ax.axvline(med, color="#2e7d32", lw=1.5)
ax.axvspan(med - 3 * mad, med + 3 * mad, color="#c8e6c9", alpha=0.5, label="參考組中位數 ± 3 個「標準差」")
ax.text(med, 1.55, f"中位數 {med:+.2f}\n（全區季節性下降）", ha="center", fontsize=9, color="#2e7d32")
ax.set_yticks([0, 1]); ax.set_yticklabels(["參考組", "待判斷"])
ax.set_ylim(-0.6, 2.0)
ax.set_xlabel("NDVI 變化（災後 − 災前），越左邊掉越多")
ax.set_title("圖 E4　NDVI 相對分數：不是看掉了多少，而是看「比沒事的田多掉多少」（模擬資料）")
ax.legend(loc="lower left", fontsize=9)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "figE4_ndvi_z.png"), dpi=120, bbox_inches="tight")
plt.close(fig)

print("像素", (fy, fx), "淹水；", (ly, lx), "沒事；Otsu", round(float(thr), 1))
print("輸出到", OUT)
