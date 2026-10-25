"""
下載颱風前一整年的 Sentinel-1（軌道 105，研究區裁切），給作物判釋用。
2024-07-01 ～ 2025-07-05，每 12 天取一期（同軌道），VV、VH。
濾波後轉 dB、存 float16，節省空間。

執行：python fetch_s1_year.py   （需網路，約 5–10 分鐘，存到 real_data/s1_year.npz）
"""
import json
import os
import urllib.request
from datetime import datetime

import numpy as np
import tifffile

import skyaide_demo as sky

H = {"User-Agent": "skyaide/1.0"}
BBOX = [120.10, 23.25, 120.25, 23.40]
SIZE = 1600
ORBIT = 105
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "real_data")
TMP = os.path.join(OUT, "_tmp_year.tif")


def post(body):
    req = urllib.request.Request("https://planetarycomputer.microsoft.com/api/stac/v1/search",
                                 data=json.dumps(body).encode(),
                                 headers={**H, "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def crop(item_id, band):
    b = ",".join(map(str, BBOX))
    url = (f"https://planetarycomputer.microsoft.com/api/data/v1/item/bbox/{b}.tif"
           f"?collection=sentinel-1-rtc&item={item_id}&assets={band}&width={SIZE}&height={SIZE}")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=180) as r:
                open(TMP, "wb").write(r.read())
            a = tifffile.imread(TMP)
            return np.where(a[..., 1] > 0, a[..., 0], np.nan).astype("float32")
        except Exception as e:
            print("    重試", attempt + 1, e)
    raise RuntimeError("下載失敗")


items = post({"collections": ["sentinel-1-rtc"], "bbox": BBOX,
              "datetime": "2024-07-01/2025-07-05", "limit": 200})["features"]
items = sorted([f for f in items if f["properties"].get("sat:relative_orbit") == ORBIT],
               key=lambda f: f["properties"]["datetime"])
# 每 12 天取一期：同一天只留一張，且與上一期相隔至少 11 天
picked, last = [], None
for f in items:
    t = datetime.fromisoformat(f["properties"]["datetime"].replace("Z", "+00:00"))
    if last is None or (t - last).days >= 11:
        picked.append(f); last = t
print(f"同軌道影像 {len(items)} 張，取 {len(picked)} 期")

vv, vh, dates = [], [], []
for i, f in enumerate(picked):
    d = f["properties"]["datetime"][:10]
    a_vv = crop(f["id"], "vv"); a_vh = crop(f["id"], "vh")
    vv.append(sky.to_db(sky.lee_filter(np.nan_to_num(a_vv, nan=1e-4))).astype("float16"))
    vh.append(sky.to_db(sky.lee_filter(np.nan_to_num(a_vh, nan=1e-4))).astype("float16"))
    dates.append(d)
    print(f"  {i + 1}/{len(picked)} {d}")
if os.path.exists(TMP):
    os.remove(TMP)
np.savez_compressed(os.path.join(OUT, "s1_year.npz"), vv=np.stack(vv), vh=np.stack(vh), dates=np.array(dates))
print("完成", np.stack(vv).shape)
