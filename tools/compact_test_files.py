"""将 trusted evaluation inputs 转换为未压缩的 compact 200-case bundle。"""

from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


DIAGNOSTIC_RESOLUTION = {
    "width": 200,
    "height": 150,
    "downsample": "linear-area-average",
}
REFERENCE_MANIFEST_NAME = "reference-manifest.json"
OCCLUSION_MASK_WEIGHTS_NAME = "occlusion-mask-weights.f32"
MAX_FILES = 500
MAX_BYTES = 500_000_000


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} 必须是 JSON object")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def read_pfm(path: Path) -> np.ndarray:
    with path.open("rb") as stream:
        magic = stream.readline().strip()
        dimensions = stream.readline().split()
        while dimensions and dimensions[0].startswith(b"#"):
            dimensions = stream.readline().split()
        if len(dimensions) != 2:
            raise ValueError(f"{path} PFM dimensions 无效")
        width, height = (int(value) for value in dimensions)
        scale = float(stream.readline())
        channels = 3 if magic == b"PF" else 1
        dtype = ("<" if scale < 0 else ">") + "f4"
        values = np.fromfile(stream, dtype=dtype, count=width * height * channels)
    if values.size != width * height * channels:
        raise ValueError(f"{path} PFM payload size 无效")
    return np.flipud(values.reshape((height, width, channels))).astype(
        np.float64, copy=False
    )


def write_pfm(path: Path, image: np.ndarray) -> None:
    value = np.asarray(image, dtype="<f4")
    if value.ndim != 3 or value.shape[2] not in (1, 3):
        raise ValueError("PFM image 必须是 HxWx1 或 HxWx3")
    height, width, channels = value.shape
    with path.open("wb") as stream:
        stream.write((b"PF\n" if channels == 3 else b"Pf\n"))
        stream.write(f"{width} {height}\n-1.0\n".encode("ascii"))
        stream.write(np.flipud(value).tobytes())


def downsample_area(image: np.ndarray, width: int, height: int) -> np.ndarray:
    value = np.asarray(image, dtype=np.float64)
    if value.ndim != 3:
        raise ValueError("downsample input 必须是 HxWxC")
    source_height, source_width, channels = value.shape
    if source_width % width != 0 or source_height % height != 0:
        raise ValueError(
            f"无法从 {source_width}x{source_height} area-average 到 {width}x{height}"
        )
    block_width = source_width // width
    block_height = source_height // height
    return value.reshape(
        height, block_height, width, block_width, channels
    ).mean(axis=(1, 3), dtype=np.float64)


def symmetric_l1(reference: np.ndarray, candidate: np.ndarray) -> float:
    reference = np.maximum(reference, 0.0)
    candidate = np.maximum(candidate, 0.0)
    denominator = float(np.sum(reference + candidate, dtype=np.float64))
    if denominator == 0.0:
        return 1.0
    error = float(np.sum(np.abs(candidate - reference), dtype=np.float64)) / denominator
    return max(0.0, min(1.0, 1.0 - error))


def weighted_score(flip: float, indirect: float) -> float:
    if flip <= 0.0 or indirect <= 0.0:
        return 0.0
    return math.exp(0.7 * math.log(flip) + 0.3 * math.log(indirect))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--baseline-report", type=Path, required=True)
    parser.add_argument("--baseline-realtime", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = args.source.resolve()
    baseline_report_path = args.baseline_report.resolve()
    baseline_realtime = args.baseline_realtime.resolve()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"output 已存在，拒绝覆盖：{output}")

    source_references = source / "references" / "cases"
    lines = [
        line
        for line in (source / "cases.jsonl").read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    if not lines:
        raise SystemExit("cases.jsonl 为空")
    baseline_report = read_json(baseline_report_path)
    baseline_cases = baseline_report.get("cases")
    if not isinstance(baseline_cases, list) or len(baseline_cases) != len(lines):
        raise SystemExit("baseline report case 数量不匹配")

    config = read_json(source / "render-score-config.json")
    config["schemaVersion"] = 6
    config["diagnosticResolution"] = DIAGNOSTIC_RESOLUTION
    output.mkdir(parents=True)
    shutil.copy2(source / "cases.jsonl", output / "cases.jsonl")
    shutil.copy2(
        source / "realtime-render-contract.json",
        output / "realtime-render-contract.json",
    )
    write_json(output / "render-score-config.json", config)

    width = int(DIAGNOSTIC_RESOLUTION["width"])
    height = int(DIAGNOSTIC_RESOLUTION["height"])
    output_references = output / "references"
    output_cases = output_references / "cases"
    output_cases.mkdir(parents=True)
    compact_baseline_cases: list[dict[str, Any]] = []
    common_manifest: dict[str, Any] | None = None
    mask_path = output_references / OCCLUSION_MASK_WEIGHTS_NAME
    with mask_path.open("wb") as mask_stream:
        for index, line in enumerate(lines, 1):
            case_id = f"case-{index:04d}"
            source_case = source_references / case_id
            destination_case = output_cases / case_id
            destination_case.mkdir()
            manifest = read_json(source_case / "manifest.json")
            static_manifest = {
                "samplesPerPixel": manifest.get("samplesPerPixel"),
                "antialiasing": manifest.get("antialiasing"),
                "displayResolution": {
                    "width": manifest.get("width"),
                    "height": manifest.get("height"),
                },
            }
            if common_manifest is None:
                common_manifest = static_manifest
            elif static_manifest != common_manifest:
                raise SystemExit(f"{case_id} reference manifest static fields 不一致")
            if int(manifest.get("samplesPerPixel", 0)) < 4096:
                raise SystemExit(f"{case_id} reference SPP < 4096")
            if manifest.get("antialiasing") != config["antialiasing"]:
                raise SystemExit(f"{case_id} antialiasing protocol 不匹配")

            offline_full = read_pfm(source_case / "offline-indirect-linear.pfm")
            offline_compact = downsample_area(offline_full, width, height)
            write_pfm(
                destination_case / "offline-indirect-linear.pfm",
                offline_compact,
            )
            shutil.copy2(source_case / "offline.png", destination_case / "offline.png")

            mask = np.asarray(
                Image.open(source_case / "offline-occlusion-mask.pgm").convert("L"),
                dtype=np.float64,
            )
            mask_weight = np.rint(mask * 4.0 / 255.0) / 4.0
            compact_mask_weight = downsample_area(
                mask_weight[:, :, np.newaxis], width, height
            )[:, :, 0]
            mask_stream.write(np.asarray(compact_mask_weight, dtype="<f4").tobytes())

            baseline_case = baseline_cases[index - 1]
            if baseline_case.get("id") != case_id or baseline_case.get("mode") != "strict":
                raise SystemExit(f"baseline {case_id} id/mode 不匹配")
            baseline_full = read_pfm(
                baseline_realtime / "cases" / case_id / "indirect-linear.pfm"
            )
            flip = float(baseline_case["scores"]["perceptualFlip"])
            old_total = weighted_score(flip, symmetric_l1(offline_full, baseline_full))
            if not math.isclose(
                old_total,
                float(baseline_case["totalScore"]),
                rel_tol=0.0,
                abs_tol=5.0e-10,
            ):
                raise SystemExit(f"baseline {case_id} 与 full-resolution report 不一致")
            baseline_compact = downsample_area(baseline_full, width, height)
            indirect = symmetric_l1(offline_compact, baseline_compact)
            compact_baseline_cases.append(
                {
                    "id": case_id,
                    "definitionFingerprint": baseline_case["definitionFingerprint"],
                    "mode": "strict",
                    "scores": {
                        "perceptualFlip": flip,
                        "indirectTransport": indirect,
                    },
                    "diagnosticScores": {
                        "worstPatchFlip": float(
                            baseline_case["diagnosticScores"]["worstPatchFlip"]
                        )
                    },
                    "totalScore": weighted_score(flip, indirect),
                }
            )
            if index % 10 == 0 or index == len(lines):
                print(f"Compacted {index}/{len(lines)} cases", flush=True)

    assert common_manifest is not None
    reference_manifest = {
        "schemaVersion": 1,
        "caseCount": len(lines),
        **common_manifest,
        "diagnosticResolution": DIAGNOSTIC_RESOLUTION,
        "occlusionMaskWeights": {
            "path": OCCLUSION_MASK_WEIGHTS_NAME,
            "format": "float32-little-endian-case-major",
        },
    }
    write_json(output_references / REFERENCE_MANIFEST_NAME, reference_manifest)
    compact_baseline_report = {
        "schemaVersion": 1,
        "sourceProtocolFingerprint": baseline_report.get("protocolFingerprint"),
        "diagnosticResolution": DIAGNOSTIC_RESOLUTION,
        "weights": config["weights"],
        "regressionGates": config["regressionGates"],
        "cases": compact_baseline_cases,
    }
    write_json(output / "baseline-score-report.json", compact_baseline_report)

    files = [path for path in output.rglob("*") if path.is_file()]
    total_bytes = sum(path.stat().st_size for path in files)
    if len(files) > MAX_FILES:
        raise SystemExit(f"compact bundle 文件数超过 {MAX_FILES}：{len(files)}")
    if total_bytes > MAX_BYTES:
        raise SystemExit(f"compact bundle 大小超过 500 MB：{total_bytes} bytes")
    print(
        f"Compact bundle ready：{output}，files={len(files)}，"
        f"bytes={total_bytes}，MB={total_bytes / 1_000_000:.2f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
