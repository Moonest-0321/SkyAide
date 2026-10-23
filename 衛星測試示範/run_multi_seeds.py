"""換 10 個不同的工況（不同地形、不同災損分布）重跑，看指標是否穩定。"""
import numpy as np
import skyaide_demo as s


def iou(a, b):
    return (a & b).sum() / max(1, (a | b).sum())


res, ious = [], {k: [] for k in ("otsu", "change", "anomaly", "vote")}
for seed in range(200, 210):
    sc = s.simulate_scene(seed)
    maps, rows = s.analyse(sc)
    for r, p in zip(rows, sc.parcels):
        r["true_loss"], r["crop"], r["kind"] = p["true_loss"], p["crop"], p["kind"]
    s.classify_parcels(rows)
    ponds, _ = s.classify_ponds(sc, maps)
    res.append(s.evaluate(rows, ponds))
    truth = sc.truth_flood & ~maps["perm_water"]
    for k in ("otsu", "change", "anomaly"):
        ious[k].append(iou(maps[k], truth))
    ious["vote"].append(iou(maps["flood"], truth))

for k in ["A級精確度", "B級精確度", "申請案件C級比例", "區間覆蓋率", "中位數絕對誤差",
          "作物判釋準確率", "魚塭A級精確度", "申請魚塭C級比例"]:
    v = np.array([r[k] for r in res], float)
    print(f"{k}: 平均 {np.nanmean(v):.3f}｜最低 {np.nanmin(v):.3f}｜最高 {np.nanmax(v):.3f}")
print("A", sum(r["A件數"] for r in res), "B", sum(r["B件數"] for r in res), "C", sum(r["C件數"] for r in res))
print("淹水像素 IoU：", {k: round(float(np.mean(v)), 3) for k, v in ious.items()})
