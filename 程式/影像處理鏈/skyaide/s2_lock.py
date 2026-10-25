"""S2 計算環境鎖定：災害開始時凍結程式、參數與套件版本，整場災害使用同一版本（表 37 S2）。
僅可使用通過前次評等的版本；新版本只用於下一場災害。"""
import glob
import hashlib
import json
import os
import platform


def _file_hash(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def env_record(root, params):
    code = {os.path.relpath(p, root): _file_hash(p) for p in sorted(glob.glob(os.path.join(root, "skyaide", "**", "*.py"), recursive=True))}
    pkgs = {}
    for name in ("numpy", "scipy", "sklearn", "lightgbm", "matplotlib", "cryptography"):
        try:
            mod = __import__(name)
            pkgs[name] = getattr(mod, "__version__", "?")
        except Exception:
            pkgs[name] = "未安裝"
    p_hash = hashlib.sha256(json.dumps(params, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    c_hash = hashlib.sha256(json.dumps(code, sort_keys=True).encode()).hexdigest()
    e_hash = hashlib.sha256(json.dumps(dict(pkgs=pkgs, py=platform.python_version()), sort_keys=True).encode()).hexdigest()
    return dict(version=params.get("version"), code=code, packages=pkgs, python=platform.python_version(),
                params_hash=p_hash, code_hash=c_hash, env_hash=e_hash)


def run(ctx, st):
    root = ctx["root"]
    rec = env_record(root, ctx["params"])
    ctx["env"] = rec
    approved_path = os.path.join(root, "config", "approved_versions.json")
    approved = json.load(open(approved_path, encoding="utf-8")) if os.path.exists(approved_path) else []
    known = any(a["code_hash"] == rec["code_hash"] and a["params_hash"] == rec["params_hash"] for a in approved)
    st.check("使用通過前次評等的版本", known or not approved,
             "此版本已在核可清單" if known else ("尚無核可清單：本次為第一次執行，登記為基準版本" if not approved else "程式或參數與核可版本不同"),
             action="改用核可版本；新版本只用於下一場災害", severity="warn", basis="表 37 S2")
    if not approved:
        json.dump([dict(code_hash=rec["code_hash"], params_hash=rec["params_hash"], version=rec["version"], note="第一次執行登記")],
                  open(approved_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    st.metric("程式雜湊", rec["code_hash"][:16]); st.metric("參數雜湊", rec["params_hash"][:16]); st.metric("環境雜湊", rec["env_hash"][:16])
    st.table("套件版本", ["套件", "版本"], [[k, v] for k, v in rec["packages"].items()] + [["python", rec["python"]]])
    st.table("程式檔案雜湊", ["檔案", "SHA-256（前 16 碼）"], [[k, v[:16]] for k, v in rec["code"].items()])
    st.count(程式檔=len(rec["code"]))
    st.d["outputs_hash"] = hashlib.sha256((rec["code_hash"] + rec["params_hash"] + rec["env_hash"]).encode()).hexdigest()
    json.dump(rec, open(os.path.join(ctx["run_dir"], "environment.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
