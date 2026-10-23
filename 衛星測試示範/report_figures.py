"""
《丹娜絲颱風衛星影像分析報告》用圖：以「看得出來」為優先，少用專業術語。
需要 real_data/ 裡的 danas_s1.npz、danas_s2.npz、truecolor.npz，
以及 output_real/ 裡的 flood_mask.npy、ndvi_damage_mask.npy（先跑 real_*_analysis.py）。
"""
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects
from matplotlib.patches import Patch, Rectangle
from PIL import Image

import skyaide_demo as sky

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output_report")
SLIDE = os.path.join(OUT, "slider")
os.makedirs(SLIDE, exist_ok=True)
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
W_, E_, S_, N_ = 120.10, 120.25, 23.25, 23.40
N = 1600
BLUE, RED, GRAY = (0.0, 0.55, 1.0), (1.0, 0.15, 0.1), (0.55, 0.55, 0.55)

# ---------------- 讀資料 ----------------
s1 = np.load(os.path.join(HERE, "real_data", "danas_s1.npz"))
s2 = np.load(os.path.join(HERE, "real_data", "danas_s2.npz"))
tc = np.load(os.path.join(HERE, "real_data", "truecolor.npz"))
flood = np.load(os.path.join(HERE, "output_real", "flood_mask.npy"))
ndmg = np.load(os.path.join(HERE, "output_real", "ndvi_damage_mask.npy"))

pre_db = sky.to_db(np.stack([sky.lee_filter(np.nan_to_num(s1[f"pre{i}_vv"], nan=1e-4)) for i in range(6)]))
post_db = sky.to_db(sky.lee_filter(np.nan_to_num(s1["post_vv"], nan=1e-4)))
radar_pre = np.clip((pre_db[-2:].mean(0) + 22) / 20, 0, 1)      # 0–1 灰階
radar_post = np.clip((post_db + 22) / 20, 0, 1)

# 把雷達「明顯變暗」分成兩類：
#   疑似設施受損：災前非常亮（> −4 dB，金屬屋頂、光電板）且暗了 5 dB 以上
#   疑似積水：其他被三法投票判為淹水的
from scipy import ndimage as ndi
_pm = pre_db.mean(0)
_drop = post_db - pre_db[-2:].mean(0)
facility = ndi.binary_opening((_pm > -4) & (_drop < -5), iterations=1)
wet = flood & ~facility & ~(_pm > -4)
OPEN_WATER = float((post_db[wet] < -15).mean())
HA = 15330 / 1600 * 16600 / 1600 / 1e4                # 每像素公頃數
A_WET, A_FAC, A_ND = wet.sum() * HA, facility.sum() * HA, ndmg.sum() * HA
A_BOTH = (wet & ndmg).sum() * HA
print(f"疑似積水 {A_WET:.0f} 公頃（其中接近水面 {OPEN_WATER:.0%}）、疑似設施受損 {A_FAC:.1f} 公頃、"
      f"植物變少 {A_ND:.0f} 公頃、積水＋植物 {A_BOTH:.0f} 公頃")


def photo(a, gain=1.7):
    """真彩色影像調亮（原始 TCI 偏暗）。"""
    return np.clip(a.astype(float) / 255 * gain, 0, 1) ** 0.85


tc_pre, tc_post = photo(tc["tc_pre"]), photo(tc["tc_post"])
nd_pre, nd_post = s2["y2025_pre_ndvi"], s2["y2025_post_ndvi"]
s2_ok = np.isfinite(s2["y2025_pre_ndvi"] - s2["y2025_post_ndvi"] - s2["y2024_post_ndvi"] + s2["y2024_pre_ndvi"])

cmap_green = matplotlib.colors.LinearSegmentedColormap.from_list(
    "veg", ["#8d6e63", "#d7ccc8", "#f0f4c3", "#9ccc65", "#2e7d32", "#1b5e20"])


def veg_rgb(nd):
    """NDVI → 顏色（褐＝沒植物、深綠＝茂密），雲為淺灰。"""
    rgb = cmap_green(np.clip((np.nan_to_num(nd, nan=0) - 0.0) / 0.85, 0, 1))[..., :3]
    rgb[np.isnan(nd)] = 0.86
    return rgb


def rc(lat, lon):
    return int((N_ - lat) / (N_ - S_) * N), int((lon - W_) / (E_ - W_) * N)


def win(lat, lon, size):
    r, c = rc(lat, lon)
    return slice(r - size // 2, r + size // 2), slice(c - size // 2, c + size // 2)


def km_ext(sl):
    """放大圖的座標改用公里，方便看大小。"""
    h = (sl[0].stop - sl[0].start) * 10.4 / 1000
    w = (sl[1].stop - sl[1].start) * 9.6 / 1000
    return [0, w, h, 0]


def outline(ax, mask, color, ext, lw=1.6):
    """在影像上畫出 mask 的外框。extent=[左, 右, 下, 上]，第 0 列對應「上」。"""
    h, w = mask.shape
    xs = np.linspace(ext[0], ext[1], w)
    ys = np.linspace(ext[3], ext[2], h)          # 第 0 列 → 上（ext[3]）
    ax.contour(xs, ys, mask.astype(float), [0.5], colors=[color], linewidths=lw)


def scalebar(ax, ext, km=0.5):
    x0 = ext[0] + (ext[1] - ext[0]) * 0.05
    y0 = ext[2] - (ext[2] - ext[3]) * 0.06
    ax.plot([x0, x0 + km], [y0, y0], color="white", lw=4, solid_capstyle="butt")
    ax.plot([x0, x0 + km], [y0, y0], color="black", lw=2, solid_capstyle="butt")
    ax.text(x0 + km / 2, y0 - (ext[2] - ext[3]) * 0.025, f"{km:g} 公里", ha="center", va="bottom",
            fontsize=9, color="black", bbox=dict(fc="white", ec="none", alpha=0.7, pad=1))


def clean(ax):
    ax.set_xticks([]); ax.set_yticks([])


def save(fig, name):
    fig.text(0.5, -0.015, CREDIT, ha="center", fontsize=8, color="gray")
    fig.savefig(os.path.join(OUT, name), dpi=130, bbox_inches="tight")
    plt.close(fig)


EXT = [W_, E_, S_, N_]
ZOOMS = {   # 名稱: (中心緯度, 中心經度, 視窗像素)
    "A": (23.333, 120.135, 420),    # 河口泥沙
    "B": (23.355, 120.200, 420),    # 雷達穿雲
    "C": (23.262, 120.184, 220),    # 植物變少
    "D": (23.265, 120.193, 170),    # 疑似積水
    "E": (23.2967, 120.1536, 160),  # 很亮的人造物變暗
}
ZNAME = {"A": "河口泥沙", "B": "雷達穿雲", "C": "植物變少", "D": "疑似積水", "E": "人造物變暗"}

# ======== 圖 1：總覽 ========
fig, axs = plt.subplots(1, 3, figsize=(19, 7))
axs[0].imshow(tc_pre, extent=EXT)
axs[0].set_title("① 颱風前　6 月 15 日　衛星照片")
axs[1].imshow(tc_post, extent=EXT)
axs[1].set_title("② 颱風後　7 月 18 日　衛星照片")
axs[2].imshow(radar_post, cmap="gray", extent=EXT, vmin=0, vmax=1)
axs[2].set_title("③ 颱風後　7 月 10 日　雷達影像")
for ax in axs:
    for k, (la, lo, sz) in ZOOMS.items():
        sl = win(la, lo, sz)
        x0 = W_ + sl[1].start / N * (E_ - W_); x1 = W_ + sl[1].stop / N * (E_ - W_)
        y0 = N_ - sl[0].stop / N * (N_ - S_); y1 = N_ - sl[0].start / N * (N_ - S_)
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ec="#ffeb3b", lw=2))
        ax.text(x0, y1, f" {k}", color="#ffeb3b", fontsize=13, fontweight="bold", va="bottom",
                path_effects=[matplotlib.patheffects.withStroke(linewidth=3, foreground="black")])
    ax.set_xlabel("東經"); ax.set_ylabel("北緯")
axs[1].annotate("雲", xy=(120.205, 23.355), xytext=(120.225, 23.385), fontsize=13, color="white",
                fontweight="bold", arrowprops=dict(arrowstyle="->", color="white", lw=2),
                path_effects=[matplotlib.patheffects.withStroke(linewidth=3, foreground="black")])
axs[1].annotate("土黃色泥水", xy=(120.118, 23.335), xytext=(120.103, 23.365), fontsize=12, color="white",
                fontweight="bold", arrowprops=dict(arrowstyle="->", color="white", lw=2),
                path_effects=[matplotlib.patheffects.withStroke(linewidth=3, foreground="black")])
axs[2].text(120.175, 23.392, "亮＝陸地、房子　暗＝水面", ha="center", fontsize=10, color="black",
            bbox=dict(fc="white", ec="none", alpha=0.8))
fig.suptitle("圖 1　研究區總覽：嘉義布袋～台南北門沿海，約 15 × 17 公里（黃框 A～E 為後面的放大區）",
             fontsize=14, y=0.99)
fig.tight_layout()
save(fig, "fig1_overview.png")

# ======== 圖 2：A 河口泥沙 ========
sl = win(*ZOOMS["A"]); ext = km_ext(sl)
fig, axs = plt.subplots(1, 2, figsize=(14, 7.2))
for ax, img, t in [(axs[0], tc_pre[sl], "颱風前　6 月 15 日"), (axs[1], tc_post[sl], "颱風後　7 月 18 日")]:
    ax.imshow(img, extent=ext); ax.set_title(t); clean(ax); scalebar(ax, ext, 1)
axs[1].annotate("河水變成\n土黃色", xy=(2.9, 3.35), xytext=(2.2, 2.3), fontsize=12, color="white",
                fontweight="bold", arrowprops=dict(arrowstyle="->", color="white", lw=2),
                path_effects=[matplotlib.patheffects.withStroke(linewidth=3, foreground="black")])
fig.suptitle("圖 2　放大區 A：颱風後河水從綠色變成土黃色，豪雨帶來大量泥沙\n（潟湖裡露出的泥灘，也可能是拍攝時剛好退潮）", fontsize=14)
fig.tight_layout()
save(fig, "fig2_A_river.png")

# ======== 圖 3：B 雷達穿雲 ========
sl = win(*ZOOMS["B"]); ext = km_ext(sl)
fig, axs = plt.subplots(1, 3, figsize=(19, 6.8))
axs[0].imshow(tc_post[sl], extent=ext); axs[0].set_title("颱風後的照片：被雲擋住")
axs[1].imshow(radar_post[sl], cmap="gray", vmin=0, vmax=1, extent=ext); axs[1].set_title("同一個地方的雷達：雲擋不住")
blend = tc_post[sl].copy()
cl = tc_post[sl].sum(-1) > 2.3
blend[cl] = np.dstack([radar_post[sl]] * 3)[cl]
axs[2].imshow(blend, extent=ext); axs[2].set_title("把雲的部分換成雷達：沒有死角")
for ax in axs:
    clean(ax); scalebar(ax, ext, 1)
fig.suptitle("圖 3　放大區 B：光學衛星會被雲擋住，雷達衛星可以穿透雲層", fontsize=14)
fig.tight_layout(rect=[0, 0, 1, 0.94])
save(fig, "fig3_B_cloud.png")

# ======== 圖 4：C 植物變少 ========
sl = win(*ZOOMS["C"]); ext = km_ext(sl)
m = ndmg[sl]
fig, axs = plt.subplots(2, 2, figsize=(13.5, 13))
axs[0, 0].imshow(tc_pre[sl], extent=ext); axs[0, 0].set_title("颱風前照片　6 月 15 日")
axs[0, 1].imshow(tc_post[sl], extent=ext); axs[0, 1].set_title("颱風後照片　7 月 18 日")
axs[1, 0].imshow(veg_rgb(nd_pre[sl]), extent=ext); axs[1, 0].set_title("颱風前　植物茂密程度　6 月 28 日")
axs[1, 1].imshow(veg_rgb(nd_post[sl]), extent=ext); axs[1, 1].set_title("颱風後　植物茂密程度　7 月 18 日")
for ax in axs.flat:
    clean(ax); scalebar(ax, ext, 0.5)
for ax in (axs[0, 1], axs[1, 1], axs[1, 0]):
    outline(ax, m, RED, ext, 2)
fig.legend(handles=[Patch(color="#1b5e20", label="深綠：植物茂密"), Patch(color="#f0f4c3", label="淺黃：植物稀疏"),
                    Patch(color="#8d6e63", label="褐色：沒有植物"), Patch(color="#dbdbdb", label="淺灰：被雲遮"),
                    Patch(fc="none", ec=RED, lw=2, label="紅框：比去年同期多掉很多的田")],
           loc="lower center", ncol=5, fontsize=10, frameon=False, bbox_to_anchor=(0.5, 0.015))
fig.suptitle("圖 4　放大區 C：紅框裡的田，颱風後植物明顯變少（已扣除每年收割的正常下降）", fontsize=14)
fig.tight_layout(rect=[0, 0.04, 1, 0.97])
save(fig, "fig4_C_vegetation.png")

# ======== 圖 5：D 疑似積水 ========
sl = win(*ZOOMS["D"]); ext = km_ext(sl)
m = wet[sl]
fig, axs = plt.subplots(1, 3, figsize=(19, 6.8))
axs[0].imshow(radar_pre[sl], cmap="gray", vmin=0, vmax=1, extent=ext); axs[0].set_title("颱風前雷達　6 月 28 日～7 月 4 日")
axs[1].imshow(radar_post[sl], cmap="gray", vmin=0, vmax=1, extent=ext); axs[1].set_title("颱風後雷達　7 月 10 日")
ov = np.dstack([radar_post[sl]] * 3); ov[m] = BLUE
axs[2].imshow(ov, extent=ext); axs[2].set_title("藍色：明顯變暗的地方（疑似積水）")
for ax in axs:
    clean(ax); scalebar(ax, ext, 0.5)
outline(axs[0], m, (1, 0.85, 0), ext, 1.8)
outline(axs[1], m, (1, 0.85, 0), ext, 1.8)
fig.suptitle("圖 5　放大區 D：黃框裡的田，颱風後在雷達上變深色（雷達上越暗，越可能有水）", fontsize=14)
fig.tight_layout(rect=[0, 0, 1, 0.94])
save(fig, "fig5_D_water.png")

# ======== 圖 5b：E 很亮的人造物變暗 ========
sl = win(*ZOOMS["E"]); ext = km_ext(sl)
m = facility[sl]
ed = np.load(os.path.join(HERE, "real_data", "solar_E_dates.npz"))   # 這一小塊另外抓的無雲照片
bright = lambda db: np.clip((db + 6) / 18, 0, 1)
fig, axs = plt.subplots(2, 2, figsize=(13, 13.4))
axs[0, 0].imshow(photo(ed["2025_07_03"]), extent=ext); axs[0, 0].set_title("颱風前 3 天照片　7 月 3 日")
axs[0, 1].imshow(photo(ed["2025_07_23"]), extent=ext); axs[0, 1].set_title("颱風後照片　7 月 23 日")
axs[1, 0].imshow(bright(pre_db[-2:].mean(0)[sl]), cmap="inferno", vmin=0, vmax=1, extent=ext)
axs[1, 0].set_title("颱風前雷達：框內非常亮")
axs[1, 1].imshow(bright(post_db[sl]), cmap="inferno", vmin=0, vmax=1, extent=ext)
axs[1, 1].set_title("颱風後雷達：框內暗了約 10 dB")
for ax in axs.flat:
    clean(ax); scalebar(ax, ext, 0.3)
    outline(ax, m, "#00e5ff", ext, 2)
fig.legend(handles=[Patch(fc="none", ec="#00e5ff", lw=2, label="青色框：雷達亮度大幅下降的範圍"),
                    Patch(color="#fcffa4", label="雷達很亮"), Patch(color="#000004", label="雷達很暗")],
           loc="lower center", ncol=3, fontsize=10.5, frameon=False, bbox_to_anchor=(0.5, 0.012))
fig.suptitle("圖 5b　放大區 E：太陽能案場（紫灰色方塊）中間的空地，颱風前偏白、颱風後變淺綠，雷達同時暗了約 10 dB。\n"
             "原因待查：可能是堆放的金屬材料或機具被移走，也可能是地面整理過；需要到現場確認", fontsize=13.5)
fig.tight_layout(rect=[0, 0.04, 1, 0.95])
save(fig, "fig5b_E_object.png")

# ======== 圖 6：結果總圖 ========
base = tc_pre.mean(-1, keepdims=True) * 0.55 + 0.35
base = np.repeat(base, 3, -1)
res = base.copy()
nocheck = ~s2_ok & (radar_post > 0.25)                   # 光學四期有任一期被雲遮（不含海）
res[nocheck] = res[nocheck] * 0.75 + np.array([0.75, 0.75, 0.8]) * 0.25
ORANGE = (1.0, 0.6, 0.0)
res[ndmg] = RED
res[wet] = BLUE
res[wet & ndmg] = (0.6, 0.0, 0.8)
res[ndi.binary_dilation(facility, iterations=2)] = ORANGE           # 小塊，加粗才看得到
fig, ax = plt.subplots(figsize=(11, 11.5))
ax.imshow(res, extent=EXT)
for k, (la, lo, sz) in ZOOMS.items():
    sl = win(la, lo, sz)
    x0 = W_ + sl[1].start / N * (E_ - W_); x1 = W_ + sl[1].stop / N * (E_ - W_)
    y0 = N_ - sl[0].stop / N * (N_ - S_); y1 = N_ - sl[0].start / N * (N_ - S_)
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ec="#ff9800", lw=1.5, ls="--"))
    ax.text(x0, y1, f" {k}", color="#e65100", fontsize=12, fontweight="bold", va="bottom")
ax.legend(handles=[Patch(color=BLUE, label=f"雷達：明顯變暗、疑似積水（約 {A_WET:.0f} 公頃）"),
                   Patch(color=RED, label=f"光學：植物比往年多掉很多（約 {A_ND:.0f} 公頃）"),
                   Patch(color=(0.6, 0.0, 0.8), label=f"積水＋植物變少都有（約 {A_BOTH:.0f} 公頃）"),
                   Patch(color=(1.0, 0.6, 0.0), label=f"雷達：很亮的人造物變暗、原因待查（約 {A_FAC:.0f} 公頃）"),
                   Patch(color=(0.72, 0.72, 0.75), label="光學被雲遮過、無法比較")],
          loc="upper center", bbox_to_anchor=(0.5, -0.06), ncol=2, fontsize=11, frameon=False)
ax.set_xlabel("東經"); ax.set_ylabel("北緯")
ax.set_title("圖 6　丹娜絲颱風後，衛星標出的疑似受災位置")
save(fig, "fig6_result_map.png")

# ======== 圖 7：數字 ========
items = [("光學四期都沒被雲遮、\n可以比較的農作物", 3164, "#a5d6a7"),
         ("植物變少（只看今年）", 899, "#ffcc80"),
         ("植物比往年多掉很多\n（扣掉每年正常收割）", 480, "#e53935"),
         ("雷達：明顯變暗、疑似積水", round(A_WET), "#1e88e5"),
         ("雷達：很亮的人造物變暗\n（原因待查）", round(A_FAC), "#fb8c00"),
         ("積水＋植物變少都有", round(A_BOTH), "#8e24aa")]
fig, ax = plt.subplots(figsize=(12, 5.6))
ys = np.arange(len(items))[::-1]
for y, (lab, v, c) in zip(ys, items):
    ax.barh(y, v, color=c, height=0.62)
    ax.text(v + 40, y, f"{v:,} 公頃", va="center", fontsize=12, fontweight="bold")
ax.set_xlim(0, 3900)
ax.set_yticks(ys); ax.set_yticklabels([i[0] for i in items], fontsize=11)
ax.set_xticks([]); [s_.set_visible(False) for s_ in ax.spines.values()]
ax.annotate("", xy=(480, ys[2] + 0.05), xytext=(899, ys[1] - 0.05),
            arrowprops=dict(arrowstyle="->", color="#555", lw=1.5))
ax.text(1050, (ys[1] + ys[2]) / 2, "將近一半是每年都會發生的收割，扣掉之後才是颱風造成的", fontsize=10.5,
        color="#555", va="center")
ax.set_title("圖 7　數字一覽（研究區總面積約 25,450 公頃）")
fig.tight_layout()
save(fig, "fig7_numbers.png")

# ======== 互動對比用的成對影像 ========
def to_jpg(arr, name, size=1100):
    im = Image.fromarray((np.clip(arr, 0, 1) * 255).astype("uint8"))
    im = im.resize((size, size), Image.LANCZOS)
    im.save(os.path.join(SLIDE, name), quality=86)


to_jpg(tc_pre, "photo_pre.jpg"); to_jpg(tc_post, "photo_post.jpg")
to_jpg(np.dstack([radar_pre] * 3), "radar_pre.jpg"); to_jpg(np.dstack([radar_post] * 3), "radar_post.jpg")
to_jpg(veg_rgb(nd_pre), "veg_pre.jpg"); to_jpg(veg_rgb(nd_post), "veg_post.jpg")
to_jpg(base, "result_base.jpg"); to_jpg(res, "result_map.jpg")
for k in ("A", "C"):
    sl = win(*ZOOMS[k])
    to_jpg(tc_pre[sl], f"zoom{k}_pre.jpg", 700); to_jpg(tc_post[sl], f"zoom{k}_post.jpg", 700)
sl = win(*ZOOMS["D"])
to_jpg(np.dstack([radar_pre[sl]] * 3), "zoomD_pre.jpg", 700)
to_jpg(np.dstack([radar_post[sl]] * 3), "zoomD_post.jpg", 700)
sl = win(*ZOOMS["E"])
_cm = matplotlib.colormaps["inferno"]
to_jpg(_cm(np.clip((pre_db[-2:].mean(0)[sl] + 6) / 18, 0, 1))[..., :3], "zoomE_pre.jpg", 700)
to_jpg(_cm(np.clip((post_db[sl] + 6) / 18, 0, 1))[..., :3], "zoomE_post.jpg", 700)
_ed = np.load(os.path.join(HERE, "real_data", "solar_E_dates.npz"))
to_jpg(photo(_ed["2025_07_03"]), "zoomE_photo_pre.jpg", 700); to_jpg(photo(_ed["2025_07_23"]), "zoomE_photo_post.jpg", 700)
sl = win(*ZOOMS["B"])
to_jpg(tc_post[sl], "zoomB_photo.jpg", 700); to_jpg(np.dstack([radar_post[sl]] * 3), "zoomB_radar.jpg", 700)
print("完成：", OUT)
