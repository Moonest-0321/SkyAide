"""共用小工具：dB 換算、Lee 濾波、Otsu、Clopper–Pearson 下界、畫圖設定。"""
import hashlib
import json
import math

import numpy as np
from scipy import ndimage as ndi
from scipy.stats import beta

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

_CJK = ["Noto Sans CJK TC", "Noto Sans CJK JP", "PingFang TC", "Heiti TC", "Microsoft JhengHei", "Arial Unicode MS"]
_have = {f.name for f in font_manager.fontManager.ttflist}
plt.rcParams["font.family"] = [f for f in _CJK if f in _have] + ["DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.facecolor"] = "white"


def to_db(lin):
    return 10 * np.log10(np.maximum(lin, 1e-6))


def lee_filter(img, size=5, looks=4):
    """Lee 濾波：平坦處取平均去斑點，邊緣保留。輸入線性強度。"""
    mean = ndi.uniform_filter(img, size)
    sq = ndi.uniform_filter(img ** 2, size)
    var = np.maximum(sq - mean ** 2, 1e-12)
    cu2 = 1.0 / looks
    var_x = np.maximum((var - mean ** 2 * cu2) / (1 + cu2), 0)
    return mean + (var_x / var) * (img - mean)


def enl(img, mask):
    """等效視數：均勻區的 mean² / var，越大代表斑點越少。"""
    v = img[mask]
    return float(v.mean() ** 2 / max(v.var(), 1e-12))


def otsu(values, bins=256):
    v = values[np.isfinite(values)]
    hist, edges = np.histogram(v, bins=bins)
    c = (edges[:-1] + edges[1:]) / 2
    w0 = np.cumsum(hist); w1 = w0[-1] - w0
    m0 = np.cumsum(hist * c) / np.maximum(w0, 1)
    m1 = (np.sum(hist * c) - np.cumsum(hist * c)) / np.maximum(w1, 1)
    return float(c[np.argmax(w0 * w1 * (m0 - m1) ** 2)])


def cp_lower(k, n, conf=0.95):
    """Clopper–Pearson 單側下界。"""
    if n <= 0:
        return None
    if k <= 0:
        return 0.0
    return float(beta.ppf(1 - conf, k, n - k + 1))


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_payload(payload):
    """與資料來源相同的產品雜湊算法（陣列逐一雜湊）。"""
    h = hashlib.sha256()
    if isinstance(payload, dict):
        for k in sorted(payload, key=str):
            v = payload[k]
            h.update(str(k).encode())
            h.update(np.ascontiguousarray(v).tobytes() if isinstance(v, np.ndarray) else repr(v).encode())
    else:
        h.update(np.ascontiguousarray(payload).tobytes())
    return h.hexdigest()


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=_default)


def _default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if not math.isfinite(float(o)) else round(float(o), 6)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))


def fig(w=6.4, h=4.0):
    return plt.figure(figsize=(w, h))


def show(ax, img, title, cmap="gray", vmin=None, vmax=None, cbar=True):
    im = ax.imshow(img, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest")
    ax.set_title(title, fontsize=10)
    ax.set_xticks([]); ax.set_yticks([])
    if cbar:
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.02)
    return im


def parcel_map(label, values, default=np.nan):
    """把每坵塊的數值鋪回圖上（choropleth）。values: {id: value}"""
    lut = np.full(int(label.max()) + 1, default, dtype="float64")
    for k, v in values.items():
        if v is not None and k < len(lut):
            lut[int(k)] = v
    return lut[label]
