"""
天相星函式練習：一次只看一個函式
================================

執行：python tutorial.py
每一段都用很小的假資料，印出「給了什麼、拿到什麼」。
看懂之後，可以改裡面的數字，看結果怎麼變。
"""
import numpy as np

import skyaide_demo as sky

np.set_printoptions(precision=1, suppress=True, linewidth=120)
rng = np.random.default_rng(0)


def title(t):
    print("\n" + "=" * 60 + f"\n{t}\n" + "=" * 60)


# ------------------------------------------------------------
title("1. to_db：線性強度 → dB")
# 雷達原始值是線性強度，數字很小又差很多倍，換成 dB 比較好比較
lin = np.array([0.001, 0.01, 0.1, 1.0])
print("線性強度：", [f"{v:g}" for v in lin])
print("dB       ：", sky.to_db(lin))
print("→ 每差 10 倍，dB 差 10。水面約 −20 dB，農田約 −10 dB。")


# ------------------------------------------------------------
title("2. lee_filter：去掉雷達的斑點雜訊")
# 做一張 8×8 的假影像：左半是田（−10 dB），右半是水（−20 dB）
truth_db = np.full((8, 8), -10.0)
truth_db[:, 4:] = -20.0
noisy = 10 ** (truth_db / 10) * rng.gamma(4, 1 / 4, size=truth_db.shape)   # 加雜訊（線性）
clean = sky.lee_filter(noisy, size=3)
print("加雜訊後（dB）：\n", sky.to_db(noisy))
print("Lee 濾波後（dB）：\n", sky.to_db(clean))
print("→ 同一塊地的數字變整齊了，田和水的交界還在。")
print("  注意：lee_filter 要吃「線性強度」，濾完再用 to_db 轉。")


# ------------------------------------------------------------
title("3. otsu：自動找出區分「水」和「陸地」的門檻")
values = np.concatenate([rng.normal(-20, 1.5, 500),     # 500 個水面像素
                         rng.normal(-9, 1.5, 1500)])    # 1500 個陸地像素
thr = sky.otsu(values)
print(f"自動門檻：{thr:.1f} dB")
print(f"低於門檻（判為水）的像素：{(values < thr).sum()} 個（實際 500 個）")
print("→ 沿海影像海面太多時，門檻會被拉高，所以真實資料另外設上限 −15 dB。")


# ------------------------------------------------------------
title("4. flood_vote：淹水三法投票")
# 6 期災前 + 1 期災後，影像 10×10，全部都是 dB
pre = np.full((6, 10, 10), -10.0) + rng.normal(0, 0.5, (6, 10, 10))   # (期數, 列, 欄)
pre[:, :, 8:] = -21.0                                                   # 右邊兩欄本來就是水（魚塭）
post = pre[-1].copy()
post[2:5, 2:5] = -20.0                                                  # 中間 3×3 淹水
post[7, 6] = -14.0                                                      # 一格變暗 4 dB，但沒暗到水面
flood, detail = sky.flood_vote(pre, post)
print("災後 VV（dB）：\n", post)
print(f"法 1 水體門檻 {detail['threshold_db']:.1f} dB，低於門檻：\n", detail["otsu"].astype(int))
print("法 2 比災前暗 3 dB：\n", detail["change"].astype(int))
print("法 3 低於災前 3 個標準差：\n", detail["anomaly"].astype(int))
print("投票結果（≥2 法同意）：\n", flood.astype(int))
print("災前就是水（不算淹水）：\n", detail["perm_water"].astype(int))
print("→ 右邊兩欄災前就是水，不算淹水。中間 3×3 三法都同意 → 淹水。")
print("  第 8 列那一格只暗了 4 dB，沒到水面那麼暗（法 1 沒抓到），")
print("  但法 2、法 3 都說它明顯變暗，兩票 → 也算淹水（可能是部分積水）。")


# ------------------------------------------------------------
title("5. lodging_map：倒伏（VH 變化很大）")
vh_pre = np.full((6, 6, 6), -16.0)
vh_post = vh_pre[-1].copy()
vh_post[:3, :3] = -12.0          # 左上 3×3 變亮 4 dB（水稻倒伏）
vh_post[4, 4] = -20.0            # 單獨一格變暗 4 dB（可能只是雜訊）
no_flood = np.zeros((6, 6), bool)
lodge, ratio = sky.lodging_map(vh_pre, vh_post, no_flood)
print("VH 災後 − 災前（dB）：\n", ratio)
print("判為倒伏：\n", lodge.astype(int))
print(f"→ 變化絕對值超過 {sky.LODGE_DB} dB 才算倒伏，變亮（水稻）、變暗（香蕉）都算。")
print("  之後用 3×3 中位數平滑：成片的倒伏會留下（邊角被修掉一點），")
print("  單獨一格的變化會被當成雜訊去掉。")


# ------------------------------------------------------------
title("6. buried_map：埋沒、流失（同調性下降）")
coh_pre = np.full((3, 3), 0.65)
coh_post = np.array([[0.62, 0.60, 0.20],
                     [0.63, 0.25, 0.22],
                     [0.61, 0.60, 0.64]])
buried = sky.buried_map(coh_pre, coh_post, np.zeros((3, 3), bool))
print("災後同調性：\n", coh_post)
print("判為埋沒：\n", buried.astype(int))
print(f"→ 降到 {sky.COH_BURIED} 以下、且比災前少 0.3 以上 → 地表整個變了（泥沙、沖走）。")


# ------------------------------------------------------------
title("7. inset_mask：坵塊向內縮一圈")
labels = np.array([[1, 1, 1, 1, 2, 2],
                   [1, 1, 1, 1, 2, 2],
                   [1, 1, 1, 1, 2, 2],
                   [1, 1, 1, 1, 2, 2]])
print("原本的坵塊編號：\n", labels)
print("內縮後：\n", sky.inset_mask(labels))
print("→ 邊緣像素可能混到田埂或隔壁田，先拿掉；坵塊 2 太窄，整塊被吃光 → 之後會列 C（小田）。")


# ------------------------------------------------------------
title("8. guess_crop：用災前時序猜作物（規則版）")
rice = {**{f"nd{k}": 0.40 + 0.08 * k for k in range(6)}, **{f"vv{k}": -12 for k in range(6)}}
banana = {**{f"nd{k}": 0.80 for k in range(6)}, **{f"vv{k}": -8 for k in range(6)}}
fruit = {**{f"nd{k}": 0.66 for k in range(6)}, **{f"vv{k}": -9.5 for k in range(6)}}
for name, r in [("NDVI 逐期上升", rice), ("VV 很亮、NDVI 穩定", banana), ("都普通", fruit)]:
    print(f"{name:12s} → {sky.CROPS[sky.guess_crop(r)]}")


# ------------------------------------------------------------
title("9. estimate_loss：估損失區間（第 10、50、90 百分位）")
cases = {
    "整塊淹水的水稻": dict(pred_crop=0, flood_frac=1.0, lodge_frac=0, buried_frac=0, ndvi_z=-10, cloud_frac=0),
    "一半倒伏的香蕉": dict(pred_crop=1, flood_frac=0, lodge_frac=0.5, buried_frac=0, ndvi_z=-4, cloud_frac=0),
    "完全沒事的果樹": dict(pred_crop=2, flood_frac=0, lodge_frac=0, buried_frac=0, ndvi_z=0.3, cloud_frac=0),
    "被雲遮、只有一點淹水": dict(pred_crop=0, flood_frac=0.2, lodge_frac=0, buried_frac=0, ndvi_z=np.nan, cloud_frac=1),
}
for name, r in cases.items():
    lo, mid, hi = sky.estimate_loss(r)
    print(f"{name:12s} → {lo:.0%} ～ {hi:.0%}（中間 {mid:.0%}）")


# ------------------------------------------------------------
title("10. three_gates：三道關卡 → A／B／C")
base = dict(n_pix=200, misregistered=False, applied=True, pred_crop=0, declared_crop=0,
            flood_frac=0, lodge_frac=0, buried_frac=0, ndvi_z=0.0, cloud_frac=0)
tests = {
    "淹水、區間 80–100%": dict(flood_frac=1.0, ndvi_z=-10, q10=0.80, q90=1.00),
    "沒事、沒申請": dict(applied=False, q10=0.0, q90=0.07),
    "沒事、但有申請": dict(q10=0.0, q90=0.07),
    "區間 10–40%（跨 20%）": dict(lodge_frac=0.3, ndvi_z=-4, q10=0.10, q90=0.40),
    "淹水但申報作物不同": dict(flood_frac=1.0, ndvi_z=-10, q10=0.80, q90=1.00, declared_crop=1),
    "太小的田": dict(n_pix=3, flood_frac=1.0, ndvi_z=-10, q10=0.80, q90=1.00),
}
for name, t in tests.items():
    grade, why = sky.three_gates({**base, **t})
    print(f"{name:16s} → {grade}｜{'；'.join(why)}")


# ------------------------------------------------------------
title("11. 整條流程：模擬一個場景 → 判讀 → 分級")
sc = sky.simulate_scene(seed=7)           # 換 seed 就是另一個工況
maps, rows = sky.analyse(sc)               # 前處理＋判讀＋坵塊特徵
sky.classify_parcels(rows)                 # 作物、損失區間、三道關卡
grades = [r["grade"] for r in rows]
print(f"坵塊 {len(rows)} 個：A {grades.count('A')}、B {grades.count('B')}、C {grades.count('C')}")
r = rows[0]
print(f"第 1 塊：淹水 {r['flood_frac']:.0%}、倒伏 {r['lodge_frac']:.0%}、"
      f"損失 {r['q10']:.0%}～{r['q90']:.0%} → {r['grade']}（{'；'.join(r['reasons'])}）")
print("→ 想看圖、CSV、存證報告，直接跑 python skyaide_demo.py。")

print("\n練習完畢。可以試著改：LODGE_DB、COH_BURIED、GATE_A_Q10 這些門檻，看分級怎麼變。")
