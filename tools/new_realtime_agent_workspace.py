"""Clone a physically independent realtime-only agent workspace。"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from _tooling import REPOSITORY_ROOT


def main() -> int:
    parser = argparse.ArgumentParser(description="创建 realtime-only agent workspace")
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    source = REPOSITORY_ROOT / "PBR_PRTdemo"
    destination = args.destination.resolve()
    if destination.exists():
        raise SystemExit("agent workspace 已存在，拒绝覆盖")
    if not (source / ".git").exists():
        raise SystemExit("PBR_PRTdemo 尚未初始化为独立 Git repository")
    completed = subprocess.run(["git", "clone", "--no-local", str(source), str(destination)])
    if completed.returncode != 0:
        raise SystemExit(f"创建 realtime agent workspace 失败，exit code={completed.returncode}")
    print("Realtime-only agent workspace ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
