"""S5 存證報告簽發與通知（表 37 S5、三、4(8)）。
固定格式序列化 → SHA-256 → 數位簽章（Ed25519；正式系統用憑證機構簽發的憑證）→ 時戳（正式系統 RFC 3161）→ 查驗碼（報告編號＋雜湊前 16 碼）。
簽發前重新比對輸入清單與計算環境的雜湊，不符即停止。通知內容依系統等級：乙等起發 C 級補件提醒，甲等才通知 A 級結果。"""
import hashlib
import json
import os
from datetime import datetime

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from .common import canonical
from . import s2_lock

GR = {"A_MET": "A 達標", "A_NOT_MET": "A 未達標", "B": "B 邊緣", "C": "C 缺失"}
PLAIN = {"A_MET": "受損明顯", "A_NOT_MET": "影像顯示未達 20%", "B": "需公所到場確認", "C": "請補充資料"}


def run(ctx, st):
    # 簽發前檢核：輸入與環境沒有變
    man_hash = hashlib.sha256(json.dumps([m["sha256"] for m in ctx["manifest"] if not m.get("late")]).encode()).hexdigest()
    st.check("輸入清單雜湊與 S1 相同", man_hash == ctx["manifest_hash"], man_hash[:16], severity="stop", action="停止簽發，重新登錄")
    env_now = s2_lock.env_record(ctx["root"], ctx["params"])
    st.check("計算環境雜湊與 S2 相同", env_now["code_hash"] == ctx["env"]["code_hash"] and env_now["params_hash"] == ctx["env"]["params_hash"],
             env_now["code_hash"][:16], severity="stop", action="停止簽發，改用鎖定版本")

    key = Ed25519PrivateKey.generate()                        # 示範金鑰；正式系統金鑰存於硬體安全模組
    kdir = os.path.join(ctx["run_dir"], "keys"); os.makedirs(kdir, exist_ok=True)
    pub = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    open(os.path.join(kdir, "datacenter_public.pem"), "wb").write(pub)
    rdir = os.path.join(ctx["run_dir"], "reports"); os.makedirs(rdir, exist_ok=True)
    ev = ctx["event"]
    s1 = [m for m in ctx["manifest"] if m["kind"] in ("S1_GRD", "S2_L2A") and m["usable"]]
    reports, notices = {}, []
    for pid, c in sorted(ctx["cases"].items()):
        no = f"SKY-{ev['id']}-{pid:04d}"
        body = dict(報告編號=no, 事件=ev["id"], 地號=c["land_no"], 坵塊=pid, 面積_公頃=c["area_ha"], 申報作物=c["crop"],
                    類別=c["category"], 分級=GR[c["grade"]], 原因碼=c["reasons"], 可信度=c["credibility"],
                    損失區間=c["interval"], 影響判定最多的特徵=c.get("top", []),
                    輸入=[dict(產品=m["id"], SHA256=m["sha256"]) for m in s1],
                    程式雜湊=ctx["env"]["code_hash"], 參數雜湊=ctx["env"]["params_hash"], 版本=ctx["params"]["version"],
                    效力說明="影像存證參考，尚非種植客觀證明文件；以公所認定為準" if c["level"] != "甲" else "本類別已經政府審核列入種植客觀證明；以公所認定為準")
        h = hashlib.sha256(canonical(body).encode()).hexdigest()
        sig = key.sign(bytes.fromhex(h)).hex()
        ts = datetime.now().astimezone().isoformat(timespec="seconds")
        rep = dict(report=body, hash=h, signature=sig, timestamp=dict(time=ts, note="模擬時戳；正式系統為 RFC 3161"),
                   verify_code=f"{no}-{h[:16]}")
        json.dump(rep, open(os.path.join(rdir, f"{no}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        reports[pid] = dict(no=no, hash=h, verify_code=rep["verify_code"], signature=sig[:32] + "…")
        # 通知：依系統等級
        lv, g = c["level"], c["grade"]
        if lv == "甲":
            kind = {"A_MET": "自動申報通知", "A_NOT_MET": "A 未達標通知（勘查期內送達，可補件或異議）", "B": "公所會到田裡確認", "C": "補件提醒"}[g]
            notices.append([pid, lv, kind, PLAIN[g]])
        elif lv == "乙" and g == "C":
            notices.append([pid, lv, "補件提醒", PLAIN[g]])
    for x in ctx.get("notify_unapplied", []):
        lv = next((c["level"] for c in ctx["source"].categories()["items"] if c["crop"] == x["crop"]), None)
        if lv in ("甲", "乙"):
            notices.append([x["id"], lv, "明顯受損、尚未申請：通知可以申請", "受損明顯"])
    ctx["reports"] = reports
    ctx["notices"] = notices
    st.count(存證報告=len(reports), 通知=len(notices))
    from collections import Counter
    st.table("通知（依系統等級）", ["種類", "件數"], [[k, v] for k, v in Counter(n[2] for n in notices).most_common()],
             note="丙等不發結果通知；乙等只發補件提醒；甲等才通知 A 級結果")
    st.metric("數位簽章", "Ed25519（示範金鑰）"); st.metric("公開金鑰", "keys/datacenter_public.pem")
    st.table("存證報告（前 10 份）", ["報告編號", "查驗碼", "分級"], [[r["no"], r["verify_code"], GR[ctx["cases"][k]["grade"]]] for k, r in list(reports.items())[:10]])
    st.d["outputs_hash"] = hashlib.sha256("".join(r["hash"] for r in reports.values()).encode()).hexdigest()
    if not ctx.get("quiet"):
        for pid, r in reports.items():
            ctx["mon"].parcel(pid, "S5", r)
