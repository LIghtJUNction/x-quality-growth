#!/usr/bin/env python3
"""Synthetic panel-order demo: placeholder text files, explicitly assigned mtimes.

This demonstrates sorting logic, not AI image generation or a verified product bug.
Only a TemporaryDirectory is touched; its files are removed when the demo ends.
"""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory


def demo():
    with TemporaryDirectory(prefix="synthetic-panel-order-") as directory:
        root = Path(directory)
        manifest = []
        for index in range(1, 5):
            path = root / f"panel-{index}.txt"
            path.write_text(f"Synthetic placeholder for panel {index}\n", encoding="utf-8")
            os.utime(path, ns=(index * 1_000_000_000, index * 1_000_000_000))
            manifest.append({"panel_index": index, "path": path.name})

        def mtime_order():
            return [int(path.stem.split("-")[1]) for path in
                    sorted(root.glob("panel-*.txt"), key=lambda path: path.stat().st_mtime_ns)]

        before = mtime_order()
        second = root / "panel-2.txt"
        second.write_text("Synthetic rewritten placeholder for panel 2\n", encoding="utf-8")
        os.utime(second, ns=(5_000_000_000, 5_000_000_000))
        retry = mtime_order()
        safe = [item["panel_index"] for item in
                sorted(manifest, key=lambda item: (item["panel_index"], item["path"]))]
        return {"scope": "synthetic .txt placeholders and assigned mtimes; sorting logic only",
                "before": before, "retry": retry, "safe": safe,
                "pass_checks": before == [1, 2, 3, 4] and retry == [1, 3, 4, 2] and safe == [1, 2, 3, 4]}


if __name__ == "__main__":
    print(json.dumps(demo(), ensure_ascii=False, separators=(",", ":")))
