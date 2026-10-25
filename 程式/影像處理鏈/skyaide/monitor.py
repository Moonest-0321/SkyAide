"""
監看：每一步的狀態、檢核點、指標、圖、表、警示與日誌，以及單一坵塊在各步的紀錄。

每次更新都重寫 runs/<run_id>/monitor_data.js（window.SKY_RUN = {...}），
monitor.html 用 <script> 載入，file:// 也能讀；執行中每 2 秒重新載入一次。
"""
import json
import os
import time
import traceback
from contextlib import contextmanager
from datetime import datetime, timezone

from . import ledger as ledger_mod


class StopPipeline(Exception):
    """檢核點未通過且規定為「停止計算」時拋出。"""


def _now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _jsonable(v):
    try:
        import numpy as np
        if isinstance(v, (np.floating,)):
            return None if not np.isfinite(v) else float(v)
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, (np.bool_,)):
            return bool(v)
        if isinstance(v, np.ndarray):
            return [_jsonable(x) for x in v.tolist()]
    except ImportError:
        pass
    if isinstance(v, float):
        return v if v == v and abs(v) != float("inf") else None
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    return v


class StageRecord:
    def __init__(self, mon, key, title, spec):
        self.mon = mon
        self.d = dict(key=key, title=title, spec=spec, status="running", started=_now(), ended=None,
                      seconds=None, checks=[], metrics=[], images=[], tables=[], warnings=[], log=[],
                      counts={}, outputs_hash=None)
        self._t0 = time.time()

    # ---- 紀錄 ----
    def check(self, name, passed, detail="", action="", severity="warn", basis=""):
        """檢核點。severity: 'stop' 未過即停止計算；'warn' 未過記警示並依 action 處理；'info' 只記錄。"""
        self.d["checks"].append(dict(name=name, passed=bool(passed), detail=str(detail), action=str(action),
                                     severity=severity, basis=basis))
        if not passed and severity in ("warn", "stop"):
            self.d["warnings"].append(f"檢核未過：{name}｜{detail}" + (f"｜處理：{action}" if action else ""))
        self.mon.flush()
        if not passed and severity == "stop":
            raise StopPipeline(f"{self.d['key']} 檢核未過：{name}（{detail}）")
        return passed

    def metric(self, name, value, unit="", target=None, ok=None, note=""):
        self.d["metrics"].append(dict(name=name, value=_jsonable(value), unit=unit, target=target,
                                      ok=None if ok is None else bool(ok), note=note))

    def image(self, name, fig, caption=""):
        fn = f"{self.d['key'].lower().replace('-', '_')}_{len(self.d['images']) + 1:02d}.png"
        path = os.path.join(self.mon.img_dir, fn)
        fig.savefig(path, dpi=110, bbox_inches="tight")
        import matplotlib.pyplot as plt
        plt.close(fig)
        self.d["images"].append(dict(name=name, src=f"img/{fn}", caption=caption))
        self.mon.flush()

    def table(self, name, columns, rows, note=""):
        self.d["tables"].append(dict(name=name, columns=columns, rows=_jsonable(rows), note=note))

    def warn(self, msg):
        self.d["warnings"].append(str(msg))

    def log(self, msg):
        self.d["log"].append(f"{datetime.now().strftime('%H:%M:%S')}  {msg}")
        self.mon.flush()

    def count(self, **kw):
        self.d["counts"].update(_jsonable(kw))


class NullStage:
    """準備期回溯等不需要監看細節的地方使用：介面相同、不記錄。"""
    def __init__(self):
        self.d = {}

    def check(self, name, passed, *a, severity="warn", **kw):
        if not passed and severity == "stop":
            raise StopPipeline(name)
        return passed

    def metric(self, *a, **kw): pass
    def image(self, name, fig, caption=""):
        import matplotlib.pyplot as plt
        plt.close(fig)
    def table(self, *a, **kw): pass
    def warn(self, *a, **kw): pass
    def log(self, *a, **kw): pass
    def count(self, **kw): pass


class Monitor:
    def __init__(self, root, run_id, meta):
        self.root = root
        self.run_id = run_id
        self.run_dir = os.path.join(root, run_id)
        self.img_dir = os.path.join(self.run_dir, "img")
        os.makedirs(self.img_dir, exist_ok=True)
        self.data = dict(run_id=run_id, meta=_jsonable(meta), status="running", started=_now(), ended=None,
                         seconds=None, stages=[], parcels={}, series={}, ledger=[], error=None)
        self._t0 = time.time()
        self._last_flush = 0
        self.ledger = ledger_mod.Ledger(os.path.join(self.run_dir, "ledger.jsonl"))
        self._register_run()
        self.flush(force=True)

    # ---- 步驟 ----
    @contextmanager
    def stage(self, key, title, spec=""):
        rec = StageRecord(self, key, title, spec)
        self.data["stages"].append(rec.d)
        self.flush(force=True)
        try:
            yield rec
        except StopPipeline as e:
            rec.d["status"] = "stop"
            rec.d["log"].append(str(e))
            self._close(rec)
            raise
        except Exception as e:
            rec.d["status"] = "error"
            rec.d["log"].append("".join(traceback.format_exception(type(e), e, e.__traceback__))[-3000:])
            self._close(rec)
            raise
        else:
            failed = [c for c in rec.d["checks"] if not c["passed"] and c["severity"] != "info"]
            rec.d["status"] = "warn" if (failed or rec.d["warnings"]) else "ok"
            self._close(rec)

    def _close(self, rec):
        rec.d["ended"] = _now()
        rec.d["seconds"] = round(time.time() - rec._t0, 2)
        summary = dict(stage=rec.d["key"], status=rec.d["status"], counts=rec.d["counts"],
                       checks=[(c["name"], c["passed"]) for c in rec.d["checks"]], outputs_hash=rec.d["outputs_hash"])
        entry = self.ledger.append(rec.d["key"], summary)
        self.data["ledger"].append(entry)
        self.flush(force=True)

    # ---- 單一坵塊的紀錄 ----
    def parcel(self, pid, stage, data):
        self.data["parcels"].setdefault(str(pid), {})[stage] = _jsonable(data)

    def series(self, pid, data):
        self.data["series"][str(pid)] = _jsonable(data)

    # ---- 輸出 ----
    def finish(self, status="done", error=None):
        self.data["status"] = status
        self.data["error"] = error
        self.data["ended"] = _now()
        self.data["seconds"] = round(time.time() - self._t0, 2)
        self.flush(force=True)
        self._register_run()

    def flush(self, force=False):
        if not force and time.time() - self._last_flush < 0.5:
            return
        self._last_flush = time.time()
        js = "window.SKY_RUN = " + json.dumps(_jsonable(self.data), ensure_ascii=False) + ";\n"
        tmp = os.path.join(self.run_dir, "monitor_data.js.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(js)
        os.replace(tmp, os.path.join(self.run_dir, "monitor_data.js"))

    def _register_run(self):
        idx_path = os.path.join(self.root, "index.json")
        runs = []
        if os.path.exists(idx_path):
            try:
                runs = json.load(open(idx_path, encoding="utf-8"))
            except Exception:
                runs = []
        runs = [r for r in runs if r["id"] != self.run_id]
        runs.insert(0, dict(id=self.run_id, started=self.data["started"], status=self.data["status"],
                            source=self.data["meta"].get("source"), event=self.data["meta"].get("event")))
        json.dump(runs, open(idx_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        with open(os.path.join(self.root, "index.js"), "w", encoding="utf-8") as f:
            f.write("window.SKY_RUNS = " + json.dumps(runs, ensure_ascii=False) + ";\n")
