"""
下載研究區的 Sentinel-2 L2A（紅光 B04、近紅外 B08、場景分類 SCL），算 NDVI。
研究區跨 4 個圖幅（51QTG、51QTF、50QRM、50QRL），每個日期把 4 塊拼起來。

執行：python fetch_s2.py   （需網路，約 1–2 分鐘，存到 real_data/danas_s2.npz）
"""
import json
import os
import urllib.request

import numpy as np
import tifffile

H = {"User-Agent": "skyaide/1.0"}
BBOX = [120.10, 23.25, 120.25, 23.40]
SIZE = 1600                                   # 與 Sentinel-1 同一個網格
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "real_data")
DATES = {                                     # 名稱: 日期
    "y2025_pre": "2025-06-28",                # 災前（颱風 7/6 登陸）
    "y2025_post": "2025-07-18",               # 災後，颱風後雲最少的一張
    "y2024_pre": "2024-07-03",                # 去年同期（基準）
    "y2024_post": "2024-07-18",
}
os.makedirs(OUT, exist_ok=True)


def post(body):
    req = urllib.request.Request("https://planetarycomputer.microsoft.com/api/stac/v1/search",
                                 data=json.dumps(body).encode(),
                                 headers={**H, "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def crop(item_id, asset):
    b = ",".join(map(str, BBOX))
    url = (f"https://planetarycomputer.microsoft.com/api/data/v1/item/bbox/{b}.tif"
           f"?collection=sentinel-2-l2a&item={item_id}&assets={asset}"
           f"&width={SIZE}&height={SIZE}&resampling=nearest")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=120) as r:
                raw = r.read()
            break
        except Exception as e:
            print("    重試", attempt + 1, e)
    path = os.path.join(OUT, "_tmp.tif")
    open(path, "wb").write(raw)
    a = tifffile.imread(path)
    os.remove(path)
    return a[..., 0].astype("float32"), a[..., 1] > 0      # 數值、有效遮罩


arrs, meta = {}, {}
for name, day in DATES.items():
    items = post({"collections": ["sentinel-2-l2a"], "bbox": BBOX,
                  "datetime": f"{day}T00:00:00Z/{day}T23:59:59Z", "limit": 10})["features"]
    red = np.full((SIZE, SIZE), np.nan, "float32")
    nir = red.copy()
    scl = np.zeros((SIZE, SIZE), "uint8")
    for it in items:
        r, m = crop(it["id"], "B04")
        n, _ = crop(it["id"], "B08")
        s, _ = crop(it["id"], "SCL")
        fill = m & np.isnan(red)                 # 還沒填到的像素才填
        red[fill], nir[fill], scl[fill] = r[fill], n[fill], s[fill]
    # 2022 年起的 L2A（處理版本 04.00 以後）數值含 +1000 偏移
    red, nir = (red - 1000) / 10000, (nir - 1000) / 10000
    ndvi = (nir - red) / np.maximum(nir + red, 1e-6)
    # SCL：3 雲影、8–10 雲與卷雲、0–1 無資料或飽和 → 不能用
    bad = np.isin(scl, [0, 1, 3, 8, 9, 10]) | np.isnan(ndvi)
    ndvi[bad] = np.nan
    arrs[f"{name}_ndvi"], arrs[f"{name}_scl"] = ndvi, scl
    meta[name] = {"date": day, "items": [it["id"] for it in items],
                  "可用比例": round(float(np.isfinite(ndvi).mean()), 3)}
    print(name, day, f"{len(items)} 個圖幅", f"可用（無雲）{np.isfinite(ndvi).mean():.0%}",
          f"NDVI 中位數 {np.nanmedian(ndvi):.2f}")

np.savez_compressed(os.path.join(OUT, "danas_s2.npz"), **arrs)
json.dump({"bbox": BBOX, "scenes": meta}, open(os.path.join(OUT, "scenes_s2.json"), "w"),
          ensure_ascii=False, indent=2)
print("完成")
