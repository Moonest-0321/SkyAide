"""準備期回溯（構想書 三、4(14)）：試辦前以過去 2–3 場災害的核定清冊重跑判讀，
作為作物判釋與損失區間模型的訓練與校準資料；判讀元件依驗證結果決定能否支撐 A 級。
這一步不影響本場災害的輸入，只產生模型。"""
import numpy as np
from sklearn.ensemble import RandomForestClassifier

from . import s1_ingest, s3_1_preprocess, s3_2_parcel, s3_3_interpret
from .common import cp_lower
from .monitor import NullStage


def _run_past(src, params, root, run_dir, model=None):
    ctx = dict(source=src, params=params, event=src.event(), quiet=True, root=root, run_dir=run_dir, crop_model=model)
    ns = NullStage()
    s1_ingest.run(ctx, ns); s3_1_preprocess.run(ctx, ns); s3_2_parcel.run(ctx, ns)
    return ctx


def _crop_xy(src, ctx):
    hist = next(x for p, x in ctx["products"].values() if p["kind"] == "HISTORY")
    truth = src.truth()
    X, y = [], []
    for pid, p in ctx["parcels"].items():
        if p["kind"] != "farm" or pid not in hist:
            continue
        x = s3_3_interpret.crop_features(hist[pid])
        if x is None:
            continue
        X.append(x); y.append(truth[pid]["crop"])           # 標註：農地覆蓋物資料庫與公所回填作物（模擬時取地真值）
    return np.array(X), np.array(y)


def run(ctx, st):
    past = ctx["source"].past_events()
    st.check("有過去災害可回溯", len(past) >= 2, f"{len(past)} 場", action="沒有回溯資料時，損失區間只用半經驗損傷函數，案件一律不判 A", severity="warn")
    if len(past) < 2:
        ctx["crop_model"] = None; ctx["train_rows"] = []; ctx["calib_rows"] = []; ctx["crop_ok"] = {}
        return
    pcs = []
    for src in past:
        st.log(f"回溯 {src.event()['name']}（{src.event()['alert'][:10]}）：S1→S3-2")
        pcs.append((src, _run_past(src, ctx["params"], ctx["root"], ctx["run_dir"])))
    # 作物判釋：前 n−1 場訓練，最後一場驗證
    Xtr, ytr = map(np.concatenate, zip(*[_crop_xy(s, c) for s, c in pcs[:-1]]))
    Xva, yva = _crop_xy(*pcs[-1])
    clf = RandomForestClassifier(n_estimators=300, min_samples_leaf=2, random_state=0).fit(Xtr, ytr)
    pred = clf.predict(Xva)
    rows, crop_ok = [], {}
    thr = ctx["params"]["crop_component"]["accuracy_lb_min"]
    for c in sorted(set(yva)):
        m = yva == c
        k, n = int((pred[m] == c).sum()), int(m.sum())
        lb = cp_lower(k, n)
        crop_ok[c] = bool(lb is not None and lb >= thr)
        rows.append([c, n, f"{k / n:.0%}", f"{lb:.0%}" if lb is not None else "—", "可判釋" if crop_ok[c] else "以申報為準，衛星只查物候"])
    st.table("作物判釋驗證（最後一場過去災害）", ["作物", "坵塊數", "準確率", "95% 下界", "使用方式"], rows,
             note=f"準確率下界 ≥ {thr:.0%} 才用於「申報一致」檢核（表 70）")
    st.metric("作物判釋整體準確率", round(float((pred == yva).mean()) * 100, 1), "%", target="下界 ≥ 80%")
    clf_all = RandomForestClassifier(n_estimators=300, min_samples_leaf=2, random_state=0).fit(np.vstack([Xtr, Xva]), np.concatenate([ytr, yva]))
    ctx["crop_model"] = clf_all
    ctx["crop_ok"] = crop_ok

    # 損失模型的訓練與校準資料：過去災害跑完判讀，對上核定損失率
    from .s3_4_loss import feature_rows
    sets = []
    for src, c in pcs:
        c["crop_model"] = clf_all
        s3_3_interpret.run(c, NullStage())
        approved = src.approved_losses()
        sets.append([dict(r, y=approved[r["id"]]) for r in feature_rows(c) if r["id"] in approved])
    ctx["train_rows"] = [r for s in sets[:-1] for r in s]
    ctx["calib_rows"] = sets[-1]
    st.count(過去災害=len(past), 作物標註=len(ytr) + len(yva), 損失訓練筆數=len(ctx["train_rows"]), 校準筆數=len(ctx["calib_rows"]))
    st.check("損失模型訓練資料足夠", len(ctx["train_rows"]) >= 100, f"{len(ctx['train_rows'])} 筆核定損失率", severity="warn")
