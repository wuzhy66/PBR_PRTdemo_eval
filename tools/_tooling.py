"""Trusted evaluation CLI shared helpers。"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
IS_WINDOWS = os.name == "nt"


def resolve_repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (REPOSITORY_ROOT / path).resolve()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run(
    command: list[str | Path],
    *,
    cwd: Path = REPOSITORY_ROOT,
    env: dict[str, str] | None = None,
    accepted_codes: tuple[int, ...] = (0,),
) -> int:
    completed = subprocess.run([str(value) for value in command], cwd=cwd, env=env)
    if completed.returncode not in accepted_codes:
        raise SystemExit(f"命令执行失败，exit code={completed.returncode}：{command[0]}")
    return completed.returncode


def find_visual_studio() -> Path:
    command = shutil.which("vswhere.exe")
    if command is None:
        program_files_x86 = os.environ.get("ProgramFiles(x86)")
        if program_files_x86:
            candidate = Path(program_files_x86) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
            if candidate.is_file():
                command = str(candidate)
    if command is None:
        raise SystemExit("找不到 vswhere.exe；请安装 Visual Studio Installer。")
    result = subprocess.run(
        [
            command,
            "-latest",
            "-products",
            "*",
            "-requires",
            "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
            "-property",
            "installationPath",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        raise SystemExit("未找到带 C++ x64 toolset 的 Visual Studio。")
    return Path(lines[0])


def visual_studio_tools() -> dict[str, Path]:
    root = find_visual_studio()
    tools = {
        "vcvars": root / "VC" / "Auxiliary" / "Build" / "vcvars64.bat",
        "cmake": root / "Common7" / "IDE" / "CommonExtensions" / "Microsoft" / "CMake" / "CMake" / "bin" / "cmake.exe",
        "ctest": root / "Common7" / "IDE" / "CommonExtensions" / "Microsoft" / "CMake" / "CMake" / "bin" / "ctest.exe",
        "ninja": root / "Common7" / "IDE" / "CommonExtensions" / "Microsoft" / "CMake" / "Ninja" / "ninja.exe",
    }
    missing = [name for name, path in tools.items() if not path.is_file()]
    if missing:
        raise SystemExit("缺少 Visual Studio build dependency：" + ", ".join(missing))
    return tools


def command_path(name: str) -> Path:
    command = shutil.which(name)
    if command is None:
        raise SystemExit(f"找不到 build dependency：{name}")
    return Path(command)


def native_build_tools() -> dict[str, Path | dict[str, str]]:
    """返回当前平台的 CMake/Ninja toolchain 与已配置环境。"""

    if IS_WINDOWS:
        tools = visual_studio_tools()
        return {
            "cmake": tools["cmake"],
            "ctest": tools["ctest"],
            "ninja": tools["ninja"],
            "environment": developer_environment(tools["vcvars"]),
        }
    if os.name != "posix":
        raise SystemExit(f"不支持的 build platform：{os.name}")
    command_path("c++")
    return {
        "cmake": command_path("cmake"),
        "ctest": command_path("ctest"),
        "ninja": command_path("ninja"),
        "environment": os.environ.copy(),
    }


def executable_name(stem: str) -> str:
    return stem + (".exe" if IS_WINDOWS else "")


def offline_build_directory() -> Path:
    return REPOSITORY_ROOT / "offline" / (
        "build-auto-vs2022-ninja" if IS_WINDOWS else "build-auto-linux-ninja"
    )


def offline_renderer_executable() -> Path:
    return offline_build_directory() / executable_name("prt_offline_reference")


def realtime_renderer_executable(repository: Path) -> Path:
    return repository / "bin" / "getting_started" / executable_name("PRTdemo")


def developer_environment(vcvars: Path) -> dict[str, str]:
    result = subprocess.run(
        f'call "{vcvars}" >nul && set',
        shell=True,
        check=True,
        capture_output=True,
        text=True,
        encoding=os.device_encoding(1) or "utf-8",
        errors="replace",
    )
    environment = os.environ.copy()
    for line in result.stdout.splitlines():
        if "=" in line and not line.startswith("="):
            key, value = line.split("=", 1)
            environment[key] = value
    return environment


def assert_exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise ValueError(f"{label} 只允许字段 {sorted(expected)}，actual={sorted(actual)}")


def validate_render_state(state: dict[str, Any], contract: dict[str, Any]) -> None:
    assert_exact_keys(state, {"camera", "light"}, "state")
    assert_exact_keys(state["camera"], {"position", "yawDegrees", "pitchDegrees"}, "camera")
    assert_exact_keys(state["light"], {"position", "intensity"}, "light")
    for label, values in (
        ("camera.position", state["camera"]["position"]),
        ("light.position", state["light"]["position"]),
        ("light.intensity", state["light"]["intensity"]),
    ):
        if not isinstance(values, list) or len(values) != 3:
            raise ValueError(f"{label} 必须包含 3 个 number")
        if any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in values):
            raise ValueError(f"{label} 包含无效 number")
    minimum = contract["light"]["intensityRange"]["minimum"]
    maximum = contract["light"]["intensityRange"]["maximum"]
    if any(
        float(value) < float(minimum[index]) or float(value) > float(maximum[index])
        for index, value in enumerate(state["light"]["intensity"])
    ):
        raise ValueError("light.intensity 超出 render contract 范围")


def load_contract(path: Path) -> dict[str, Any]:
    contract = read_json(path)
    if contract.get("contractId") != "prt-realtime-render-v3":
        raise ValueError(f"不支持的 render contract：{contract.get('contractId')}")
    if contract["output"]["realtime"]["path"] != "cases/<case-id>/realtime.png":
        raise ValueError("render contract 的 realtime output path 无效")
    return contract


def format_number(value: int | float) -> str:
    return repr(float(value))


def format_vector(values: list[int | float]) -> str:
    if len(values) != 3:
        raise ValueError("vector 必须包含 3 个 number")
    return ",".join(format_number(value) for value in values)
