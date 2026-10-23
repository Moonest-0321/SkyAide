"""
真實資料：丹娜絲颱風 Sentinel-2 植生受損（相對於去年同期）
==========================================================

做法（技術說明 參、五 ⑤「相對於自身往年同期」）：
  今年變化  Δ2025 = NDVI(2025-07-18) − NDVI(2025-06-28)     颱風 7/6 登陸
  去年變化  Δ2024 = NDVI(2024-07-18) − NDVI(2024-07-03)     同季節、沒有颱風
  異常      = Δ2025 − Δ2024
7 月是一期稻收割季，NDVI 本來就會降；減掉去年同期，扣除「每年都會發生的下降」，
剩下明顯更差（異常 < −0.2）的地方，才標為疑似受損。

只看：四期都沒被雲遮、且今年災前 NDVI > 0.4（有作物）的像素。
另外把 Sentinel-1 的淹水斑塊疊上去，看兩種衛星是否指向同一批田。

執行：python fetch_s2.py 之後 python real_s2_analysis.py
"""
import json
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "real_data")
OUT = os.path.join(HERE, "output_real")
os.makedirs(OUT, exist_ok=True)

ANOM = -0.2          # 比去年同期多降 0.2 以上 → 疑似受損
VEG = 0.4            # 災前 NDVI > 0.4 才算有作物
MIN_PIX = 20         # 連在一起至少 20 像素（約 0.2 公頃）才算

d = np.load(os.path.join(DATA, "danas_s2.npz"))
meta = json.load(open(os.path.join(DATA, "scenes_s2.json"), encoding="utf-8"))
W_, S_, E_, N_ = meta["bbox"]
ext = [W_, E_, S_, N_]
pix_m2 = (15330 / 1600) * (16600 / 1600)

pre25, post25 = d["y2025_pre_ndvi"], d["y2025_post_ndvi"]
pre24, post24 = d["y2024_pre_ndvi"], d["y2024_post_ndvi"]
d25 = post25 - pre25
d24 = post24 - pre24
anom = d25 - d24

valid = np.isfinite(anom)
crop = valid & (pre25 > VEG)
raw = crop & (anom < ANOM)
lab, n = ndi.label(raw)
sizes = ndi.sum(raw, lab, index=np.arange(1, n + 1))
damage = np.isin(lab, np.where(sizes >= MIN_PIX)[0] + 1)

# 如果只看今年（不扣去年）會標出多少？用來說明「往年同期」的必要
naive = crop & (d25 < ANOM)
lab2, n2 = ndi.label(naive)
s2 = ndi.sum(naive, lab2, index=np.arange(1, n2 + 1))
naive = np.isin(lab2, np.where(s2 >= MIN_PIX)[0] + 1)

# 和 Sentinel-1 淹水斑塊比對
s1_path = os.path.join(OUT, "flood_mask.npy")
s1 = np.load(s1_path) if os.path.exists(s1_path) else np.zeros_like(damage)
both = damage & s1

ha = lambda m: round(float(m.sum()) * pix_m2 / 1e4, 1)
stats = {
    "日期": {k: v["date"] for k, v in meta["scenes"].items()},
    "四期都無雲的比例": round(float(valid.mean()), 3),
    "可分析作物面積_公頃": ha(crop),
    "作物像素NDVI變化中位數_今年": round(float(np.nanmedian(d25[crop])), 3),
    "作物像素NDVI變化中位數_去年同期": round(float(np.nanmedian(d24[crop])), 3),
    "只看今年下降>0.2_公頃": ha(naive),
    "扣除去年同期後疑似受損_公頃": ha(damage),
    "疑似受損占可分析作物面積": round(float(damage.sum() / max(1, crop.sum())), 3),
    "Sentinel1淹水斑塊_公頃": ha(s1),
    "兩種衛星都指向的面積_公頃": ha(both),
    "淹水斑塊中可用光學判讀的比例": round(float((s1 & valid).sum() / max(1, s1.sum())), 3),
}
json.dump(stats, open(os.path.join(OUT, "real_s2_stats.json"), "w"), ensure_ascii=False, indent=2)
np.save(os.path.join(OUT, "ndvi_damage_mask.npy"), damage)
for k, v in stats.items():
    print(k, v)

# ---------------- 圖 ----------------
for f in ["Noto Sans CJK TC", "PingFang TC", "Heiti TC", "Microsoft JhengHei", "Arial Unicode MS"]:
    try:
        from matplotlib import font_manager
        font_manager.findfont(f, fallback_to_default=False)
        plt.rcParams["font.family"] = f
        break
    except Exception:
        continue
plt.rcParams["axes.unicode_minus"] = False
credit = "Contains modified Copernicus Sentinel data 2024–2025, processed by Microsoft Planetary Computer"
D = stats["日期"]

fig, axs = plt.subplots(2, 3, figsize=(19, 13))
cloud_bg = "#cfd8dc"
for ax, arr, title in [(axs[0, 0], pre25, f"① 今年災前 NDVI（{D['y2025_pre']}）"),
                       (axs[0, 1], post25, f"② 今年災後 NDVI（{D['y2025_post']}）"),
                       (axs[0, 2], post24, f"③ 去年同期 NDVI（{D['y2024_post']}）")]:
    ax.set_facecolor(cloud_bg)
    im = ax.imshow(arr, cmap="RdYlGn", vmin=-0.1, vmax=0.85, extent=ext, interpolation="nearest")
    ax.set_title(title + "　灰＝雲")
plt.colorbar(im, ax=axs[0, :], fraction=0.015, pad=0.01, label="NDVI")
for ax, arr, title in [(axs[1, 0], np.where(crop, d25, np.nan), "④ 今年變化 Δ2025（作物像素）"),
                       (axs[1, 1], np.where(crop, anom, np.nan), "⑤ 異常 ＝ Δ2025 − Δ2024")]:
    ax.set_facecolor(cloud_bg)
    im2 = ax.imshow(arr, cmap="RdBu", vmin=-0.5, vmax=0.5, extent=ext, interpolation="nearest")
    ax.set_title(title)
cb = plt.colorbar(im2, ax=axs[1, 1], fraction=0.046, pad=0.02)
cb.ax.set_title("紅＝降", fontsize=9)

show = np.zeros(damage.shape)
show[crop] = 1
show[naive & ~damage] = 2
show[damage] = 3
show[s1] = np.where(damage[s1], 5, 4)
cm = ListedColormap(["#ffffff", "#e8f5e9", "#ffe0b2", "#d32f2f", "#1e88e5", "#6a1b9a"])
axs[1, 2].imshow(show, cmap=cm, vmin=0, vmax=5, extent=ext, interpolation="nearest")
axs[1, 2].set_title(f"⑥ 多源證據：疑似受損 {stats['扣除去年同期後疑似受損_公頃']:.0f} 公頃")
axs[1, 2].legend(handles=[
    Patch(color="#e8f5e9", label="可判讀的作物"),
    Patch(color="#ffe0b2", label="只看今年會被標、扣去年同期後不算"),
    Patch(color="#d32f2f", label="光學：比去年同期多降 0.2 以上"),
    Patch(color="#1e88e5", label="雷達：淹水斑塊"),
    Patch(color="#6a1b9a", label="兩者都有")],
    loc="upper center", bbox_to_anchor=(0.5, -0.06), ncol=2, fontsize=9, frameon=False)
for ax in axs.flat:
    ax.set_xlabel("東經")
fig.suptitle("圖 R4　丹娜絲颱風 Sentinel-2 植生受損：相對於去年同期｜嘉義布袋～台南北門", fontsize=14)
fig.text(0.5, 0.005, credit, ha="center", fontsize=8, color="gray")
fig.savefig(os.path.join(OUT, "figR4_ndvi_anomaly.png"), dpi=110, bbox_inches="tight")
plt.close(fig)
print("圖已輸出到", OUT)
