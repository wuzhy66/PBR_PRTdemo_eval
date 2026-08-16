"""Reject machine absolute paths from tracked text in both repositories。"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from _tooling import REPOSITORY_ROOT


TEXT_EXTENSIONS = {
    ".c", ".cc", ".cmake", ".cpp", ".h", ".hpp", ".ini", ".json", ".md",
    ".py", ".toml", ".txt", ".xml", ".yaml", ".yml",
}
MACHINE_PATH = re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]|/(?:home|Users|usr|opt|var|tmp)/")


def tracked_files(repository: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repository), "ls-files"], check=True, capture_output=True, text=True
    )
    return result.stdout.splitlines()


def main() -> int:
    repositories = (("trusted", REPOSITORY_ROOT), ("realtime", REPOSITORY_ROOT / "PBR_PRTdemo"))
    violations: list[str] = []
    for label, repository in repositories:
        if not (repository / ".git").exists():
            raise SystemExit(f"缺少 {label} Git repository")
        for relative in tracked_files(repository):
            path = repository / relative
            if not path.is_file() or path.suffix not in TEXT_EXTENSIONS:
                continue
            content = path.read_text(encoding="utf-8", errors="ignore")
            # env-based shebang 是 portable executable lookup，不是用户机器数据路径。
            portable_shebang = r"\A#!\s*/" + r"usr/bin/env[^\r\n]*(?:\r?\n)?"
            content = re.sub(portable_shebang, "", content)
            if MACHINE_PATH.search(content):
                portable = relative.replace("\\", "/")
                violations.append(f"{label}/{portable}")
    if violations:
        raise SystemExit("tracked text 暴露 machine absolute path：" + ", ".join(violations))
    print("PASS：trusted/realtime tracked text 不含 machine absolute path。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
