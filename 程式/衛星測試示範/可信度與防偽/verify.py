"""
天相星 SkyAide｜存證報告查驗工具（公所、縣府、審計或農民皆可使用）

  verify_envelope(報告, 信任清單)  檢查報告是否被改過、是否由資料中心簽發、時戳是否吻合
  verify_ledger(日誌)              檢查作業日誌的雜湊鏈是否完整
  verify_in_batch(報告雜湊, 批次)   檢查報告是否屬於已封存的批次（Merkle 根）
  reproduce(報告, 輸入資料夾)       用同一批輸入、同一版程式重算，比對是否得到同一份報告

執行：python verify.py sop_output/reports/SKY-....json
"""

import json
import os
import sys

import sop_pipeline as sp


def verify_envelope(env, trust):
    problems = []
    body = sp.canon(env["報告"])
    if sp.sha256(body) != env["報告雜湊"]:
        problems.append("報告內容與報告雜湊不符（內容被改過）")
    if not sp.verify_sig(trust["datacenter"]["公鑰"], env["資料中心簽章"], body):
        problems.append("資料中心簽章驗證失敗（非信任清單內的金鑰所簽，或內容被改過）")
    ts = env["時戳"]
    if ts["報告雜湊"] != env["報告雜湊"]:
        problems.append("時戳記載的雜湊與報告不符")
    ts_body = sp.canon({k: v for k, v in ts.items() if k != "時戳簽章"})
    if not sp.verify_sig(trust["tsa"]["公鑰"], ts["時戳簽章"], ts_body):
        problems.append("時戳簽章驗證失敗")
    rid, short = env["查驗碼"].split("|")[1:]
    if rid != env["報告"]["報告編號"] or not env["報告雜湊"].startswith(short):
        problems.append("查驗碼與報告不符")
    return problems


def verify_office(dec, env, trust):
    problems = []
    if dec["判定"]["報告雜湊"] != env["報告雜湊"]:
        problems.append("公所判定指向的報告雜湊與報告不符")
    if not sp.verify_sig(trust["office"]["公鑰"], dec["公所簽章"], sp.canon(dec["判定"])):
        problems.append("公所簽章驗證失敗")
    return problems


def verify_ledger(path):
    prev = "0" * 64
    with open(path, encoding="utf-8") as f:
        entries = [json.loads(line) for line in f if line.strip()]
    for i, e in enumerate(entries, start=1):
        if e["序號"] != i:
            return [f"第 {i} 筆序號不連續（記載為 {e['序號']}），可能有紀錄被刪除"]
        if e["前一筆雜湊"] != prev:
            return [f"第 {i} 筆的前一筆雜湊對不上，鏈結於此斷開"]
        body = {k: v for k, v in e.items() if k != "本筆雜湊"}
        if sp.sha256(sp.canon(body)) != e["本筆雜湊"]:
            return [f"第 {i} 筆內容與本筆雜湊不符（內容被改過）"]
        prev = e["本筆雜湊"]
    return []


def verify_in_batch(report_hashes, batch_root):
    return [] if sp.merkle_root(report_hashes) == batch_root else ["報告集合與封存的 Merkle 根不符（有報告被抽換、刪除或事後補入）"]


def reproduce(env, indir, manifest):
    """以報告記載的輸入與版本重算。回傳 (問題清單, 重算後的報告雜湊)。"""
    problems = []
    cur = sp.environment()
    if cur["參數雜湊"] != env["報告"]["溯源"]["參數雜湊"]:
        problems.append("目前的判讀參數與報告記載的參數雜湊不同（版本不一致）")
    try:
        sc = sp.load_scene(indir, manifest)
    except sp.IntegrityError as ex:
        return problems + [str(ex)], None
    _, rows = sp.compute(sc)
    rid = env["報告"]["坵塊"]["編號"]
    sp.apply_credibility(rows)
    r = next(x for x in rows if x["id"] == rid)
    new = sp.build_report(r, manifest, sp.env_with_hash())
    h = sp.sha256(sp.canon(new))
    if h != env["報告雜湊"]:
        problems.append("重算結果與報告不同")
    return problems, h


if __name__ == "__main__":
    out = sp.OUT
    trust = json.load(open(os.path.join(out, "keys", "trust_list.json"), encoding="utf-8"))
    for path in sys.argv[1:]:
        env = json.load(open(path, encoding="utf-8"))
        p = verify_envelope(env, trust)
        print(path, "通過" if not p else "；".join(p))
    p = verify_ledger(os.path.join(out, "ledger.jsonl"))
    print("作業日誌", "完整" if not p else "；".join(p))
