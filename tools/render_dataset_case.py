"""Render one trusted offline reference from a render-state JSON file。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from _tooling import (
    REPOSITORY_ROOT,
    format_number,
    format_vector,
    load_contract,
    offline_renderer_executable,
    read_json,
    resolve_repo_path,
    run,
    validate_render_state,
)
from render_metric_images import prepare_reference_metric_images


def render_case(
    state: dict[str, Any],
    output: Path,
    samples_per_pixel: int,
    *,
    skip_build: bool,
    renderer_threads: int | None = None,
) -> None:
    if samples_per_pixel < 4 or samples_per_pixel > 65536 or samples_per_pixel % 4 != 0:
        raise ValueError("samples-per-pixel 必须在 4..65536 且能被 4 整除")
    contract = load_contract(REPOSITORY_ROOT / "realtime-render-contract.json")
    validate_render_state(state, contract)
    width = int(contract["camera"]["width"])
    height = int(contract["camera"]["height"])
    if contract["camera"]["viewport"] != [0, 0, width, height]:
        raise ValueError("render contract 的 viewport 无效")
    if contract["camera"]["ssaaRasterViewport"] != [0, 0, width * 2, height * 2]:
        raise ValueError("render contract 的 deterministic 2x2 SSAA viewport 无效")
    if int(contract["lighting"]["indirectBounces"]) != 1:
        raise ValueError("offline renderer 只接受 one indirect bounce contract")
    if output.exists():
        raise FileExistsError(f"reference output 已存在，拒绝覆盖：{output.name}")
    output.mkdir(parents=True)
    if not skip_build:
        run([sys.executable, REPOSITORY_ROOT / "tools" / "build_offline_renderer.py"])
    executable = offline_renderer_executable()
    if not executable.is_file():
        raise FileNotFoundError(f"缺少 offline renderer executable：{executable.name}")
    camera = state["camera"]
    light = state["light"]
    material = contract["material"]
    command = [
            executable,
            f"--output={output}",
            f"--width={width}",
            f"--height={height}",
            f"--spp={samples_per_pixel}",
            "--bounces=2",
            "--seed=20260812",
            f"--camera-position={format_vector(camera['position'])}",
            f"--camera-yaw={format_number(camera['yawDegrees'])}",
            f"--camera-pitch={format_number(camera['pitchDegrees'])}",
            f"--camera-fov={format_number(contract['camera']['verticalFovDegrees'])}",
            f"--light-position={format_vector(light['position'])}",
            f"--light-intensity={format_vector(light['intensity'])}",
            f"--material-metallic={format_number(material['metallic'])}",
            f"--material-roughness={format_number(material['roughness'])}",
            f"--material-ior={format_number(material['ior'])}",
            f"--material-ao={format_number(material['ao'])}",
        ]
    if renderer_threads is not None:
        if renderer_threads < 1:
            raise ValueError("renderer_threads 必须大于 0")
        command.append(f"--threads={renderer_threads}")
    run(command)
    prepare_reference_metric_images(output)


def main() -> int:
    parser = argparse.ArgumentParser(description="渲染一条 offline reference case")
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--output-directory", required=True)
    parser.add_argument("--samples-per-pixel", type=int, default=4096)
    parser.add_argument("--threads", type=int)
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()
    state_path = resolve_repo_path(args.state)
    render_case(
        read_json(state_path),
        resolve_repo_path(args.output_directory),
        args.samples_per_pixel,
        skip_build=args.skip_build,
        renderer_threads=args.threads,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
