"""產生示範資料庫 data/parcels.gpkg 與展示頁資料 viewer/data.js。

python build_demo.py            # 預設亂數種子
python build_demo.py --seed 3
"""
import argparse
import json
import os
import time

from lpis import gpkg
from lpis.simulate import Sim, X0, Y0

HERE = os.path.dirname(os.path.abspath(__file__))


def rings(g):
    """幾何 → 以農區左下角為原點的座標（公尺，取到 0.1）。"""
    polys = [g] if g.geom_type == "Polygon" else list(g.geoms)
    return [[[round(x - X0, 1), round(y - Y0, 1)] for x, y in p.exterior.coords] for p in polys]


def rows(con, sql, geom=False):
    out = []
    for r in con.execute(sql):
        d = dict(r)
        if "geom" in d:
            g = d.pop("geom")
            if geom and g is not None:
                d["shape"] = rings(gpkg.from_blob(g))
        d.pop("rid", None)
        out.append(d)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    path = os.path.join(HERE, "data", "parcels.gpkg")
    if os.path.exists(path):
        os.replace(path, path + ".old")
    t = time.time()
    sim = Sim(path, seed=a.seed).run()
    db = sim.db
    ok, bad = db.verify_log()
    con = db.con
    data = dict(
        built=time.strftime("%Y-%m-%d %H:%M"), seed=a.seed, origin=[X0, Y0],
        lots=rows(con, "SELECT * FROM lots ORDER BY lot_id, version", True),
        parcels=rows(con, "SELECT * FROM parcels ORDER BY parcel_id, version", True),
        ineligible=rows(con, "SELECT * FROM ineligible", True),
        links=rows(con, "SELECT * FROM lot_parcel"),
        operators=rows(con, "SELECT * FROM operators"),
        rights=rows(con, "SELECT * FROM use_rights"),
        crops=rows(con, "SELECT * FROM crop_declarations"),
        registrations=rows(con, "SELECT * FROM registrations ORDER BY reg_id, version"),
        baselines=rows(con, "SELECT * FROM baselines ORDER BY locked_at"),
        observations=rows(con, "SELECT parcel_id, date, ndvi, vh_db, cloud_frac, interpolated FROM observations ORDER BY parcel_id, date"),
        qa_runs=rows(con, "SELECT * FROM qa_runs"),
        qa_results=rows(con, "SELECT * FROM qa_results"),
        log=rows(con, "SELECT * FROM change_log ORDER BY seq"),
        events=sorted(sim.events, key=lambda e: e["date"]),
        baseline_ok={r["baseline_id"]: db.verify_baseline(r["baseline_id"]) for r in con.execute("SELECT baseline_id FROM baselines")},
        log_ok=ok,
    )
    os.makedirs(os.path.join(HERE, "viewer"), exist_ok=True)
    with open(os.path.join(HERE, "viewer", "data.js"), "w", encoding="utf-8") as f:
        f.write("window.LPIS = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n")
    if os.path.exists(path + ".old"):
        os.remove(path + ".old")
    n = lambda q: con.execute(q).fetchone()[0]
    print(f"完成（{time.time() - t:.1f} 秒）  {path}")
    print(f"  地號 {n('SELECT COUNT(*) FROM lots_current')} 筆（歷史版本共 {n('SELECT COUNT(*) FROM lots')}）")
    print(f"  坵塊 {n('SELECT COUNT(*) FROM parcels_current')} 塊（歷史版本共 {n('SELECT COUNT(*) FROM parcels')}）")
    print(f"  災前基準 {n('SELECT COUNT(*) FROM baselines')} 份；觀測 {n('SELECT COUNT(*) FROM observations')} 筆")
    print(f"  異動紀錄 {n('SELECT COUNT(*) FROM change_log')} 筆，雜湊鏈{'完整' if ok else f'第 {bad} 筆斷裂'}")
    for r in con.execute("SELECT status, COUNT(*) c FROM registrations WHERE valid_to IS NULL GROUP BY status"):
        print(f"  登錄 {r['status']} {r['c']}")
    print("  品質檢查", con.execute("SELECT summary_json FROM qa_runs").fetchone()[0])


if __name__ == "__main__":
    main()
