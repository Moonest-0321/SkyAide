"""下載研究區 Sentinel-2 真彩色影像（visual / TCI，像照片），拼接 4 個圖幅。"""
import json, os, urllib.request
import numpy as np, tifffile

H = {"User-Agent": "skyaide/1.0"}
BBOX = [120.10, 23.25, 120.25, 23.40]
SIZE = 1600
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "real_data")
DATES = {"tc_pre": "2025-06-15", "tc_post": "2025-07-18"}


def post(body):
    req = urllib.request.Request("https://planetarycomputer.microsoft.com/api/stac/v1/search",
                                 data=json.dumps(body).encode(),
                                 headers={**H, "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def crop(item_id, asset):
    b = ",".join(map(str, BBOX))
    url = (f"https://planetarycomputer.microsoft.com/api/data/v1/item/bbox/{b}.tif"
           f"?collection=sentinel-2-l2a&item={item_id}&assets={asset}&width={SIZE}&height={SIZE}")
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=120) as r:
                raw = r.read(); break
        except Exception as e:
            print("  重試", i + 1, e)
    p = os.path.join(OUT, "_tmp.tif"); open(p, "wb").write(raw)
    a = tifffile.imread(p); os.remove(p)
    return a


out = {}
for name, day in DATES.items():
    items = post({"collections": ["sentinel-2-l2a"], "bbox": BBOX,
                  "datetime": f"{day}T00:00:00Z/{day}T23:59:59Z", "limit": 10})["features"]
    rgb = np.zeros((SIZE, SIZE, 3), "uint8"); filled = np.zeros((SIZE, SIZE), bool)
    for it in items:
        a = crop(it["id"], "visual")              # (H, W, 4)：R、G、B、遮罩
        m = (a[..., 3] > 0) & ~filled
        rgb[m] = a[..., :3][m]; filled |= m
    out[name] = rgb
    print(name, day, len(items), "圖幅", "填滿", f"{filled.mean():.0%}")
np.savez_compressed(os.path.join(OUT, "truecolor.npz"), **out)
