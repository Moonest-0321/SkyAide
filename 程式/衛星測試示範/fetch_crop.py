"""用 Planetary Computer 的裁切服務，只抓研究區那一塊的 Sentinel-1 RTC（線性 γ0）。"""
import json
import os
import urllib.request

import numpy as np
import tifffile

H = {"User-Agent": "skyaide/1.0"}
BBOX = [120.10, 23.25, 120.25, 23.40]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "real_data")
os.makedirs(OUT, exist_ok=True)


def post(body):
    req = urllib.request.Request("https://planetarycomputer.microsoft.com/api/stac/v1/search",
                                 data=json.dumps(body).encode(),
                                 headers={**H, "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def crop(item_id, band, path):
    b = ",".join(map(str, BBOX))
    url = (f"https://planetarycomputer.microsoft.com/api/data/v1/item/bbox/{b}.tif"
           f"?collection=sentinel-1-rtc&item={item_id}&assets={band}&width=1600&height=1600")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=120) as r:
                open(path, "wb").write(r.read())
            break
        except Exception as e:
            print("  重試", attempt + 1, e)
    a = tifffile.imread(path)
    data, mask = a[..., 0], a[..., 1]
    data = np.where(mask > 0, data, np.nan).astype("float32")
    return data


post_item = post({"collections": ["sentinel-1-rtc"], "bbox": BBOX,
                  "datetime": "2025-07-07/2025-07-14", "limit": 5})["features"][0]
orbit = post_item["properties"]["sat:relative_orbit"]
pre = [f for f in post({"collections": ["sentinel-1-rtc"], "bbox": BBOX,
                        "datetime": "2025-06-01/2025-07-05", "limit": 20})["features"]
       if f["properties"]["sat:relative_orbit"] == orbit]
pre = sorted(pre, key=lambda f: f["properties"]["datetime"])[-6:]

arrs = {}
dates = {}
for tag, it in [("post", post_item)] + [(f"pre{i}", f) for i, f in enumerate(pre)]:
    for band in ("vv", "vh"):
        arrs[f"{tag}_{band}"] = crop(it["id"], band, f"{OUT}/{tag}_{band}.tif")
    dates[tag] = {"id": it["id"], "datetime": it["properties"]["datetime"]}
    print(tag, it["properties"]["datetime"][:10], arrs[f"{tag}_vv"].shape,
          "有效像素", f"{np.isfinite(arrs[f'{tag}_vv']).mean():.0%}")

np.savez_compressed(f"{OUT}/danas_s1.npz", **arrs)
json.dump({"bbox": BBOX, "orbit": orbit, "scenes": dates}, open(f"{OUT}/scenes.json", "w"),
          ensure_ascii=False, indent=2)
print("完成")
