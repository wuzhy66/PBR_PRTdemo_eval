"""Windows visual regression runner for realtime PRT modes。"""

from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import json
import math
import os
import shutil
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageGrab

from _tooling import REPOSITORY_ROOT, resolve_repo_path, run


if os.name != "nt":
    raise SystemExit(
        "tools/test_visual.py 是 Win32 interactive window screenshot runner；"
        "Linux 请使用 tools/replay_render_dataset.py --software-rendering。"
    )


class RECT(ctypes.Structure):
    _fields_ = (("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long))


class POINT(ctypes.Structure):
    _fields_ = (("x", ctypes.c_long), ("y", ctypes.c_long))


USER32 = ctypes.windll.user32
ENUM_WINDOWS_PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行 PRT visual regression")
    parser.add_argument("--renderer", choices=("all", "phong", "pbr"), default="all", type=str.lower)
    parser.add_argument(
        "--modes", nargs="+", choices=("combined", "direct", "indirect", "probes"),
        default=("combined", "direct", "indirect", "probes"),
    )
    parser.add_argument("--bands", type=int, choices=(2, 3, 4), default=3)
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--include-dynamic", action="store_true")
    parser.add_argument("--settle-seconds", type=float, default=3.0)
    parser.add_argument("--dynamic-interval-seconds", type=float, default=4.0)
    parser.add_argument("--output-directory")
    parser.add_argument("--baseline-directory")
    parser.add_argument("--update-baseline", action="store_true")
    parser.add_argument("--baseline-rms-threshold", type=float, default=3.0)
    args = parser.parse_args()
    if not 0.5 <= args.settle_seconds <= 30.0:
        parser.error("--settle-seconds 必须在 0.5..30")
    if not 1.0 <= args.dynamic_interval_seconds <= 30.0:
        parser.error("--dynamic-interval-seconds 必须在 1..30")
    if not 0.0 <= args.baseline_rms_threshold <= 255.0:
        parser.error("--baseline-rms-threshold 必须在 0..255")
    return args


def window_for_process(process_id: int) -> int | None:
    handles: list[int] = []

    @ENUM_WINDOWS_PROC
    def callback(handle: int, _: int) -> bool:
        owner = wintypes.DWORD()
        USER32.GetWindowThreadProcessId(handle, ctypes.byref(owner))
        if owner.value == process_id and USER32.IsWindowVisible(handle):
            handles.append(handle)
            return False
        return True

    USER32.EnumWindows(callback, 0)
    return handles[0] if handles else None


def start_renderer(executable: Path, renderer: str, mode: str, bands: int, dynamic: bool):
    environment = os.environ.copy()
    environment.update(
        {
            "PRT_VISUAL_TEST": "1",
            "PRT_RENDERER": renderer,
            "PRT_TEST_MODE": mode,
            "PRT_BANDS": str(bands),
            "PRT_DYNAMIC": "1" if dynamic else "0",
        }
    )
    process = subprocess.Popen([str(executable)], cwd=executable.parent, env=environment)
    deadline = time.monotonic() + 20.0
    handle = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"demo 在创建窗口前退出，exit code={process.returncode}")
        handle = window_for_process(process.pid)
        if handle:
            break
        time.sleep(0.1)
    if not handle:
        process.kill()
        raise RuntimeError("等待 demo 窗口超时")
    USER32.ShowWindow(handle, 9)
    USER32.SetWindowPos(handle, 0, 40, 40, 0, 0, 0x0041)
    USER32.SetForegroundWindow(handle)
    return process, handle


def stop_renderer(process: subprocess.Popen[Any] | None) -> None:
    if process is not None and process.poll() is None:
        process.kill()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass


def save_client_screenshot(handle: int, path: Path) -> None:
    rect = RECT()
    if not USER32.GetClientRect(handle, ctypes.byref(rect)):
        raise RuntimeError("GetClientRect 失败")
    origin = POINT()
    if not USER32.ClientToScreen(handle, ctypes.byref(origin)):
        raise RuntimeError("ClientToScreen 失败")
    width, height = rect.right - rect.left, rect.bottom - rect.top
    if width <= 0 or height <= 0:
        raise RuntimeError(f"无效窗口尺寸：{width}x{height}")
    USER32.SetForegroundWindow(handle)
    time.sleep(0.25)
    image = ImageGrab.grab((origin.x, origin.y, origin.x + width, origin.y + height))
    image.save(path)


def rgb(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float64)


def analyze(path: Path) -> dict[str, float | int]:
    pixels = rgb(path)
    luma = pixels @ np.asarray([0.2126, 0.7152, 0.0722])
    return {
        "width": int(pixels.shape[1]),
        "height": int(pixels.shape[0]),
        "meanLuma": float(np.mean(luma)),
        "stdDevLuma": float(np.std(luma)),
        "darkPixelRatio": float(np.mean(luma < 3.0)),
    }


def rms_difference(first: Path, second: Path) -> float:
    a, b = rgb(first), rgb(second)
    if a.shape != b.shape:
        return math.inf
    return float(np.sqrt(np.mean(np.square(a - b))))


def portable_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return f"<external>/{path.name}"


def result_row(renderer: str, scenario: str, image: Path | None, **values: Any) -> dict[str, Any]:
    return {
        "renderer": renderer,
        "scenario": scenario,
        "image": None if image is None else portable_path(image),
        **values,
    }


def main() -> int:
    args = parse_args()
    output = resolve_repo_path(
        args.output_directory
        or f"test-results/visual/{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}"
    )
    output.mkdir(parents=True, exist_ok=True)
    baseline = None
    if args.update_baseline and not args.baseline_directory:
        baseline = REPOSITORY_ROOT / "tests" / "visual-baseline"
    elif args.baseline_directory:
        baseline = resolve_repo_path(args.baseline_directory)
    if baseline is not None:
        baseline.mkdir(parents=True, exist_ok=True)
    if not args.skip_build:
        run(
            [
                sys.executable,
                REPOSITORY_ROOT / "tools" / "build_prt_demo.py",
                "--renderer",
                args.renderer,
            ]
        )
    executable = REPOSITORY_ROOT / "PBR_PRTdemo" / "bin" / "getting_started" / "PRTdemo.exe"
    if not executable.is_file():
        raise SystemExit("未找到 realtime executable")
    renderers = ("phong", "pbr") if args.renderer == "all" else (args.renderer,)
    results: list[dict[str, Any]] = []
    failures: list[str] = []
    warnings: list[str] = []
    for renderer in renderers:
        scenario_images: dict[str, Path] = {}
        for mode in args.modes:
            process = None
            filename = f"{renderer}-{mode}-sh{args.bands}.png"
            image_path = output / filename
            try:
                process, handle = start_renderer(executable, renderer, mode, args.bands, False)
                time.sleep(args.settle_seconds)
                if process.poll() is not None:
                    raise RuntimeError(f"demo 在截图前退出，exit code={process.returncode}")
                save_client_screenshot(handle, image_path)
                stats = analyze(image_path)
                passed = (
                    stats["meanLuma"] > 1.0
                    and stats["stdDevLuma"] > 2.0
                    and stats["darkPixelRatio"] < 0.99
                )
                if not passed:
                    failures.append(f"{renderer}/{mode} 截图疑似空白或无有效渲染")
                baseline_rms = None
                if baseline is not None:
                    baseline_path = baseline / filename
                    if args.update_baseline:
                        shutil.copy2(image_path, baseline_path)
                    elif baseline_path.is_file():
                        baseline_rms = rms_difference(baseline_path, image_path)
                        if baseline_rms > args.baseline_rms_threshold:
                            failures.append(
                                f"{renderer}/{mode} baseline RMS={baseline_rms:.3f}，"
                                f"超过阈值 {args.baseline_rms_threshold:.3f}"
                            )
                    else:
                        warnings.append(f"缺少 baseline：{filename}")
                scenario_images[mode] = image_path
                results.append(
                    result_row(
                        renderer,
                        mode,
                        image_path,
                        width=stats["width"],
                        height=stats["height"],
                        meanLuma=round(float(stats["meanLuma"]), 3),
                        stdDevLuma=round(float(stats["stdDevLuma"]), 3),
                        darkPixelRatio=round(float(stats["darkPixelRatio"]), 5),
                        baselineRms=None if baseline_rms is None else round(baseline_rms, 3),
                        passed=passed,
                    )
                )
            except Exception as error:
                failures.append(f"{renderer}/{mode}：{error}")
            finally:
                stop_renderer(process)
        for first, second in (("combined", "direct"), ("combined", "indirect"), ("direct", "indirect")):
            if first in scenario_images and second in scenario_images:
                difference = rms_difference(scenario_images[first], scenario_images[second])
                passed = difference >= 1.0
                if not passed:
                    failures.append(f"{renderer} 的 {first}/{second} 几乎无视觉差异，RMS={difference:.3f}")
                results.append(
                    result_row(
                        renderer,
                        f"{first}-vs-{second}",
                        None,
                        width=None,
                        height=None,
                        meanLuma=None,
                        stdDevLuma=None,
                        darkPixelRatio=None,
                        baselineRms=round(difference, 3),
                        passed=passed,
                    )
                )
        if args.include_dynamic:
            process = None
            first_path = output / f"{renderer}-dynamic-a-sh{args.bands}.png"
            second_path = output / f"{renderer}-dynamic-b-sh{args.bands}.png"
            try:
                process, handle = start_renderer(executable, renderer, "combined", args.bands, True)
                time.sleep(args.settle_seconds)
                save_client_screenshot(handle, first_path)
                time.sleep(args.dynamic_interval_seconds)
                save_client_screenshot(handle, second_path)
                difference = rms_difference(first_path, second_path)
                passed = difference >= 0.5
                if not passed:
                    failures.append(f"{renderer} dynamic 场景变化不足，RMS={difference:.3f}")
                results.append(
                    result_row(
                        renderer, "dynamic", second_path, width=None, height=None,
                        meanLuma=None, stdDevLuma=None, darkPixelRatio=None,
                        baselineRms=round(difference, 3), passed=passed,
                    )
                )
            except Exception as error:
                failures.append(f"{renderer}/dynamic：{error}")
            finally:
                stop_renderer(process)
    report = {
        "generatedAt": dt.datetime.now(dt.timezone.utc).astimezone().isoformat(),
        "renderer": args.renderer,
        "bands": args.bands,
        "outputDirectory": portable_path(output),
        "results": results,
        "warnings": warnings,
        "failures": failures,
        "passed": not failures,
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    markdown = [
        "# PRT visual test report",
        "",
        f"- 结果：{'PASS' if report['passed'] else 'FAIL'}",
        f"- SH bands：{args.bands}",
        f"- 生成时间：{report['generatedAt']}",
        "",
        "| Renderer | Scenario | Metric/RMS | Passed |",
        "|---|---|---:|:---:|",
    ]
    for item in results:
        metric = (
            f"mean={item['meanLuma']}, std={item['stdDevLuma']}"
            if item["meanLuma"] is not None
            else f"RMS={item['baselineRms']}"
        )
        markdown.append(f"| {item['renderer']} | {item['scenario']} | {metric} | {item['passed']} |")
    if failures:
        markdown.extend(("", "## Failures", *(f"- {value}" for value in failures)))
    if warnings:
        markdown.extend(("", "## Warnings", *(f"- {value}" for value in warnings)))
    (output / "report.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    for item in results:
        print(
            f"{item['renderer']:6} {item['scenario']:24} "
            f"mean={str(item['meanLuma']):>8} std={str(item['stdDevLuma']):>8} "
            f"rms={str(item['baselineRms']):>8} passed={item['passed']}"
        )
    print(f"Visual report: {portable_path(output / 'report.md')}")
    if failures:
        raise SystemExit("visual test 失败，详见 report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
