"""
天相星 SkyAide｜衛星影像災前災後比對與 A／B／C 分級：最小可跑範例
=====================================================================

工況：2025 年丹娜絲颱風，嘉義沿海農區（水稻、香蕉、果樹）＋台南沿海魚塭。
資料：本範例用「模擬影像」，格式與真實資料一致：
      - Sentinel-1：VV、VH 後向散射（線性強度，含斑點雜訊），10 米像素
      - Sentinel-1：災前／災後干涉同調性（0–1）
      - Sentinel-2：NDVI（災後部分被颱風雲遮蔽 → NaN）
      - VIIRS 夜間燈光：每日亮度（魚塭停電判斷）
      換成真實影像時，只要把同樣形狀的陣列丟進「二、判讀流程」的函式即可
      （見 fetch_real_s1.py）。

流程（對應技術說明 參、四～七）：
  一、模擬工況影像（地真值已知，才能算精確度）
  二、前處理：Lee 斑點濾波
  三、坵塊化：每個坵塊向內縮 10 米（1 像素）取統計值
  四、判讀：淹水三法投票／倒伏 VH 對數比值／埋沒同調性／NDVI 相對標準分數
  五、作物判釋：簡單規則（看災前時序長相）
  六、損失區間：簡單公式估中間值，左右各加一段誤差範圍
  七、三道關卡分級 A／B／C ＋原因碼
  八、魚塭：溢堤、池水流失、停電、在養證據
  九、驗證指標、圖表、存證報告（含可溯源資料）

刻意用最簡單的規則，不用機器學習、不需要訓練資料；正式系統再換成
技術說明裡的 Transformer 與分位數梯度提升樹。

執行：python skyaide_demo.py        （約 5 秒，輸出在 ./output/）
需要：numpy scipy matplotlib
"""

import json
import os
import hashlib
from dataclasses import dataclass

import numpy as np
from scipy import ndimage as ndi

VERSION = "skyaide-demo-0.1"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

H, W = 240, 240          # 2.4 公里 × 2.4 公里，每像素 10 米
FARM_W = 160             # 左邊 160 欄是農田，右邊是魚塭
CROPS = ["水稻", "香蕉", "果樹"]
N_PRE = 6                # 災前 6 個日期（約 36 天，Sentinel-1 六天再訪）
LOOKS = 4                # 模擬斑點雜訊的視數

# 判讀門檻（技術說明中的起始值）
FLOOD_DIFF_DB = -3.0     # 變遷偵測：災後比災前暗 3 dB
FLOOD_Z = -3.0           # 時序異常：低於災前平均 3 個標準差
LODGE_DB = 2.5           # 倒伏：VH 對數比值絕對值 > 2.5 dB
COH_BURIED = 0.5         # 埋沒：災後同調性 < 0.5 且下降 > 0.3
GATE_A_Q10 = 0.40        # A 級：損失區間第 10 百分位 ≥ 40%
GATE_B_Q90 = 0.10        # B 級：損失區間第 90 百分位 ≤ 10%
MIN_PIX = 5              # 內縮後少於 5 個像素 → 小田，列 C


# =====================================================================
# 一、模擬工況影像
# =====================================================================

def split_parcels(rng, x0, x1, y0, y1, out, max_side=38, min_side=8):
    """遞迴切出長方形坵塊（模擬地籍／農地覆蓋物坵塊）。"""
    w, h = x1 - x0, y1 - y0
    if (w <= max_side and h <= max_side) or (w < 2 * min_side and h < 2 * min_side):
        out.append((x0, x1, y0, y1))
        return
    if (w >= h and w >= 2 * min_side) or h < 2 * min_side:
        c = rng.integers(x0 + min_side, x1 - min_side + 1)
        split_parcels(rng, x0, c, y0, y1, out, max_side, min_side)
        split_parcels(rng, c, x1, y0, y1, out, max_side, min_side)
    else:
        c = rng.integers(y0 + min_side, y1 - min_side + 1)
        split_parcels(rng, x0, x1, y0, c, out, max_side, min_side)
        split_parcels(rng, x0, x1, c, y1, out, max_side, min_side)


def speckle(rng, db):
    """把 dB 值轉成線性強度並加上 Gamma 分佈斑點雜訊（雷達影像的顆粒感）。"""
    lin = 10 ** (db / 10)
    return lin * rng.gamma(LOOKS, 1.0 / LOOKS, size=db.shape)


@dataclass
class Scene:
    parcel: np.ndarray        # 農田坵塊編號（0 = 田埂／農路）
    pond: np.ndarray          # 魚塭編號（0 = 非魚塭）
    vv_pre: np.ndarray        # (N_PRE, H, W) 線性強度
    vh_pre: np.ndarray
    vv_post: np.ndarray       # (H, W)
    vh_post: np.ndarray
    coh_pre: np.ndarray       # 災前兩期同調性
    coh_post: np.ndarray      # 災前－災後同調性
    ndvi_pre: np.ndarray      # (N_PRE, H, W)
    ndvi_post: np.ndarray     # (H, W)，雲遮處為 NaN
    parcels: list             # 每個坵塊的地真值與申報資料
    ponds: list               # 每口魚塭的地真值與申報資料
    night_pre: np.ndarray     # (3 區, 30 天) 夜間燈光
    night_post: np.ndarray    # (3 區, 10 天)
    seed: int
    truth_flood: np.ndarray = None   # 地真值：實際淹水像素（只用於驗證）


def simulate_scene(seed):
    rng = np.random.default_rng(seed)

    # --- 地形：低窪處容易淹水，右上有一條河道（埋沒、流失） ---
    elev = ndi.gaussian_filter(rng.normal(size=(H, W)), 25)
    elev = (elev - elev.min()) / (elev.max() - elev.min())
    yy, xx = np.mgrid[0:H, 0:W]
    river_y = 40 + 15 * np.sin(xx / 30.0 + seed)
    near_river = np.abs(yy - river_y) < 12

    # --- 農田坵塊 ---
    rects = []
    split_parcels(rng, 0, FARM_W, 0, H, rects)
    parcel = np.zeros((H, W), int)
    for i, (x0, x1, y0, y1) in enumerate(rects, start=1):
        parcel[y0 + 1:y1 - 1, x0 + 1:x1 - 1] = i      # 留 2 像素田埂／農路

    # --- 魚塭 ---
    pond = np.zeros((H, W), int)
    pond_boxes = []
    k = 0
    for y0 in range(4, H - 20, 23):
        for x0 in range(FARM_W + 8, W - 17, 18):
            k += 1
            pond[y0:y0 + 20, x0:x0 + 15] = k
            pond_boxes.append((x0, x0 + 15, y0, y0 + 20))

    # --- 背景（田埂、農路、魚塭堤岸） ---
    vv_base = np.full((N_PRE, H, W), -12.0)
    vh_base = np.full((N_PRE, H, W), -19.0)
    nd_base = np.full((N_PRE, H, W), 0.30)
    vv_base[:, :, FARM_W:] = -7.0      # 堤岸：亮線
    vh_base[:, :, FARM_W:] = -14.0
    t = np.linspace(0, 1, N_PRE)[:, None, None]

    parcels = []
    water_level = np.quantile(elev[:, :FARM_W], 0.18)   # 最低的 18% 區域會淹
    flood_px = np.zeros((H, W), bool)
    lodge_px = np.zeros((H, W), bool)
    buried_px = np.zeros((H, W), bool)
    ndvi_drop = np.zeros((H, W))

    for i in range(1, len(rects) + 1):
        m = parcel == i
        crop = int(rng.integers(0, 3))
        # 作物的災前時序特徵（讓作物判釋有東西可學）
        if crop == 0:   # 水稻：生長中，VH 與 NDVI 逐期上升
            vv_base[:, m] = (-13 + 3 * t)[:, :, 0]
            vh_base[:, m] = (-22 + 6 * t)[:, :, 0]
            nd_base[:, m] = (0.40 + 0.40 * t)[:, :, 0]
        elif crop == 1:  # 香蕉：大葉片，穩定且亮
            vv_base[:, m] = -8.0
            vh_base[:, m] = -13.0
            nd_base[:, m] = 0.80
        else:            # 果樹：中等，NDVI 小幅季節變化
            vv_base[:, m] = (-9.5 + 0.5 * np.sin(6 * t))[:, :, 0]
            vh_base[:, m] = (-15 + 0.5 * np.sin(6 * t))[:, :, 0]
            nd_base[:, m] = (0.66 + 0.05 * np.sin(6 * t))[:, :, 0]

        # 災損類型：依地形決定，不是亂數貼標籤
        fl = m & (elev < water_level)
        if near_river[m].mean() > 0.4 and rng.random() < 0.7:
            kind = "埋沒"
            buried_px |= m
            ndvi_drop[m] = 0.55
        elif fl.sum() > 0.05 * m.sum():
            kind = "淹水"
            flood_px |= fl
            ndvi_drop[fl] = 0.45
        elif rng.random() < 0.25:
            kind = "倒伏"
            ys, xs = np.where(m)
            frac = rng.uniform(0.2, 1.0)                # 倒伏佔坵塊比例
            cut = xs.min() + frac * (xs.max() - xs.min() + 1)
            lp = m & (xx < cut)
            lodge_px |= lp
            ndvi_drop[lp] = 0.25
        elif rng.random() < 0.15:
            kind = "輕微"                                # 只有輕微植生下降
            ndvi_drop[m] = rng.uniform(0.03, 0.12)
        else:
            kind = "無"

        parcels.append(dict(id=i, crop=crop, kind=kind, area_ha=m.sum() / 100))

    # 每個坵塊的真實損失率（由像素層級的災害比例產生 + 雜訊）
    for p in parcels:
        m = parcel == p["id"]
        f_fl, f_lo = flood_px[m].mean(), lodge_px[m].mean()
        sens = [1.0, 0.8, 0.6][p["crop"]]          # 水稻最怕淹
        loss = {
            "埋沒": rng.uniform(0.85, 1.0),
            "淹水": 0.10 + 0.85 * f_fl * sens,
            "倒伏": 0.05 + 0.75 * f_lo,
            "輕微": rng.uniform(0.05, 0.30),
            "無": rng.uniform(0.0, 0.06),
        }[p["kind"]]
        p["true_loss"] = float(np.clip(loss + rng.normal(0, 0.04), 0, 1))
        # 申請行為：損失大多會申請；少數未受損也申請；少數受損未申請
        prob = 0.92 if p["true_loss"] >= 0.2 else (0.35 if p["true_loss"] >= 0.1 else 0.06)
        p["applied"] = bool(rng.random() < prob)
        p["declared_crop"] = p["crop"] if rng.random() > 0.05 else int((p["crop"] + 1) % 3)
        p["misregistered"] = bool(rng.random() < 0.05)    # 圖解地籍區、對位誤差大
        p["rain_mm"] = float(250 + 200 * (1 - elev[m].mean()) + rng.normal(0, 25))

    # --- 魚塭 ---
    ponds = []
    zone_of = lambda x0: min(2, (x0 - FARM_W - 8) // 27)   # 三個供電區
    outage_days = [0, 2, 5]
    vv_post_extra = np.zeros((H, W))                       # 災後魚塭變化的 dB 增量
    pond_water_pre = np.zeros((H, W), bool)
    for j, (x0, x1, y0, y1) in enumerate(pond_boxes, start=1):
        m = pond == j
        in_use = rng.random() < 0.85
        has_water = in_use or rng.random() < 0.5
        if has_water:
            vv_base[:, m] = -22.0
            vh_base[:, m] = -28.0
            nd_base[:, m] = -0.20
            pond_water_pre |= m
        else:                                   # 廢棄乾池：泥地
            vv_base[:, m] = -13.0
            vh_base[:, m] = -21.0
            nd_base[:, m] = 0.15
        r = rng.random()
        damage = "溢堤" if (r < 0.25 and has_water) else ("池水流失" if (r < 0.35 and has_water) else "無")
        overflow_frac = rng.uniform(0.85, 1.0) if damage == "溢堤" else (rng.uniform(0.2, 0.5) if rng.random() < 0.15 else 0.0)
        z = zone_of(x0)
        died = in_use and (damage != "無" or (outage_days[z] >= 3 and rng.random() < 0.5))
        ponds.append(dict(
            id=j, in_use=in_use, damage=damage, overflow_frac=overflow_frac,
            zone=z, truly_damaged=bool(died),
            aerator_seen=bool(rng.random() < (0.9 if in_use else 0.03)),   # 模擬福衛八號水車偵測
            stocking_declared=bool(in_use and rng.random() < 0.9),         # 放養申報
            applied=bool(rng.random() < (0.9 if died else (0.5 if in_use and outage_days[z] else 0.05))),
            box=(x0, x1, y0, y1),
        ))

    # --- 產生災前影像（含斑點雜訊） ---
    vv_pre = speckle(rng, vv_base + rng.normal(0, 0.3, size=(N_PRE, 1, 1)))
    vh_pre = speckle(rng, vh_base + rng.normal(0, 0.3, size=(N_PRE, 1, 1)))
    ndvi_pre = nd_base + rng.normal(0, 0.03, size=nd_base.shape)

    # --- 災後影像 ---
    season = -0.03                                     # 季節性普遍下降（應被相對分數抵銷）
    vv_post_db = vv_base[-1].copy()
    vh_post_db = vh_base[-1].copy()
    vv_post_db[flood_px] = -21.0                      # 淹水：鏡面反射，變很暗
    vh_post_db[flood_px] = -27.0
    crop_map = np.full((H, W), -1)
    for p in parcels:
        crop_map[parcel == p["id"]] = p["crop"]
    vh_post_db[lodge_px & (crop_map == 0)] += 4.0     # 水稻倒伏：VH 變亮
    vh_post_db[lodge_px & (crop_map != 0)] -= 4.0     # 香蕉／果樹倒伏：冠層崩塌，VH 變暗
    vv_post_db[buried_px] = -10.0                     # 埋沒：泥沙裸地
    vh_post_db[buried_px] = -18.0

    for pd_ in ponds:
        x0, x1, y0, y1 = pd_["box"]
        m = pond == pd_["id"]
        if pd_["damage"] == "池水流失":               # 池水少 50–90%，露出泥底
            keep = rng.uniform(0.1, 0.5)
            cut = y0 + int(keep * (y1 - y0))
            dry = m & (yy >= cut)
            vv_post_db[dry] = -13.0
            vh_post_db[dry] = -21.0
        if pd_["overflow_frac"] > 0:                  # 堤岸被淹：亮線變暗
            ring = ndi.binary_dilation(m, iterations=3) & ~m & (pond == 0) & (xx >= FARM_W)
            ys, xs = np.where(ring)
            sel = rng.random(len(ys)) < pd_["overflow_frac"]
            flood_px[ys[sel], xs[sel]] = True
            vv_post_db[ys[sel], xs[sel]] = -21.0
            vh_post_db[ys[sel], xs[sel]] = -27.0

    vv_post = speckle(rng, vv_post_db)
    vh_post = speckle(rng, vh_post_db)

    # 同調性：植生約 0.6；水面很低；埋沒、淹水處下降
    coh_pre = np.clip(rng.normal(0.62, 0.08, (H, W)), 0, 1)
    coh_pre[pond_water_pre] = np.clip(rng.normal(0.15, 0.05, pond_water_pre.sum()), 0, 1)
    coh_post = coh_pre * np.clip(rng.normal(0.95, 0.05, (H, W)), 0, 1)
    low = buried_px | flood_px
    coh_post[low] = np.clip(rng.normal(0.22, 0.07, low.sum()), 0, 1)

    # Sentinel-2：災後 NDVI，左下有颱風殘雲
    ndvi_post = nd_base[-1] - ndvi_drop + season + rng.normal(0, 0.03, (H, W))
    cloud = ndi.gaussian_filter(rng.normal(size=(H, W)), 20)
    cloud = cloud > np.quantile(cloud, 0.70)          # 約 30% 被雲遮
    ndvi_post[cloud] = np.nan

    # VIIRS 夜間燈光：三個供電區，停電天數 0／2／5
    night_pre = rng.normal(20, 1.5, (3, 30))
    night_post = rng.normal(20, 1.5, (3, 10))
    for z, d in enumerate(outage_days):
        night_post[z, :d] = rng.normal(4, 1, d)

    return Scene(parcel, pond, vv_pre, vh_pre, vv_post, vh_post, coh_pre, coh_post,
                 ndvi_pre, ndvi_post, parcels, ponds, night_pre, night_post, seed, flood_px)


# =====================================================================
# 二、前處理：Lee 斑點濾波
# =====================================================================

def lee_filter(img, size=5, looks=LOOKS):
    """經典 Lee 濾波：平坦處取平均去雜訊，邊緣處保留原值。輸入為線性強度。"""
    mean = ndi.uniform_filter(img, size)
    sq = ndi.uniform_filter(img ** 2, size)
    var = np.maximum(sq - mean ** 2, 1e-12)
    cu2 = 1.0 / looks
    var_x = np.maximum((var - mean ** 2 * cu2) / (1 + cu2), 0)
    k = var_x / var
    return mean + k * (img - mean)


def to_db(lin):
    return 10 * np.log10(np.maximum(lin, 1e-6))


# =====================================================================
# 三、坵塊化：向內縮 10 米（1 像素），避免田埂與鄰田的混合像素
# =====================================================================

def inset_mask(labels, iterations=1):
    """回傳內縮後的標籤圖：像素周圍 3×3 都屬同一坵塊才保留。"""
    out = labels.copy()
    for _ in range(iterations):
        mx = ndi.maximum_filter(out, 3)
        mn = ndi.minimum_filter(out, 3)
        out = np.where((mx == mn), out, 0)
    return out


# =====================================================================
# 四、判讀
# =====================================================================

def otsu(values, bins=256):
    """Otsu 自動門檻：把直方圖切成兩群，使群間變異最大。"""
    v = values[np.isfinite(values)]
    hist, edges = np.histogram(v, bins=bins)
    c = (edges[:-1] + edges[1:]) / 2
    w0 = np.cumsum(hist)
    w1 = w0[-1] - w0
    m0 = np.cumsum(hist * c) / np.maximum(w0, 1)
    m1 = (np.sum(hist * c) - np.cumsum(hist * c)) / np.maximum(w1, 1)
    return c[np.argmax(w0 * w1 * (m0 - m1) ** 2)]


def flood_vote(vv_pre_db, vv_post_db, max_thr_db=None):
    """
    淹水三法投票（技術說明 參、五 ②；參考歐盟 GFM 的多演算法合併）。
      法 1：Otsu 門檻 —— 災後 VV 低於自動門檻 = 水
      法 2：變遷偵測 —— 災後比災前平均暗 3 dB 以上
      法 3：時序異常 —— 低於災前時序平均 3 個標準差
    （正式系統的第三法為微調 Prithvi；此範例以時序異常＋變遷偵測示範投票機制）
    災前就是水的地方（魚塭、埤塘）不算淹水。至少兩法同意才算淹水。
    """
    pre_mean = vv_pre_db.mean(0)
    pre_std = np.maximum(vv_pre_db.std(0), 0.5)
    thr = otsu(vv_post_db)
    if max_thr_db is not None:          # 真實影像：Otsu 可能被海面拉高，水體門檻不超過此值
        thr = min(thr, max_thr_db)
    m1 = vv_post_db < thr
    m2 = (vv_post_db - vv_pre_db[-2:].mean(0)) < FLOOD_DIFF_DB   # 與災前最近兩期比
    m3 = (vv_post_db - pre_mean) / pre_std < FLOOD_Z
    perm_water = pre_mean < thr
    votes = m1.astype(int) + m2 + m3
    flood = (votes >= 2) & ~perm_water
    return flood, dict(otsu=m1 & ~perm_water, change=m2 & ~perm_water,
                       anomaly=m3 & ~perm_water, threshold_db=float(thr), perm_water=perm_water)


def lodging_map(vh_pre_db, vh_post_db, flood):
    """倒伏：VH 災後／災前對數比值（dB 差）絕對值超過門檻，再以 3×3 中位數平滑（代替隱馬可夫隨機場）。"""
    ratio = vh_post_db - vh_pre_db[-2:].mean(0)     # 用災前最後兩期當基準，避免把作物正常生長當成變化
    raw = (np.abs(ratio) > LODGE_DB) & ~flood
    return ndi.median_filter(raw.astype(np.uint8), 3).astype(bool), ratio


def buried_map(coh_pre, coh_post, flood):
    """埋沒、流失：同調性降到 0.5 以下且下降超過 0.3；淹水也會讓同調性下降，所以排除淹水像素。"""
    return (coh_post < COH_BURIED) & ((coh_pre - coh_post) > 0.3) & ~flood


def parcel_features(sc, flood, lodge, buried, inset):
    """把像素結果彙整到每個坵塊（地號時序特徵表的一列）。"""
    dndvi = sc.ndvi_post - sc.ndvi_pre[-1]
    vv_db_pre = to_db(np.stack([lee_filter(x) for x in sc.vv_pre]))
    vh_db_pre = to_db(np.stack([lee_filter(x) for x in sc.vh_pre]))
    rows = []
    for p in sc.parcels:
        m = inset == p["id"]
        n = int(m.sum())
        r = dict(id=p["id"], n_pix=n, area_ha=p["area_ha"], rain_mm=p["rain_mm"],
                 declared_crop=p["declared_crop"], applied=p["applied"],
                 misregistered=p["misregistered"])
        if n == 0:
            m = sc.parcel == p["id"]           # 太小，內縮後沒剩，只好用整塊（之後會被關卡 1 擋下）
        r["flood_frac"] = float(flood[m].mean())
        r["lodge_frac"] = float(lodge[m].mean())
        r["buried_frac"] = float(buried[m].mean())
        cl = np.isnan(dndvi[m])
        r["cloud_frac"] = float(cl.mean())
        r["dndvi"] = float(np.nanmean(dndvi[m])) if (~cl).sum() >= 3 else np.nan
        # 作物判釋用的災前時序特徵
        for k in range(N_PRE):
            r[f"vv{k}"] = float(vv_db_pre[k][m].mean())
            r[f"vh{k}"] = float(vh_db_pre[k][m].mean())
            r[f"nd{k}"] = float(sc.ndvi_pre[k][m].mean())
        rows.append(r)
    return rows


def add_ndvi_z(rows, crop_key):
    """
    植生受損：NDVI 災後變化，相對於「同作物、雷達未見變化」的鄰近坵塊，算穩健標準分數（中位數／MAD）。
    參考組只放雷達看起來沒事的田，否則受損田會把基準拉低、把離散度撐大，訊號就被稀釋了。
    季節性的普遍下降（全部田都降一點）會被這個相對分數抵銷。
    """
    for c in range(3):
        ref = np.array([r["dndvi"] for r in rows if r[crop_key] == c and np.isfinite(r["dndvi"])
                        and max(r["flood_frac"], r["lodge_frac"], r["buried_frac"]) < 0.1])
        if len(ref) < 3:
            ref = np.array([r["dndvi"] for r in rows if np.isfinite(r["dndvi"])])
        med = np.median(ref)
        mad = max(1.4826 * np.median(np.abs(ref - med)), 0.02)
        for r in rows:
            if r[crop_key] == c:
                r["ndvi_z"] = (r["dndvi"] - med) / mad if np.isfinite(r["dndvi"]) else np.nan


# =====================================================================
# 五、作物判釋（簡單規則）＆ 六、損失區間（簡單公式）
# =====================================================================

def analyse(sc):
    """單一場景：前處理 → 判讀 → 坵塊特徵。回傳像素圖與坵塊表。"""
    vv_pre_db = to_db(np.stack([lee_filter(x) for x in sc.vv_pre]))
    vh_pre_db = to_db(np.stack([lee_filter(x) for x in sc.vh_pre]))
    vv_post_db = to_db(lee_filter(sc.vv_post))
    vh_post_db = to_db(lee_filter(sc.vh_post))
    flood, fl_detail = flood_vote(vv_pre_db, vv_post_db)
    lodge, vh_ratio = lodging_map(vh_pre_db, vh_post_db, flood)
    buried = buried_map(sc.coh_pre, sc.coh_post, flood)
    inset = inset_mask(sc.parcel)
    rows = parcel_features(sc, flood, lodge, buried, inset)
    maps = dict(vv_pre_db=vv_pre_db, vv_post_db=vv_post_db, flood=flood, lodge=lodge,
                buried=buried, vh_ratio=vh_ratio, inset=inset, **fl_detail)
    return maps, rows


def guess_crop(r):
    """
    看災前 6 期時序的長相猜作物：
      - NDVI 從第 1 期到第 6 期上升超過 0.2 → 正在長的「水稻」
      - 否則 VV 很亮（平均 > −9 dB，大葉片）→「香蕉」
      - 其他 →「果樹」
    """
    if r[f"nd{N_PRE - 1}"] - r["nd0"] > 0.2:
        return 0
    if np.mean([r[f"vv{k}"] for k in range(N_PRE)]) > -9:
        return 1
    return 2


def estimate_loss(r):
    """
    損失率中間值：取三種雷達訊號裡最嚴重的那一個（淹水、倒伏、埋沒的像素比例 × 權重）。
    權重的意思：淹水的水稻約 95% 會損失、香蕉 80%、果樹 65%；倒伏約 75%；埋沒約 95%。
    雷達沒看到任何東西時，改用 NDVI：每低 1 個標準差約多 2% 損失（上限 30%）。
    誤差範圍：雷達有訊號 ±15%；雷達沒訊號（只靠 NDVI 或根本沒變化）±5%；
              光學被雲遮一半以上時看不到植生，再加寬 5%。
    """
    flood_w = [0.95, 0.80, 0.65][r["pred_crop"]]
    mid = max(0.05 + flood_w * r["flood_frac"],
              0.05 + 0.75 * r["lodge_frac"],
              0.95 * r["buried_frac"])
    half = 0.15
    if r["flood_frac"] + r["lodge_frac"] + r["buried_frac"] < 0.05:
        z = r["ndvi_z"] if np.isfinite(r["ndvi_z"]) else 0.0
        mid = max(0.02, min(0.30, -0.02 * z))
        half = 0.05
    if r["cloud_frac"] >= 0.5:
        half += 0.05
    clip = lambda v: float(np.clip(v, 0, 1))
    return clip(mid - half), clip(mid), clip(mid + half)


# =====================================================================
# 七、三道關卡
# =====================================================================

def three_gates(r):
    """回傳 (等級, 原因碼清單)。任一關未過即列 C。"""
    reasons = []
    # 關卡 1：影像信心
    if r["n_pix"] < MIN_PIX:
        reasons.append("C1 小田：內縮後像素不足，需福衛八號或到場")
    if r["misregistered"]:
        reasons.append("C1 對位不確定：圖解地籍區")
    radar_strong = r["flood_frac"] >= 0.5 or r["buried_frac"] >= 0.5
    radar_damage = r["flood_frac"] > 0.2 or r["lodge_frac"] > 0.2 or r["buried_frac"] > 0.2
    if np.isfinite(r["ndvi_z"]) and r["cloud_frac"] < 0.5:
        optical_damage = r["ndvi_z"] < -3
        if radar_damage != optical_damage and not radar_strong:
            reasons.append("C1 雷達與光學結論不一致")
    elif not radar_strong:
        reasons.append("C1 光學被雲遮，雷達訊號不夠強")

    # 關卡 2：遠離 20% 門檻
    cand = None
    if r["q10"] >= GATE_A_Q10:
        cand = "A"
    elif r["q90"] <= GATE_B_Q90:
        cand = "B"
    else:
        reasons.append("C2 損失區間跨越門檻附近")

    # 關卡 3：與申報一致
    if r["applied"] and r["pred_crop"] != r["declared_crop"]:
        reasons.append("C3 作物與申報不符")
    if cand == "B" and r["applied"]:
        reasons.append("C3 農民申請但衛星未見變化")

    if reasons:
        return "C", reasons
    return cand, ["通過三道關卡"]


def classify_parcels(rows):
    for r in rows:
        r["pred_crop"] = guess_crop(r)
    add_ndvi_z(rows, "pred_crop")
    for r in rows:
        r["q10"], r["q50"], r["q90"] = estimate_loss(r)
        r["grade"], r["reasons"] = three_gates(r)


# =====================================================================
# 八、魚塭
# =====================================================================

def classify_ponds(sc, maps):
    flood = maps["flood"]
    vv_pre_db, vv_post_db = maps["vv_pre_db"], maps["vv_post_db"]
    water_thr = maps["threshold_db"]
    xx = np.arange(W)[None, :].repeat(H, 0)
    # 停電：夜間燈光低於災前 30 天中位數的一半，算連續天數
    base = np.median(sc.night_pre, axis=1)
    outage = [(sc.night_post[z] < base[z] / 2).astype(int) for z in range(3)]
    outage_days = [int(np.argmin(np.append(o, 0))) for o in outage]   # 從第 1 天起連續停電天數

    rows = []
    for p in sc.ponds:
        m = sc.pond == p["id"]
        core = ndi.binary_erosion(m, iterations=2)
        ring = ndi.binary_dilation(m, iterations=3) & ~m & (sc.pond == 0) & (xx >= FARM_W)
        water_pre = float((vv_pre_db.mean(0)[core] < water_thr).mean())
        water_post = float((vv_post_db[core] < water_thr).mean())
        bank_flooded = float(flood[ring].mean())
        water_loss = 1 - water_post / water_pre if water_pre > 0.5 else 0.0
        strong_in_use = water_pre > 0.7 and p["aerator_seen"] and p["stocking_declared"]
        od = outage_days[p["zone"]]

        signals = []
        if bank_flooded >= 0.8:
            signals.append("整池溢堤")
        elif bank_flooded >= 0.2:
            signals.append(f"部分溢堤 {bank_flooded:.0%}")
        if water_loss >= 0.5:
            signals.append(f"池水流失 {water_loss:.0%}")
        if od > 0:
            signals.append(f"停電 {od} 天")

        direct = bank_flooded >= 0.8 or water_loss >= 0.5
        if strong_in_use and direct and p["applied"]:
            grade, why = "A", "災前在養（水面＋水車＋放養申報）且" + "、".join(s for s in signals if "停電" not in s)
        elif not p["applied"] and not signals:
            grade, why = "B", "未申請、無任何變化"
        else:
            grade = "C"
            why = "間接訊號，需到場確認" if signals else "申請但衛星未見變化"
            if not strong_in_use:
                why = "缺在養強證據；" + why
        priority = od * 10 + bank_flooded * 50 + water_loss * 30
        rows.append(dict(id=p["id"], grade=grade, reason=why, signals=signals,
                         water_pre=water_pre, water_loss=water_loss, bank_flooded=bank_flooded,
                         outage_days=od, priority=priority, applied=p["applied"],
                         truly_damaged=p["truly_damaged"], in_use=p["in_use"]))
    return rows, outage_days


# =====================================================================
# 九、驗證、圖表、存證報告
# =====================================================================

def evaluate(rows, ponds):
    def prec(grade, ok):
        sel = [r for r in rows if r["grade"] == grade]
        return (sum(ok(r) for r in sel) / len(sel) if sel else float("nan")), len(sel)
    a_prec, nA = prec("A", lambda r: r["true_loss"] >= 0.2)
    b_prec, nB = prec("B", lambda r: r["true_loss"] < 0.2)
    applied = [r for r in rows if r["applied"]]
    c_rate = sum(r["grade"] == "C" for r in applied) / len(applied)
    cover = np.mean([r["q10"] <= r["true_loss"] <= r["q90"] for r in rows])
    mae = np.mean([abs(r["q50"] - r["true_loss"]) for r in rows])
    crop_acc = np.mean([r["pred_crop"] == r["crop"] for r in rows])
    pa = [p for p in ponds if p["grade"] == "A"]
    pond_a_prec = sum(p["truly_damaged"] for p in pa) / len(pa) if pa else float("nan")
    return dict(
        農田坵塊數=len(rows), 申請件數=len(applied),
        A件數=nA, B件數=nB, C件數=sum(r["grade"] == "C" for r in rows),
        A級精確度=a_prec, B級精確度=b_prec, 申請案件C級比例=c_rate,
        區間覆蓋率=float(cover), 中位數絕對誤差=float(mae), 作物判釋準確率=float(crop_acc),
        魚塭數=len(ponds), 魚塭A件數=len(pa), 魚塭A級精確度=pond_a_prec,
        魚塭C件數=sum(p["grade"] == "C" for p in ponds),
        魚塭申請件數=sum(p["applied"] for p in ponds),
        申請魚塭C級比例=(sum(p["grade"] == "C" for p in ponds if p["applied"]) /
                    max(1, sum(p["applied"] for p in ponds))),
    )


def make_figures(sc, maps, rows, ponds, metrics):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch
    for f in ["Noto Sans CJK TC", "PingFang TC", "Heiti TC", "Microsoft JhengHei", "Arial Unicode MS"]:
        try:
            from matplotlib import font_manager
            font_manager.findfont(f, fallback_to_default=False)
            plt.rcParams["font.family"] = f
            break
        except Exception:
            continue
    plt.rcParams["axes.unicode_minus"] = False
    ext = [0, W * 10 / 1000, H * 10 / 1000, 0]   # 公里

    def outline(ax, lab, color="w", lw=0.4):
        ax.contour(np.arange(W) / 100, np.arange(H) / 100, (lab > 0).astype(float), [0.5], colors=color, linewidths=lw)

    # 圖 D1：災前災後影像
    fig, axs = plt.subplots(1, 4, figsize=(16, 4.4))
    axs[0].imshow(maps["vv_pre_db"].mean(0), cmap="gray", vmin=-24, vmax=-4, extent=ext)
    axs[0].set_title("① 災前 Sentinel-1 VV（6 期平均，dB）")
    axs[1].imshow(maps["vv_post_db"], cmap="gray", vmin=-24, vmax=-4, extent=ext)
    axs[1].set_title("② 災後 Sentinel-1 VV（dB）")
    nd = np.where(np.isnan(sc.ndvi_post), np.nan, sc.ndvi_post)
    im = axs[2].imshow(nd, cmap="RdYlGn", vmin=-0.2, vmax=0.9, extent=ext)
    axs[2].set_facecolor("#cfd8dc")
    axs[2].set_title("③ 災後 Sentinel-2 NDVI（灰＝雲遮）")
    plt.colorbar(im, ax=axs[2], fraction=0.046)
    axs[3].imshow(sc.coh_post, cmap="magma", vmin=0, vmax=1, extent=ext)
    axs[3].set_title("④ 災前－災後同調性")
    for ax in axs:
        ax.set_xlabel("公里")
    fig.suptitle("圖 D1　模擬工況影像：丹娜絲颱風後的嘉義農區（左 1.6 公里）與台南魚塭（右）", fontsize=12)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "figD1_images.png"), dpi=130, bbox_inches="tight")
    plt.close(fig)

    # 圖 D2：淹水三法投票
    fig, axs = plt.subplots(1, 4, figsize=(16, 4.4))
    for ax, key, title in zip(axs, ["otsu", "change", "anomaly"],
                              [f"法 1 Otsu 門檻（{maps['threshold_db']:.1f} dB）", "法 2 變遷偵測（暗 3 dB）", "法 3 時序異常（−3σ）"]):
        ax.imshow(maps[key], cmap="Blues", extent=ext)
        ax.set_title(title)
    votes = maps["otsu"].astype(int) + maps["change"] + maps["anomaly"]
    axs[3].imshow(np.where(maps["flood"], 2, np.where(votes == 1, 1, 0)),
                  cmap=ListedColormap(["#ffffff", "#ffcc80", "#1565c0"]), extent=ext)
    axs[3].set_title("投票結果：深藍＝≥2 法同意；橘＝只有 1 法")
    for ax in axs:
        outline(ax, sc.parcel, "#9e9e9e")
        ax.set_xlabel("公里")
    fig.suptitle("圖 D2　淹水三法投票：單一方法的零星誤判（橘點）在投票後被濾掉", fontsize=12)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "figD2_flood_vote.png"), dpi=130, bbox_inches="tight")
    plt.close(fig)

    # 圖 D3：分級結果地圖
    grade_map = np.zeros((H, W))
    code = {"A": 1, "B": 2, "C": 3}
    for r in rows:
        grade_map[sc.parcel == r["id"]] = code[r["grade"]]
    for p in ponds:
        grade_map[sc.pond == p["id"]] = code[p["grade"]]
    fig, axs = plt.subplots(1, 2, figsize=(13, 7))
    kind_map = np.zeros((H, W))
    kinds = ["無", "輕微", "倒伏", "淹水", "埋沒"]
    for p in sc.parcels:
        kind_map[sc.parcel == p["id"]] = kinds.index(p["kind"]) + 1
    for p in sc.ponds:
        kind_map[sc.pond == p["id"]] = 6 if p["truly_damaged"] else 1
    cm_k = ListedColormap(["#eceff1", "#c8e6c9", "#fff59d", "#ffb74d", "#64b5f6", "#8d6e63", "#7e57c2"])
    axs[0].imshow(kind_map, cmap=cm_k, vmin=0, vmax=6, extent=ext, interpolation="nearest")
    axs[0].set_title("地真值（模擬時設定的災損類型）")
    axs[0].legend(handles=[Patch(color=cm_k(i + 1), label=k) for i, k in enumerate(kinds)] +
                  [Patch(color=cm_k(6), label="魚塭實際受災")],
                  loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=6, fontsize=9, frameon=False)
    cm_g = ListedColormap(["#eceff1", "#c62828", "#2e7d32", "#f9a825"])
    axs[1].imshow(grade_map, cmap=cm_g, vmin=0, vmax=3, extent=ext, interpolation="nearest")
    for r in rows:
        if r["grade"] == "C" and r["applied"]:
            ys, xs = np.where(sc.parcel == r["id"])
            axs[1].text(xs.mean() / 100, ys.mean() / 100, "申", ha="center", va="center", fontsize=6)
    for p in ponds:
        if p["grade"] == "C" and p["applied"]:
            ys, xs = np.where(sc.pond == p["id"])
            axs[1].text(xs.mean() / 100, ys.mean() / 100, "申", ha="center", va="center", fontsize=6)
    nB = metrics["B件數"] + sum(p["grade"] == "B" for p in ponds)
    axs[1].set_title("天相星分級（C 級上標「申」＝有申請，公所需到場）")
    axs[1].legend(handles=[Patch(color=cm_g(1), label=f"A 受損已確認（{metrics['A件數'] + metrics['魚塭A件數']}）"),
                           Patch(color=cm_g(2), label=f"B 未見受損（{nB}）"),
                           Patch(color=cm_g(3), label=f"C 需到場確認（{metrics['C件數'] + metrics['魚塭C件數']}）")],
                  loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=3, fontsize=9, frameon=False)
    for ax in axs:
        ax.set_xlabel("公里")
    fig.suptitle("圖 D3　地真值與分級結果對照", fontsize=12)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "figD3_grades.png"), dpi=130, bbox_inches="tight")
    plt.close(fig)

    # 圖 D4：損失區間 vs 真實損失
    fig, ax = plt.subplots(figsize=(7.5, 6))
    colors = {"A": "#c62828", "B": "#2e7d32", "C": "#f9a825"}
    for g in "ABC":
        sel = [r for r in rows if r["grade"] == g]
        if not sel:
            continue
        t = np.array([r["true_loss"] for r in sel])
        md = np.array([r["q50"] for r in sel])
        lo = md - np.array([r["q10"] for r in sel])
        hi = np.array([r["q90"] for r in sel]) - md
        ax.errorbar(t, md, yerr=[lo, hi], fmt="o", ms=4, color=colors[g], ecolor=colors[g],
                    alpha=0.75, elinewidth=1, label=f"{g} 級（{len(sel)}）")
    ax.plot([0, 1], [0, 1], "k--", lw=0.8)
    ax.axvline(0.2, color="gray", lw=0.8, ls=":")
    ax.axhline(0.4, color="#c62828", lw=0.6, ls=":")
    ax.axhline(0.1, color="#2e7d32", lw=0.6, ls=":")
    ax.text(0.205, 0.97, "救助門檻 20%", fontsize=8, color="gray", va="top")
    ax.set_xlabel("真實損失率（模擬地真值）")
    ax.set_ylabel("預測損失率（點＝第 50 百分位，線＝第 10–90 百分位）")
    ax.set_title(f"圖 D4　損失區間預測｜覆蓋率 {metrics['區間覆蓋率']:.0%}、中位數誤差 {metrics['中位數絕對誤差']:.2f}")
    ax.legend(loc="upper left", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "figD4_loss_interval.png"), dpi=130, bbox_inches="tight")
    plt.close(fig)


LOSS_KEYS = ["flood_frac", "lodge_frac", "buried_frac", "ndvi_z", "cloud_frac", "pred_crop"]


def evidence_report(sc, r, maps):
    """一筆 A 級坵塊的存證報告，附可溯源資料（STAC／PROV 精神；影像編號為模擬值）。"""
    crop = CROPS[r["pred_crop"]]
    # 主要災害證據：只列有訊號的項目，附白話說明（比例與標準分數尺度不同，不直接比大小）
    evidence = []
    if r["flood_frac"] > 0.05:
        evidence.append(f"雷達淹水投票：{r['flood_frac']:.0%} 的像素至少兩法判為淹水")
    if r["lodge_frac"] > 0.05:
        evidence.append(f"雷達 VH 對數比值：{r['lodge_frac']:.0%} 的像素變化超過 {LODGE_DB} dB（倒伏）")
    if r["buried_frac"] > 0.05:
        evidence.append(f"干涉同調性：{r['buried_frac']:.0%} 的像素降到 {COH_BURIED} 以下（埋沒／流失）")
    if np.isfinite(r["ndvi_z"]):
        evidence.append(f"Sentinel-2 NDVI：比同作物未受災田低 {abs(r['ndvi_z']):.1f} 個標準差"
                        f"（僅用未被雲遮的 {1 - r['cloud_frac']:.0%} 面積）")
    else:
        evidence.append("Sentinel-2 被雲遮，本筆僅依雷達判定")
    params = dict(lee_size=5, inset_m=10, flood_diff_db=FLOOD_DIFF_DB, flood_z=FLOOD_Z,
                  otsu_db=round(maps["threshold_db"], 2), lodge_db=LODGE_DB,
                  coh_buried=COH_BURIED, gate_a_q10=GATE_A_Q10, gate_b_q90=GATE_B_Q90)
    report = {
        "報告編號": f"SKY-SIM-{sc.seed}-{r['id']:04d}",
        "地號／坵塊": {"坵塊編號": r["id"], "面積_公頃": round(r["area_ha"], 2), "內縮後像素": r["n_pix"]},
        "生產事實": {"判釋作物": crop,
                   "申報作物": CROPS[r["declared_crop"]], "依據": "災前 6 期 Sentinel-1 VV/VH ＋ Sentinel-2 NDVI 時序"},
        "損失": {"損失區間_第10百分位": round(r["q10"], 2), "第50百分位": round(r["q50"], 2),
               "第90百分位": round(r["q90"], 2), "判定": r["grade"], "原因": r["reasons"]},
        "主要災害證據": evidence,
        "可溯源資料": {
            "原始影像": [
                {"衛星": "Sentinel-1", "影像編號": f"SIM-S1-PRE-{k}", "取像": f"災前第 {N_PRE - k} 期"} for k in range(N_PRE)
            ] + [{"衛星": "Sentinel-1", "影像編號": "SIM-S1-POST", "取像": "災後第 1 期"},
                 {"衛星": "Sentinel-2", "影像編號": "SIM-S2-POST", "雲遮比例": round(r["cloud_frac"], 2)}],
            "處理過程": {"程式版本": VERSION, "參數": params},
            "判讀結果": {"模型": "規則版 guess_crop／estimate_loss",
                       "輸入特徵": {k: (round(float(r[k]), 4) if np.isfinite(r[k]) else None) for k in LOSS_KEYS}},
            "人工處理": None,
        },
    }
    body = json.dumps(report, ensure_ascii=False, sort_keys=True)
    report["可溯源資料"]["報告雜湊_SHA256"] = hashlib.sha256(body.encode()).hexdigest()
    return report


def main():
    os.makedirs(OUT, exist_ok=True)
    print("1/4 模擬測試工況（丹娜絲：嘉義農區＋台南魚塭）並判讀 …")
    sc = simulate_scene(42)
    maps, rows = analyse(sc)
    for r, p in zip(rows, sc.parcels):
        r["true_loss"], r["crop"], r["kind"] = p["true_loss"], p["crop"], p["kind"]

    print("2/4 損失區間與三道關卡分級 …")
    classify_parcels(rows)
    pond_rows, outage_days = classify_ponds(sc, maps)

    print("3/4 驗證指標 …")
    m = evaluate(rows, pond_rows)
    for k, v in m.items():
        print(f"    {k}: {v:.3f}" if isinstance(v, float) else f"    {k}: {v}")

    print("4/4 輸出圖表、坵塊表、存證報告 …")
    make_figures(sc, maps, rows, pond_rows, m)
    import csv
    with open(os.path.join(OUT, "parcels.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["坵塊", "面積公頃", "真實災損類型", "真實損失", "申請", "申報作物", "判釋作物",
                    "淹水比例", "倒伏比例", "埋沒比例", "NDVI相對分數", "雲遮比例",
                    "q10", "q50", "q90", "等級", "原因碼"])
        for r in rows:
            w.writerow([r["id"], round(r["area_ha"], 2), r["kind"], round(r["true_loss"], 3), r["applied"],
                        CROPS[r["declared_crop"]], CROPS[r["pred_crop"]],
                        round(r["flood_frac"], 3), round(r["lodge_frac"], 3), round(r["buried_frac"], 3),
                        round(r["ndvi_z"], 2) if np.isfinite(r["ndvi_z"]) else "", round(r["cloud_frac"], 2),
                        round(r["q10"], 3), round(r["q50"], 3), round(r["q90"], 3), r["grade"], "；".join(r["reasons"])])
    with open(os.path.join(OUT, "ponds.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["魚塭", "等級", "說明", "訊號", "災前水面比例", "池水流失", "堤岸被淹比例",
                    "停電天數", "現勘優先分數", "申請", "實際在養", "實際受災"])
        for p in sorted(pond_rows, key=lambda p: -p["priority"]):
            w.writerow([p["id"], p["grade"], p["reason"], "、".join(p["signals"]), round(p["water_pre"], 2),
                        round(p["water_loss"], 2), round(p["bank_flooded"], 2), p["outage_days"],
                        round(p["priority"], 1), p["applied"], p["in_use"], p["truly_damaged"]])
    best = max((r for r in rows if r["grade"] == "A"), key=lambda r: r["q10"], default=None)
    if best:
        with open(os.path.join(OUT, "evidence_report_example.json"), "w", encoding="utf-8") as f:
            json.dump(evidence_report(sc, best, maps), f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(dict(m, 停電天數_三區=outage_days), f, ensure_ascii=False, indent=2)
    print(f"完成，輸出在 {OUT}")


if __name__ == "__main__":
    main()
