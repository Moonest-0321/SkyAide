"""
天相星 SkyAide｜防偽與可重現測試

每一項測試都先做一次「正常情況」確認可以通過，再做一次竄改或偽造，確認會被擋下。
結果寫入 sop_output/tamper_results.json 與 tamper_results.md。

執行：python tamper_tests.py
"""

import copy
import io
import json
import os
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image, ImageEnhance

import skyaide_demo as s
import sop_pipeline as sp
import verify as v

OUT = sp.OUT
BARE = 27
results = []


def record(no, name, attack, expect, ok, detail):
    results.append(dict(編號=no, 測試=name, 竄改方式=attack, 預期=expect, 結果="通過" if ok else "未通過", 說明=detail))
    print(f"[{'通過' if ok else '未通過'}] {no} {name}：{detail}")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- 準備
res = sp.run(seed=42, inject_bare=BARE, quiet=True)
trust = res["trust"]
manifest = res["manifest"]
envs = {e["報告"]["報告編號"]: e for e in res["envelopes"]}
a_env = next(e for e in res["envelopes"] if e["報告"]["分級"] == "A")
indir = os.path.join(OUT, "inputs")
assert all(not v.verify_envelope(e, trust) for e in res["envelopes"])
assert not v.verify_ledger(os.path.join(OUT, "ledger.jsonl"))

# ---------------------------------------------------------------- T1 可重現
out2 = OUT + "_rerun"
shutil.rmtree(out2, ignore_errors=True)
os.makedirs(out2)
shutil.copytree(indir, os.path.join(out2, "inputs"))
shutil.copytree(os.path.join(OUT, "keys"), os.path.join(out2, "keys"))
code = ("import sop_pipeline as sp, json;"
        f"r=sp.run(seed=42,out={out2!r},fresh_inputs=False,quiet=True);"
        "print(json.dumps({e['報告']['報告編號']:e['報告雜湊'] for e in r['envelopes']}))")
p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=sp.HERE)
h2 = json.loads(p.stdout.strip().splitlines()[-1])
same = sum(h2.get(k) == e["報告雜湊"] for k, e in envs.items())
record("T1", "重算一致", "另開程序，以同一批輸入與同一版程式重算全部報告",
       "全部報告雜湊相同", same == len(envs), f"{same}／{len(envs)} 份報告雜湊完全相同")

# ---------------------------------------------------------------- T2 改報告內容
t = copy.deepcopy(a_env)
t["報告"]["損失區間"]["第10百分位"] = round(t["報告"]["損失區間"]["第10百分位"] + 0.10, 3)
pr = v.verify_envelope(t, trust)
record("T2", "竄改報告內容", f"將 {a_env['報告']['報告編號']} 的損失區間下限提高 10 個百分點",
       "雜湊與簽章不符", len(pr) >= 2, "；".join(pr))

# ---------------------------------------------------------------- T3 改內容並重算雜湊
t["報告雜湊"] = sp.sha256(sp.canon(t["報告"]))
t["查驗碼"] = f"SKY|{t['報告']['報告編號']}|{t['報告雜湊'][:16]}"
pr = v.verify_envelope(t, trust)
record("T3", "竄改後自行重算雜湊", "同 T2，並重新計算報告雜湊與查驗碼",
       "簽章與時戳不符", any("簽章" in x for x in pr), "；".join(pr))

# ---------------------------------------------------------------- T4 自行簽發假報告
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
fake_key = Ed25519PrivateKey.generate()
f = copy.deepcopy(a_env)
f["報告"]["報告編號"] = "SKY-DANAS-2025-SIM-9999"
f["報告"]["坵塊"]["編號"] = 9999
body = sp.canon(f["報告"])
f["報告雜湊"] = sp.sha256(body)
f["資料中心簽章"] = fake_key.sign(body).hex()
f["時戳"] = {"報告雜湊": f["報告雜湊"], "時間": sp.now()}
f["時戳"]["時戳簽章"] = fake_key.sign(sp.canon(f["時戳"])).hex()
f["查驗碼"] = f"SKY|{f['報告']['報告編號']}|{f['報告雜湊'][:16]}"
pr = v.verify_envelope(f, trust)
pr_b = v.verify_in_batch([e["報告雜湊"] for e in res["envelopes"]] + [f["報告雜湊"]], res["root"])
record("T4", "偽造整份報告", "以非信任清單的金鑰自行簽發一份格式完全相同的報告",
       "簽章失敗且不在封存批次內", bool(pr) and bool(pr_b), "；".join(pr + pr_b))

# ---------------------------------------------------------------- T5 改日誌
led = os.path.join(OUT, "ledger.jsonl")
lines = open(led, encoding="utf-8").read().splitlines()
tmp = led + ".t"
e = json.loads(lines[9]); e["內容"]["報告雜湊"] = "0" * 64
open(tmp, "w", encoding="utf-8").write("\n".join(lines[:9] + [json.dumps(e, ensure_ascii=False)] + lines[10:]))
pr1 = v.verify_ledger(tmp)
open(tmp, "w", encoding="utf-8").write("\n".join(lines[:20] + lines[21:]))
pr2 = v.verify_ledger(tmp)
os.remove(tmp)
record("T5", "竄改或刪除作業日誌", "改第 10 筆紀錄記載的報告雜湊；另刪除第 21 筆紀錄",
       "指出斷點位置", bool(pr1) and bool(pr2), "；".join(pr1 + pr2))

# ---------------------------------------------------------------- T6 抽換輸入影像
vp = os.path.join(indir, "vv_post.npy")
backup = vp + ".bak"
shutil.copy(vp, backup)
arr = np.load(vp)
arr[120, 80] *= 10 ** (0.1 / 10)          # 單一像素改 0.1 dB
np.save(vp, arr)
pr, _ = v.reproduce(a_env, indir, manifest)
shutil.move(backup, vp)
record("T6", "抽換輸入影像", "災後雷達影像 57,600 個像素中，僅將 1 個像素調亮 0.1 dB",
       "計算前即中止", any("不符" in x for x in pr), "；".join(pr))

# ---------------------------------------------------------------- T7 私改參數
old = s.FLOOD_DIFF_DB
s.FLOOD_DIFF_DB = -2.0
pr, _ = v.reproduce(a_env, indir, manifest)
sc = sp.load_scene(indir, manifest)
_, rows2 = sp.compute(sc)
s.FLOOD_DIFF_DB = old
changed = sum(1 for r in rows2 if r["grade"] != next(x for x in res["rows"] if x["id"] == r["id"])["grade"])
record("T7", "私改判讀參數", "未更新版本即將淹水變遷門檻由 −3 dB 改為 −2 dB 後重算",
       "標示版本不一致", any("參數" in x for x in pr),
       "；".join(pr) + f"（此改動使 {changed} 筆坵塊分級改變）")

# ---------------------------------------------------------------- T8 事後抽換批次
hs = [e["報告雜湊"] for e in res["envelopes"]]
pr = v.verify_in_batch(hs[1:], res["root"])
record("T8", "事後抽掉一份報告", "從已封存的 49 份報告中移除 1 份後重新比對",
       "與 Merkle 根不符", bool(pr), "；".join(pr))

# ---------------------------------------------------------------- T9 公所判定被改
dec = load(os.path.join(OUT, "reports", f"{a_env['報告']['報告編號']}.office.json"))
ok0 = not v.verify_office(dec, a_env, trust)
dec["判定"]["核定受害率"] = 0.85
pr = v.verify_office(dec, a_env, trust)
record("T9", "竄改公所核定結果", "將承辦已簽章的核定受害率由 55% 改為 85%",
       "公所簽章不符", ok0 and bool(pr), "；".join(pr))

# ---------------------------------------------------------------- T10 未種植仍申請
r = next(x for x in res["rows"] if x["id"] == BARE)
record("T10", "未種植仍申請", f"坵塊 {BARE}（8.16 公頃）災前 6 期皆為裸地，仍以果樹申請救助",
       "列 C、可信度低並附原因", r["grade"] == "C" and r["cred"] == "低",
       f"分級 {r['grade']}、可信度{r['cred']}；原因：{'、'.join(r['reasons'])}；災前 NDVI 平均 {r['pre_ndvi_mean']:.2f}")

# ---------------------------------------------------------------- T11 照片重複上傳
def dhash(img, n=8):
    g = img.convert("L").resize((n + 1, n), Image.LANCZOS)
    a = np.asarray(g, dtype=np.int16)
    return (a[:, 1:] > a[:, :-1]).flatten()


IMG = "/mnt/user-data/uploads/天相/衛星測試示範/web/img"
names = ["photo_pre.jpg", "photo_post.jpg", "zoomA_post.jpg", "zoomC_post.jpg", "zoomE_photo_post.jpg", "zoomB_photo.jpg"]
imgs = {n: Image.open(os.path.join(IMG, n)).convert("RGB") for n in names}


def variants(im):
    w, h = im.size
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=55); buf.seek(0)
    return {"重新壓縮": Image.open(buf).convert("RGB"),
            "縮小 70%": im.resize((int(w * .7), int(h * .7))),
            "裁切 5%": im.crop((int(w * .05), int(h * .05), w, h)),
            "調亮 15%": ImageEnhance.Brightness(im).enhance(1.15)}


THR = 16   # 複本（含裁切）與不同影像之間的分界；正式系統以真實 App 照片重訂
hits = tot = 0
dmax = {}
for n, im in imgs.items():
    h0 = dhash(im)
    for vn, vim in variants(im).items():
        tot += 1
        d = int((dhash(vim) != h0).sum())
        dmax[vn] = max(dmax.get(vn, 0), d)
        hits += int(d <= THR)
fp = pairs = 0
dmin = 64
for i in range(len(names)):
    for j in range(i + 1, len(names)):
        d = int((dhash(imgs[names[i]]) != dhash(imgs[names[j]])).sum())
        pairs += 1; fp += int(d <= THR); dmin = min(dmin, d)
record("T11", "照片重複上傳", "6 張影像各做重新壓縮、縮小、裁切、調亮共 24 份複本，與原圖比對；另兩兩比對 6 張不同影像",
       "複本全數標出、不同影像不誤標", hits == tot and fp == 0,
       f"複本標出 {hits}／{tot}；不同影像誤標 {fp}／{pairs}（複本最大差異：" + "、".join(f"{k} {v}" for k, v in dmax.items()) + f"；不同影像最小差異 {dmin}；64 位元，門檻 {THR}）")

# ---------------------------------------------------------------- T12 品質評估觸發停判
fp_ = os.path.join(indir, "field_results.json")
fr = load(fp_)
rice_a = {r["id"] for r in res["rows"] if r["grade"] == "A" and r["pred_crop"] == 0}
for f_ in fr:
    if f_["id"] in rice_a:
        f_["true_loss"] = 0.12                       # 假設現勘發現水稻 A 級其實未達 20%
tmp_ = fp_ + ".t"
json.dump(fr, open(tmp_, "w", encoding="utf-8"), ensure_ascii=False)
qa0 = sp.quality_assessment(res["rows"], fp_)
qa1 = sp.quality_assessment(res["rows"], tmp_)
os.remove(tmp_)
record("T12", "品質評估觸發停判", "將水稻 A 級坵塊的現勘損失改為 12%（模擬判讀偏差），重跑災後品質評估",
       "水稻列入下次停判 A", not qa0["下次停判A的作物"] and "水稻" in qa1["下次停判A的作物"],
       f"正常情況停判清單 {qa0['下次停判A的作物'] or '無'}；偏差情況停判清單 {qa1['下次停判A的作物']}，改正措施：{qa1['改正措施']}")

# ---------------------------------------------------------------- 輸出
with open(os.path.join(OUT, "tamper_results.json"), "w", encoding="utf-8") as fh:
    json.dump(results, fh, ensure_ascii=False, indent=1)
with open(os.path.join(OUT, "tamper_results.md"), "w", encoding="utf-8") as fh:
    fh.write("| 編號 | 測試 | 竄改方式 | 結果 | 說明 |\n|---|---|---|---|---|\n")
    for x in results:
        fh.write(f"| {x['編號']} | {x['測試']} | {x['竄改方式']} | {x['結果']} | {x['說明']} |\n")
print(f"\n{sum(x['結果'] == '通過' for x in results)}／{len(results)} 項通過")
