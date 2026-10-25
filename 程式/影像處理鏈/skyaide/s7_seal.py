"""S7 批次封存與回填（表 37 S7）。
同批報告的雜湊組成 Merkle 樹，根雜湊交公所留存；封存後不得增刪報告。
現勘回填：丙、乙等全部現勘；甲等為救助系統隨機抽中的 A 級 20%，加上 B、C 級。"""
import hashlib
import json
import os

import numpy as np


def merkle_root(hashes):
    level = [bytes.fromhex(h) for h in hashes]
    if not level:
        return None
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [hashlib.sha256(level[i] + level[i + 1]).digest() for i in range(0, len(level), 2)]
    return level[0].hex()


def run(ctx, st):
    reps = sorted(ctx["reports"].values(), key=lambda r: r["no"])
    root = merkle_root([r["hash"] for r in reps])
    seal = dict(event=ctx["event"]["id"], reports=len(reps), merkle_root=root)
    json.dump(seal, open(os.path.join(ctx["run_dir"], "batch_seal.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 封存驗證：抽換任何一份，根雜湊即不符
    if len(reps) > 1:
        fake = [r["hash"] for r in reps]; fake[0] = hashlib.sha256(b"tampered").hexdigest()
        st.check("抽換一份報告後根雜湊改變", merkle_root(fake) != root, "封存有效", severity="stop")
    st.metric("Merkle 根", root[:32] + "…" if root else None); st.metric("封存報告數", len(reps), "份")

    # 現勘回填
    rate = ctx["params"]["levels"]["sample_rate"]
    rng = np.random.default_rng(int(hashlib.sha256(ctx["event"]["id"].encode()).hexdigest()[:8], 16))   # 救助系統隨機抽選（模擬）
    levels = ctx["levels"]
    survey, why = [], {}
    for pid, c in ctx["cases"].items():
        lv = levels.get(c["category"], c["level"])
        if lv in ("丙", "乙"):
            survey.append(pid); why[pid] = f"{lv}等全部現勘"
        elif c["grade"] in ("B", "C"):
            survey.append(pid); why[pid] = "B、C 到場"
        elif rng.random() < rate:
            survey.append(pid); why[pid] = "A 級 20% 抽查"
    res = ctx["source"].field_survey(survey)
    back = {pid: dict(survey_loss=round(v["loss"], 1), survey_crop=v["crop"], reason=why[pid]) for pid, v in res.items()}
    ctx["backfill"] = back
    json.dump({str(k): v for k, v in back.items()}, open(os.path.join(ctx["run_dir"], "backfill.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    from collections import Counter
    st.count(封存=len(reps), 回填=len(back))
    st.table("回填來源", ["原因", "件數"], [[k, v] for k, v in Counter(why[p] for p in back).most_common()])
    st.d["outputs_hash"] = root
    if not ctx.get("quiet"):
        for pid, v in back.items():
            ctx["mon"].parcel(pid, "S7", v)
