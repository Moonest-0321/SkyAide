"""
資料來源介面。處理鏈只透過這裡取得資料；換成真實影像時，實作一個同樣介面的類別即可，流程不用改。

產品種類（catalog 每一筆的 kind）：
  S1_GRD      Sentinel-1 GRD，VV、VH 線性 σ⁰（未做地形正規化），每期一筆
  S1_COH      Sentinel-1 干涉同調性（災前對、災後對）
  S2_L2A      Sentinel-2 L2A 地表反射率 B3、B4、B5、B8、B11，加逐像素清晰度（Cloud Score+ 的 cs）
  DEM         數值地形模型（公尺）與雷達入射角、觀測方位
  VIIRS       夜間燈光 VNP46A2，每日、約 500 米
  CADASTRE    地籍坵塊（標籤圖＋屬性：地號、登記面積、圖解或數值地籍）
  LANDUSE     國土利用調查（農地範圍）
  DECLARE     申報資料（申請、作物、面積、使用權、放養與收成申報）
  APP_PHOTO   農業部 App 照片的登錄資訊（拍攝方式、時間、座標、感知雜湊）
  HISTORY     平時累積的坵塊時序表（多年 NDVI、一年 VH）
  HR          熱區高解析影像（福衛八號等），需於判讀時下單，回傳後補登

每一筆產品：dict(id, kind, sensor, datetime, official_checksum, meta)
"""


class Source:
    name = "base"

    def event(self):
        """災害事件：id、名稱、類型、警報時間、雷達到站時間、公告日、範圍、像素大小。"""
        raise NotImplementedError

    def catalog(self):
        """可取得的產品清單。"""
        raise NotImplementedError

    def load(self, product):
        """讀取一筆產品，回傳 numpy 陣列或 dict。"""
        raise NotImplementedError

    def order_hr(self, parcel_ids):
        """熱區高解析影像下單。回傳新產品清單（可能部分取像失敗）。"""
        return []

    def categories(self):
        """類別（作物 × 災害類型）與目前系統等級。"""
        raise NotImplementedError

    def past_events(self):
        """準備期回溯用的過去災害（同介面的 Source 物件清單），其核定清冊作為訓練與校準資料。"""
        return []

    def approved_losses(self):
        """公所核定清冊（過去災害才有）：{坵塊編號: 核定損失率}。"""
        return {}

    def field_survey(self, parcel_ids):
        """現勘回填：公所到場的結果（模擬時由地真值加上現勘誤差產生）。"""
        return {}

    def truth(self):
        """地真值（只有模擬來源有，用來在監看畫面對答案）。真實來源回傳 None。"""
        return None
