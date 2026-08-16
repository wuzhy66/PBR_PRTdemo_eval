"""使用当前平台的 CMake/Ninja toolchain 构建 trusted CPU offline renderer。"""

from __future__ import annotations

from _tooling import (
    REPOSITORY_ROOT,
    native_build_tools,
    offline_build_directory,
    offline_renderer_executable,
    run,
)


def main() -> int:
    tools = native_build_tools()
    environment = tools["environment"]
    source = REPOSITORY_ROOT / "offline"
    build = offline_build_directory()
    run(
        [
            tools["cmake"],
            "-S",
            source,
            "-B",
            build,
            "-G",
            "Ninja",
            f"-DCMAKE_MAKE_PROGRAM={tools['ninja']}",
            "-DCMAKE_BUILD_TYPE=Release",
        ],
        env=environment,
    )
    run([tools["cmake"], "--build", build, "--config", "Release"], env=environment)
    executable = offline_renderer_executable()
    if not executable.is_file():
        raise SystemExit(f"构建结束但未找到 {executable}")
    print(f"Executable={executable.relative_to(REPOSITORY_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
