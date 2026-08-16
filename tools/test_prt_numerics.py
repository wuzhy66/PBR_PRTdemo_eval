"""Build and run the standalone numerical regression executables。"""

from __future__ import annotations

import sys

from _tooling import REPOSITORY_ROOT, executable_name, run


def main() -> int:
    run([sys.executable, REPOSITORY_ROOT / "tools" / "build_prt_demo.py", "--renderer", "all"])
    binaries = (
        executable_name("frame_timing_tests"),
        executable_name("realtime_capture_tests"),
        executable_name("prt_numerics_phong"),
        executable_name("prt_numerics_pbr"),
    )
    for name in binaries:
        executable = REPOSITORY_ROOT / "PBR_PRTdemo" / "bin" / name
        if not executable.is_file():
            raise SystemExit(f"未找到 numerical test executable：{name}")
        run([executable], cwd=executable.parent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
