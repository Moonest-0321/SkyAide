"""
天相星 SkyAide｜標準作業流程（SOP）原型：資料輸入 → 模型計算 → 輸出，附可信度與防偽
=====================================================================================

在 skyaide_demo.py 的判讀與分級之外，加上一層「作業紀錄」：

  S1 資料輸入登錄：每個輸入檔算 SHA-256、記錄來源與影像編號，做品質檢核
  S2 計算環境鎖定：程式碼、參數、套件版本各算雜湊，災害事件開始時凍結
  S3 模型計算：計算前重新比對輸入雜湊，不符即中止
  S4 可信度評定：每筆坵塊依五項檢核給「高／中／低」，並列出原因
  S5 存證輸出：報告以固定格式序列化 → 雜湊 → 數位簽章 → 時戳 → 寫入雜湊鏈日誌
  S6 公所判定：承辦人員的判定另行簽章，與系統判讀並列，不覆蓋
  S7 批次封存：同一批報告的雜湊組成 Merkle 樹，根雜湊交公所留存
  S8 災後品質評估：以法定抽查樣本與 C 級現勘結果評估各作物 A 級精確度，未達標者下次停判 A

所有步驟寫入 ledger.jsonl，每筆紀錄包含前一筆的雜湊，刪改任何一筆都會使後面的鏈結斷掉。

說明：
  - 影像為模擬資料（與 skyaide_demo.py 相同），真實資料時把 S1 的來源換成
    Copernicus／福衛八號的產品編號與官方檢查碼即可。
  - 金鑰在本機產生，僅供示範。正式系統由憑證機構簽發憑證（電子簽章法第 2 條的數位簽章），
    公所端用機關憑證；時戳改用 RFC 3161 時戳服務。

執行：python sop_pipeline.py      （輸出在 ./sop_output/）
需要：numpy scipy cryptography
"""

import hashlib
import json
import os
import platform
import shutil
import sys
import time
from datetime import datetime, timezone

import numpy as np
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

import skyaide_demo as s

SOP_VERSION = "skyaide-sop-0.1"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "sop_output")
EVENT_ID = "DANAS-2025-SIM"
EVENT_DATE = "2025-07-06"


# ---------------------------------------------------------------------
# 共用：固定格式序列化與雜湊
# ---------------------------------------------------------------------

def canon(obj):
    """固定格式：鍵排序、無多餘空白、UTF-8。同樣內容永遠得到同樣位元組。"""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------
# 金鑰與信任清單（示範）
# ---------------------------------------------------------------------

def load_or_make_key(path):
    if os.path.exists(path):
        with open(path, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)
    k = Ed25519PrivateKey.generate()
    with open(path, "wb") as f:
        f.write(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption()))
    return k


def pub_hex(k):
    return k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()


def keys(keydir):
    os.makedirs(keydir, exist_ok=True)
    ks = {name: load_or_make_key(os.path.join(keydir, f"{name}.pem"))
          for name in ("datacenter", "tsa", "office")}
    trust = {
        "datacenter": {"名稱": "天相星資料中心（示範金鑰）", "公鑰": pub_hex(ks["datacenter"])},
        "tsa": {"名稱": "時戳服務（示範金鑰，正式改用 RFC 3161）", "公鑰": pub_hex(ks["tsa"])},
        "office": {"名稱": "竹崎鄉公所農業課（示範金鑰，正式改用機關憑證）", "公鑰": pub_hex(ks["office"])},
    }
    with open(os.path.join(keydir, "trust_list.json"), "w", encoding="utf-8") as f:
        json.dump(trust, f, ensure_ascii=False, indent=2)
    return ks, trust


def sign(k, b):
    return k.sign(b).hex()


def verify_sig(pub_hex_, sig_hex, b):
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub_hex_)).verify(bytes.fromhex(sig_hex), b)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------
# 雜湊鏈日誌
# ---------------------------------------------------------------------

class Ledger:
    def __init__(self, path):
        self.path = path
        self.prev = "0" * 64
        self.seq = 0
        open(path, "w").close()

    def add(self, stage, actor, content):
        self.seq += 1
        e = {"序號": self.seq, "時間": now(), "階段": stage, "執行者": actor,
             "內容": content, "前一筆雜湊": self.prev}
        e["本筆雜湊"] = sha256(canon(e))
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
        self.prev = e["本筆雜湊"]
        return e["本筆雜湊"]


def merkle_root(hashes):
    level = [bytes.fromhex(h) for h in sorted(hashes)]
    if not level:
        return "0" * 64
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [hashlib.sha256(level[i] + level[i + 1]).digest() for i in range(0, len(level), 2)]
    return level[0].hex()


# ---------------------------------------------------------------------
# S1 資料輸入：把模擬工況存成「檔案」，之後一律從檔案讀
# ---------------------------------------------------------------------

LAYERS = ["parcel", "vv_pre", "vh_pre", "vv_post", "vh_post", "coh_pre", "coh_post", "ndvi_pre", "ndvi_post"]
SOURCE = {   # 模擬影像對應的產品類型；真實資料時填官方產品編號
    "parcel": ("地籍坵塊", "SIM-CADASTRE-v2025.1"),
    "vv_pre": ("Sentinel-1 GRD VV（災前 6 期）", "SIM-S1-PRE-0..5"),
    "vh_pre": ("Sentinel-1 GRD VH（災前 6 期）", "SIM-S1-PRE-0..5"),
    "vv_post": ("Sentinel-1 GRD VV（災後）", "SIM-S1-POST"),
    "vh_post": ("Sentinel-1 GRD VH（災後）", "SIM-S1-POST"),
    "coh_pre": ("Sentinel-1 干涉同調性（災前）", "SIM-S1-COH-PRE"),
    "coh_post": ("Sentinel-1 干涉同調性（災前－災後）", "SIM-S1-COH-POST"),
    "ndvi_pre": ("Sentinel-2 L2A NDVI（災前 6 期）", "SIM-S2-PRE-0..5"),
    "ndvi_post": ("Sentinel-2 L2A NDVI（災後）", "SIM-S2-POST"),
}
DECL_KEYS = ["id", "area_ha", "rain_mm", "declared_crop", "applied", "misregistered"]
TRUTH_KEYS = ["id", "crop", "kind", "true_loss"]


def write_inputs(sc, indir, inject_bare=None):
    """把工況寫成輸入檔。inject_bare：把某一坵塊改成「災前即為裸地」且有申請（竹塘案型）。"""
    os.makedirs(indir, exist_ok=True)
    parcels = [dict(p) for p in sc.parcels]
    if inject_bare is not None:
        m = sc.parcel == inject_bare
        sc.ndvi_pre[:, m] = 0.15 + np.random.default_rng(7).normal(0, 0.02, (s.N_PRE, int(m.sum())))
        sc.ndvi_post[m & np.isfinite(sc.ndvi_post)] = 0.12
        bare_vv = 10 ** (-13.0 / 10)
        bare_vh = 10 ** (-21.0 / 10)
        sc.vv_pre[:, m] = bare_vv
        sc.vh_pre[:, m] = bare_vh
        sc.vv_post[m] = bare_vv
        sc.vh_post[m] = bare_vh
        for p in parcels:
            if p["id"] == inject_bare:
                p.update(applied=True, declared_crop=2, kind="無", true_loss=0.0, crop=-1)
    for name in LAYERS:
        np.save(os.path.join(indir, f"{name}.npy"), getattr(sc, name))
    with open(os.path.join(indir, "declarations.json"), "w", encoding="utf-8") as f:
        json.dump([{k: p[k] for k in DECL_KEYS} for p in parcels], f, ensure_ascii=False, indent=1)
    # 現勘回填（地真值）：只用於驗證與校準，不進入計算
    with open(os.path.join(indir, "field_results.json"), "w", encoding="utf-8") as f:
        json.dump([{k: p[k] for k in TRUTH_KEYS} for p in parcels], f, ensure_ascii=False, indent=1)


def register_inputs(indir, ledger, event_date=EVENT_DATE):
    """S1：登錄每個輸入檔並做品質檢核。回傳輸入清單（manifest）。"""
    items, problems = [], []
    for name in LAYERS:
        path = os.path.join(indir, f"{name}.npy")
        arr = np.load(path)
        desc, pid = SOURCE[name]
        q = {"形狀": list(arr.shape)}
        if name != "parcel":
            finite = np.isfinite(arr)
            q["有效像素率"] = round(float(finite.mean()), 4)
            if name.startswith(("vv", "vh")):
                db = 10 * np.log10(np.clip(arr[finite], 1e-6, None))
                q["dB_1至99百分位"] = [round(float(np.percentile(db, 1)), 1), round(float(np.percentile(db, 99)), 1)]
                if q["dB_1至99百分位"][0] < -40 or q["dB_1至99百分位"][1] > 10:
                    problems.append(f"{name} 後向散射超出合理範圍")
            if name.startswith("ndvi"):
                v = arr[finite]
                if v.min() < -1 or v.max() > 1:
                    problems.append(f"{name} NDVI 超出 −1～1")
            if name.endswith("post") and q["有效像素率"] < 0.3:
                problems.append(f"{name} 有效像素率低於 30%")
        items.append({"圖層": name, "說明": desc, "產品編號": pid, "檔名": f"{name}.npy",
                      "SHA256": file_sha256(path), "品質": q})
    shapes = {tuple(i["品質"]["形狀"][-2:]) for i in items}
    if len(shapes) != 1:
        problems.append("各圖層網格大小不一致")
    decl_path = os.path.join(indir, "declarations.json")
    items.append({"圖層": "declarations", "說明": "申請與申報資料（公所匯出）", "產品編號": "SIM-APPLY-EXPORT",
                  "檔名": "declarations.json", "SHA256": file_sha256(decl_path), "品質": {}})
    # 災前影像新鮮度：模擬資料以 Sentinel-1 六天再訪推算，最後一期距事件 2 天
    freshness_days = 2
    if freshness_days > 10:
        problems.append("災前影像距災害超過 10 日")
    manifest = {"事件": EVENT_ID, "災害日期": event_date, "輸入": items,
                "災前影像新鮮度_日": freshness_days, "檢核問題": problems,
                "通過": not problems}
    manifest["清單雜湊"] = sha256(canon({k: v for k, v in manifest.items() if k != "清單雜湊"}))
    ledger.add("S1 資料輸入登錄", "資料中心", {"清單雜湊": manifest["清單雜湊"],
                                         "輸入數": len(items), "通過": manifest["通過"], "問題": problems})
    return manifest


def register_real_scene_ids(path):
    """真實資料的登錄格式示例：丹娜絲 Sentinel-1 產品編號（取自 real_data/scenes.json）。"""
    with open(path, encoding="utf-8") as f:
        sc = json.load(f)
    return [{"期別": k, "產品編號": v["id"], "取像時間": v["datetime"],
             "官方檢查碼": "下載時由 CDSE 取得（MD5／BLAKE3）"} for k, v in sc["scenes"].items()]


# ---------------------------------------------------------------------
# S2 計算環境鎖定
# ---------------------------------------------------------------------

def params():
    return dict(lee_size=5, inset_iter=1, flood_diff_db=s.FLOOD_DIFF_DB, flood_z=s.FLOOD_Z,
                lodge_db=s.LODGE_DB, coh_buried=s.COH_BURIED, gate_a_q10=s.GATE_A_Q10,
                gate_b_q90=s.GATE_B_Q90, min_pix=s.MIN_PIX, bare_ndvi=BARE_NDVI)


def environment():
    return {
        "程式": {"skyaide_demo.py": file_sha256(os.path.join(HERE, "skyaide_demo.py")),
               "sop_pipeline.py": file_sha256(os.path.abspath(__file__))},
        "版本": {"判讀": s.VERSION, "作業流程": SOP_VERSION},
        "參數": params(), "參數雜湊": sha256(canon(params())),
        "套件": {"python": platform.python_version(), "numpy": np.__version__,
               "scipy": __import__("scipy").__version__},
    }


def env_with_hash():
    env = environment()
    env["環境雜湊"] = sha256(canon({k: env[k] for k in ("程式", "參數", "套件")}))
    return env


def lock_environment(ledger):
    env = env_with_hash()
    ledger.add("S2 計算環境鎖定", "資料中心", {"環境雜湊": env["環境雜湊"], "參數雜湊": env["參數雜湊"],
                                         "版本": env["版本"]})
    return env


# ---------------------------------------------------------------------
# S3 模型計算（從檔案讀，讀之前先比對雜湊）
# ---------------------------------------------------------------------

class IntegrityError(Exception):
    pass


def load_scene(indir, manifest):
    bad = [i["檔名"] for i in manifest["輸入"] if file_sha256(os.path.join(indir, i["檔名"])) != i["SHA256"]]
    if bad:
        raise IntegrityError("輸入檔與登錄雜湊不符：" + "、".join(bad))
    arr = {n: np.load(os.path.join(indir, f"{n}.npy")) for n in LAYERS}
    with open(os.path.join(indir, "declarations.json"), encoding="utf-8") as f:
        decl = json.load(f)
    return s.Scene(arr["parcel"], np.zeros_like(arr["parcel"]), arr["vv_pre"], arr["vh_pre"],
                   arr["vv_post"], arr["vh_post"], arr["coh_pre"], arr["coh_post"],
                   arr["ndvi_pre"], arr["ndvi_post"], decl, [], None, None, 0)


BARE_NDVI = 0.30   # 災前 6 期 NDVI 平均低於此值，視為災前未見作物


def compute(sc):
    maps, rows = s.analyse(sc)
    s.classify_parcels(rows)
    for r in rows:   # 生產事實檢核：災前是否在生產（對應「未種植仍申請」）
        r["pre_ndvi_mean"] = float(np.mean([r[f"nd{k}"] for k in range(s.N_PRE)]))
        r["producing"] = r["pre_ndvi_mean"] >= BARE_NDVI
        if not r["producing"]:
            r["grade"] = "C"
            r["reasons"] = ["C3 災前 6 期未見作物生長（裸地或休耕）"] + [x for x in r["reasons"] if x != "通過三道關卡"]
    return maps, rows


# ---------------------------------------------------------------------
# S4 可信度評定
# ---------------------------------------------------------------------

CHECKS = ["影像條件", "觀測完整", "多源一致", "申報一致", "生產事實"]


def credibility(r):
    """
    可信度只看「證據本身夠不夠好」，不看損失大小（損失是否遠離門檻由三道關卡的第二關處理）。
    五項檢核全過＝高；生產事實未過或兩項以上未過＝低；其餘＝中。只有「高」可以判 A。
    """
    radar_strong = r["flood_frac"] >= 0.5 or r["buried_frac"] >= 0.5
    radar_damage = max(r["flood_frac"], r["lodge_frac"], r["buried_frac"]) > 0.2
    optical_ok = bool(np.isfinite(r["ndvi_z"])) and r["cloud_frac"] < 0.5
    res = {
        "影像條件": r["n_pix"] >= s.MIN_PIX and not r["misregistered"],       # 田夠大、地籍對位可靠
        "觀測完整": optical_ok or radar_strong,                               # 光學可用，或雷達訊號強到可單獨判定
        "多源一致": (not optical_ok) or radar_strong or (radar_damage == (r["ndvi_z"] < -3)),
        "申報一致": r["pred_crop"] == r["declared_crop"],
        "生產事實": r["producing"],
    }
    fails = [k for k in CHECKS if not res[k]]
    level = "高" if not fails else ("低" if ("生產事實" in fails or len(fails) >= 2) else "中")
    return level, res, fails


def apply_credibility(rows):
    for r in rows:
        r["cred"], r["cred_checks"], r["cred_fails"] = credibility(r)
        if r["grade"] == "A" and r["cred"] != "高":     # 理論上不會發生（關卡 1、3 已涵蓋），保留為最後防線
            r["grade"], r["reasons"] = "C", ["C1 可信度未達「高」：" + "、".join(r["cred_fails"])]


# ---------------------------------------------------------------------
# S5 存證報告：序列化 → 雜湊 → 簽章 → 時戳
# ---------------------------------------------------------------------

def build_report(r, manifest, env):
    crop = s.CROPS[r["pred_crop"]]
    level, res, fails = r["cred"], r["cred_checks"], r["cred_fails"]
    ev = []
    if r["flood_frac"] > 0.05:
        ev.append(f"雷達淹水投票：{r['flood_frac']:.0%} 像素至少兩法判為淹水")
    if r["lodge_frac"] > 0.05:
        ev.append(f"雷達 VH 對數比值：{r['lodge_frac']:.0%} 像素變化超過 {s.LODGE_DB} dB")
    if r["buried_frac"] > 0.05:
        ev.append(f"干涉同調性：{r['buried_frac']:.0%} 像素低於 {s.COH_BURIED}")
    if np.isfinite(r["ndvi_z"]):
        ev.append(f"Sentinel-2 NDVI 較同作物未受災田低 {abs(r['ndvi_z']):.1f} 個標準差")
    return {
        "報告編號": f"SKY-{EVENT_ID}-{r['id']:04d}",
        "坵塊": {"編號": r["id"], "面積_公頃": round(r["area_ha"], 2), "內縮後像素": r["n_pix"]},
        "生產事實": {"判釋作物": crop, "申報作物": s.CROPS[r["declared_crop"]],
                 "災前NDVI平均": round(r["pre_ndvi_mean"], 3), "災前在生產": bool(r["producing"])},
        "損失區間": {"第10百分位": round(r["q10"], 3), "第50百分位": round(r["q50"], 3), "第90百分位": round(r["q90"], 3)},
        "分級": r["grade"], "原因": r["reasons"],
        "可信度": {"等級": level, "檢核": {k: bool(v) for k, v in res.items()}, "未通過": fails},
        "主要證據": ev,
        "溯源": {"輸入清單雜湊": manifest["清單雜湊"],
               "輸入檔": {i["檔名"]: i["SHA256"] for i in manifest["輸入"]},
               "環境雜湊": env["環境雜湊"], "參數雜湊": env["參數雜湊"], "版本": env["版本"]},
        "效力說明": "影像存證參考，尚非種植客觀證明文件；以公所認定為準",
    }


def seal(report, ks):
    """封裝：報告雜湊、資料中心簽章、時戳（示範）。報告本體不含時間，故可重算比對。"""
    body = canon(report)
    h = sha256(body)
    ts = {"報告雜湊": h, "時間": now()}
    ts["時戳簽章"] = sign(ks["tsa"], canon(ts))
    return {"報告": report, "報告雜湊": h, "資料中心簽章": sign(ks["datacenter"], body), "時戳": ts,
            "查驗碼": f"SKY|{report['報告編號']}|{h[:16]}"}


def office_decision(envelope, ks, decision):
    """S6：公所判定另成一筆紀錄，指向報告雜湊，簽章後與系統結果並列。"""
    d = {"報告編號": envelope["報告"]["報告編號"], "報告雜湊": envelope["報告雜湊"], **decision}
    return {"判定": d, "公所簽章": sign(ks["office"], canon(d))}


def quality_assessment(rows, field_path, sample_rate=0.20, target=0.95, seed=0):
    """
    參考歐盟 AMS 年度品質評估（2022/1173 第 2 條）：量化缺失、提出改正措施。
    樣本：A 級依法定 20% 隨機抽查；C 級全部現勘。A 級精確度未達 95% 的作物，下次災害停判 A。
    """
    truth = {f["id"]: f for f in json.load(open(field_path, encoding="utf-8"))}
    rng = np.random.default_rng(seed)
    A = [r for r in rows if r["grade"] == "A"]
    k = max(1, int(np.ceil(len(A) * sample_rate)))
    sample = [A[i] for i in rng.choice(len(A), size=k, replace=False)] if A else []
    C = [r for r in rows if r["grade"] == "C" and r["applied"]]
    by_crop = {}
    for r in sample:
        d = by_crop.setdefault(s.CROPS[r["pred_crop"]], {"A抽查件數": 0, "A抽查損失達20%": 0})
        d["A抽查件數"] += 1
        d["A抽查損失達20%"] += int(truth[r["id"]]["true_loss"] >= 0.2)
    for d in by_crop.values():
        d["A精確度"] = round(d["A抽查損失達20%"] / d["A抽查件數"], 3)
    cover = [r["q10"] <= truth[r["id"]]["true_loss"] <= r["q90"] for r in C]
    stop = [c for c, d in by_crop.items() if d["A精確度"] < target]
    return {"樣本": {"A級抽查": len(sample), "A級總數": len(A), "C級現勘": len(C)},
            "依作物": by_crop,
            "C級區間覆蓋率": round(float(np.mean(cover)), 3) if cover else None,
            "C級中損失達20%比例": round(float(np.mean([truth[r["id"]]["true_loss"] >= 0.2 for r in C])), 3) if C else None,
            "下次停判A的作物": stop,
            "改正措施": ("無" if not stop else "上列作物下次災害全數列 C，並以本次現勘結果重新校準")}


# ---------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------

def run(seed=42, out=OUT, inject_bare=None, keydir=None, fresh_inputs=True, quiet=False):
    t0 = time.time()
    keydir = keydir or os.path.join(out, "keys")
    indir = os.path.join(out, "inputs")
    if fresh_inputs:
        if os.path.exists(out):
            for sub in ("inputs", "reports"):
                shutil.rmtree(os.path.join(out, sub), ignore_errors=True)
        sc = s.simulate_scene(seed)
        write_inputs(sc, indir, inject_bare)
    os.makedirs(os.path.join(out, "reports"), exist_ok=True)
    ks, trust = keys(keydir)
    ledger = Ledger(os.path.join(out, "ledger.jsonl"))

    manifest = register_inputs(indir, ledger)
    manifest["真實資料登錄示例"] = register_real_scene_ids(os.path.join(HERE, "real_data", "scenes.json"))
    with open(os.path.join(out, "input_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    if not manifest["通過"]:
        raise RuntimeError("S1 檢核未通過：" + "；".join(manifest["檢核問題"]))

    env = lock_environment(ledger)
    with open(os.path.join(out, "environment.json"), "w", encoding="utf-8") as f:
        json.dump(env, f, ensure_ascii=False, indent=1)

    sc = load_scene(indir, manifest)
    maps, rows = compute(sc)
    ledger.add("S3 模型計算", "資料中心", {"坵塊數": len(rows),
                                       "分級": {g: sum(r["grade"] == g for r in rows) for g in "ABC"}})

    apply_credibility(rows)
    ledger.add("S4 可信度評定", "資料中心", {lv: sum(r["cred"] == lv for r in rows) for lv in "高中低"})

    envelopes = []
    for r in rows:
        if not (r["applied"] or r["grade"] == "A"):
            continue
        e = seal(build_report(r, manifest, env), ks)
        envelopes.append(e)
        with open(os.path.join(out, "reports", f"{e['報告']['報告編號']}.json"), "w", encoding="utf-8") as f:
            json.dump(e, f, ensure_ascii=False, indent=1)
        ledger.add("S5 存證報告簽發", "資料中心", {"報告編號": e["報告"]["報告編號"], "報告雜湊": e["報告雜湊"],
                                             "分級": r["grade"], "可信度": r["cred"]})

    # S5 先行通知：申請案件的初步結果以白話通知農民，可於申請期內補照片或更正（參考歐盟 2022/1173 第 7、10 條）
    words = {"A": "受損明顯", "B": "未見明顯受損", "C": "需公所到場確認"}
    notices = [{"坵塊": r["id"], "初步結果": words[r["grade"]], "可補件": r["grade"] != "A",
                "說明": "以公所認定為準"} for r in rows if r["applied"]]
    with open(os.path.join(out, "notices.json"), "w", encoding="utf-8") as f:
        json.dump(notices, f, ensure_ascii=False, indent=1)
    ledger.add("S5 先行通知農民", "資料中心", {"通知件數": len(notices), "可補件": sum(n["可補件"] for n in notices)})

    # S6：示範一筆公所判定（第一筆 A 級書面審核通過）
    first_a = next((e for e in envelopes if e["報告"]["分級"] == "A"), None)
    if first_a:
        dec = office_decision(first_a, ks, {"承辦": "農業課 王○○（示範）", "判定": "書面審核通過，免實地勘查",
                                            "核定受害率": 0.55, "依據": "App 照片＋公所認定"})
        with open(os.path.join(out, "reports", f"{first_a['報告']['報告編號']}.office.json"), "w", encoding="utf-8") as f:
            json.dump(dec, f, ensure_ascii=False, indent=1)
        ledger.add("S6 公所判定", "竹崎鄉公所", {"報告雜湊": first_a["報告雜湊"], "判定雜湊": sha256(canon(dec["判定"]))})

    root = merkle_root([e["報告雜湊"] for e in envelopes])
    ledger.add("S7 批次封存", "資料中心", {"報告數": len(envelopes), "Merkle根": root})
    with open(os.path.join(out, "batch_root.json"), "w", encoding="utf-8") as f:
        json.dump({"事件": EVENT_ID, "報告數": len(envelopes), "Merkle根": root,
                   "日誌最後一筆雜湊": ledger.prev}, f, ensure_ascii=False, indent=1)

    # S8 災後品質評估：以法定抽查樣本（A 級抽 20%）與 C 級現勘結果評估，依作物類別決定下次是否停判 A
    qa = quality_assessment(rows, os.path.join(indir, "field_results.json"))
    with open(os.path.join(out, "qa_report.json"), "w", encoding="utf-8") as f:
        json.dump(qa, f, ensure_ascii=False, indent=1)
    ledger.add("S8 災後品質評估", "資料中心", {"報告雜湊": sha256(canon(qa)), "停判A類別": qa["下次停判A的作物"]})

    with open(os.path.join(out, "rows.json"), "w", encoding="utf-8") as f:
        json.dump([{k: (None if isinstance(v, float) and not np.isfinite(v) else v)
                    for k, v in r.items() if not k.startswith(("vv", "vh", "nd")) or k == "ndvi_z"}
                   for r in rows], f, ensure_ascii=False, indent=1, default=lambda o: bool(o) if isinstance(o, np.bool_) else str(o))
    dt = time.time() - t0
    if not quiet:
        g = {x: sum(r["grade"] == x for r in rows) for x in "ABC"}
        c = {x: sum(r["cred"] == x for r in rows) for x in "高中低"}
        print(f"完成：{len(rows)} 坵塊，分級 {g}，可信度 {c}，簽發報告 {len(envelopes)} 份，"
              f"日誌 {ledger.seq} 筆，耗時 {dt:.1f} 秒")
    return dict(rows=rows, envelopes=envelopes, manifest=manifest, env=env, root=root, seconds=dt, trust=trust)


if __name__ == "__main__":
    run(seed=42, inject_bare=int(sys.argv[1]) if len(sys.argv) > 1 else None)
