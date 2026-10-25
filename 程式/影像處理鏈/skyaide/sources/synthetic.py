"""
模擬資料來源：3 × 3 公里、每像素 10 米的虛構農區，地真值已知。

  左側 2/3：平地農田（水稻、香蕉、麻竹筍、木瓜，夾防風林與建物），一條河穿過
  右上：山坡竹林（陡坡，有雷達陰影與疊置）
  右下：魚塭區

產出的是「原始」產品：雷達是未做地形正規化、帶斑點雜訊的 σ⁰；光學有雲；地籍有部分圖解地籍偏移；
申報裡混有不實申請（長期休耕、新植冒充、災前已收割、前次未恢復、作物不符、面積灌水、重複申請、
使用權過期）與重複上傳的 App 照片。處理鏈看不到地真值，地真值只在 S7 模擬現勘回填與監看對答案時使用。
"""
import hashlib
from datetime import datetime, timedelta

import numpy as np
from scipy import ndimage as ndi

from .base import Source

H = W = 300
PX = 10.0
CROPS = ["水稻", "香蕉", "麻竹筍", "木瓜"]
CATS = {
    "水稻": dict(id="rice-flood", crop="水稻", hazard="淹水", level="乙", streak=6, gov_approved=False,
               prior=dict(a_met=(140, 140), a_not_met=(90, 90), b=(61, 70))),
    "香蕉": dict(id="banana-lodge", crop="香蕉", hazard="倒伏", level="甲", streak=10, gov_approved=True,
               prior=dict(a_met=(96, 96), a_not_met=(70, 71), b=(40, 46))),
    "麻竹筍": dict(id="bamboo-lodge", crop="麻竹筍", hazard="倒伏", level="甲", streak=11, gov_approved=True,
                prior=dict(a_met=(118, 118), a_not_met=(62, 62), b=(51, 58))),
    "木瓜": dict(id="papaya-lodge", crop="木瓜", hazard="倒伏", level="丙", streak=0, gov_approved=False,
               prior=dict(a_met=(52, 52), a_not_met=(48, 48), b=(20, 24))),
    "竹（山坡）": dict(id="slopebamboo-lodge", crop="竹（山坡）", hazard="倒伏", level="乙", streak=0, gov_approved=False),
    "魚塭": dict(id="pond", crop="魚塭", hazard="溢堤、停電", level="丙", streak=0, gov_approved=False),
}
OVERALL_LEVEL = "甲"
INCIDENCE = 39.0          # 入射角（度）
LOOK_AZ = 270.0           # 下降軌道、右視 → 朝西觀測
S1_PRE_DAYS = [-36, -30, -24, -18, -12, -6]
S1_POST_DAY = 4
S2_DAYS = dict(pre=-8, post=12, ly_pre=-8 - 365, ly_post=12 - 365)


def _db2lin(db):
    return 10 ** (db / 10)


def _split(rng, r0, r1, c0, c1, out, max_side, min_side):
    h, w = r1 - r0, c1 - c0
    if h <= max_side and w <= max_side and (rng.random() < 0.55 or max(h, w) < 2 * min_side):
        out.append((r0, r1, c0, c1)); return
    if h >= w and h >= 2 * min_side:
        m = rng.integers(r0 + min_side, r1 - min_side + 1)
        _split(rng, r0, m, c0, c1, out, max_side, min_side); _split(rng, m, r1, c0, c1, out, max_side, min_side)
    elif w >= 2 * min_side:
        m = rng.integers(c0 + min_side, c1 - min_side + 1)
        _split(rng, r0, r1, c0, m, out, max_side, min_side); _split(rng, r0, r1, m, c1, out, max_side, min_side)
    else:
        out.append((r0, r1, c0, c1))


def _blob(rng, shape, frac, smooth=3):
    """坵塊內的受損範圍：平滑雜訊取前 frac 比例。"""
    if frac <= 0:
        return np.zeros(shape, bool)
    if frac >= 1:
        return np.ones(shape, bool)
    n = ndi.gaussian_filter(rng.standard_normal(shape), smooth)
    return n >= np.quantile(n, 1 - frac)


def _checksum(arr_or_obj):
    h = hashlib.sha256()
    if isinstance(arr_or_obj, dict):
        for k in sorted(arr_or_obj, key=str):
            v = arr_or_obj[k]
            h.update(str(k).encode())
            h.update(np.ascontiguousarray(v).tobytes() if isinstance(v, np.ndarray) else repr(v).encode())
    else:
        h.update(np.ascontiguousarray(arr_or_obj).tobytes())
    return h.hexdigest()


class SyntheticSource(Source):
    name = "synthetic"

    def __init__(self, seed=7, event_name="模擬颱風", event_date="2025-07-06", corrupt=True, past=True):
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.event_date = datetime.fromisoformat(event_date + "T22:00:00")
        self.event_name = event_name
        self._past = past
        self._build_layout()
        self._build_truth()
        self._build_products(corrupt)

    # ------------------------------------------------------------------ 地景
    def _build_layout(self):
        rng = self.rng
        rows, cols = np.mgrid[0:H, 0:W]
        self.label = np.zeros((H, W), np.int32)
        self.parcels = []
        pid = 0
        # 河道：由上到下蜿蜒穿過農田
        river_c = (95 + 25 * np.sin(rows / 45.0 + rng.uniform(0, 3))).astype(int)
        self.river = (np.abs(cols - river_c) <= 2) & (cols < 200)
        self.dist_river = ndi.distance_transform_edt(~self.river)
        # 平地農田
        boxes = []
        _split(rng, 0, H, 0, 200, boxes, 34, 7)
        for (r0, r1, c0, c1) in boxes:
            m = np.zeros((H, W), bool)
            m[r0 + 1:r1, c0 + 1:c1] = True            # 留 1 像素當田埂、農路
            m &= ~self.river & (self.dist_river > 2)
            if m.sum() < 4:
                continue
            u = rng.random()
            if u < 0.05:
                kind, crop = "building", None
            elif u < 0.10:
                kind, crop = "windbreak", None
            else:
                kind, crop = "farm", str(rng.choice(CROPS, p=[0.34, 0.22, 0.24, 0.20]))
            pid += 1
            self.label[m] = pid
            self.parcels.append(dict(id=pid, kind=kind, crop=crop, box=(r0, r1, c0, c1)))
        # 山坡竹林
        boxes = []
        _split(rng, 0, 150, 200, W, boxes, 40, 12)
        for (r0, r1, c0, c1) in boxes:
            pid += 1
            self.label[r0 + 1:r1, c0 + 1:c1] = pid
            self.parcels.append(dict(id=pid, kind="farm", crop="竹（山坡）", box=(r0, r1, c0, c1)))
        # 魚塭（池與池之間 2 像素堤岸）
        for r0 in range(152, H - 14, 18):
            for c0 in range(202, W - 14, 24):
                pid += 1
                self.label[r0 + 2:r0 + 16, c0 + 2:c0 + 22] = pid
                self.parcels.append(dict(id=pid, kind="pond", crop="魚塭", box=(r0, r0 + 16, c0, c0 + 22)))
        self.by_id = {p["id"]: p for p in self.parcels}
        for p in self.parcels:
            p["n"] = int((self.label == p["id"]).sum())
            p["area_ha"] = round(p["n"] * PX * PX / 1e4, 4)
            ys, xs = np.nonzero(self.label == p["id"])
            p["center_px"] = (float(ys.mean()), float(xs.mean()))
        # 地形
        hill = (cols >= 200) & (rows < 150)
        z = 4 + 0.02 * rows + 3 * np.exp(-self.dist_river / 15)
        zh = 60 + 140 * (np.sin((cols - 200) / 9.0) * 0.5 + 0.5) * (1 - rows / 220) + 30 * np.sin(rows / 13.0)
        self.dem = np.where(hill, zh, z) - 6 * self.river
        self.dem = ndi.gaussian_filter(self.dem, 1.0)

    # ------------------------------------------------------------------ 地真值：作物、物候、災害
    def _build_truth(self):
        rng = self.rng
        dmg = np.zeros((H, W), np.uint8)       # 0 無、1 淹水、2 倒伏、3 埋沒、4 灌溉積水（非災害）
        for p in self.parcels:
            p["transplant_day"] = None
            p["claim"] = None
            if p["kind"] != "farm":
                p.update(loss=0.0, damage="無", applied=False)
                continue
            if p["crop"] == "水稻":
                # 一期稻收割季；約 15% 的田正在二期灌水整地（插秧前），雷達會變暗
                p["transplant_day"] = int(rng.integers(-3, 6)) if rng.random() < 0.15 else None
            d = self.dist_river[int(p["center_px"][0]), int(p["center_px"][1])]
            u = rng.random()
            # 先決定受損面積比例，再乘上作物受損程度：損失 = 受損面積 × 嚴重度 + 誤差
            def frac():
                return float(rng.uniform(0.55, 1.0) if rng.random() < 0.7 else rng.uniform(0.12, 0.45))
            if p["crop"] != "竹（山坡）" and d < 9 and u < 0.5:
                p["damage"], f, sev = "埋沒", 1.0, rng.uniform(0.9, 1.0)
            elif p["crop"] in ("水稻", "木瓜") and d < 40 and u < 0.75:
                p["damage"], f, sev = "淹水", frac(), {"水稻": 0.95, "木瓜": 0.9}[p["crop"]] + rng.normal(0, 0.03)
            elif p["crop"] in ("香蕉", "麻竹筍", "木瓜", "竹（山坡）") and u < 0.55:
                p["damage"], f, sev = "倒伏", frac(), {"香蕉": 0.88, "麻竹筍": 0.8, "木瓜": 0.85, "竹（山坡）": 0.75}[p["crop"]] + rng.normal(0, 0.04)
            elif p["crop"] == "水稻" and u < 0.2:
                p["damage"], f, sev = "倒伏", frac(), 0.7 + rng.normal(0, 0.05)
            else:
                p["damage"], f, sev = "無", 0.0, 0.0
            p["frac_target"] = f
            loss = 100 * f * sev + rng.normal(0, 3) if f > 0 else rng.uniform(0, 4)
            p["loss"] = round(float(np.clip(loss, 0, 100)), 1)
        # 像素層級的受損範圍
        self.damaged = np.zeros((H, W), bool)
        for p in self.parcels:
            if p["kind"] != "farm":
                continue
            m = self.label == p["id"]
            r0, r1, c0, c1 = p["box"]
            sub = m[r0:r1, c0:c1]
            frac = p["frac_target"]
            b = _blob(rng, sub.shape, frac) & sub
            full = np.zeros((H, W), bool); full[r0:r1, c0:c1] = b
            self.damaged |= full
            code = {"淹水": 1, "倒伏": 2, "埋沒": 3, "無": 0}[p["damage"]]
            dmg[full] = code
            p["damaged_frac"] = float(b.sum() / max(sub.sum(), 1))
            if p["transplant_day"] is not None:
                dmg[m & (dmg == 0)] = 4
        self.dmg = dmg
        # 魚塭：停電區與潰堤
        self.outage_cells = {(3, 4), (3, 5), (4, 5), (5, 5)}
        for p in self.parcels:
            if p["kind"] != "pond":
                continue
            r, c = p["center_px"]
            cell = (int(r // 50), int(c // 50))
            p["outage_days"] = int(rng.integers(2, 5)) if cell in self.outage_cells else 0
            p["breach"] = bool(rng.random() < 0.12)
            p["stocked"] = bool(rng.random() < 0.85)
            p["loss"] = float(rng.uniform(40, 90)) if (p["stocked"] and (p["breach"] or p["outage_days"] >= 3)) else float(rng.uniform(0, 10))
            p["damage"] = "潰堤" if p["breach"] else ("停電" if p["outage_days"] else "無")
        # 申報
        for p in self.parcels:
            p.update(applied=False, declared_crop=None, declared_ha=None, right_valid=True, dup_with=None,
                     stocking=None, harvest=None, photo=None, land_no=None, graphic=False, misreg=(0, 0))
            p["land_no"] = f"模擬段 {p['id']:04d}"
            if p["kind"] == "pond":
                p["stocking"] = p["stocked"] and rng.random() < 0.9
                p["harvest"] = rng.random() < 0.05
                p["applied"] = p["loss"] >= 20 or rng.random() < 0.15
                p["declared_crop"] = "魚塭"
                p["declared_ha"] = p["area_ha"]
                continue
            if p["kind"] != "farm":
                continue
            prob = 0.92 if p["loss"] >= 20 else 0.55 if p["loss"] >= 10 else 0.35
            p["applied"] = bool(rng.random() < prob)
            p["declared_crop"] = p["crop"]
            p["declared_ha"] = p["area_ha"]
            p["graphic"] = bool(rng.random() < 0.15)
            if p["graphic"] and rng.random() < 0.5:
                p["misreg"] = (int(rng.choice([-3, 3])), int(rng.choice([-3, 0, 3])))
        # 不實申請（處理鏈看不到 claim 欄位）
        farm_applied = [p for p in self.parcels if p["kind"] == "farm" and p["applied"] and p["crop"] != "竹（山坡）"]
        rng.shuffle(farm_applied)
        kinds = ["L1 長期休耕", "L2 新植冒充成樹", "L3 災前已收割", "L4 前次未恢復", "作物不符", "面積灌水", "使用權過期"]
        for p, k in zip(farm_applied[:len(kinds) * 2], kinds * 2):
            p["claim"] = k
            if k == "作物不符":
                p["declared_crop"] = [c for c in CROPS if c != p["crop"]][int(rng.integers(0, 3))]
            if k == "面積灌水":
                p["declared_ha"] = round(p["area_ha"] * 1.45, 4)
            if k == "使用權過期":
                p["right_valid"] = False
            if k in ("L1 長期休耕", "L3 災前已收割"):
                p["loss"] = round(float(rng.uniform(0, 6)), 1)        # 田裡本來就沒有作物或已收割，沒有可受損的東西
                p["damage"] = "無"; p["damaged_frac"] = 0.0
                m = self.label == p["id"]
                self.dmg[m & (self.dmg != 4)] = 0
        # 重複申請
        cands = [p for p in self.parcels if p["applied"] and p["kind"] == "farm" and not p["claim"]]
        if len(cands) > 4:
            cands[2]["dup_with"] = cands[3]["id"]; cands[2]["claim"] = "重複申請"
        # App 照片：感知雜湊（64 位元），其中幾張是舊照片重用
        self.photo_db = [int(rng.integers(0, 2 ** 63)) for _ in range(40)]     # 歷次案件照片
        for p in self.parcels:
            if p["applied"] and rng.random() < 0.55:
                h = int(rng.integers(0, 2 ** 63))
                reuse = rng.random() < 0.06
                if reuse:
                    base = self.photo_db[int(rng.integers(0, len(self.photo_db)))]
                    flips = rng.choice(64, size=int(rng.integers(2, 9)), replace=False)
                    h = base
                    for b in flips:
                        h ^= (1 << int(b))
                    h &= (2 ** 63 - 1)
                p["photo"] = dict(dhash=h, mode="相簿匯入" if rng.random() < 0.08 else "App 即時拍攝",
                                  taken=(self.event_date + timedelta(days=float(rng.uniform(0.5, 3)))).isoformat(timespec="minutes"),
                                  reused=reuse)
        # 熱區高解析影像：取像時是否有雲
        for p in self.parcels:
            p["hr_cloudy"] = bool(rng.random() < 0.15)

    # ------------------------------------------------------------------ 物候
    def _ndvi_on(self, p, day, year_offset=0):
        """某坵塊在相對事件第 day 天的 NDVI（不含災害）。year_offset=-1 為去年同期。"""
        rng = self.rng
        c = p["crop"]
        doy = (self.event_date + timedelta(days=day)).timetuple().tm_yday
        if p["kind"] == "building":
            return 0.08
        if p["kind"] == "windbreak":
            return 0.80
        if p["kind"] == "pond":
            return -0.3
        if c == "水稻":
            # 兩期稻：2 月中、7 月中插秧，生長約 115 天
            t = (doy - 45) % 182
            v = 0.15 + 0.7 * np.clip(t / 60, 0, 1) * (1 if t < 100 else max(0, 1 - (t - 100) / 15))
            if p["transplant_day"] is not None and year_offset == 0 and day >= p["transplant_day"] - 8:
                v = 0.05
            return float(v)
        base = {"香蕉": 0.76, "麻竹筍": 0.72, "木瓜": 0.66, "竹（山坡）": 0.78}[c]
        return float(base + 0.04 * np.sin(2 * np.pi * doy / 365))

    # ------------------------------------------------------------------ 產品
    def _build_products(self, corrupt):
        rng = self.rng
        self._payload = {}
        self._catalog = []
        ev = self.event_date

        def add(kind, sensor, day, payload, meta=None, pid=None, bad=False):
            dt = (ev + timedelta(days=day)).isoformat(timespec="seconds")
            pid = pid or f"SIM_{kind}_{(ev + timedelta(days=day)).strftime('%Y%m%dT%H%M')}_{len(self._catalog):02d}"
            ck = _checksum(payload)
            if bad:
                ck = ck[:-6] + "000000"        # 模擬下載不完整：檢查碼對不上
            self._payload[pid] = payload
            self._catalog.append(dict(id=pid, kind=kind, sensor=sensor, datetime=dt, day=day,
                                      official_checksum=ck, meta=meta or {}))

        # 地形與觀測幾何
        add("DEM", "模擬 30 米 DEM 重採樣", -400, dict(dem=self.dem.astype("float32")),
            dict(incidence_deg=INCIDENCE, look_azimuth_deg=LOOK_AZ, pixel_m=PX))
        # 雷達
        for i, d in enumerate(S1_PRE_DAYS):
            add("S1_GRD", "Sentinel-1", d, self._s1(d, post=False), dict(orbit=105, pass_="descending"),
                bad=(corrupt and i == 2))
        add("S1_GRD", "Sentinel-1", S1_POST_DAY, self._s1(S1_POST_DAY, post=True), dict(orbit=105, pass_="descending"))
        add("S1_COH", "Sentinel-1", -6, dict(coh=self._coh(post=False)), dict(pair="災前 −12／−6 日"))
        add("S1_COH", "Sentinel-1", S1_POST_DAY, dict(coh=self._coh(post=True)), dict(pair="災前 −6／災後 +4 日"))
        # 光學
        for name, d in S2_DAYS.items():
            add("S2_L2A", "Sentinel-2", d, self._s2(d, name), dict(role=name))
        # 夜間燈光
        add("VIIRS", "VIIRS VNP46A2", 10, self._viirs(), dict(cell_px=50, start_day=-40))
        # 地籍、國土利用、申報、照片、時序
        add("CADASTRE", "國土測繪中心（模擬）", -200, self._cadastre())
        add("LANDUSE", "國土利用調查（模擬）", -200, dict(farmland=np.isin(self.label, [p["id"] for p in self.parcels if p["kind"] in ("farm", "pond")]).astype(np.uint8)))
        add("DECLARE", "公所救助系統匯出（模擬）", 8, self._declare())
        add("APP_PHOTO", "農業部現地照相 App（模擬）", 3, dict(photos={p["id"]: p["photo"] for p in self.parcels if p["photo"]}, history_hashes=self.photo_db))
        add("HISTORY", "天相星坵塊時序表（平時累積）", -1, self._history())

    def _lut(self, fn, default):
        """依坵塊編號建查表：lut[id] = fn(p)，回傳整張圖。"""
        lut = np.full(self.label.max() + 1, default, dtype="float64")
        for p in self.parcels:
            lut[p["id"]] = fn(p)
        return lut[self.label]

    def _s1(self, day, post):
        rng = self.rng

        def base(p, pol):
            if p["kind"] == "building":
                return (1.0, -6.0)[pol]
            if p["kind"] == "windbreak":
                return (-7.5, -13.5)[pol]
            if p["kind"] == "pond":
                return (-21.0, -27.5)[pol]
            if p["crop"] == "水稻":
                if p["transplant_day"] is not None and day >= p["transplant_day"] - 8:
                    return (-19.5, -26.5)[pol]                # 灌水整地：像水面
                nd = self._ndvi_on(p, day)
                return (-14 + 6 * nd, -24 + 11 * nd)[pol]
            return {"香蕉": (-7.0, -13.0), "麻竹筍": (-8.0, -14.0), "木瓜": (-9.0, -15.0), "竹（山坡）": (-8.0, -14.0)}[p["crop"]][pol]

        vv = self._lut(lambda p: base(p, 0), -12.0)
        vh = self._lut(lambda p: base(p, 1), -19.0)
        vv[self.river], vh[self.river] = -22.0, -28.0
        if post:
            rice = self._lut(lambda p: 1.0 if p["crop"] == "水稻" else 0.0, 0.0) > 0
            d = self.dmg
            vv[d == 1], vh[d == 1] = -20.5, -27.0
            vv[d == 3], vh[d == 3] = -11.0, -19.5
            lod = d == 2
            vh[lod & ~rice] -= 4.0
            vh[lod & rice] += 3.0
            vv[lod & rice] += 1.5
            breach = self._lut(lambda p: 1.0 if p["kind"] == "pond" and p["breach"] else 0.0, 0.0) > 0
            mud = breach & _blob(rng, (H, W), 0.6, 2)
            vv[mud], vh[mud] = -12.5, -20.0
            over = (np.arange(W)[None, :] > 250) & (np.arange(H)[:, None] > 240)
            vv[over], vh[over] = np.minimum(vv[over], -20.0), np.minimum(vh[over], -27.0)
        # 地形：未做輻射地形正規化前，朝向雷達的坡面較亮、背向較暗；陰影與疊置
        gy, gx = np.gradient(self.dem, PX)
        slope_range = -gx
        theta = np.radians(INCIDENCE)
        local = theta - np.arctan(slope_range)
        gain = np.clip(np.cos(local) / np.cos(theta), 0.05, 6)
        vv_lin = _db2lin(vv) * gain; vh_lin = _db2lin(vh) * gain
        shadow = np.arctan(-slope_range) > (np.pi / 2 - theta) * 0.75
        vv_lin[shadow], vh_lin[shadow] = _db2lin(-24), _db2lin(-30)
        L = 4
        vv_lin *= rng.gamma(L, 1 / L, (H, W)); vh_lin *= rng.gamma(L, 1 / L, (H, W))
        return dict(vv=vv_lin.astype("float32"), vh=vh_lin.astype("float32"))

    def _coh(self, post):
        rng = self.rng
        c = self._lut(lambda p: 0.92 if p["kind"] == "building" else 0.1 if p["kind"] == "pond" else 0.62 if p["crop"] == "水稻" else 0.86, 0.55)
        c[self.river] = 0.1
        if post:
            c[self.dmg == 3] = 0.2
            c[self.dmg == 1] = 0.12
            c[self.dmg == 2] -= 0.12
        return np.clip(c + rng.normal(0, 0.05, (H, W)), 0, 1).astype("float32")

    def _s2(self, day, role):
        rng = self.rng
        ly = role.startswith("ly_")

        def f(p):
            v = self._ndvi_on(p, day + 365 if ly else day, -1 if ly else 0)
            if p["claim"] == "L3 災前已收割" and not ly and day >= -15:
                v = 0.18
            if p["claim"] == "L1 長期休耕":
                v = 0.38
            return v
        nd = self._lut(f, 0.15)
        nd[self.river] = -0.3
        water = nd < -0.1
        if role == "post":
            d = self.dmg
            nd = np.where(d == 2, nd - 0.35, nd)
            nd = np.where(d == 3, 0.12, nd)
            water = water | (d == 1)
        nd = np.clip(nd + rng.normal(0, 0.025, (H, W)), -0.5, 0.95)
        v = np.clip(nd, 0, 1)
        b8 = 0.04 + 0.42 * v; b4 = 0.13 - 0.10 * v; b3 = 0.09 - 0.03 * v
        b5 = 0.10 + 0.12 * v; b11 = 0.26 - 0.12 * v
        for arr, val in ((b3, 0.11 if role == "post" else 0.06), (b4, 0.05), (b8, 0.025), (b5, 0.03), (b11, 0.012)):
            arr[water] = val
        cover = dict(pre=0.08, post=0.45, ly_pre=0.12, ly_post=0.18)[role]
        field = ndi.gaussian_filter(rng.standard_normal((H, W)), 18)
        field = (field - field.mean()) / max(field.std(), 1e-9)
        cloud_prob = 1 / (1 + np.exp(-(field - np.quantile(field, 1 - cover)) * 6))
        cs = np.clip(1 - cloud_prob + rng.normal(0, 0.04, (H, W)), 0, 1)
        cl = cloud_prob > 0.5
        for arr in (b3, b4, b8, b5, b11):
            arr[cl] = 0.35 + 0.1 * cloud_prob[cl]
        return {k: x.astype("float32") for k, x in dict(B3=b3, B4=b4, B5=b5, B8=b8, B11=b11, cs=cs).items()}

    def _viirs(self):
        rng = self.rng
        days = np.arange(-40, 11)
        cells = (H // 50, W // 50)
        rad = rng.normal(22, 1.5, (len(days),) + cells)
        rad[:, :, :2] = rng.normal(9, 1, (len(days), cells[0], 2))
        for (r, c) in self.outage_cells:
            k = 3 if (r, c) != (5, 5) else 4
            rad[(days >= 0) & (days < k), r, c] = rng.normal(3, 0.8, k)
        rad[days == 1] *= 0.0                    # 颱風隔天全區雲遮，沒有可用觀測
        rad[days == 1] = np.nan
        return dict(rad=rad.astype("float32"), days=days)

    def _cadastre(self):
        lab = np.zeros((H, W), np.int32)
        attrs = {}
        for p in self.parcels:
            m = self.label == p["id"]
            dy, dx = p["misreg"]
            if dy or dx:
                m = np.roll(np.roll(m, dy, 0), dx, 1)      # 圖解地籍偏移：地籍邊界和實際田界錯開
            lab[m & (lab == 0)] = p["id"]
            attrs[p["id"]] = dict(land_no=p["land_no"], reg_ha=p["area_ha"], graphic=p["graphic"])
        return dict(label=lab, attrs=attrs)

    def _declare(self):
        out = {}
        for p in self.parcels:
            if p["kind"] not in ("farm", "pond"):
                continue
            out[p["id"]] = dict(applied=p["applied"], crop=p["declared_crop"], declared_ha=p["declared_ha"],
                                right_valid=p["right_valid"], dup_with=p["dup_with"],
                                stocking=p["stocking"], harvest=p["harvest"],
                                baseline_locked=bool(self.rng.random() < 0.8), applicant=f"模擬申請人 {p['id']:04d}")
        return out

    def _history(self):
        """平時累積的坵塊時序：過去 3 年每 6 天一筆 NDVI（35% 雲遮）、過去一年每 12 天一筆 VH。"""
        rng = self.rng
        out = {}
        nd_days = np.arange(-3 * 365, 0, 6)
        vh_days = np.arange(-360, 0, 12)
        for p in self.parcels:
            if p["kind"] != "farm":
                continue
            nd = np.array([self._ndvi_on(p, int(d)) for d in nd_days])
            claim = p["claim"]
            if claim == "L1 長期休耕":
                nd = 0.36 + 0.05 * rng.standard_normal(len(nd_days))
            elif claim == "L2 新植冒充成樹":
                nd = np.where(nd_days < -240, 0.14, np.minimum(nd, 0.14 + (nd_days + 240) / 240 * 0.5))
            elif claim == "L3 災前已收割":
                nd = np.where(nd_days >= -15, 0.18, nd)
            elif claim == "L4 前次未恢復":
                nd = np.where(nd_days >= -300, 0.25, nd)
            nd = nd + rng.normal(0, 0.03, len(nd))
            nd[rng.random(len(nd)) < 0.35] = np.nan
            vh = []
            for d in vh_days:
                n = self._ndvi_on(p, int(d))
                if p["crop"] == "水稻":
                    t = ((self.event_date + timedelta(days=int(d))).timetuple().tm_yday - 45) % 182
                    v = -24 + 11 * n - (3.0 if t < 12 else 0)        # 插秧前灌水：VH 下降
                else:
                    v = {"香蕉": -13.0, "麻竹筍": -14.0, "木瓜": -15.0, "竹（山坡）": -14.0}[p["crop"]]
                if claim == "L1 長期休耕":
                    v = -18.5
                vh.append(v + rng.normal(0, 0.6))
            out[p["id"]] = dict(nd_days=nd_days, ndvi=nd.astype("float32"), vh_days=vh_days, vh=np.array(vh, "float32"))
        return out

    # ------------------------------------------------------------------ 介面
    def event(self):
        ev = self.event_date
        return dict(id=f"SIM-{ev:%Y%m%d}-{self.seed}", name=self.event_name, hazard="颱風",
                    alert=ev.isoformat(timespec="minutes"),
                    radar_arrival=(ev + timedelta(days=S1_POST_DAY, hours=2)).isoformat(timespec="minutes"),
                    announce=(ev + timedelta(days=4)).date().isoformat(), shape=[H, W], pixel_m=PX,
                    aoi="模擬農區 3 × 3 公里")

    def catalog(self):
        return [dict(c) for c in self._catalog]

    def load(self, product):
        return self._payload[product["id"]]

    def order_hr(self, parcel_ids):
        """熱區高解析影像：回傳每塊田 0.7 米語意分割的倒伏、埋沒面積比例（以地真值加誤差模擬）。"""
        out, failed = {}, []
        for pid in parcel_ids:
            p = self.by_id[pid]
            if p["hr_cloudy"]:
                failed.append(pid); continue
            f = p.get("damaged_frac", 0.0) if p.get("damage") in ("倒伏", "埋沒") else 0.0
            out[pid] = dict(lodge_frac=float(np.clip(f + self.rng.normal(0, 0.04), 0, 1)), canopy_visible=p["crop"] != "竹（山坡）")
        prod = dict(id=f"SIM_HR_{self.event_date:%Y%m%d}_{len(parcel_ids)}", kind="HR", sensor="福衛八號（模擬）",
                    datetime=(self.event_date + timedelta(days=5)).isoformat(timespec="seconds"), day=5, meta=dict(parcels=len(parcel_ids)))
        payload = dict(results=out, failed=failed)
        prod["official_checksum"] = _checksum(payload)
        self._payload[prod["id"]] = payload
        return [prod], failed

    def categories(self):
        return dict(overall=OVERALL_LEVEL, items=list(CATS.values()))

    def past_events(self):
        if not self._past:
            return []
        return [SyntheticSource(seed=self.seed * 31 + k, event_name=f"過去災害 {k + 1}", event_date=d, corrupt=False, past=False)
                for k, d in enumerate(["2023-07-27", "2024-07-24", "2024-10-03"])]

    def approved_losses(self):
        """公所核定清冊：只有申請且經現勘者有核定損失率（模擬現勘誤差 ±4 個百分點）。"""
        rng = np.random.default_rng(self.seed + 999)
        return {p["id"]: float(np.clip(p["loss"] + rng.normal(0, 3), 0, 100))
                for p in self.parcels if p["kind"] == "farm" and p["applied"]}

    def field_survey(self, parcel_ids):
        rng = np.random.default_rng(self.seed + 123)
        return {pid: dict(loss=float(np.clip(self.by_id[pid]["loss"] + rng.normal(0, 3), 0, 100)),
                          crop=self.by_id[pid]["crop"]) for pid in parcel_ids}

    def truth(self):
        return {p["id"]: dict(kind=p["kind"], crop=p["crop"], loss=p.get("loss"), damage=p.get("damage"),
                              claim=p.get("claim"), misreg=p.get("misreg"), transplant=p.get("transplant_day") is not None)
                for p in self.parcels}
