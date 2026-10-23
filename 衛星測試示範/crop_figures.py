"""作物判釋測試用圖：分布圖、各類一年雷達曲線、v1/v2 比較、受損依作物拆分。"""
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
OUT = os.path.join(HERE, "output_crop")
for f in ["Noto Sans CJK TC", "PingFang TC", "Heiti TC", "Microsoft JhengHei"]:
    try:
        from matplotlib import font_manager
        font_manager.findfont(f, fallback_to_default=False)
        plt.rcParams["font.family"] = f
        break
    except Exception:
        continue
plt.rcParams.update({"axes.unicode_minus": False, "axes.titlesize": 13, "axes.titleweight": "bold"})
CREDIT = "影像：Contains modified Copernicus Sentinel data 2024–2025, processed by Microsoft Planetary Computer"
EXT = [120.10, 120.25, 23.25, 23.40]
HA = 15330 / 1600 * 16600 / 1600 / 1e4

NAMES = ["水體（海、河、大型水面）", "魚塭／鹽田", "水稻（有插秧訊號）", "其他作物", "建地／道路", "可能是水稻"]
COLORS = ["#1f5fa8", "#5ec8d8", "#f2c230", "#5aa54a", "#9a9a9a", "#f29a4a"]
CM = ListedColormap(COLORS)

v2 = np.load(os.path.join(OUT, "crop_map_v2.npz"))
crop = v2["crop"]
v1 = np.load(os.path.join(OUT, "crop_map.npz"))["crop"]
tc = np.load(os.path.join(HERE, "real_data", "truecolor.npz"))["tc_pre"]
photo = np.clip(tc.astype(float) / 255 * 1.7, 0, 1) ** 0.85


def save(fig, name):
    fig.text(0.5, -0.01, CREDIT, ha="center", fontsize=8, color="gray")
    fig.savefig(os.path.join(OUT, name), dpi=120, bbox_inches="tight")
    plt.close(fig)


# ---------- 圖 C1：分布圖 ----------
fig, axs = plt.subplots(1, 2, figsize=(18, 9.6))
axs[0].imshow(photo, extent=EXT); axs[0].set_title("颱風前衛星照片　2025-06-15")
axs[1].imshow(crop, cmap=CM, vmin=0, vmax=5, extent=EXT, interpolation="nearest")
axs[1].set_title("作物粗分（颱風前一年的雷達，Presto＋魚塭形狀篩選）")
for ax in axs:
    ax.set_xlabel("東經"); ax.set_ylabel("北緯")
fig.legend(handles=[Patch(color=COLORS[i], label=NAMES[i]) for i in [2, 5, 3, 1, 0, 4]],
           loc="lower center", ncol=6, fontsize=11, frameon=False, bbox_to_anchor=(0.5, -0.01))
fig.suptitle("圖 C1　嘉義布袋～台南北門　作物粗分（僅供示範，未與官方資料比對）", fontsize=14)
fig.tight_layout(rect=[0, 0.07, 1, 0.97])
save(fig, "figC1_crop_map.png")

# ---------- 圖 C2：各類一年的雷達曲線 ----------
d = np.load(os.path.join(HERE, "real_data", "s1_year.npz"))
vh = d["vh"].astype("float32"); vv = d["vv"].astype("float32")
dates = [str(s) for s in d["dates"]]
T = len(dates)
land = np.median(vv, 0) > -14
off = np.array([np.median(vh[t][land]) for t in range(T)])
vh -= (off - off.mean())[:, None, None]
rng = np.random.default_rng(0)
fig, ax = plt.subplots(figsize=(14, 6.5))
for c in [2, 5, 3, 1, 4]:
    ys, xs = np.where(crop == c)
    sel = rng.choice(len(ys), min(30000, len(ys)), replace=False)
    ax.plot(range(T), np.median(vh[:, ys[sel], xs[sel]], 1), lw=2.6, color=COLORS[c], label=NAMES[c],
            marker="o", ms=3.5)
for lo, hi, txt in [("2024-07-01", "2024-08-31", "二期稻插秧期"), ("2025-01-01", "2025-03-31", "一期稻插秧期")]:
    i0 = min(i for i, s in enumerate(dates) if s >= lo); i1 = max(i for i, s in enumerate(dates) if s <= hi)
    ax.axvspan(i0 - 0.4, i1 + 0.4, color="#f2c230", alpha=0.12)
    ax.text((i0 + i1) / 2, -11.3, txt, ha="center", fontsize=10, color="#8a6d00")
ax.set_xticks(range(T)); ax.set_xticklabels([s[2:].replace("-", "/") for s in dates], rotation=90, fontsize=9)
ax.set_ylabel("雷達 VH（dB，越高代表植物越茂密）")
ax.set_ylim(-23, -11)
ax.grid(alpha=0.3)
ax.legend(loc="lower left", fontsize=10, ncol=3)
ax.set_title("圖 C2　各類別一年的雷達變化：水稻在插秧期先變暗、再隨稻子長高變亮")
fig.tight_layout()
save(fig, "figC2_yearly_curves.png")

# ---------- 圖 C3：純規則版 vs Presto 版 ----------
fig, axs = plt.subplots(1, 2, figsize=(18, 9.4))
axs[0].imshow(v1, cmap=ListedColormap(COLORS[:5]), vmin=0, vmax=4, extent=EXT, interpolation="nearest")
axs[0].set_title("v1　純規則（自訂門檻）")
axs[1].imshow(crop, cmap=CM, vmin=0, vmax=5, extent=EXT, interpolation="nearest")
axs[1].set_title("v2　Ottinger 2022 魚塭＋Presto 預訓練模型")
for ax in axs:
    ax.set_xlabel("東經")
fig.legend(handles=[Patch(color=COLORS[i], label=NAMES[i]) for i in [2, 5, 3, 1, 0, 4]],
           loc="lower center", ncol=6, fontsize=11, frameon=False, bbox_to_anchor=(0.5, -0.01))
fig.suptitle("圖 C3　兩個版本比較", fontsize=14)
fig.tight_layout(rect=[0, 0.07, 1, 0.97])
save(fig, "figC3_v1_vs_v2.png")

# ---------- 受損依作物拆分 ----------
s1 = np.load(os.path.join(HERE, "real_data", "danas_s1.npz"))
pre_db = sky.to_db(np.stack([sky.lee_filter(np.nan_to_num(s1[f"pre{i}_vv"], nan=1e-4)) for i in range(6)]))
post_db = sky.to_db(sky.lee_filter(np.nan_to_num(s1["post_vv"], nan=1e-4)))
flood = np.load(os.path.join(HERE, "output_real", "flood_mask.npy"))
ndmg = np.load(os.path.join(HERE, "output_real", "ndvi_damage_mask.npy"))
pm = pre_db.mean(0); drop = post_db - pre_db[-2:].mean(0)
facility = ndi.binary_opening((pm > -4) & (drop < -5), iterations=1)
wet = flood & ~facility & ~(pm > -4)

table = {}
for name, m in [("植物比往年多掉很多（光學）", ndmg), ("雷達變暗、疑似積水", wet), ("很亮的人造物變暗", facility)]:
    table[name] = {NAMES[c]: round(float((m & (crop == c)).sum() * HA)) for c in range(6)}
json.dump(table, open(os.path.join(OUT, "damage_by_crop.json"), "w"), ensure_ascii=False, indent=2)

order = [2, 5, 3, 1, 0, 4]
fig, ax = plt.subplots(figsize=(13, 4.6))
rows = list(table.keys())
for i, r in enumerate(rows[::-1]):
    left = 0
    for c in order:
        v = table[r][NAMES[c]]
        ax.barh(i, v, left=left, color=COLORS[c], height=0.6)
        if v >= 12:
            ax.text(left + v / 2, i, f"{v}", ha="center", va="center", fontsize=10,
                    color="white" if c in (0, 3, 4) else "black")
        left += v
    ax.text(left + 6, i, f"{left} 公頃", va="center", fontsize=11, fontweight="bold")
ax.set_yticks(range(len(rows))); ax.set_yticklabels(rows[::-1], fontsize=11)
ax.set_xlim(0, 560)
ax.set_xlabel("公頃")
[s_.set_visible(False) for s_ in (ax.spines["top"], ax.spines["right"])]
ax.legend(handles=[Patch(color=COLORS[c], label=NAMES[c]) for c in order], loc="upper center",
          bbox_to_anchor=(0.5, -0.22), ncol=6, fontsize=10, frameon=False)
ax.set_title("圖 C4　丹娜絲疑似受災面積，依颱風前的作物類別拆開")
fig.tight_layout()
save(fig, "figC4_damage_by_crop.png")
for k, v in table.items():
    print(k, v)
