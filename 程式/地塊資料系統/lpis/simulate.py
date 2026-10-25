"""
模擬一個虛構農區，從 2023 年建置一路走到 2026 年第一期作，產生各種常見異動。
人名、地號、圖資全部虛構；座標放在 TWD97 TM2，大約嘉義縣山腳下的平原（只為了經緯度看起來合理）。

街廓（每格約 294 × 197 公尺，中間 6 公尺道路）
  C 頂坑段（圖解地籍，未重測）   D 內埔段（數值地籍，魚塭區）
  A 竹崎段（圖解地籍，2025-11 重測） B 內埔段（數值地籍）
"""
import math
import random
from datetime import date, timedelta

from shapely import affinity
from shapely.geometry import box, Polygon
from shapely.ops import unary_union

from .core import ParcelDB

X0, Y0 = 196000.0, 2598000.0
GRAPHIC_SHIFT = (2.6, -3.1)          # 圖解地籍與實地的偏移（公尺）
CROPS = {"水稻": 0.62, "香蕉": 0.14, "麻竹筍": 0.10, "木瓜": 0.08, "蔬菜": 0.06}
SURNAMES = "陳林黃張李王吳劉蔡楊許鄭謝洪郭邱曾廖賴徐周葉蘇莊呂江何蕭羅高"
GIVEN = "明雄華忠義信美玉秀春福德輝文昌榮志成國金麗英"


def _blocks():
    return {
        "A": dict(x=0, y=0, sec="竹崎段", code="ZQ", graphic=1, n=12),
        "B": dict(x=306, y=0, sec="內埔段", code="NP", graphic=0, n=12, start=101),
        "C": dict(x=0, y=203, sec="頂坑段", code="DK", graphic=1, n=12),
        "D": dict(x=306, y=203, sec="內埔段", code="NP", graphic=0, n=6, start=201, use="魚塭"),
    }


def _g(x0, y0, x1, y1):
    return box(X0 + x0, Y0 + y0, X0 + x1, Y0 + y1)


class Sim:
    def __init__(self, path, seed=7):
        self.rng = random.Random(seed)
        self.db = ParcelDB(path, create=True)
        self.truth = {}           # 坵塊真實範圍（品質檢查量測用；系統平常看不到）
        self.lot_true = {}        # 地號真實位置（重測後的結果）
        self.events = []          # 給展示頁的事件時間軸
        self.ops = []
        self.parcel_crop = {}

    # ----------------------------------------------------------------- 工具
    def ev(self, d, title, detail, ids=()):
        self.events.append(dict(date=d, title=title, detail=detail, ids=list(ids)))

    def name(self):
        return self.rng.choice(SURNAMES) + "○" + self.rng.choice(GIVEN)

    def at(self, d):
        self.db.now = d + "T09:00:00"
        return d

    # ----------------------------------------------------------------- 2023-01-01 建置
    def build(self):
        d = self.at("2023-01-01")
        db = self.db
        lots_by_block = {}
        for b, cfg in _blocks().items():
            w = 294 / cfg["n"]
            ids = []
            for i in range(cfg["n"]):
                no = str(cfg.get("start", 1) + i)
                lot_id = f"{cfg['code']}-{no}"
                true = _g(cfg["x"] + i * w, cfg["y"], cfg["x"] + (i + 1) * w, cfg["y"] + 197)
                rec = affinity.translate(true, *GRAPHIC_SHIFT) if cfg["graphic"] else true
                self.lot_true[lot_id] = true
                db.add_lot(lot_id, dict(county="嘉義縣", town="示範鄉", section=cfg["sec"], subsection="", lot_no=no,
                                        cadastre_version="地籍圖 1985" if cfg["graphic"] else "數值地籍 2008", graphic=cfg["graphic"]),
                           rec, d, "地政資料匯入", "匯入地籍")
                ids.append(lot_id)
            lots_by_block[b] = ids
        self.lots = lots_by_block
        self.ev(d, "系統建置", "匯入 42 筆地號（竹崎段、頂坑段為圖解地籍）、航照判釋坵塊與不可申報範圍")

        # 不可申報範圍（先建，坵塊面積才會扣掉）
        def tl(lot):  # 真實位置的地號
            return self.lot_true[lot]
        a11 = tl("ZQ-11").bounds
        db.add_ineligible("IN-01", "水塘", _g(a11[0] - X0 + 3, 40, a11[0] - X0 + 21, 82), d, "航照判釋")
        c2 = tl("DK-2").bounds
        db.add_ineligible("IN-02", "建物", _g(c2[0] - X0 + 4, 380, c2[0] - X0 + 20, 395), d, "航照判釋")
        db.add_ineligible("IN-03", "農路", _g(306 + 6 * 24.5, 96, 306 + 8 * 24.5, 99.5), d, "航照判釋")
        c9 = tl("DK-9").bounds
        db.add_ineligible("IN-04", "防風林", _g(c9[0] - X0, 203, c9[2] - X0, 211), d, "航照判釋")

        # 坵塊：一般一筆地號一塊田；有幾種特例
        merged = {("NP-103", "NP-104"), ("NP-109", "NP-110"), ("ZQ-5", "ZQ-6")}
        split_lot = "DK-5"              # 一筆地號裡分兩塊種不同作物
        used = set()
        n = 0
        for b, ids in lots_by_block.items():
            use = _blocks()[b].get("use", "旱田" if b == "C" else "水田")
            for lot in ids:
                if lot in used:
                    continue
                pair = next((p for p in merged if p[0] == lot), None)
                if pair:
                    g = unary_union([tl(pair[0]), tl(pair[1])]).buffer(-0.6, join_style=2)
                    used.update(pair)
                    n += 1; self._parcel(f"P{n:03d}", g, use, d)
                elif lot == split_lot:
                    t = tl(lot).bounds
                    n += 1; self._parcel(f"P{n:03d}", box(t[0], t[1], t[2], t[1] + 100).buffer(-0.6, join_style=2), use, d)
                    n += 1; self._parcel(f"P{n:03d}", box(t[0], t[1] + 100, t[2], t[3]).buffer(-0.6, join_style=2), use, d)
                else:
                    n += 1; self._parcel(f"P{n:03d}", tl(lot).buffer(-0.6, join_style=2), use, d)
        self.next_pid = n + 1

        # 經營人與使用權
        for lot in [l for ids in lots_by_block.values() for l in ids]:
            self._initial_rights(lot, d)

    def _parcel(self, pid, g, use, d, source="航照判釋 2022"):
        self.truth[pid] = g
        self.db.add_parcel(pid, g, use, d, "航照判釋", source)

    def _op(self, d, identity):
        code = f"F{len(self.ops) + 1:03d}"
        self.db.add_operator(code, self.name(), identity, d, "公所", contact=f"09{self.rng.randint(10, 99)}-***-{self.rng.randint(100, 999)}")
        self.ops.append(code)
        return code

    def _initial_rights(self, lot, d):
        db, r = self.db, self.rng.random()
        # 合併經營的地號由同一人
        partner = {"NP-104": "NP-103", "NP-110": "NP-109", "ZQ-6": "ZQ-5"}
        if lot in partner:
            src = db.con.execute("SELECT * FROM use_rights WHERE lot_id=? AND valid_to IS NULL", (partner[lot],)).fetchall()
            for i, s in enumerate(src):
                db.grant_right(f"R-{lot}-{i + 1}", s["operator_code"], lot, s["right_type"], (s["share_num"], s["share_den"]),
                               f"{s['doc_no']}-2", s["doc_from"], s["doc_to"], d, "公所")
            return
        if lot in ("ZQ-8", "NP-107"):        # 共有，各 1/2
            for i in range(2):
                db.grant_right(f"R-{lot}-{i + 1}", self._op(d, "共有人"), lot, "所有權", (1, 2), f"所有權狀 {lot}-{i + 1}", "2010-05-01", None, d, "公所")
            return
        if r < 0.35 or lot in ("DK-3", "NP-111", "ZQ-2"):   # 承租
            to = "2025-12-31" if lot in ("DK-3", "NP-111") else "2027-12-31"
            db.grant_right(f"R-{lot}-1", self._op(d, "承租人"), lot, "租約", (1, 1), f"三七五租約 {self.rng.randint(1000, 9999)}", "2022-01-01", to, d, "公所")
            return
        db.grant_right(f"R-{lot}-1", self._op(d, "自耕農"), lot, "所有權", (1, 1), f"所有權狀 {self.rng.randint(10000, 99999)}", "2005-01-01", None, d, "公所")

    # ----------------------------------------------------------------- 作物申報
    def operator_of(self, pid, at):
        links = sorted(self.db.allocate(pid, at), key=lambda l: -l["share"])
        for l in links:
            rs = self.db.rights_at(l["lot_id"], at)
            if rs:
                return rs[0]["operator_code"], l["lot_id"]
        return None, links[0]["lot_id"] if links else None

    def declare_season(self, season, d):
        self.at(d)
        db = self.db
        y, s = season.split("-")
        planting = f"{y}-02-{self.rng.randint(5, 25):02d}" if s == "1" else f"{y}-08-{self.rng.randint(1, 20):02d}"
        for p in db.rows_at("parcels", d):
            pid = p["parcel_id"]
            if p["land_use"] == "魚塭":
                crop = "虱目魚"
            else:
                prev = self.parcel_crop.get(pid)
                if prev in ("香蕉", "麻竹筍", "木瓜"):
                    crop = prev                               # 多年生作物不換
                elif prev and self.rng.random() < 0.8:
                    crop = prev
                else:
                    crop = self.rng.choices(list(CROPS), weights=list(CROPS.values()))[0]
                    if p["land_use"] == "旱田" and crop == "水稻":
                        crop = "麻竹筍"
            self.parcel_crop[pid] = crop
            op, _ = self.operator_of(pid, d)
            if op is None:
                continue
            src = self.rng.choices(["農民申報", "產銷履歷", "公糧收購"], weights=[0.7, 0.15, 0.15])[0]
            db.declare_crop(f"D-{season}-{pid}", pid, op, season, crop, planting if crop in ("水稻", "蔬菜") else None, src,
                            self.rng.random() < 0.7, d, "農民")

    # ----------------------------------------------------------------- 時間軸
    def run(self):
        db = self.db
        self.build()
        db.commit()
        for season, d in (("2023-1", "2023-02-01"), ("2023-2", "2023-08-05"), ("2024-1", "2024-02-01")):
            self.declare_season(season, d)

        # 2024-04-15 地號分割
        d = self.at("2024-04-15")
        t = self.lot_true["NP-112"].bounds
        db.subdivide_lot("NP-112", [("NP-112", box(t[0], t[1], t[2], t[1] + 98.5), "112"),
                                    ("NP-112-1", box(t[0], t[1] + 98.5, t[2], t[3]), "112-1")], d, "地政資料匯入", "地號分割（繼承分割）")
        self.lot_true["NP-112-1"] = box(t[0], t[1] + 98.5, t[2], t[3])
        self.lot_true["NP-112"] = box(t[0], t[1], t[2], t[1] + 98.5)
        r = db.rights_at("NP-112", "2024-04-14")
        op = r[0]["operator_code"] if r else self._op(d, "自耕農")
        if r:
            db.end_right(r[0]["right_id"], d, "公所", "地號分割")
        db.grant_right("R-NP-112-a", op, "NP-112", "所有權", (1, 1), "所有權狀 分割後", d, None, d, "公所", "地號分割後重新登錄")
        db.grant_right("R-NP-112-1-a", self._op(d, "自耕農"), "NP-112-1", "所有權", (1, 1), "所有權狀 分割後", d, None, d, "公所", "繼承取得")
        pid = next(l["parcel_id"] for l in db.rows_at("lot_parcel", d) if l["lot_id"] == "NP-112")
        self.ev(d, "地號分割", "內埔段 112 號分割為 112 與 112-1；坵塊 " + pid + " 自動改為對應兩筆地號", ["NP-112", "NP-112-1", pid])

        self.declare_season("2024-2", self.at("2024-08-05"))
        self.declare_season("2025-1", self.at("2025-02-01"))

        # 2025-03-10 坵塊分割
        d = self.at("2025-03-10")
        pid = next(l["parcel_id"] for l in db.rows_at("lot_parcel", d) if l["lot_id"] == "ZQ-2")
        t = self.truth[pid].bounds
        mid = (t[1] + t[3]) / 2
        a, b = f"P{self.next_pid:03d}", f"P{self.next_pid + 1:03d}"
        self.next_pid += 2
        ga, gb = box(t[0], t[1], t[2], mid - 0.4), box(t[0], mid + 0.4, t[2], t[3])
        db.split_parcel(pid, [(a, ga), (b, gb)], d, "公所", "坵塊分割（北半改種木瓜）")
        self.truth[a], self.truth[b] = ga, gb
        op, _ = self.operator_of(a, d)
        db.declare_crop(f"D-2025-1-{a}", a, op, "2025-1", "水稻", "2025-03-01", "農民申報", True, d, "農民")
        db.declare_crop(f"D-2025-1-{b}", b, op, "2025-1", "木瓜", None, "農民申報", True, d, "農民")
        self.parcel_crop[a], self.parcel_crop[b] = "水稻", "木瓜"
        self.ev(d, "坵塊分割", f"竹崎段 2 號北半改種木瓜，{pid} 分成 {a}、{b}", [pid, a, b])

        # 2025-03-20 前後：第一期作災前基準確認並鎖定
        self.lock_season("2025-1", "2025-03-20", frac=0.85)

        # 颱風
        self.ev("2025-07-06", "颱風當天", "查詢當天的範圍、作物、經營人與災前基準（以此為判讀依據）")

        self.declare_season("2025-2", self.at("2025-08-05"))

        # 2025-09-01 租約換人
        d = self.at("2025-09-01")
        old = db.rights_at("ZQ-2", d)
        if old:
            db.end_right(old[0]["right_id"], d, "公所", "租約提前終止")
        newop = self._op(d, "承租人")
        db.grant_right("R-ZQ-2-b", newop, "ZQ-2", "租約", (1, 1), "租約 2025-0901", d, "2028-07-31", d, "公所", "新承租人")
        for pid in [l["parcel_id"] for l in db.rows_at("lot_parcel", d) if l["lot_id"] == "ZQ-2"]:
            cur = db.current("crop_declarations", f"D-2025-2-{pid}")
            if cur:
                db.declare_crop(cur["decl_id"], pid, newop, "2025-2", cur["crop"], cur["planting_date"], "農民申報", True, d, "農民")
        self.ev(d, "經營人變更", "竹崎段 2 號換承租人；第二期作的申報改到新承租人名下", ["ZQ-2"])

        # 2025-10-01 坵塊合併（承租隔壁一起種）
        d = self.at("2025-10-01")
        p7 = next(l["parcel_id"] for l in db.rows_at("lot_parcel", d) if l["lot_id"] == "DK-7")
        p8 = next(l["parcel_id"] for l in db.rows_at("lot_parcel", d) if l["lot_id"] == "DK-8")
        nid = f"P{self.next_pid:03d}"; self.next_pid += 1
        op7 = db.rights_at("DK-7", d)[0]["operator_code"]
        r8 = db.rights_at("DK-8", d)
        db.grant_right("R-DK-8-b", op7, "DK-8", "租約", (1, 1), "租約 2025-1001", d, "2030-09-30", d, "公所", "承租隔壁合併經營")
        if r8:
            db.end_right(r8[0]["right_id"], d, "公所", "出租給鄰地")
        db.merge_parcels([p7, p8], nid, d, "公所")
        self.truth[nid] = unary_union([self.truth[p7], self.truth[p8]])
        self.ev(d, "坵塊合併", f"頂坑段 7、8 號由同一人經營，{p7}、{p8} 合併為 {nid}", [p7, p8, nid])

        # 2025-11-20 竹崎段地籍圖重測
        d = self.at("2025-11-20")
        for lot in self.lots["A"]:
            db.resurvey_lot(lot, self.lot_true[lot], d, "地政資料匯入", "地籍圖重測 2025")
        self.ev(d, "地籍圖重測", "竹崎段完成重測，改為數值地籍；地號與坵塊重新對應，對位偏移標記消失", self.lots["A"])

        # 未申報的擴耕：實地範圍變大，但系統沒有更新（品質檢查會抓到）
        for lot, dx in (("NP-105", 0), ("DK-11", 0)):
            pid = next(l["parcel_id"] for l in db.rows_at("lot_parcel", d) if l["lot_id"] == lot)
            t = self.truth[pid].bounds
            self.truth[pid] = box(t[0], t[1], t[2], t[3]).union(box(t[2], t[1], t[2] + 9, t[3]))   # 越過田埂多種 9 公尺
        self.ev("2025-12-15", "（實地）擴耕未登錄", "內埔段 105、頂坑段 11 實地多種了約 9 公尺寬，系統沒有更新", [])

        # 2026 第一期：作物申報 → 農民登錄 → 公所確認
        self.declare_season("2026-1", self.at("2026-01-10"))
        self.register_season("2026-1")

        # 觀測時序
        self.observations()

        # 2026-03-01 年度品質檢查
        d = self.at("2026-03-01")
        current = [r["parcel_id"] for r in db.rows_at("parcels", d)]
        sample = sorted(self.rng.sample(current, 30))
        def measure(pid):
            g = self.truth[pid]
            inel = [r for r in db.rows_at("ineligible", d)]
            from . import gpkg
            cut = unary_union([gpkg.from_blob(r["geom"]) for r in inel])
            return g.difference(cut).area + self.rng.gauss(0, 15)
        summary = db.run_qa(2026, sample, measure, d, "品質檢查小組")
        self.ev(d, "年度品質檢查", f"抽 {summary['sample']} 塊，以航照重新量測；面積超過容許差 {summary['area_fail']} 塊", sample)
        db.commit()
        return self

    def lock_season(self, season, d, frac):
        db = self.db
        self.at(d)
        n = 0
        for p in db.rows_at("parcels", d):
            if self.rng.random() > frac:
                continue
            if db._crop_at(p["parcel_id"], season, d) is None:
                continue
            db.lock_baseline(p["parcel_id"], season, "依套疊結果確認", d, "公所")
            n += 1
        self.ev(d, f"{season} 災前基準鎖定", f"{n} 塊田完成確認並鎖定（快照＋雜湊，災後不再量面積）")

    def register_season(self, season):
        db = self.db
        rng = self.rng
        d0 = date(2026, 1, 12)
        regs = []
        for i, p in enumerate(db.rows_at("parcels", d0.isoformat())):
            pid = p["parcel_id"]
            d = (d0 + timedelta(days=rng.randint(0, 20))).isoformat()
            self.at(d)
            links = sorted(db.allocate(pid, d), key=lambda l: -l["share"])
            for j, l in enumerate(links):
                if l["share"] < 0.2:
                    continue          # 偏移造成的小片重疊不另外登錄
                rs = db.rights_at(l["lot_id"], d) or db.rights_at(l["lot_id"], "2025-12-31")
                if not rs:
                    continue
                r = rs[0]
                major = sum(x["share"] for x in links if x["share"] >= 0.2)
                declared = p["eff_area_m2"] * l["share"] / major          # 農民申報的是整塊田，跨地號時依比例分
                if l["lot_id"] == "NP-102":
                    declared *= 1.12                                      # 報得比實際種的多
                crop = db._crop_at(pid, season, d)
                reg_id = f"G-{season}-{pid}-{j + 1}"
                db.submit_registration(reg_id, r["operator_code"], l["lot_id"], pid, declared, crop["crop"] if crop else "未申報",
                                       rng.choice(["農糧署申報", "產銷履歷", "現場照片"]), d, "農民（App）")
                regs.append((reg_id, d))
        blocked = sum(1 for r in db.rows_at("registrations", "2026-02-10") if r["status"] == "系統已擋下")
        # 公所確認：待確認的大多直接依套疊確認；範圍需確認的部分修正或排定到場
        for reg_id, d in regs:
            r = db.current("registrations", reg_id)
            dd = (date.fromisoformat(d) + timedelta(days=rng.randint(3, 15))).isoformat()
            self.at(dd)
            if r["status"] == "待確認" and rng.random() < 0.9:
                db.confirm_registration(reg_id, "依套疊結果確認", season, dd, "公所")
            elif r["status"] == "範圍需確認" and rng.random() < 0.5:
                db.confirm_registration(reg_id, rng.choice(["修正範圍後確認", "排定到場確認"]), season, dd, "公所")
        st = {}
        for r in db.rows_at("registrations", "2026-03-31"):
            st[r["status"]] = st.get(r["status"], 0) + 1
        self.ev("2026-01-12", "2026-1 農民登錄", "登錄 " + str(len(regs)) + " 筆；" + "、".join(f"{k} {v}" for k, v in sorted(st.items())) + "（截至 3 月底）")

    def observations(self):
        """每月一筆坵塊平均值（NDVI、雷達 VH）。雲量高的月份標為內插。"""
        db = self.db
        rows = []
        months = [date(2024, 1, 15) + timedelta(days=30.44 * i) for i in range(27)]
        pids = set()
        for m in months:
            for p in db.rows_at("parcels", m.isoformat()):
                pids.add(p["parcel_id"])
        for pid in sorted(pids):
            for m in months:
                ds = m.isoformat()
                p = db.current("parcels", pid, ds)
                if p is None:
                    continue
                season = f"{m.year}-{1 if m.month <= 7 else 2}"
                c = db._crop_at(pid, season, ds)
                crop = c["crop"] if c else self.parcel_crop.get(pid, "水稻")
                if crop in ("水稻", "蔬菜"):
                    # 一期 2–6 月、二期 8–11 月生長，其餘休耕
                    k = (m.month - 2) / 4.5 if 2 <= m.month <= 6 else ((m.month - 8) / 3.5 if 8 <= m.month <= 11 else -1)
                    ndvi = 0.2 + 0.62 * math.sin(math.pi * min(max(k, 0), 1) * 0.9 + 0.15) if k >= 0 else 0.2
                elif crop == "虱目魚":
                    ndvi = -0.25
                else:
                    ndvi = 0.68 + 0.08 * math.sin(2 * math.pi * m.month / 12)
                if m.year == 2025 and m.month == 7 and crop != "虱目魚":
                    ndvi -= 0.25 * self.rng.random()           # 颱風後
                cloud = min(1, max(0, self.rng.betavariate(1.2, 2.5) + (0.3 if m.month in (5, 6, 7, 8) else 0)))
                vh = -22 + 9 * max(ndvi, 0) + self.rng.gauss(0, 0.6)
                rows.append((pid, ds, "Sentinel-2/1 月合成", round(ndvi + self.rng.gauss(0, 0.03), 3), round(vh, 2), round(cloud, 2), int(cloud > 0.6)))
        db.con.executemany("INSERT INTO observations (parcel_id, date, sensor, ndvi, vh_db, cloud_frac, interpolated) VALUES (?,?,?,?,?,?,?)", rows)
