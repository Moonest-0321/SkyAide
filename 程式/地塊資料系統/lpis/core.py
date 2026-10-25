"""
天相星 地塊資料系統（參考歐盟 LPIS 農地坵塊識別系統）

原則
  1. 不覆蓋，只新增版本：每筆資料有生效日（valid_from）與失效日（valid_to，空白表示現行）。
     任何日期都能查回「當時」的範圍、作物、經營人與地號對應（例如颱風當天）。
  2. 地號是地政的正式依據，坵塊是衛星判讀的單位，兩者以「地號↔坵塊對應」連起來，記錄重疊面積與比例。
  3. 災前基準一經公所確認即鎖定，存成不可修改的快照並記錄雜湊；災後不再量面積。
  4. 每一次異動寫入異動紀錄，每筆記下前一筆的雜湊（雜湊鏈），刪改任何一筆即可被發現。
"""
import hashlib
import json
import sqlite3
from datetime import date, datetime, timedelta

from shapely.geometry import shape, mapping
from shapely.ops import unary_union

from . import gpkg
from .tm2 import to_lonlat

VERSIONED = {
    # 表名: (主鍵欄, 是否有幾何, 說明)
    "lots": ("lot_id", True, "地號（地籍）"),
    "parcels": ("parcel_id", True, "坵塊（實際耕作範圍）"),
    "ineligible": ("feature_id", True, "不可申報範圍（農路、水塘、建物、防風林）"),
    "lot_parcel": ("link_id", False, "地號↔坵塊對應"),
    "operators": ("operator_code", False, "經營人"),
    "use_rights": ("right_id", False, "使用權"),
    "crop_declarations": ("decl_id", False, "作物申報"),
    "registrations": ("reg_id", False, "農民登錄（災前基準確認佇列）"),
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS lots (rid INTEGER PRIMARY KEY, lot_id TEXT NOT NULL, version INTEGER NOT NULL,
  county TEXT, town TEXT, section TEXT, subsection TEXT, lot_no TEXT, reg_area_m2 REAL, cadastre_version TEXT, graphic INTEGER,
  geom BLOB, valid_from TEXT NOT NULL, valid_to TEXT, recorded_at TEXT, recorded_by TEXT, reason TEXT);
CREATE TABLE IF NOT EXISTS parcels (rid INTEGER PRIMARY KEY, parcel_id TEXT NOT NULL, version INTEGER NOT NULL,
  land_use TEXT, gross_area_m2 REAL, ineligible_m2 REAL, eff_area_m2 REAL, perimeter_m REAL,
  center_x REAL, center_y REAL, center_lon REAL, center_lat REAL, source TEXT,
  geom BLOB, valid_from TEXT NOT NULL, valid_to TEXT, recorded_at TEXT, recorded_by TEXT, reason TEXT);
CREATE TABLE IF NOT EXISTS ineligible (rid INTEGER PRIMARY KEY, feature_id TEXT NOT NULL, version INTEGER NOT NULL,
  kind TEXT, area_m2 REAL, geom BLOB, valid_from TEXT NOT NULL, valid_to TEXT, recorded_at TEXT, recorded_by TEXT, reason TEXT);
CREATE TABLE IF NOT EXISTS lot_parcel (rid INTEGER PRIMARY KEY, link_id TEXT NOT NULL, version INTEGER NOT NULL,
  lot_id TEXT, parcel_id TEXT, overlap_m2 REAL, share_of_parcel REAL, share_of_lot REAL, flag TEXT,
  valid_from TEXT NOT NULL, valid_to TEXT, recorded_at TEXT, recorded_by TEXT, reason TEXT);
CREATE TABLE IF NOT EXISTS operators (rid INTEGER PRIMARY KEY, operator_code TEXT NOT NULL, version INTEGER NOT NULL,
  name TEXT, identity TEXT, contact TEXT, valid_from TEXT NOT NULL, valid_to TEXT, recorded_at TEXT, recorded_by TEXT, reason TEXT);
CREATE TABLE IF NOT EXISTS use_rights (rid INTEGER PRIMARY KEY, right_id TEXT NOT NULL, version INTEGER NOT NULL,
  operator_code TEXT, lot_id TEXT, right_type TEXT, share_num INTEGER, share_den INTEGER, doc_no TEXT, doc_from TEXT, doc_to TEXT,
  valid_from TEXT NOT NULL, valid_to TEXT, recorded_at TEXT, recorded_by TEXT, reason TEXT);
CREATE TABLE IF NOT EXISTS crop_declarations (rid INTEGER PRIMARY KEY, decl_id TEXT NOT NULL, version INTEGER NOT NULL,
  parcel_id TEXT, operator_code TEXT, season TEXT, crop TEXT, planting_date TEXT, source TEXT, has_proof INTEGER,
  valid_from TEXT NOT NULL, valid_to TEXT, recorded_at TEXT, recorded_by TEXT, reason TEXT);
CREATE TABLE IF NOT EXISTS registrations (rid INTEGER PRIMARY KEY, reg_id TEXT NOT NULL, version INTEGER NOT NULL,
  operator_code TEXT, lot_id TEXT, parcel_id TEXT, crop TEXT, proof_type TEXT, declared_area_m2 REAL, cap_area_m2 REAL,
  road_pond_pct REAL, status TEXT, notes TEXT, valid_from TEXT NOT NULL, valid_to TEXT, recorded_at TEXT, recorded_by TEXT, reason TEXT);
CREATE TABLE IF NOT EXISTS baselines (baseline_id TEXT PRIMARY KEY, parcel_id TEXT, season TEXT, locked_at TEXT, locked_by TEXT, method TEXT,
  crop TEXT, operator_code TEXT, eff_area_m2 REAL, lots_json TEXT, geom BLOB, content_hash TEXT, reg_id TEXT);
CREATE TABLE IF NOT EXISTS observations (obs_id INTEGER PRIMARY KEY, parcel_id TEXT, date TEXT, sensor TEXT,
  ndvi REAL, vh_db REAL, cloud_frac REAL, interpolated INTEGER);
CREATE TABLE IF NOT EXISTS qa_runs (qa_id TEXT PRIMARY KEY, year INTEGER, run_at TEXT, sample_n INTEGER, method TEXT, summary_json TEXT);
CREATE TABLE IF NOT EXISTS qa_results (qa_id TEXT, parcel_id TEXT, recorded_m2 REAL, measured_m2 REAL, diff_m2 REAL, tolerance_m2 REAL,
  pass INTEGER, issues TEXT);
CREATE TABLE IF NOT EXISTS change_log (seq INTEGER PRIMARY KEY, at TEXT, actor TEXT, action TEXT, table_name TEXT, entity_id TEXT,
  version INTEGER, valid_from TEXT, reason TEXT, content_hash TEXT, prev_hash TEXT, hash TEXT);
CREATE TRIGGER IF NOT EXISTS baselines_no_update BEFORE UPDATE ON baselines BEGIN SELECT RAISE(ABORT, '災前基準已鎖定，不可修改'); END;
CREATE TRIGGER IF NOT EXISTS baselines_no_delete BEFORE DELETE ON baselines BEGIN SELECT RAISE(ABORT, '災前基準已鎖定，不可刪除'); END;
CREATE TRIGGER IF NOT EXISTS log_no_update BEFORE UPDATE ON change_log BEGIN SELECT RAISE(ABORT, '異動紀錄不可修改'); END;
CREATE TRIGGER IF NOT EXISTS log_no_delete BEFORE DELETE ON change_log BEGIN SELECT RAISE(ABORT, '異動紀錄不可刪除'); END;
CREATE INDEX IF NOT EXISTS ix_lots ON lots(lot_id, valid_from);
CREATE INDEX IF NOT EXISTS ix_parcels ON parcels(parcel_id, valid_from);
CREATE INDEX IF NOT EXISTS ix_links ON lot_parcel(parcel_id, lot_id);
CREATE INDEX IF NOT EXISTS ix_obs ON observations(parcel_id, date);
"""

VIEWS = """
CREATE VIEW IF NOT EXISTS parcels_current AS SELECT * FROM parcels WHERE valid_to IS NULL;
CREATE VIEW IF NOT EXISTS lots_current AS SELECT * FROM lots WHERE valid_to IS NULL;
CREATE VIEW IF NOT EXISTS ineligible_current AS SELECT * FROM ineligible WHERE valid_to IS NULL;
"""

# 規則參數
RULES = dict(
    sliver_share=0.005,          # 地號↔坵塊重疊比例低於此值視為邊界誤差，不建立對應
    misreg_share=(0.02, 0.20),   # 坵塊有一部分落在另一筆地號，比例在此範圍 → 標記「疑似對位偏移」
    road_pond_review=0.10,       # 農路水塘佔比超過 10% → 範圍需確認
    qa_buffer_m=1.5,             # 年度品質檢查：面積容許差＝周長 × 1.5 公尺（歐盟 LPIS 品質檢查的作法）
    stale_years=4,               # 超過 4 年未更新的坵塊列入檢查
)


def _canon(o):
    return json.dumps(o, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(s):
    return hashlib.sha256(s.encode("utf-8") if isinstance(s, str) else s).hexdigest()


def _iso(d):
    return d if isinstance(d, str) else d.isoformat()


class ParcelDB:
    def __init__(self, path, create=False):
        self.path = path
        self.con = gpkg.connect(path)
        if create:
            gpkg.init(self.con)
            self.con.executescript(SCHEMA)
            self.con.executescript(VIEWS)
            for t, (_, has_geom, desc) in VERSIONED.items():
                gpkg.register(self.con, t, "features" if has_geom else "attributes", description=desc)
            for t, desc in (("parcels_current", "現行坵塊"), ("lots_current", "現行地號"), ("ineligible_current", "現行不可申報範圍")):
                gpkg.register(self.con, t, "features", description=desc)
            gpkg.register(self.con, "baselines", "features", description="災前基準（鎖定快照）")
            for t, desc in (("observations", "坵塊觀測時序"), ("qa_runs", "年度品質檢查"), ("qa_results", "品質檢查結果"), ("change_log", "異動紀錄（雜湊鏈）")):
                gpkg.register(self.con, t, "attributes", description=desc)
            self.con.commit()
        self.now = None           # 模擬時可指定「系統時間」

    # ------------------------------------------------------------ 共用：版本與異動紀錄
    def _stamp(self):
        return self.now or datetime.now().isoformat(timespec="seconds")

    def _log(self, actor, action, table, eid, version, valid_from, reason, content):
        prev = self.con.execute("SELECT hash FROM change_log ORDER BY seq DESC LIMIT 1").fetchone()
        prev = prev[0] if prev else "0" * 64
        body = dict(at=self._stamp(), actor=actor, action=action, table=table, entity=eid, version=version,
                    valid_from=valid_from, reason=reason, content_hash=_sha(_canon(content)), prev=prev)
        h = _sha(_canon(body))
        self.con.execute("INSERT INTO change_log (at, actor, action, table_name, entity_id, version, valid_from, reason, content_hash, prev_hash, hash) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                         (body["at"], actor, action, table, eid, version, valid_from, reason, body["content_hash"], prev, h))

    def current(self, table, eid, at=None):
        key = VERSIONED[table][0]
        if at is None:
            return self.con.execute(f"SELECT * FROM {table} WHERE {key}=? AND valid_to IS NULL", (eid,)).fetchone()
        at = _iso(at)
        return self.con.execute(f"SELECT * FROM {table} WHERE {key}=? AND valid_from<=? AND (valid_to IS NULL OR valid_to>?)", (eid, at, at)).fetchone()

    def put(self, table, eid, fields, valid_from, actor, reason, geom=None):
        """新增一個版本：現行版本在 valid_from 失效，新版本自 valid_from 生效。"""
        key, has_geom, _ = VERSIONED[table]
        valid_from = _iso(valid_from)
        cur = self.current(table, eid)
        if cur is not None:
            if valid_from < cur["valid_from"]:
                raise ValueError(f"{table} {eid}：新版本生效日 {valid_from} 早於現行版本 {cur['valid_from']}")
            self.con.execute(f"UPDATE {table} SET valid_to=? WHERE rid=?", (valid_from, cur["rid"]))
        mx = self.con.execute(f"SELECT MAX(version) FROM {table} WHERE {key}=?", (eid,)).fetchone()[0]
        ver = (mx or 0) + 1
        row = dict(fields, **{key: eid, "version": ver, "valid_from": valid_from, "valid_to": None,
                              "recorded_at": self._stamp(), "recorded_by": actor, "reason": reason})
        if has_geom:
            row["geom"] = gpkg.to_blob(geom)
        cols = ",".join(row)
        self.con.execute(f"INSERT INTO {table} ({cols}) VALUES ({','.join('?' * len(row))})", list(row.values()))
        content = dict(fields, geom=geom.wkt if geom is not None else None)
        self._log(actor, "修正" if cur is not None else "新增", table, eid, ver, valid_from, reason, content)
        return ver

    def retire(self, table, eid, valid_to, actor, reason):
        """讓現行版本在 valid_to 失效（例如地號分割、坵塊合併後舊的不再使用）。"""
        cur = self.current(table, eid)
        if cur is None:
            return
        self.con.execute(f"UPDATE {table} SET valid_to=? WHERE rid=?", (_iso(valid_to), cur["rid"]))
        self._log(actor, "失效", table, eid, cur["version"], _iso(valid_to), reason, {})

    def commit(self):
        for t in ("lots", "parcels", "ineligible", "baselines"):
            gpkg.update_extent(self.con, t)
        self.con.commit()

    # ------------------------------------------------------------ 地號
    def add_lot(self, lot_id, attrs, geom, valid_from, actor, reason="匯入地籍"):
        attrs = dict(attrs)
        attrs.setdefault("reg_area_m2", round(geom.area, 2))
        return self.put("lots", lot_id, attrs, valid_from, actor, reason, geom)

    def subdivide_lot(self, lot_id, parts, at, actor, reason="地號分割"):
        """地號分割：舊地號失效，新地號生效，受影響的坵塊重新建立對應。"""
        old = self.current("lots", lot_id)
        self.retire("lots", lot_id, at, actor, reason)
        for new_id, g, lot_no in parts:
            attrs = {k: old[k] for k in ("county", "town", "section", "subsection", "graphic")}
            attrs.update(lot_no=lot_no, cadastre_version=old["cadastre_version"])
            self.add_lot(new_id, attrs, g, at, actor, f"{reason}（原 {old['lot_no']}）")
        for pid in self._parcels_touching(gpkg.from_blob(old["geom"]), at):
            self.relink(pid, at, actor, reason)

    def resurvey_lot(self, lot_id, geom, at, actor, cadastre_version, reason="地籍重測"):
        old = self.current("lots", lot_id)
        attrs = {k: old[k] for k in ("county", "town", "section", "subsection", "lot_no")}
        attrs.update(graphic=0, cadastre_version=cadastre_version, reg_area_m2=round(geom.area, 2))
        self.put("lots", lot_id, attrs, at, actor, reason, geom)
        for pid in self._parcels_touching(geom.union(gpkg.from_blob(old["geom"])), at):
            self.relink(pid, at, actor, reason)

    # ------------------------------------------------------------ 坵塊
    def _parcel_fields(self, geom, land_use, source, at):
        inel = [gpkg.from_blob(r["geom"]) for r in self.rows_at("ineligible", at)]
        cut = unary_union([g for g in inel if g.intersects(geom)]) if inel else None
        inel_area = geom.intersection(cut).area if cut is not None and not cut.is_empty else 0.0
        c = geom.centroid
        lon, lat = to_lonlat(c.x, c.y)
        return dict(land_use=land_use, gross_area_m2=round(geom.area, 2), ineligible_m2=round(inel_area, 2),
                    eff_area_m2=round(geom.area - inel_area, 2), perimeter_m=round(geom.length, 2),
                    center_x=round(c.x, 2), center_y=round(c.y, 2), center_lon=round(lon, 6), center_lat=round(lat, 6), source=source)

    def add_parcel(self, parcel_id, geom, land_use, at, actor, source="航照判釋", reason="新增坵塊"):
        ver = self.put("parcels", parcel_id, self._parcel_fields(geom, land_use, source, at), at, actor, reason, geom)
        self.relink(parcel_id, at, actor, reason)
        return ver

    def reshape_parcel(self, parcel_id, geom, at, actor, source, reason):
        cur = self.current("parcels", parcel_id)
        self.put("parcels", parcel_id, self._parcel_fields(geom, cur["land_use"], source, at), at, actor, reason, geom)
        self.relink(parcel_id, at, actor, reason)

    def split_parcel(self, parcel_id, parts, at, actor, reason="坵塊分割（分種不同作物）"):
        cur = self.current("parcels", parcel_id)
        self.retire("parcels", parcel_id, at, actor, reason)
        self._retire_links(parcel_id, at, actor, reason)
        for new_id, g in parts:
            self.add_parcel(new_id, g, cur["land_use"], at, actor, "公所修正", f"{reason}（原 {parcel_id}）")

    def merge_parcels(self, ids, new_id, at, actor, reason="坵塊合併（相鄰地號合併經營）"):
        geoms = [gpkg.from_blob(self.current("parcels", i)["geom"]) for i in ids]
        lu = self.current("parcels", ids[0])["land_use"]
        for i in ids:
            self.retire("parcels", i, at, actor, reason)
            self._retire_links(i, at, actor, reason)
        self.add_parcel(new_id, unary_union(geoms), lu, at, actor, "公所修正", f"{reason}（原 {'、'.join(ids)}）")

    def add_ineligible(self, feature_id, kind, geom, at, actor, reason="航照判釋"):
        self.put("ineligible", feature_id, dict(kind=kind, area_m2=round(geom.area, 2)), at, actor, reason, geom)

    def rows_at(self, table, at):
        at = _iso(at)
        return self.con.execute(f"SELECT * FROM {table} WHERE valid_from<=? AND (valid_to IS NULL OR valid_to>?)", (at, at)).fetchall()

    def _parcels_touching(self, geom, at):
        return [r["parcel_id"] for r in self.rows_at("parcels", at) if gpkg.from_blob(r["geom"]).intersects(geom)]

    # ------------------------------------------------------------ 地號↔坵塊對應
    def _retire_links(self, parcel_id, at, actor, reason):
        for r in self.con.execute("SELECT link_id FROM lot_parcel WHERE parcel_id=? AND valid_to IS NULL", (parcel_id,)).fetchall():
            self.retire("lot_parcel", r["link_id"], at, actor, reason)

    def relink(self, parcel_id, at, actor, reason="重新建立對應"):
        """以幾何重疊計算坵塊與地號的對應；低於 0.5% 視為邊界誤差。"""
        p = self.current("parcels", parcel_id, at)
        self._retire_links(parcel_id, at, actor, reason)
        if p is None:
            return []
        pg = gpkg.from_blob(p["geom"])
        links = []
        for lot in self.rows_at("lots", at):
            lg = gpkg.from_blob(lot["geom"])
            if not lg.intersects(pg):
                continue
            ov = lg.intersection(pg).area
            sp = ov / pg.area
            if sp < RULES["sliver_share"]:
                continue
            links.append((lot, ov, sp, ov / lg.area))
        lo, hi = RULES["misreg_share"]
        major = sum(1 for l in links if l[2] > hi)
        for lot, ov, sp, sl in links:
            flag = "疑似對位偏移" if (lo <= sp <= hi and lot["graphic"]) else ("跨地號" if major > 1 and sp > hi else "")
            self.put("lot_parcel", f"{lot['lot_id']}|{parcel_id}", dict(lot_id=lot["lot_id"], parcel_id=parcel_id, overlap_m2=round(ov, 2),
                     share_of_parcel=round(sp, 4), share_of_lot=round(sl, 4), flag=flag), at, actor, reason)
        return links

    def allocate(self, parcel_id, at):
        """判讀結果依面積比例分攤回各地號（表 32）。"""
        return [dict(lot_id=r["lot_id"], share=r["share_of_parcel"], area_m2=r["overlap_m2"])
                for r in self.rows_at("lot_parcel", at) if r["parcel_id"] == parcel_id]

    # ------------------------------------------------------------ 經營人、使用權、作物
    def add_operator(self, code, name, identity, at, actor, contact=""):
        return self.put("operators", code, dict(name=name, identity=identity, contact=contact), at, actor, "登錄經營人")

    def grant_right(self, right_id, operator, lot_id, right_type, share, doc_no, doc_from, doc_to, at, actor, reason="登錄使用權"):
        return self.put("use_rights", right_id, dict(operator_code=operator, lot_id=lot_id, right_type=right_type,
                        share_num=share[0], share_den=share[1], doc_no=doc_no, doc_from=_iso(doc_from), doc_to=_iso(doc_to) if doc_to else None),
                        at, actor, reason)

    def end_right(self, right_id, at, actor, reason):
        self.retire("use_rights", right_id, at, actor, reason)

    def declare_crop(self, decl_id, parcel_id, operator, season, crop, planting, source, has_proof, at, actor):
        return self.put("crop_declarations", decl_id, dict(parcel_id=parcel_id, operator_code=operator, season=season, crop=crop,
                        planting_date=_iso(planting) if planting else None, source=source, has_proof=int(has_proof)), at, actor, "作物申報")

    def rights_at(self, lot_id, at):
        at_s = _iso(at)
        return [r for r in self.rows_at("use_rights", at) if r["lot_id"] == lot_id and r["doc_from"] <= at_s and (r["doc_to"] is None or r["doc_to"] >= at_s)]

    def cap_area(self, operator, lot_id, at):
        """可申報上限＝本筆面積 × 持分（表 22）。沒有有效使用權回傳 None。"""
        lot = self.current("lots", lot_id, at)
        rs = [r for r in self.rights_at(lot_id, at) if r["operator_code"] == operator]
        if not lot or not rs:
            return None
        return round(lot["reg_area_m2"] * max(r["share_num"] / r["share_den"] for r in rs), 2)

    # ------------------------------------------------------------ 登錄與災前基準
    def submit_registration(self, reg_id, operator, lot_id, parcel_id, declared_m2, crop, proof_type, at, actor, partial=False):
        """農民登錄：系統先檢查，分成待確認、範圍需確認、系統已擋下（表 24 A）。"""
        cap = self.cap_area(operator, lot_id, at)
        p = self.current("parcels", parcel_id, at)
        rp = (p["ineligible_m2"] / p["gross_area_m2"]) if p and p["gross_area_m2"] else 0
        notes = []
        if cap is None:
            status = "系統已擋下"; notes.append("沒有有效的使用權文件")
        elif declared_m2 > cap + 0.5:
            status = "系統已擋下"; notes.append(f"申報 {declared_m2:.0f} m² 超過本筆面積 × 持分 {cap:.0f} m²")
        else:
            links = self.allocate(parcel_id, at)
            mis = [l for l in self.rows_at("lot_parcel", at) if l["parcel_id"] == parcel_id and l["flag"] == "疑似對位偏移"]
            lot = self.current("lots", lot_id, at)
            if rp > RULES["road_pond_review"]:
                notes.append(f"農路水塘佔 {rp:.0%}")
            if partial:
                notes.append("只租其中一部分")
            if mis or (lot and lot["graphic"]):
                notes.append("圖解地籍，地籍與航照可能偏移")
            if p and declared_m2 > p["eff_area_m2"] * 1.05:
                notes.append(f"申報大於有效種植面積 {p['eff_area_m2']:.0f} m²")
            status = "範圍需確認" if notes else "待確認"
        return self.put("registrations", reg_id, dict(operator_code=operator, lot_id=lot_id, parcel_id=parcel_id, crop=crop, proof_type=proof_type,
                        declared_area_m2=round(declared_m2, 2), cap_area_m2=cap, road_pond_pct=round(rp, 4), status=status,
                        notes="；".join(notes)), at, actor, "農民登錄送出")

    def confirm_registration(self, reg_id, method, season, at, actor):
        r = self.current("registrations", reg_id)
        if r["status"] == "系統已擋下":
            raise ValueError("系統已擋下的登錄不能確認，須先補件")
        bid = self.lock_baseline(r["parcel_id"], season, method, at, actor, reg_id=reg_id)
        fields = {k: r[k] for k in ("operator_code", "lot_id", "parcel_id", "crop", "proof_type", "declared_area_m2", "cap_area_m2", "road_pond_pct", "notes")}
        fields["status"] = "已鎖定"
        self.put("registrations", reg_id, fields, at, actor, f"公所確認（{method}），鎖定災前基準 {bid}")
        return bid

    def lock_baseline(self, parcel_id, season, method, at, actor, reg_id=None):
        """鎖定災前基準：把當時的範圍、有效面積、作物、經營人、地號對應存成不可修改的快照。"""
        p = self.current("parcels", parcel_id, at)
        crop = self._crop_at(parcel_id, season, at)
        links = self.allocate(parcel_id, at)
        snap = dict(parcel_id=parcel_id, season=season, eff_area_m2=p["eff_area_m2"], geom=gpkg.from_blob(p["geom"]).wkt,
                    crop=crop["crop"] if crop else None, operator=crop["operator_code"] if crop else None, lots=links)
        h = _sha(_canon(snap))
        bid = f"BL-{season}-{parcel_id}"
        if self.con.execute("SELECT 1 FROM baselines WHERE baseline_id=?", (bid,)).fetchone():
            return bid                       # 同一塊田跨兩筆地號，第二筆登錄確認時沿用已鎖定的基準
        self.con.execute("INSERT INTO baselines VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (bid, parcel_id, season, _iso(at), actor, method, snap["crop"], snap["operator"], p["eff_area_m2"],
                          _canon(links), p["geom"], h, reg_id))
        self._log(actor, "鎖定", "baselines", bid, 1, _iso(at), f"災前基準（{method}）", snap)
        return bid

    def _crop_at(self, parcel_id, season, at):
        rows = [r for r in self.rows_at("crop_declarations", at) if r["parcel_id"] == parcel_id and r["season"] == season]
        return rows[0] if rows else None

    def verify_baseline(self, bid):
        b = self.con.execute("SELECT * FROM baselines WHERE baseline_id=?", (bid,)).fetchone()
        snap = dict(parcel_id=b["parcel_id"], season=b["season"], eff_area_m2=b["eff_area_m2"], geom=gpkg.from_blob(b["geom"]).wkt,
                    crop=b["crop"], operator=b["operator_code"], lots=json.loads(b["lots_json"]))
        return _sha(_canon(snap)) == b["content_hash"]

    # ------------------------------------------------------------ 查詢
    def as_of(self, parcel_id, at):
        """某一天的完整狀態：範圍、面積、地號對應、作物、經營人與使用權、災前基準。"""
        p = self.current("parcels", parcel_id, at)
        if p is None:
            return None
        links = [dict(r) for r in self.rows_at("lot_parcel", at) if r["parcel_id"] == parcel_id]
        lots = {l["lot_id"]: dict(self.current("lots", l["lot_id"], at) or {}) for l in links}
        crops = [dict(r) for r in self.rows_at("crop_declarations", at) if r["parcel_id"] == parcel_id]
        rights = [dict(r) for l in links for r in self.rights_at(l["lot_id"], at)]
        base = [dict(r) for r in self.con.execute("SELECT * FROM baselines WHERE parcel_id=? AND locked_at<=? ORDER BY locked_at", (parcel_id, _iso(at)))]
        return dict(parcel={k: p[k] for k in p.keys() if k != "geom"}, geom=gpkg.from_blob(p["geom"]),
                    links=links, lots={k: {kk: v[kk] for kk in v if kk != "geom"} for k, v in lots.items()},
                    crops=crops, rights=rights, baselines=[{k: v for k, v in b.items() if k != "geom"} for b in base])

    def history(self, entity_id):
        return [dict(r) for r in self.con.execute("SELECT * FROM change_log WHERE entity_id=? OR entity_id LIKE ? OR entity_id LIKE ? ORDER BY seq",
                                                  (entity_id, f"%|{entity_id}", f"BL-%-{entity_id}"))]

    # ------------------------------------------------------------ 年度品質檢查（參考歐盟 LPIS QA）
    def run_qa(self, year, sample, measure, at, actor):
        """抽樣以航照重新量測坵塊面積，與帳上有效面積比較；容許差＝周長 × 1.5 m。
        另檢查：超過 3 年未更新、地號對應比例加總不為 1、疑似對位偏移。"""
        qa_id = f"QA-{year}"
        res = []
        stale_before = (date.fromisoformat(_iso(at)) - timedelta(days=365 * RULES["stale_years"])).isoformat()
        for pid in sample:
            p = self.current("parcels", pid, at)
            m = measure(pid)
            tol = p["perimeter_m"] * RULES["qa_buffer_m"]
            diff = m - p["eff_area_m2"]
            issues = []
            if abs(diff) > tol:
                issues.append(f"面積差 {diff:+.0f} m² 超過容許 {tol:.0f} m²")
            if p["valid_from"] < stale_before:
                issues.append(f"超過 {RULES['stale_years']} 年未更新")
            links = [r for r in self.rows_at("lot_parcel", at) if r["parcel_id"] == pid]
            s = sum(r["share_of_parcel"] for r in links)
            if abs(s - 1) > 0.02:
                issues.append(f"地號對應比例加總 {s:.2f}")
            if any(r["flag"] == "疑似對位偏移" for r in links):
                issues.append("疑似對位偏移")
            ok = abs(diff) <= tol
            res.append((qa_id, pid, p["eff_area_m2"], round(m, 2), round(diff, 2), round(tol, 2), int(ok), "；".join(issues)))
        self.con.executemany("INSERT INTO qa_results VALUES (?,?,?,?,?,?,?,?)", res)
        n_fail = sum(1 for r in res if not r[6])
        summary = dict(sample=len(res), area_fail=n_fail, area_pass_rate=round(1 - n_fail / max(len(res), 1), 3),
                       with_issues=sum(1 for r in res if r[7]))
        self.con.execute("INSERT INTO qa_runs VALUES (?,?,?,?,?,?)", (qa_id, year, _iso(at), len(res), "隨機抽樣，航照重新量測（容許差＝周長 × 1.5 m）", _canon(summary)))
        self._log(actor, "品質檢查", "qa_runs", qa_id, 1, _iso(at), "年度品質檢查", summary)
        return summary

    # ------------------------------------------------------------ 異動紀錄查驗
    def verify_log(self):
        prev = "0" * 64
        for r in self.con.execute("SELECT * FROM change_log ORDER BY seq"):
            body = dict(at=r["at"], actor=r["actor"], action=r["action"], table=r["table_name"], entity=r["entity_id"], version=r["version"],
                        valid_from=r["valid_from"], reason=r["reason"], content_hash=r["content_hash"], prev=prev)
            if r["prev_hash"] != prev or _sha(_canon(body)) != r["hash"]:
                return False, r["seq"]
            prev = r["hash"]
        return True, None
