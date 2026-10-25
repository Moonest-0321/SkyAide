"""
真實資料來源（接口預留）。

建議做法：
  S1_GRD   Microsoft Planetary Computer `sentinel-1-grd`（或 Copernicus Data Space），用官方產品編號與檢查碼登錄
  S1_COH   需 SLC 影像自行計算（SNAP / ISCE），或採購商業產品
  S2_L2A   Planetary Computer `sentinel-2-l2a`；Cloud Score+ 目前在 Google Earth Engine，PC 上可先用 SCL 代替並在監看註明
  DEM      Planetary Computer `cop-dem-glo-30`
  VIIRS    NASA LAADS VNP46A2（需帳號）
  CADASTRE、LANDUSE、DECLARE、APP_PHOTO、HISTORY 由試辦機關介接（構想書 三、4(13)）
  HR       福衛八號由國家太空中心或經銷商交付

`程式/衛星測試示範/fetch_crop.py`、`fetch_s2.py`、`fetch_s1_year.py` 已示範從 Planetary Computer 下載丹娜絲的 Sentinel-1／2。
"""
from .base import Source


class PlanetarySource(Source):
    name = "planetary"

    def __init__(self, *a, **kw):
        raise NotImplementedError("真實資料來源尚未接上，請先用 --source synthetic。說明見本檔開頭。")
