"""Build the nested realtime renderer repository。"""

from __future__ import annotations

import argparse
import sys

from _tooling import REPOSITORY_ROOT, run


def main() -> int:
    parser = argparse.ArgumentParser(description="构建 realtime PRT demo")
    parser.add_argument("--renderer", choices=("all", "phong", "pbr"), default="all", type=str.lower)
    args = parser.parse_args()
    run(
        [
            sys.executable,
            REPOSITORY_ROOT / "PBR_PRTdemo" / "tools" / "build.py",
            "--renderer",
            args.renderer,
        ]
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
