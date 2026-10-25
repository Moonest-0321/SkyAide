"""地塊資料查詢（命令列）

python query.py asof P001 2025-07-06       某塊田在某一天的狀態（範圍、地號對應、作物、經營人、災前基準）
python query.py history P001               某塊田（或地號、登錄編號）的所有異動
python query.py cap F001 ZQ-1 2026-01-15   某經營人在某地號的可申報上限（本筆面積 × 持分）
python query.py alloc P019 2025-07-06      判讀結果要怎麼分攤回各地號
python query.py verify                     查驗異動紀錄雜湊鏈與全部災前基準
python query.py --db 其他檔.gpkg ...
"""
import argparse
import json
import os

from lpis.core import ParcelDB

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser(description="地塊資料查詢")
    ap.add_argument("--db", default=os.path.join(HERE, "data", "parcels.gpkg"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("asof"); s.add_argument("parcel"); s.add_argument("date")
    s = sub.add_parser("history"); s.add_argument("id")
    s = sub.add_parser("cap"); s.add_argument("operator"); s.add_argument("lot"); s.add_argument("date")
    s = sub.add_parser("alloc"); s.add_argument("parcel"); s.add_argument("date")
    sub.add_parser("verify")
    a = ap.parse_args()
    db = ParcelDB(a.db)

    if a.cmd == "asof":
        r = db.as_of(a.parcel, a.date)
        if r is None:
            print(f"{a.date} 當天沒有坵塊 {a.parcel}（可能尚未建立、已分割或已合併），用 history 查它的異動。")
            return
        p = r["parcel"]
        print(f"坵塊 {a.parcel}（{a.date}）  第 {p['version']} 版，{p['valid_from']} 起生效")
        print(f"  土地使用 {p['land_use']}；總面積 {p['gross_area_m2']:.0f} m²，扣除不可申報 {p['ineligible_m2']:.0f} m²，有效種植 {p['eff_area_m2']:.0f} m²")
        print(f"  中心 TWD97 {p['center_x']:.1f}, {p['center_y']:.1f}／WGS84 {p['center_lat']:.6f}, {p['center_lon']:.6f}")
        print("  地號對應：")
        for l in r["links"]:
            lot = r["lots"].get(l["lot_id"], {})
            print(f"    {lot.get('section', '')} {lot.get('lot_no', l['lot_id'])}  佔本田 {l['share_of_parcel']:.1%}  {l['flag']}{'（圖解地籍）' if lot.get('graphic') else ''}")
        for c in r["crops"]:
            print(f"  作物 {c['season']}：{c['crop']}（{c['source']}，經營人 {c['operator_code']}）")
        for x in r["rights"]:
            print(f"  使用權 {x['lot_id']}：{x['operator_code']} {x['right_type']} {x['share_num']}/{x['share_den']}，{x['doc_from']}～{x['doc_to'] or '無期限'}")
        for b in r["baselines"]:
            print(f"  災前基準 {b['baseline_id']}：{b['locked_at']} 鎖定（{b['method']}），{b['eff_area_m2']:.0f} m²，查驗{'通過' if db.verify_baseline(b['baseline_id']) else '不符'}")
    elif a.cmd == "history":
        for h in db.history(a.id):
            print(f"{h['seq']:>4}  {h['at'][:10]}  {h['action']:<4} {h['table_name']:<18} {h['entity_id']:<22} 第{h['version']}版  {h['reason']}（{h['actor']}）")
    elif a.cmd == "cap":
        c = db.cap_area(a.operator, a.lot, a.date)
        print("沒有有效的使用權文件" if c is None else f"可申報上限 {c:.0f} m²")
    elif a.cmd == "alloc":
        print(json.dumps(db.allocate(a.parcel, a.date), ensure_ascii=False, indent=1))
    elif a.cmd == "verify":
        ok, bad = db.verify_log()
        print("異動紀錄雜湊鏈：" + ("完整" if ok else f"第 {bad} 筆起斷裂"))
        ids = [r[0] for r in db.con.execute("SELECT baseline_id FROM baselines")]
        badb = [i for i in ids if not db.verify_baseline(i)]
        print(f"災前基準 {len(ids)} 份，" + ("全部與鎖定時的雜湊相符" if not badb else f"不符：{', '.join(badb)}"))


if __name__ == "__main__":
    main()
