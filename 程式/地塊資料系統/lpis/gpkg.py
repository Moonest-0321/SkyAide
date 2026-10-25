"""GeoPackage（OGC 標準）讀寫的最小實作：只用 Python 內建 sqlite3 與 shapely。
QGIS、ArcGIS 都能直接打開 .gpkg 檔看圖層與屬性。"""
import sqlite3
import struct

import shapely
from shapely import wkb

SRS_TWD97 = 3826
WKT_3826 = ('PROJCS["TWD97 / TM2 zone 121",GEOGCS["TWD97",DATUM["Taiwan_Datum_1997",SPHEROID["GRS 1980",6378137,298.257222101]],'
            'PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],PARAMETER["latitude_of_origin",0],'
            'PARAMETER["central_meridian",121],PARAMETER["scale_factor",0.9999],PARAMETER["false_easting",250000],PARAMETER["false_northing",0],'
            'UNIT["metre",1],AUTHORITY["EPSG","3826"]]')


def init(con):
    con.execute("PRAGMA application_id = 1196444487")       # 'GPKG'
    con.execute("PRAGMA user_version = 10300")
    con.executescript("""
    CREATE TABLE IF NOT EXISTS gpkg_spatial_ref_sys (srs_name TEXT NOT NULL, srs_id INTEGER PRIMARY KEY, organization TEXT NOT NULL,
        organization_coordsys_id INTEGER NOT NULL, definition TEXT NOT NULL, description TEXT);
    CREATE TABLE IF NOT EXISTS gpkg_contents (table_name TEXT PRIMARY KEY, data_type TEXT NOT NULL, identifier TEXT UNIQUE, description TEXT DEFAULT '',
        last_change DATETIME NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')), min_x DOUBLE, min_y DOUBLE, max_x DOUBLE, max_y DOUBLE, srs_id INTEGER);
    CREATE TABLE IF NOT EXISTS gpkg_geometry_columns (table_name TEXT NOT NULL, column_name TEXT NOT NULL, geometry_type_name TEXT NOT NULL,
        srs_id INTEGER NOT NULL, z TINYINT NOT NULL, m TINYINT NOT NULL, PRIMARY KEY (table_name, column_name));
    """)
    rows = [("Undefined cartesian SRS", -1, "NONE", -1, "undefined", None),
            ("Undefined geographic SRS", 0, "NONE", 0, "undefined", None),
            ("WGS 84 geodetic", 4326, "EPSG", 4326, 'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433],AUTHORITY["EPSG","4326"]]', None),
            ("TWD97 / TM2 zone 121", SRS_TWD97, "EPSG", 3826, WKT_3826, "臺灣地籍常用的平面座標")]
    con.executemany("INSERT OR IGNORE INTO gpkg_spatial_ref_sys VALUES (?,?,?,?,?,?)", rows)


def register(con, table, data_type="features", geom_col="geom", geom_type="POLYGON", description=""):
    con.execute("INSERT OR REPLACE INTO gpkg_contents (table_name, data_type, identifier, description, srs_id) VALUES (?,?,?,?,?)",
                (table, data_type, table, description, SRS_TWD97 if data_type == "features" else None))
    if data_type == "features":
        con.execute("INSERT OR REPLACE INTO gpkg_geometry_columns VALUES (?,?,?,?,0,0)", (table, geom_col, geom_type, SRS_TWD97))


def to_blob(geom, srs=SRS_TWD97):
    """shapely 幾何 → GeoPackage 幾何 BLOB（標頭＋外框＋WKB）。"""
    if geom is None:
        return None
    minx, miny, maxx, maxy = geom.bounds
    header = b"GP" + bytes([0, 0b00000011]) + struct.pack("<i", srs) + struct.pack("<4d", minx, maxx, miny, maxy)
    return header + shapely.to_wkb(geom, byte_order=1)


def from_blob(blob):
    if blob is None:
        return None
    flags = blob[3]
    env = (flags >> 1) & 0b111
    n = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}[env]
    return wkb.loads(bytes(blob[8 + n:]))


def update_extent(con, table):
    rows = con.execute(f"SELECT geom FROM {table} WHERE geom IS NOT NULL").fetchall()
    if not rows:
        return
    bs = [from_blob(r[0]).bounds for r in rows]
    con.execute("UPDATE gpkg_contents SET min_x=?, min_y=?, max_x=?, max_y=? WHERE table_name=?",
                (min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs), table))


def connect(path):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con
