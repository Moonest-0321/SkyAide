"""
天相星 影像處理鏈：一鍵執行 S1 → S8，每一步寫入監看紀錄。

    python run.py                      用內建模擬資料跑一次（約 1 分鐘）
    python run.py --seed 11            換一組模擬地景
    python run.py --until S3-4         只跑到某一步

執行時打開 monitor.html 可以即時看每一步的狀態；跑完後也能回頭看任何一次的紀錄。
需要：numpy scipy scikit-learn lightgbm matplotlib cryptography
"""
import argparse
import json
import os
import sys
import time
import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from skyaide.monitor import Monitor, StopPipeline
from skyaide import (s1_ingest, s2_lock, p0_prepare, s3_1_preprocess, s3_2_parcel, s3_3_interpret, s3_4_loss,
                     s4_grade, s5_report, s6_deliver, s7_seal, s8_review)

STAGES = [
    ("S1", "資料輸入：登錄與檢核", "來源、產品編號、SHA-256、官方檢查碼；有效像素、數值範圍、網格；災前影像 ≤ 10 日", s1_ingest),
    ("S2", "計算環境鎖定", "凍結程式、參數與套件版本並記錄雜湊；只用通過前次評等的版本", s2_lock),
    ("P0", "準備期回溯：過去災害", "以過去災害的核定清冊訓練作物判釋與損失模型，並決定判讀元件能否支撐 A 級", p0_prepare),
    ("S3-1", "前處理", "雷達地形正規化、Lee 濾波、陰影疊置；光學 Cloud Score+ 去雲與植生指數；夜間燈光基準", s3_1_preprocess),
    ("S3-2", "坵塊化", "對位檢查與排除、內縮 10 米、每塊田一張時序表", s3_2_parcel),
    ("S3-3", "影像判讀", "淹水三法投票、倒伏、埋沒、植生、作物、魚塭與停電；熱區高解析影像", s3_3_interpret),
    ("S3-4", "損失區間", "半經驗損傷函數＋LightGBM 分位數堆疊，保形校準", s3_4_loss),
    ("S4", "案件分級", "先看證據（五項檢核、L1–L4、R1–R5），再看損失；A 達標、A 未達標、B 邊緣、C 缺失", s4_grade),
    ("S5", "存證報告簽發與通知", "固定格式序列化、SHA-256、數位簽章、時戳、查驗碼；依系統等級發通知", s5_report),
    ("S6", "交付公所", "依類別系統等級決定交付方式：丙不交、乙參考、甲參與判定", s6_deliver),
    ("S7", "批次封存與回填", "Merkle 根；現勘結果回填", s7_seal),
    ("S8", "災後檢討與評等", "逐類別兩種 A 精確度、判定正確率、直接判定率、B 邊緣確認率與下界；下一場等級", s8_review),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="synthetic")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--until", default=None)
    a = ap.parse_args()

    params = json.load(open(os.path.join(ROOT, "config", "params.json"), encoding="utf-8"))
    if a.source == "synthetic":
        from skyaide.sources.synthetic import SyntheticSource
        src = SyntheticSource(seed=a.seed)
    else:
        from skyaide.sources.planetary import PlanetarySource
        src = PlanetarySource()
    ev = src.event()
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + f"-{a.source}-{a.seed}"
    runs = os.path.join(ROOT, "runs")
    mon = Monitor(runs, run_id, dict(source=src.name, event=ev["name"], event_id=ev["id"], seed=a.seed,
                                     aoi=ev["aoi"], alert=ev["alert"], radar_arrival=ev["radar_arrival"],
                                     stages=[dict(key=k, title=t, spec=s) for k, t, s, _ in STAGES],
                                     sla_hours=params["sla_hours"]))
    ctx = dict(source=src, params=params, event=ev, root=ROOT, run_dir=mon.run_dir, mon=mon,
               truth=src.truth(), quiet=False)
    if ctx["truth"]:
        mon.data["truth"] = {str(k): v for k, v in ctx["truth"].items()}      # 模擬才有，監看畫面用來對答案
    print(f"執行 {run_id}，監看紀錄：{os.path.join('runs', run_id)}")
    t0 = time.time()
    try:
        for key, title, spec, mod in STAGES:
            print(f"  {key} {title} …", flush=True)
            with mon.stage(key, title, spec) as st:
                mod.run(ctx, st)
            if a.until and key == a.until:
                break
        mon.finish("done")
        print(f"完成，{time.time() - t0:.1f} 秒")
    except StopPipeline as e:
        mon.finish("stopped", str(e))
        print("停止：", e)
    except Exception as e:
        mon.finish("error", f"{type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    main()
