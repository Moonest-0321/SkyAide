"""作業日誌：每一步完成寫一筆，每筆記下前一筆的雜湊，形成雜湊鏈（表 37）。刪改任何一筆，其後鏈結即斷開。"""
import hashlib
import json
from datetime import datetime, timezone


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256(b):
    if isinstance(b, str):
        b = b.encode("utf-8")
    return hashlib.sha256(b).hexdigest()


class Ledger:
    def __init__(self, path):
        self.path = path
        self.prev = "0" * 64
        open(path, "w").close()

    def append(self, stage, summary):
        body = dict(stage=stage, at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    summary=summary, prev=self.prev)
        h = sha256(canonical(body))
        entry = dict(body, hash=h)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(canonical(entry) + "\n")
        self.prev = h
        return entry


def verify_file(path):
    prev = "0" * 64
    for i, line in enumerate(open(path, encoding="utf-8")):
        e = json.loads(line)
        h = e.pop("hash")
        if e["prev"] != prev or sha256(canonical(e)) != h:
            return False, i
        prev = h
    return True, None
