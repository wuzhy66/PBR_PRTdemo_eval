"""将 realtime PRT 与 CPU offline reference 汇总成可解释的 0~1 渲染分数。"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

TOOLS_DIRECTORY = Path(__file__).resolve().parent
if str(TOOLS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIRECTORY))

from render_metric_images import write_case_metric_images, write_existing_metric_overview

try:
    import flip_evaluator
except ImportError as error:
    raise SystemExit(
        "缺少 FLIP evaluator；请运行：python -m pip install -r "
        "requirements.txt"
    ) from error


LUMINANCE = np.asarray([0.2126, 0.7152, 0.0722], dtype=np.float64)
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="评测 manual render dataset，分数范围为 0~1")
    parser.add_argument("--test-set", type=Path, required=True, help="render-state JSONL test set")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).with_name("render-score-config.json"),
        help="评分权重与 FLIP viewing condition",
    )
    parser.add_argument(
        "--realtime-root", type=Path, required=True, help="本次 realtime run 输出根目录",
    )
    parser.add_argument(
        "--reference-root", type=Path, required=True, help="本次 trusted reference run 输出根目录",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="JSON report 路径；默认写入 realtime run 根目录",
    )
    parser.add_argument(
        "--label",
        default="",
        help="报告标签，例如 baseline、candidate 或 git revision",
    )
    parser.add_argument(
        "--min-reference-spp",
        type=int,
        default=4096,
        help="排除低于该 SPP 的 reference；v3 正式评分要求 4096",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="任一纳入 case 缺少 linear AOV/mask 时返回失败",
    )
    parser.add_argument(
        "--reuse-metrics-from",
        type=Path,
        help="复用既有逐 case 指标；缺少新 diagnostic 时只补所需计算，不重算其他指标",
    )
    parser.add_argument(
        "--refresh-overviews",
        action="store_true",
        help="复用指标时同步刷新 metrics-explained.png；默认跳过以保持快速重聚合",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def report_path(path: Path) -> str:
    """报告中只保存 repository-relative 或脱敏 external path。"""
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return f"<external>/{resolved.name}"


def sanitize_error_message(message: str, roots: dict[str, Path]) -> str:
    sanitized = message
    ordered = sorted(roots.items(), key=lambda item: len(str(item[1])), reverse=True)
    for label, root in ordered:
        resolved = root.resolve()
        for spelling in {str(resolved), resolved.as_posix()}:
            sanitized = sanitized.replace(spelling, f"<{label}>")
    return sanitized


def render_states_equivalent(
    expected: dict[str, Any], actual: dict[str, Any], *, absolute_tolerance: float = 1.0e-5
) -> bool:
    """比较 replay state，并容纳 JSON -> float32 -> JSON 的可预期舍入。"""
    try:
        if set(expected) != {"camera", "light"} or set(actual) != {"camera", "light"}:
            return False
        if set(expected["camera"]) != {"position", "yawDegrees", "pitchDegrees"}:
            return False
        if set(actual["camera"]) != {"position", "yawDegrees", "pitchDegrees"}:
            return False
        if set(expected["light"]) != {"position", "intensity"}:
            return False
        if set(actual["light"]) != {"position", "intensity"}:
            return False

        expected_values = (
            list(expected["camera"]["position"])
            + [expected["camera"]["yawDegrees"], expected["camera"]["pitchDegrees"]]
            + list(expected["light"]["position"])
            + list(expected["light"]["intensity"])
        )
        actual_values = (
            list(actual["camera"]["position"])
            + [actual["camera"]["yawDegrees"], actual["camera"]["pitchDegrees"]]
            + list(actual["light"]["position"])
            + list(actual["light"]["intensity"])
        )
        if len(expected_values) != 11 or len(actual_values) != 11:
            return False
        return all(
            math.isclose(
                float(expected_value),
                float(actual_value),
                rel_tol=0.0,
                abs_tol=absolute_tolerance,
            )
            for expected_value, actual_value in zip(expected_values, actual_values)
        )
    except (KeyError, TypeError, ValueError):
        return False


def read_test_set(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        state = json.loads(line)
        if set(state) != {"camera", "light"}:
            raise ValueError(f"test set 第 {line_number} 行含非 render-state 字段")
        if set(state["camera"]) != {"position", "yawDegrees", "pitchDegrees"}:
            raise ValueError(f"test set 第 {line_number} 行 camera schema 无效")
        if set(state["light"]) != {"position", "intensity"}:
            raise ValueError(f"test set 第 {line_number} 行 light schema 无效")
        intensity = state["light"]["intensity"]
        if (
            not isinstance(intensity, list)
            or len(intensity) != 3
            or any(
                not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0.0
                or value > 500.0
                for value in intensity
            )
        ):
            raise ValueError(f"test set 第 {line_number} 行 light intensity 无效")
        cases.append(state)
    return cases


def file_set_hash(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    return digest.hexdigest()


def read_pfm(path: Path) -> np.ndarray:
    with path.open("rb") as stream:
        magic = stream.readline().strip()
        if magic not in (b"PF", b"Pf"):
            raise ValueError(f"不是 PFM：{path}")
        dimensions = stream.readline().split()
        while dimensions and dimensions[0].startswith(b"#"):
            dimensions = stream.readline().split()
        if len(dimensions) != 2:
            raise ValueError(f"PFM dimensions 无效：{path}")
        width, height = (int(value) for value in dimensions)
        scale = float(stream.readline().strip())
        endian = "<" if scale < 0 else ">"
        channels = 3 if magic == b"PF" else 1
        values = np.frombuffer(stream.read(), dtype=endian + "f4")
    expected = width * height * channels
    if values.size != expected:
        raise ValueError(f"PFM payload size 无效：{path}，expected={expected}, actual={values.size}")
    image = values.reshape((height, width, channels))
    return np.flipud(image).astype(np.float64, copy=False)


def resolve_image(case_dir: Path, images: dict[str, Any], key: str, fallback: str) -> Path:
    return case_dir / str(images.get(key, fallback))


def require_same_shape(label: str, first: np.ndarray, second: np.ndarray) -> None:
    if first.shape != second.shape:
        raise ValueError(f"{label} resolution 不一致：{first.shape} vs {second.shape}")


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def symmetric_l1_similarity(reference: np.ndarray, candidate: np.ndarray) -> tuple[float, float]:
    reference = np.maximum(reference, 0.0)
    candidate = np.maximum(candidate, 0.0)
    denominator = float(np.sum(reference + candidate, dtype=np.float64))
    if denominator == 0.0:
        return 1.0, 0.0
    error = float(np.sum(np.abs(candidate - reference), dtype=np.float64)) / denominator
    return clamp01(1.0 - error), error


def occlusion_leak_similarity(
    reference: np.ndarray, candidate: np.ndarray, mask: np.ndarray
) -> tuple[float, float, int]:
    # PGM 以 8-bit 保存 0/4...4/4 coverage；还原到精确 quarter，避免 64/255 的量化偏差。
    mask_weight = np.rint(mask.astype(np.float64) * 4.0 / 255.0) / 4.0
    selected = mask_weight > 0.0
    selected_pixels = int(np.count_nonzero(selected))
    if selected_pixels == 0:
        # 当前 camera/light 几何可能没有被遮挡 subpixel；此时没有可观测 leak，因而不施加 penalty。
        return 1.0, 0.0, 0
    reference_luminance = np.maximum(reference, 0.0) @ LUMINANCE
    candidate_luminance = np.maximum(candidate, 0.0) @ LUMINANCE
    reference_values = reference_luminance[selected]
    candidate_values = candidate_luminance[selected]
    weights = mask_weight[selected]
    denominator = float(
        np.sum(weights * np.maximum(reference_values, candidate_values), dtype=np.float64)
    )
    if denominator == 0.0:
        return 1.0, 0.0, selected_pixels
    excess = float(
        np.sum(weights * np.maximum(candidate_values - reference_values, 0.0), dtype=np.float64)
    )
    ratio = excess / denominator
    return clamp01(1.0 - ratio), ratio, selected_pixels


def weighted_geometric_mean(scores: dict[str, float], weights: dict[str, float]) -> float:
    positive_weights = {name: weight for name, weight in weights.items() if weight > 0.0}
    weight_sum = sum(positive_weights.values())
    if weight_sum <= 0.0:
        raise ValueError("至少需要一个正权重")
    for name in positive_weights:
        if name not in scores:
            raise ValueError(f"缺少 weighted metric：{name}")
        if scores[name] <= 0.0:
            return 0.0
    log_score = sum(
        weight * math.log(scores[name]) for name, weight in positive_weights.items()
    ) / weight_sum
    return clamp01(math.exp(log_score))


def worst_patch_flip_similarity(
    flip_map: np.ndarray, *, tile_size: int, percentile: float
) -> tuple[float, float, int]:
    """将 FLIP map 分块后取高分位 tile mean，强调成片 artifact 而非单 pixel。"""
    values = np.asarray(flip_map, dtype=np.float64).squeeze()
    if values.ndim != 2 or values.size == 0:
        raise ValueError("FLIP map 必须是非空二维数组")
    if not np.all(np.isfinite(values)):
        raise ValueError("FLIP map 含 NaN/Inf")
    if tile_size <= 0:
        raise ValueError("worst-patch tileSize 必须为正整数")
    if not 0.0 <= percentile <= 1.0:
        raise ValueError("worst-patch percentile 必须位于 [0,1]")

    tile_means = [
        float(np.mean(values[y:y + tile_size, x:x + tile_size], dtype=np.float64))
        for y in range(0, values.shape[0], tile_size)
        for x in range(0, values.shape[1], tile_size)
    ]
    tail_error = float(np.quantile(tile_means, percentile))
    return clamp01(1.0 - tail_error), clamp01(tail_error), len(tile_means)


def score_case(case_id: str, state: dict[str, Any], config: dict[str, Any],
               realtime_root: Path, reference_root: Path,
               minimum_reference_spp: int) -> dict[str, Any]:
    realtime_dir = realtime_root / "cases" / case_id
    reference_dir = reference_root / "cases" / case_id
    reference_manifest = read_json(reference_dir / "manifest.json")
    reference_spp = int(reference_manifest.get("samplesPerPixel", 0))
    if reference_spp < minimum_reference_spp:
        raise ValueError(
            f"case {case_id} reference SPP {reference_spp} < {minimum_reference_spp}"
        )
    if reference_manifest.get("antialiasing") != config.get("antialiasing"):
        raise ValueError(f"case {case_id} antialiasing protocol 不匹配")
    realtime_display = realtime_dir / "realtime.png"
    offline_display = reference_dir / "offline.png"
    if not realtime_display.is_file() or not offline_display.is_file():
        missing = [report_path(path) for path in (realtime_display, offline_display) if not path.is_file()]
        raise FileNotFoundError("缺少 display 输入：" + ", ".join(missing))

    flip_map, flip_error, flip_parameters = flip_evaluator.evaluate(
        str(offline_display),
        str(realtime_display),
        "LDR",
        applyMagma=False,
        parameters={"ppd": float(config["flip"]["pixelsPerDegree"])},
    )
    flip_colormap, _, _ = flip_evaluator.evaluate(
        str(offline_display),
        str(realtime_display),
        "LDR",
        applyMagma=True,
        computeMeanError=False,
        parameters={"ppd": float(config["flip"]["pixelsPerDegree"])},
    )
    perceptual_score = clamp01(1.0 - float(flip_error))
    worst_patch_config = config["flip"]["worstPatch"]
    worst_patch_score, worst_patch_error, worst_patch_tiles = worst_patch_flip_similarity(
        flip_map,
        tile_size=int(worst_patch_config["tileSize"]),
        percentile=float(worst_patch_config["percentile"]),
    )
    result: dict[str, Any] = {
        "id": case_id,
        "definitionFingerprint": canonical_hash(state),
        "referenceSamplesPerPixel": reference_spp,
        "mode": "provisional",
        "scores": {"perceptualFlip": perceptual_score},
        "diagnosticScores": {"worstPatchFlip": worst_patch_score},
        "rawErrors": {
            "meanFlip": float(flip_error),
            "maxFlip": float(np.max(flip_map)),
            "worstPatchFlip": worst_patch_error,
            "worstPatchTileCount": worst_patch_tiles,
        },
        "flipParameters": {
            "pixelsPerDegree": float(flip_parameters["ppd"]),
            "worstPatch": worst_patch_config,
        },
        "strictMissing": [],
    }

    realtime_indirect = realtime_dir / "indirect-linear.pfm"
    offline_indirect = reference_dir / "offline-indirect-linear.pfm"
    occlusion_mask = reference_dir / "offline-occlusion-mask.pgm"
    for path in (realtime_indirect, offline_indirect, occlusion_mask):
        if not path.is_file():
            result["strictMissing"].append(report_path(path))
    if result["strictMissing"]:
        return result

    replay_metadata_path = realtime_dir / "state.json"
    if not replay_metadata_path.is_file():
        raise FileNotFoundError(
            f"realtime capture 缺少 state metadata：{report_path(replay_metadata_path)}"
        )
    replay_metadata = read_json(replay_metadata_path)
    replay_metadata.pop("id", None)
    if not render_states_equivalent(state, replay_metadata):
        raise ValueError(f"case {result['id']} realtime camera/light state 不一致")

    realtime_linear = read_pfm(realtime_indirect)
    offline_linear = read_pfm(offline_indirect)
    require_same_shape("indirect linear AOV", offline_linear, realtime_linear)
    mask = np.asarray(Image.open(occlusion_mask).convert("L"))
    require_same_shape("occlusion mask", offline_linear[:, :, 0], mask)

    transport_score, transport_error = symmetric_l1_similarity(offline_linear, realtime_linear)
    leak_score, leak_ratio, mask_pixels = occlusion_leak_similarity(
        offline_linear, realtime_linear, mask
    )
    result["mode"] = "strict"
    result["referenceFingerprint"] = file_set_hash(
        [offline_display, offline_indirect, occlusion_mask]
    )
    result["scores"].update(
        {
            "indirectTransport": transport_score,
            "occlusionLeak": leak_score,
        }
    )
    result["rawErrors"].update(
        {
            "indirectSymmetricL1": transport_error,
            "occlusionLeakExcessRatio": leak_ratio,
        }
    )
    result["occlusionMaskPixels"] = mask_pixels
    result["totalScore"] = weighted_geometric_mean(result["scores"], config["weights"])
    result["metricImages"] = write_case_metric_images(
        reference_dir,
        realtime_dir,
        case_id,
        offline_linear,
        realtime_linear,
        mask,
        flip_colormap,
        {**result["scores"], **result["diagnosticScores"]},
    )
    return result


def mean(values: list[float]) -> float | None:
    return float(sum(values) / len(values)) if values else None


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    aggregate = report["aggregate"]
    lines = [
        "# Rendering score report",
        "",
        f"- Strict score: `{aggregate['strictScore']}`",
        f"- Perceptual-only score: `{aggregate['perceptualScore']}`",
        f"- Strict coverage: `{aggregate['strictCases']}/{aggregate['includedCases']}`",
        "",
        "| Case | Mode | Total | FLIP | Worst patch | Transport | Leak | SPP |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for case in report["cases"]:
        scores = case["scores"]
        lines.append(
            "| {id} | {mode} | {total} | {flip} | {worst_patch} | {transport} | {leak} | {spp} |".format(
                id=case["id"],
                mode=case["mode"],
                total="—" if "totalScore" not in case else f"{case['totalScore']:.6f}",
                flip=f"{scores['perceptualFlip']:.6f}",
                worst_patch=f"{case['diagnosticScores']['worstPatchFlip']:.6f}",
                transport="—" if "indirectTransport" not in scores else f"{scores['indirectTransport']:.6f}",
                leak="—" if "occlusionLeak" not in scores else f"{scores['occlusionLeak']:.6f}",
                spp=case["referenceSamplesPerPixel"],
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_case_score_files(realtime_root: Path, report: dict[str, Any]) -> None:
    common = {
        "schemaVersion": 1,
        "label": report["label"],
        "protocolFingerprint": report["protocolFingerprint"],
        "evaluationSetFingerprint": report["evaluationSetFingerprint"],
        "aggregation": report["aggregation"],
        "weights": report["weights"],
        "diagnosticMetrics": report["diagnosticMetrics"],
        "regressionGates": report["regressionGates"],
    }
    entries = list(report["cases"])
    entries.extend(
        {"id": error["id"], "mode": "error", "error": error["error"]}
        for error in report["errors"]
    )
    for entry in entries:
        case_directory = realtime_root / "cases" / entry["id"]
        case_directory.mkdir(parents=True, exist_ok=True)
        payload = {**common, **entry}
        (case_directory / "score.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


def reuse_case_metrics(
    report_path_value: Path,
    states: list[dict[str, Any]],
    config: dict[str, Any],
    minimum_reference_spp: int,
    realtime_root: Path,
    reference_root: Path,
    refresh_overviews: bool,
) -> list[dict[str, Any]]:
    """复用不受 aggregation weights 影响的逐 case 原始指标。"""
    previous = read_json(report_path_value.resolve())
    previous_cases = previous.get("cases", [])
    if previous.get("errors") or previous.get("excluded"):
        raise ValueError("不能从包含 error 或 excluded case 的 report 复用指标")
    if len(previous_cases) != len(states):
        raise ValueError("既有 report 与 test set 的 case 数量不一致")

    cases: list[dict[str, Any]] = []
    required_scores = set(config["weights"])
    for index, (state, previous_case) in enumerate(zip(states, previous_cases), 1):
        case_id = f"case-{index:04d}"
        if previous_case.get("id") != case_id:
            raise ValueError(f"既有 report 的 case 顺序不一致：预期 {case_id}")
        if previous_case.get("definitionFingerprint") != canonical_hash(state):
            raise ValueError(f"既有 report 的 render state 不匹配：{case_id}")
        if int(previous_case.get("referenceSamplesPerPixel", 0)) < minimum_reference_spp:
            raise ValueError(f"既有 report 的 reference SPP 不足：{case_id}")
        case = dict(previous_case)
        scores = case.get("scores", {})
        missing = sorted(required_scores - set(scores))
        if missing:
            raise ValueError(f"既有 report 缺少 {case_id} 指标：{', '.join(missing)}")
        if "worstPatchFlip" in config.get("diagnosticMetrics", []):
            diagnostic_scores = dict(case.get("diagnosticScores", {}))
            if "worstPatchFlip" not in diagnostic_scores:
                offline_display = reference_root / "cases" / case_id / "offline.png"
                realtime_display = realtime_root / "cases" / case_id / "realtime.png"
                flip_map, _, flip_parameters = flip_evaluator.evaluate(
                    str(offline_display),
                    str(realtime_display),
                    "LDR",
                    applyMagma=False,
                    computeMeanError=False,
                    parameters={"ppd": float(config["flip"]["pixelsPerDegree"])},
                )
                worst_patch_config = config["flip"]["worstPatch"]
                score, error, tile_count = worst_patch_flip_similarity(
                    flip_map,
                    tile_size=int(worst_patch_config["tileSize"]),
                    percentile=float(worst_patch_config["percentile"]),
                )
                diagnostic_scores["worstPatchFlip"] = score
                raw_errors = dict(case.get("rawErrors", {}))
                raw_errors["worstPatchFlip"] = error
                raw_errors["worstPatchTileCount"] = tile_count
                case["rawErrors"] = raw_errors
                flip_config = dict(case.get("flipParameters", {}))
                flip_config["pixelsPerDegree"] = float(flip_parameters["ppd"])
                flip_config["worstPatch"] = worst_patch_config
                case["flipParameters"] = flip_config
                metric_images = dict(case.get("metricImages", {}))
                metric_images["worstPatchFlip"] = {
                    "offline": {"root": "reference-case", "path": "offline.png"},
                    "realtime": {"root": "realtime-case", "path": "realtime.png"},
                    "error": {
                        "root": "realtime-case",
                        "path": "error-perceptual-flip.png",
                    },
                }
                case["metricImages"] = metric_images
            case["diagnosticScores"] = diagnostic_scores
        case["totalScore"] = weighted_geometric_mean(scores, config["weights"])
        if refresh_overviews:
            write_existing_metric_overview(
                reference_root / "cases" / case_id,
                realtime_root / "cases" / case_id,
                case_id,
                {**scores, **case["diagnosticScores"]},
            )
        cases.append(case)
    return cases


def main() -> int:
    args = parse_args()
    config = read_json(args.config)
    test_set = args.test_set.resolve()
    realtime_root = args.realtime_root.resolve()
    reference_root = args.reference_root.resolve()
    output = (args.output or realtime_root / "score-report.json").resolve()
    states = read_test_set(test_set)
    cases: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    if args.reuse_metrics_from:
        cases = reuse_case_metrics(
            args.reuse_metrics_from,
            states,
            config,
            args.min_reference_spp,
            realtime_root,
            reference_root,
            args.refresh_overviews,
        )
    else:
        for index, state in enumerate(states, 1):
            case_id = f"case-{index:04d}"
            try:
                cases.append(score_case(case_id, state, config, realtime_root,
                                        reference_root, args.min_reference_spp))
            except Exception as error:  # 每个坏 case 都写入 report，避免整批结果静默消失。
                errors.append(
                    {
                        "id": case_id,
                        "error": sanitize_error_message(
                            str(error),
                            {
                                "test-set": test_set,
                                "realtime-root": realtime_root,
                                "reference-root": reference_root,
                                "repository": REPOSITORY_ROOT,
                            },
                        ),
                    }
                )

    strict_scores = [case["totalScore"] for case in cases if case["mode"] == "strict"]
    perceptual_scores = [case["scores"]["perceptualFlip"] for case in cases]
    normalization = {
        "perceptualFlip": "1 - mean(FLIP)",
        "indirectTransport": "1 - sum(abs(candidate-reference)) / sum(candidate+reference)",
        "occlusionLeak": "1 - sum(mask*max(candidate-reference,0)) / sum(mask*max(candidate,reference))",
        "worstPatchFlip": "1 - p95(mean(FLIP over 32x32 tiles))",
    }
    protocol = {
        "scoreConfigSchemaVersion": config["schemaVersion"],
        "evaluatorSourceSha256": file_set_hash([Path(__file__).resolve()]),
        "flipEvaluatorVersion": importlib.metadata.version("flip-evaluator"),
        "antialiasing": config["antialiasing"],
        "aggregation": config["aggregation"],
        "weights": config["weights"],
        "diagnosticMetrics": config.get("diagnosticMetrics", []),
        "regressionGates": config.get("regressionGates", {}),
        "flip": config["flip"],
        "normalization": normalization,
    }
    strict_case_fingerprints = [
        {
            "id": case["id"],
            "definition": case["definitionFingerprint"],
            "reference": case["referenceFingerprint"],
        }
        for case in cases
        if case["mode"] == "strict"
    ]
    report = {
        "schemaVersion": 2,
        "label": args.label,
        "testSet": report_path(test_set),
        "realtimeRoot": report_path(realtime_root),
        "referenceRoot": report_path(reference_root),
        "normalization": normalization,
        "aggregation": config["aggregation"],
        "weights": config["weights"],
        "diagnosticMetrics": config.get("diagnosticMetrics", []),
        "regressionGates": config.get("regressionGates", {}),
        "protocolFingerprint": canonical_hash(protocol),
        "protocol": protocol,
        "evaluationSetFingerprint": canonical_hash(strict_case_fingerprints),
        "selection": {
            "minimumReferenceSamplesPerPixel": args.min_reference_spp,
            "strictRequired": args.strict,
        },
        "aggregate": {
            "strictScore": mean(strict_scores),
            "perceptualScore": mean(perceptual_scores),
            "worstPatchFlipScore": mean(
                [case["diagnosticScores"]["worstPatchFlip"] for case in cases]
            ),
            "strictCases": len(strict_scores),
            "includedCases": len(cases),
            "excludedCases": len(excluded),
            "errorCases": len(errors),
        },
        "cases": cases,
        "excluded": excluded,
        "errors": errors,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(output.with_suffix(".md"), report)
    write_case_score_files(realtime_root, report)
    print(json.dumps(report["aggregate"], ensure_ascii=False, indent=2))
    print(f"Report: {report_path(output)}")

    has_incomplete = any(case["mode"] != "strict" for case in cases)
    if errors or not cases or (args.strict and has_incomplete):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
