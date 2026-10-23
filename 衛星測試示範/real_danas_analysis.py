"""
真實資料：丹娜絲颱風前後 Sentinel-1，嘉義布袋～台南北門沿海淹水判釋
====================================================================

資料：Microsoft Planetary Computer sentinel-1-rtc（已做輻射地形校正，線性 γ0）
      軌道 105（下降軌道），災前 2025-06-04～07-04 共 6 期，災後 2025-07-10
範圍：東經 120.10–120.25、北緯 23.25–23.40（約 15 × 17 公里），1600 × 1600 像素
方法：和 skyaide_demo.py 完全相同的函式 —— Lee 濾波、淹水三法投票
      （沒有地籍資料，所以只做到像素層級的淹水圖，不做坵塊分級）

執行：python fetch_crop.py           先下載（需網路，約 45 秒，存到 real_data/）
      python real_danas_analysis.py  再分析
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

import skyaide_demo as sky

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "real_data")
OUT = os.path.join(HERE, "output_real")
os.makedirs(OUT, exist_ok=True)

d = np.load(os.path.join(DATA, "danas_s1.npz"))
meta = json.load(open(os.path.join(DATA, "scenes.json"), encoding="utf-8"))
W_, S_, E_, N_ = meta["bbox"]
ext = [W_, E_, S_, N_]
pix_m2 = (15330 / 1600) * (16600 / 1600)          # 每像素約 9.6 × 10.4 米

pre_vv = [d[f"pre{i}_vv"] for i in range(6)]
post_vv = d["post_vv"]

# 前處理：Lee 濾波 → dB（和模擬版同一個函式）
vv_pre_db = sky.to_db(np.stack([sky.lee_filter(np.nan_to_num(x, nan=1e-4)) for x in pre_vv]))
vv_post_db = sky.to_db(sky.lee_filter(np.nan_to_num(post_vv, nan=1e-4)))

# 淹水三法投票（和模擬版同一個函式）
otsu_raw = float(sky.otsu(vv_post_db))
# 這一區有大片海面與魚塭，Otsu 會把門檻拉到 −11 dB，連潮濕的田都算成水；
# 依文獻常用的 VV 水體門檻範圍（約 −15 至 −18 dB），上限設為 −15 dB
flood, det = sky.flood_vote(vv_pre_db, vv_post_db, max_thr_db=-15.0)
# 去掉零星小點：連在一起少於 20 個像素（約 0.2 公頃）的不算
lab, n = ndi.label(flood)
sizes = ndi.sum(flood, lab, index=np.arange(1, n + 1))
flood_clean = np.isin(lab, np.where(sizes >= 20)[0] + 1)

stats = {
    "Otsu原始門檻_dB": round(otsu_raw, 2),
    "採用門檻_dB": round(det["threshold_db"], 2),
    "永久水體_平方公里": round(det["perm_water"].sum() * pix_m2 / 1e6, 2),
    "法1_Otsu_平方公里": round(det["otsu"].sum() * pix_m2 / 1e6, 2),
    "法2_變遷_平方公里": round(det["change"].sum() * pix_m2 / 1e6, 2),
    "法3_時序異常_平方公里": round(det["anomaly"].sum() * pix_m2 / 1e6, 2),
    "投票淹水_平方公里": round(flood.sum() * pix_m2 / 1e6, 2),
    "投票淹水去零星點_平方公里": round(flood_clean.sum() * pix_m2 / 1e6, 2),
    "淹水_公頃": round(flood_clean.sum() * pix_m2 / 1e4, 1),
}
# 每一期的整體平均 dB，看災前是否穩定
stats["各期VV中位數_dB"] = {meta["scenes"][f"pre{i}"]["datetime"][:10]: round(float(np.nanmedian(vv_pre_db[i])), 2)
                          for i in range(6)}
stats["各期VV中位數_dB"][meta["scenes"]["post"]["datetime"][:10] + "（災後）"] = round(float(np.nanmedian(vv_post_db)), 2)
json.dump(stats, open(os.path.join(OUT, "real_stats.json"), "w"), ensure_ascii=False, indent=2)
np.save(os.path.join(OUT, "flood_mask.npy"), flood_clean)
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
post_date = meta["scenes"]["post"]["datetime"][:10]
pre_last = meta["scenes"]["pre5"]["datetime"][:10]
credit = "Contains modified Copernicus Sentinel data 2025, processed by Microsoft Planetary Computer"


def stretch(x, lo=-22, hi=-3):
    return np.clip((x - lo) / (hi - lo), 0, 1)


# 圖 R1：災前、災後、變遷合成
fig, axs = plt.subplots(1, 3, figsize=(18, 6.4))
axs[0].imshow(vv_pre_db[-2:].mean(0), cmap="gray", vmin=-22, vmax=-3, extent=ext)
axs[0].set_title(f"① 災前 VV（{pre_last} 前兩期平均）")
axs[1].imshow(vv_post_db, cmap="gray", vmin=-22, vmax=-3, extent=ext)
axs[1].set_title(f"② 災後 VV（{post_date}）")
rgb = np.dstack([stretch(vv_pre_db[-2:].mean(0)), stretch(vv_post_db), stretch(vv_post_db)])
axs[2].imshow(rgb, extent=ext)
axs[2].set_title("③ 變遷合成：紅＝災前亮、災後變暗（疑似淹水）")
for ax in axs:
    ax.set_xlabel("東經")
    ax.set_ylabel("北緯")
fig.suptitle("圖 R1　丹娜絲颱風前後 Sentinel-1 雷達影像｜嘉義布袋～台南北門沿海", fontsize=13)
fig.text(0.5, 0.01, credit, ha="center", fontsize=8, color="gray")
fig.tight_layout(rect=[0, 0.03, 1, 1])
fig.savefig(os.path.join(OUT, "figR1_pre_post.png"), dpi=120, bbox_inches="tight")
plt.close(fig)

# 圖 R2：三法與投票
fig, axs = plt.subplots(1, 4, figsize=(22, 6))
for ax, key, title in zip(axs, ["otsu", "change", "anomaly"],
                          [f"法 1 水體門檻（{det['threshold_db']:.1f} dB）",
                           "法 2 變遷偵測（比災前暗 3 dB）", "法 3 時序異常（−3σ）"]):
    ax.imshow(det[key], cmap="Blues", extent=ext, interpolation="nearest")
    ax.set_title(f"{title}\n{det[key].sum() * pix_m2 / 1e6:.1f} 平方公里")
votes = det["otsu"].astype(int) + det["change"] + det["anomaly"]
show = np.full(flood.shape, 0)
show[det["perm_water"]] = 1
show[(votes == 1) & ~det["perm_water"]] = 2
show[flood_clean] = 3
cm = ListedColormap(["#ffffff", "#b0bec5", "#ffcc80", "#1565c0"])
axs[3].imshow(show, cmap=cm, vmin=0, vmax=3, extent=ext, interpolation="nearest")
axs[3].set_title(f"投票結果：淹水 {stats['淹水_公頃']:.0f} 公頃")
axs[3].legend(handles=[Patch(color="#b0bec5", label="災前就是水（海、魚塭）"),
                       Patch(color="#ffcc80", label="只有 1 法判淹水"),
                       Patch(color="#1565c0", label="≥2 法同意＝淹水")],
              loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=1, fontsize=9, frameon=False)
for ax in axs:
    ax.set_xlabel("東經")
fig.suptitle("圖 R2　真實資料淹水三法投票（與模擬版同一套程式）", fontsize=13, y=1.04)
fig.text(0.5, -0.02, credit, ha="center", fontsize=8, color="gray")
fig.tight_layout()
fig.savefig(os.path.join(OUT, "figR2_flood_vote.png"), dpi=120, bbox_inches="tight")
plt.close(fig)

# 圖 R3：疊在災後影像上的淹水範圍
fig, ax = plt.subplots(figsize=(9, 9.5))
ax.imshow(vv_post_db, cmap="gray", vmin=-22, vmax=-3, extent=ext)
ov = np.zeros(flood.shape + (4,))
ov[det["perm_water"]] = [0.55, 0.65, 0.75, 0.35]
ov[flood_clean] = [0.0, 0.45, 1.0, 0.85]
ax.imshow(ov, extent=ext, interpolation="nearest")
ax.set_title(f"圖 R3　判定淹水範圍（藍）｜{post_date}｜約 {stats['淹水_公頃']:.0f} 公頃", fontsize=12)
ax.legend(handles=[Patch(color=(0, 0.45, 1), label="新增水面（淹水）"),
                   Patch(color=(0.55, 0.65, 0.75), label="災前就是水")],
          loc="lower right", fontsize=9)
ax.set_xlabel("東經")
ax.set_ylabel("北緯")
fig.text(0.5, 0.01, credit, ha="center", fontsize=8, color="gray")
fig.savefig(os.path.join(OUT, "figR3_flood_overlay.png"), dpi=130, bbox_inches="tight")
plt.close(fig)
print("圖已輸出到", OUT)
