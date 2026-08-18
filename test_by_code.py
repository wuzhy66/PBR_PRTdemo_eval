#!/usr/bin/env python3
"""Standalone trusted evaluator for a realtime PRT candidate.

允许的任务数据输入只有 /workspace 与 /test_files；所有临时产物和最终结果均写入
/eval。最终 /eval/code_result.json 只包含 resolved、score、reason 三个字段。
"""

from __future__ import annotations

import concurrent.futures
import contextlib
import hashlib
import importlib.metadata
import json
import math
import multiprocessing
import os
import re
import selectors
import shutil
import statistics
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any, Iterator


WORKSPACE = Path("/workspace")
TEST_FILES = Path("/test_files")
EVAL_ROOT = Path("/eval")
RESULT_PATH = EVAL_ROOT / "code_result.json"
RUNTIME_ROOT = EVAL_ROOT / "test_by_code_runtime"

REQUIRED_RESULT_KEYS = {"resolved", "score", "reason"}
REQUIRED_CAPTURE_FILES = ("realtime.png", "indirect-linear.pfm", "state.json")
REFERENCE_MANIFEST_NAME = "reference-manifest.json"
OCCLUSION_MASK_WEIGHTS_NAME = "occlusion-mask-weights.f32"
LUMINANCE = (0.2126, 0.7152, 0.0722)

_numpy: Any = None
_image: Any = None
_flip_evaluator: Any = None


class EvaluationError(RuntimeError):
    pass


def load_dependencies() -> None:
    global _numpy, _image, _flip_evaluator
    if _numpy is not None:
        return
    try:
        import numpy as numpy_module
        from PIL import Image as image_module
        import flip_evaluator as flip_module
    except ImportError as error:
        raise EvaluationError(
            "缺少 Python dependency；需要 flip-evaluator==1.7、numpy 和 Pillow"
        ) from error
    try:
        flip_version = importlib.metadata.version("flip-evaluator")
    except importlib.metadata.PackageNotFoundError as error:
        raise EvaluationError("无法确认 flip-evaluator version") from error
    if flip_version != "1.7":
        raise EvaluationError(f"flip-evaluator version 必须为 1.7，actual={flip_version}")
    _numpy = numpy_module
    _image = image_module
    _flip_evaluator = flip_module


def sanitized(text: str) -> str:
    value = str(text).replace("\r", " ").replace("\n", " ")
    for root, label in (
        (WORKSPACE, "<workspace>"),
        (TEST_FILES, "<test_files>"),
        (EVAL_ROOT, "<eval>"),
    ):
        for spelling in {str(root), root.as_posix()}:
            value = value.replace(spelling, label)
    return " ".join(value.split())[:1200]


def write_result(result: dict[str, Any]) -> None:
    if set(result) != REQUIRED_RESULT_KEYS:
        raise RuntimeError("internal result schema error")
    resolved = result["resolved"]
    score = result["score"]
    reason = result["reason"]
    if not isinstance(resolved, bool):
        raise RuntimeError("resolved must be boolean")
    if not isinstance(score, (int, float)) or isinstance(score, bool):
        raise RuntimeError("score must be numeric")
    score = float(score)
    if not math.isfinite(score) or not 0.0 <= score <= 1.0:
        raise RuntimeError("score must be finite and in [0,1]")
    if not isinstance(reason, str):
        raise RuntimeError("reason must be string")
    if score <= 0.0:
        resolved = False
    payload = {"resolved": resolved, "score": score, "reason": sanitized(reason)}
    EVAL_ROOT.mkdir(parents=True, exist_ok=True)
    temporary = EVAL_ROOT / ".code_result.json.tmp"
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, RESULT_PATH)


def require_directory(path: Path, label: str) -> Path:
    if not path.is_dir():
        raise EvaluationError(f"缺少 {label} directory")
    return path


def require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise EvaluationError(f"缺少 {label} file")
    return path


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise EvaluationError(f"{path.name} 必须是 JSON object")
    return value


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parse_test_set(path: Path, contract: dict[str, Any]) -> list[dict[str, Any]]:
    lines = [line for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if not lines:
        raise EvaluationError("test set 为空")
    states: list[dict[str, Any]] = []
    intensity_minimum = contract["light"]["intensityRange"]["minimum"]
    intensity_maximum = contract["light"]["intensityRange"]["maximum"]
    for line_number, line in enumerate(lines, 1):
        try:
            state = json.loads(line)
            if set(state) != {"camera", "light"}:
                raise ValueError("state fields")
            if set(state["camera"]) != {"position", "yawDegrees", "pitchDegrees"}:
                raise ValueError("camera fields")
            if set(state["light"]) != {"position", "intensity"}:
                raise ValueError("light fields")
            vectors = (
                state["camera"]["position"],
                state["light"]["position"],
                state["light"]["intensity"],
            )
            if any(not isinstance(vector, list) or len(vector) != 3 for vector in vectors):
                raise ValueError("vector shape")
            values = (
                list(state["camera"]["position"])
                + [state["camera"]["yawDegrees"], state["camera"]["pitchDegrees"]]
                + list(state["light"]["position"])
                + list(state["light"]["intensity"])
            )
            if any(
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(float(value))
                for value in values
            ):
                raise ValueError("non-finite value")
            intensity = state["light"]["intensity"]
            if any(
                float(value) < float(intensity_minimum[index])
                or float(value) > float(intensity_maximum[index])
                for index, value in enumerate(intensity)
            ):
                raise ValueError("intensity range")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise EvaluationError(f"test set 第 {line_number} 行无效：{error}") from error
        states.append(state)
    return states


def validate_contract(candidate: dict[str, Any], trusted: dict[str, Any]) -> None:
    if trusted.get("contractId") != "prt-realtime-render-v3":
        raise EvaluationError("test_files render contract 不受支持")
    if candidate != trusted:
        raise EvaluationError("workspace public render contract 与 trusted contract 不一致")


def validate_config(config: dict[str, Any]) -> None:
    expected_weights = {
        "perceptualFlip": 0.7,
        "indirectTransport": 0.3,
        "occlusionLeak": 0.0,
    }
    if config.get("schemaVersion") != 6:
        raise EvaluationError("score config schemaVersion 必须为 6")
    if config.get("aggregation") != "weighted-geometric-mean":
        raise EvaluationError("score aggregation 不匹配")
    if config.get("weights") != expected_weights:
        raise EvaluationError("score weights 必须为 FLIP 70% / Indirect 30%")
    gates = config.get("regressionGates", {})
    if gates != {
        "requirePositiveMedianPerceptualFlipDelta": True,
        "requirePositiveMedianWorstPatchFlipDelta": True,
    }:
        raise EvaluationError("regression gate policy 不匹配")
    worst = config.get("flip", {}).get("worstPatch", {})
    if config.get("flip", {}).get("pixelsPerDegree") != 67.0:
        raise EvaluationError("FLIP pixelsPerDegree 必须为 67")
    if worst != {"tileSize": 32, "percentile": 0.95}:
        raise EvaluationError("worst-patch FLIP config 不匹配")
    diagnostic = config.get("diagnosticResolution", {})
    if diagnostic != {
        "width": 200,
        "height": 150,
        "downsample": "linear-area-average",
    }:
        raise EvaluationError("diagnostic resolution config 不匹配")


def validate_reference_bundle(
    reference_root: Path, config: dict[str, Any], case_count: int
) -> dict[str, Any]:
    manifest = read_json(
        require_file(reference_root / REFERENCE_MANIFEST_NAME, "reference manifest")
    )
    if manifest.get("schemaVersion") != 1:
        raise EvaluationError("reference manifest schemaVersion 必须为 1")
    if manifest.get("caseCount") != case_count:
        raise EvaluationError("reference manifest caseCount 与 test set 不一致")
    if int(manifest.get("samplesPerPixel", 0)) < 4096:
        raise EvaluationError("reference SPP < 4096")
    if manifest.get("antialiasing") != config["antialiasing"]:
        raise EvaluationError("reference antialiasing protocol 不匹配")
    if manifest.get("diagnosticResolution") != config["diagnosticResolution"]:
        raise EvaluationError("reference diagnostic resolution 不匹配")
    mask = manifest.get("occlusionMaskWeights", {})
    expected_mask = {
        "path": OCCLUSION_MASK_WEIGHTS_NAME,
        "format": "float32-little-endian-case-major",
    }
    if mask != expected_mask:
        raise EvaluationError("reference occlusion mask format 不匹配")
    mask_path = require_file(
        reference_root / OCCLUSION_MASK_WEIGHTS_NAME,
        "reference occlusion mask weights",
    )
    resolution = config["diagnosticResolution"]
    expected_bytes = case_count * int(resolution["width"]) * int(resolution["height"]) * 4
    if mask_path.stat().st_size != expected_bytes:
        raise EvaluationError("reference occlusion mask weights size 不匹配")
    return manifest


def discover_reference_cases(
    reference_root: Path, total_case_count: int
) -> list[tuple[str, int]]:
    cases_root = require_directory(reference_root / "cases", "reference cases")
    selected: list[tuple[str, int]] = []
    for path in cases_root.iterdir():
        if not path.is_dir() or not path.name.startswith("case"):
            continue
        name = path.name
        match = re.search(r"(\d+)$", name)
        if match is None:
            raise EvaluationError(f"reference case directory 缺少 numeric id：{name}")
        index = int(match.group(1))
        if index < 1 or index > total_case_count:
            raise EvaluationError(f"reference case id 越界：{name}")
        require_file(path / "offline.png", f"{name} offline.png")
        require_file(
            path / "offline-indirect-linear.pfm",
            f"{name} offline indirect",
        )
        selected.append((name, index))
    if not selected:
        raise EvaluationError("reference cases 为空")
    indices = [index for _, index in selected]
    if len(indices) != len(set(indices)):
        raise EvaluationError("reference case id 重复")
    return sorted(selected, key=lambda item: (item[1], item[0]))


def validate_baseline(
    report: dict[str, Any],
    states: list[dict[str, Any]],
    config: dict[str, Any],
    case_indices: list[int],
) -> list[dict[str, Any]]:
    if report.get("schemaVersion") != 1:
        raise EvaluationError("baseline score report schemaVersion 必须为 1")
    if report.get("diagnosticResolution") != config["diagnosticResolution"]:
        raise EvaluationError("baseline diagnostic resolution 不匹配")
    if report.get("weights") != config["weights"]:
        raise EvaluationError("baseline score weights 不匹配")
    if report.get("regressionGates") != config["regressionGates"]:
        raise EvaluationError("baseline regression gates 不匹配")
    cases = report.get("cases")
    if not isinstance(cases, list):
        raise EvaluationError("baseline cases 必须是 array")
    cases_by_id: dict[str, dict[str, Any]] = {}
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str):
            raise EvaluationError("baseline case id 无效")
        case_id = case["id"]
        if case_id in cases_by_id:
            raise EvaluationError(f"baseline case id 重复：{case_id}")
        cases_by_id[case_id] = case
    validated: list[dict[str, Any]] = []
    for index in case_indices:
        case_id = f"case-{index:04d}"
        state = states[index - 1]
        try:
            case = cases_by_id[case_id]
            if case["id"] != case_id or case["mode"] != "strict":
                raise ValueError("case id/mode")
            if case["definitionFingerprint"] != canonical_hash(state):
                raise ValueError("definition fingerprint")
            total = float(case["totalScore"])
            flip = float(case["scores"]["perceptualFlip"])
            worst = float(case["diagnosticScores"]["worstPatchFlip"])
            if not all(0.0 <= value <= 1.0 for value in (total, flip, worst)):
                raise ValueError("score range")
        except (KeyError, TypeError, ValueError) as error:
            raise EvaluationError(f"baseline {case_id} 无效：{error}") from error
        validated.append({"id": case_id, "total": total, "flip": flip, "worst": worst})
    return validated


def copy_source_repository(repository: Path, destination: Path, label: str) -> None:
    require_directory(repository, label)
    excluded_exact = {".git", ".claude", "bin", "test-results", "__pycache__"}
    excluded_prefixes = (
        "build-",
        "capture-validation",
        "iteration-render",
        "diagnostics-",
        "tmp-",
    )

    def ignored(directory: str, names: list[str]) -> set[str]:
        ignored_names: set[str] = set()
        for name in names:
            source = Path(directory) / name
            if source.is_symlink():
                raise EvaluationError(f"{label} 不允许 symbolic link")
            if name in excluded_exact or name.startswith(excluded_prefixes):
                ignored_names.add(name)
        return ignored_names

    shutil.copytree(repository, destination, ignore=ignored, symlinks=False)


def command_path(name: str) -> str:
    value = shutil.which(name)
    if value is None:
        raise EvaluationError(f"缺少 system command：{name}")
    return value


def run_command(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str] | None = None,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise EvaluationError(f"command timeout：{Path(command[0]).name}") from error


def command_failure(label: str, completed: subprocess.CompletedProcess[str]) -> EvaluationError:
    detail = (completed.stderr or completed.stdout or "no output")[-2000:]
    return EvaluationError(f"{label}，exit={completed.returncode}：{detail}")


def build_environment() -> dict[str, str]:
    environment = os.environ.copy()
    if os.name == "posix":
        # Candidate 以 Windows/VS2022 为主要开发目标。统一补入 POSIX declaration，
        # 只解决 container build portability，不修改待测源码或 rendering behavior。
        existing = environment.get("CXXFLAGS", "").strip()
        environment["CXXFLAGS"] = f"{existing} -include unistd.h".strip()
    return environment


def build_renderer(source: Path, build: Path, *, run_tests: bool) -> tuple[Path, bool]:
    cmake = command_path("cmake")
    ninja = command_path("ninja")
    environment = build_environment()
    configure = run_command(
        [
            cmake,
            "-S",
            str(source),
            "-B",
            str(build),
            "-G",
            "Ninja",
            f"-DCMAKE_MAKE_PROGRAM={ninja}",
            "-DCMAKE_BUILD_TYPE=Release",
            "-DBUILD_TESTING=ON",
        ],
        cwd=source,
        environment=environment,
        timeout=600,
    )
    if configure.returncode != 0:
        raise command_failure("CMake configure 失败", configure)
    parallel = str(min(8, max(1, os.cpu_count() or 1)))
    compiled = run_command(
        [cmake, "--build", str(build), "--config", "Release", "--parallel", parallel],
        cwd=source,
        environment=environment,
        timeout=1200,
    )
    if compiled.returncode != 0:
        raise command_failure("candidate build 失败", compiled)
    executable = source / "bin" / "getting_started" / (
        "PRTdemo.exe" if os.name == "nt" else "PRTdemo"
    )
    require_file(executable, "candidate renderer")
    ctest = shutil.which("ctest")
    tests_passed = not run_tests
    if run_tests and ctest is not None:
        tested = run_command(
            [ctest, "--test-dir", str(build), "--output-on-failure", "-C", "Release"],
            cwd=source,
            timeout=600,
        )
        tests_passed = tested.returncode == 0
    return executable, tests_passed


@contextlib.contextmanager
def software_gl_environment() -> Iterator[dict[str, str]]:
    environment = os.environ.copy()
    for key in list(environment):
        if key.startswith("PRT_"):
            del environment[key]
    environment.update(
        {
            "LIBGL_ALWAYS_SOFTWARE": "true",
            "GALLIUM_DRIVER": "llvmpipe",
            "LP_NUM_THREADS": str(min(8, max(1, os.cpu_count() or 1))),
        }
    )
    xvfb: subprocess.Popen[str] | None = None
    if os.name == "posix" and not environment.get("DISPLAY"):
        xvfb_command = command_path("Xvfb")
        xvfb = subprocess.Popen(
            [xvfb_command, "-displayfd", "1", "-screen", "0", "1600x1200x24", "-nolisten", "tcp"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if xvfb.stdout is None:
            raise EvaluationError("无法读取 Xvfb display")
        selector = selectors.DefaultSelector()
        selector.register(xvfb.stdout, selectors.EVENT_READ)
        ready = selector.select(timeout=15)
        selector.close()
        if not ready:
            xvfb.terminate()
            raise EvaluationError("Xvfb startup timeout")
        display_number = xvfb.stdout.readline().strip()
        if not display_number.isdigit():
            detail = xvfb.stderr.read() if xvfb.stderr is not None else ""
            xvfb.terminate()
            raise EvaluationError(f"Xvfb startup 失败：{detail}")
        environment["DISPLAY"] = f":{display_number}"
    try:
        yield environment
    finally:
        if xvfb is not None:
            xvfb.terminate()
            try:
                xvfb.wait(timeout=10)
            except subprocess.TimeoutExpired:
                xvfb.kill()
                xvfb.wait(timeout=5)


def format_number(value: int | float) -> str:
    return repr(float(value))


def format_vector(values: list[int | float]) -> str:
    return ",".join(format_number(value) for value in values)


def render_states_equivalent(expected: dict[str, Any], actual: dict[str, Any]) -> bool:
    try:
        if set(actual) != {"camera", "light"}:
            return False
        values_expected = (
            list(expected["camera"]["position"])
            + [expected["camera"]["yawDegrees"], expected["camera"]["pitchDegrees"]]
            + list(expected["light"]["position"])
            + list(expected["light"]["intensity"])
        )
        values_actual = (
            list(actual["camera"]["position"])
            + [actual["camera"]["yawDegrees"], actual["camera"]["pitchDegrees"]]
            + list(actual["light"]["position"])
            + list(actual["light"]["intensity"])
        )
        return len(values_expected) == len(values_actual) == 11 and all(
            math.isclose(float(first), float(second), rel_tol=0.0, abs_tol=1.0e-5)
            for first, second in zip(values_expected, values_actual)
        )
    except (KeyError, TypeError, ValueError):
        return False


def capture_cases(
    executable: Path,
    source: Path,
    output: Path,
    selected_cases: list[tuple[str, int, dict[str, Any]]],
    contract: dict[str, Any],
) -> None:
    output.mkdir(parents=True, exist_ok=False)
    application_directory = source / "src" / "getting_started" / "GIApplication"
    lighting = contract["lighting"]
    material = contract["material"]
    with software_gl_environment() as base_environment:
        for case_name, index, state in selected_cases:
            case_id = f"case-{index:04d}"
            camera = state["camera"]
            light = state["light"]
            environment = base_environment.copy()
            environment.update(
                {
                    "PRT_VISUAL_TEST": "1",
                    "PRT_RENDERER": "PBR",
                    "PRT_TEST_MODE": "combined",
                    "PRT_DYNAMIC": "1" if lighting["dynamic"] else "0",
                    "PRT_DIRECT_SHADOW": "1" if lighting["directShadow"] else "0",
                    "PRT_PROBE_SHADOW": "1" if lighting["probeShadow"] else "0",
                    "PRT_BANDS": str(int(lighting["prtBands"])),
                    "PRT_TEST_CAMERA_POSITION": format_vector(camera["position"]),
                    "PRT_TEST_CAMERA_YAW": format_number(camera["yawDegrees"]),
                    "PRT_TEST_CAMERA_PITCH": format_number(camera["pitchDegrees"]),
                    "PRT_TEST_CAMERA_FOV": format_number(contract["camera"]["verticalFovDegrees"]),
                    "PRT_TEST_LIGHT_POSITION": format_vector(light["position"]),
                    "PRT_TEST_LIGHT_INTENSITY": format_vector(light["intensity"]),
                    "PRT_TEST_MATERIAL_METALLIC": format_number(material["metallic"]),
                    "PRT_TEST_MATERIAL_ROUGHNESS": format_number(material["roughness"]),
                    "PRT_TEST_MATERIAL_IOR": format_number(material["ior"]),
                    "PRT_TEST_MATERIAL_AO": format_number(material["ao"]),
                    "PRT_REALTIME_CAPTURE_ONCE": "1",
                    "PRT_REALTIME_OUTPUT_ROOT": str(output),
                    "PRT_REALTIME_CASE_ID": case_name,
                }
            )
            completed = run_command(
                [str(executable), "--renderer", "PBR"],
                cwd=application_directory,
                environment=environment,
                timeout=120,
            )
            if completed.returncode != 0:
                raise command_failure(f"{case_id} realtime capture 失败", completed)
            case_directory = output / "cases" / case_name
            missing = [name for name in REQUIRED_CAPTURE_FILES if not (case_directory / name).is_file()]
            if missing:
                raise EvaluationError(f"{case_id} capture 缺少：{','.join(missing)}")
            metadata = read_json(case_directory / "state.json")
            metadata.pop("id", None)
            if not render_states_equivalent(state, metadata):
                raise EvaluationError(f"{case_id} captured state 与 hidden test state 不一致")


def safe_extract_references(archive_path: Path, destination: Path) -> Path:
    total_size = 0
    destination.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        for member in members:
            relative = Path(member.filename)
            unix_mode = member.external_attr >> 16
            if relative.is_absolute() or ".." in relative.parts:
                raise EvaluationError("references.zip 含越界路径")
            if (unix_mode & 0o170000) == 0o120000:
                raise EvaluationError("references.zip 不允许 symbolic link")
            total_size += member.file_size
            if total_size > 4 * 1024 * 1024 * 1024:
                raise EvaluationError("references.zip 解压尺寸超过 4 GiB")
        archive.extractall(destination)
    if (destination / "cases").is_dir():
        return destination
    nested = [path for path in destination.iterdir() if path.is_dir() and (path / "cases").is_dir()]
    if len(nested) == 1:
        return nested[0]
    raise EvaluationError("references.zip 必须包含 cases/ directory")


def resolve_references() -> Path:
    direct = TEST_FILES / "references"
    if (direct / "cases").is_dir():
        return direct
    archive = TEST_FILES / "references.zip"
    if archive.is_file():
        return safe_extract_references(archive, RUNTIME_ROOT / "references")
    raise EvaluationError("test_files 缺少 references/cases 或 references.zip")


def read_pfm(path: Path) -> Any:
    load_dependencies()
    with path.open("rb") as stream:
        magic = stream.readline().strip()
        if magic not in (b"PF", b"Pf"):
            raise EvaluationError(f"{path.name} 不是 PFM")
        dimensions = stream.readline().split()
        while dimensions and dimensions[0].startswith(b"#"):
            dimensions = stream.readline().split()
        if len(dimensions) != 2:
            raise EvaluationError(f"{path.name} PFM dimensions 无效")
        width, height = (int(value) for value in dimensions)
        scale = float(stream.readline().strip())
        endian = "<" if scale < 0 else ">"
        channels = 3 if magic == b"PF" else 1
        values = _numpy.frombuffer(stream.read(), dtype=endian + "f4")
    if values.size != width * height * channels:
        raise EvaluationError(f"{path.name} PFM payload size 无效")
    return _numpy.flipud(values.reshape((height, width, channels))).astype(
        _numpy.float64, copy=False
    )


def downsample_linear_area(image: Any, width: int, height: int, label: str) -> Any:
    load_dependencies()
    value = _numpy.asarray(image, dtype=_numpy.float64)
    if value.ndim != 3:
        raise EvaluationError(f"{label} 必须是 HxWxC image")
    source_height, source_width, channels = value.shape
    if source_width == width and source_height == height:
        return value
    if source_width % width != 0 or source_height % height != 0:
        raise EvaluationError(
            f"{label} 无法从 {source_width}x{source_height} area-average 到 {width}x{height}"
        )
    block_width = source_width // width
    block_height = source_height // height
    return value.reshape(
        height, block_height, width, block_width, channels
    ).mean(axis=(1, 3), dtype=_numpy.float64)


def read_occlusion_mask_weights(
    path: Path, case_index: int, width: int, height: int
) -> Any:
    load_dependencies()
    count = width * height
    with path.open("rb") as stream:
        stream.seek(case_index * count * 4)
        weights = _numpy.frombuffer(stream.read(count * 4), dtype="<f4")
    if weights.size != count:
        raise EvaluationError(f"case-{case_index + 1:04d} occlusion mask payload size 无效")
    weights = weights.reshape((height, width)).astype(_numpy.float64, copy=False)
    if not _numpy.all(_numpy.isfinite(weights)) or _numpy.any(weights < 0.0) or _numpy.any(weights > 1.0):
        raise EvaluationError(f"case-{case_index + 1:04d} occlusion mask weight 无效")
    return weights


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def symmetric_l1_similarity(reference: Any, candidate: Any) -> float:
    reference = _numpy.maximum(reference, 0.0)
    candidate = _numpy.maximum(candidate, 0.0)
    denominator = float(_numpy.sum(reference + candidate, dtype=_numpy.float64))
    if denominator == 0.0:
        return 1.0
    error = float(_numpy.sum(_numpy.abs(candidate - reference), dtype=_numpy.float64)) / denominator
    return clamp01(1.0 - error)


def occlusion_leak_similarity_weights(
    reference: Any, candidate: Any, mask_weight: Any
) -> float:
    mask_weight = _numpy.asarray(mask_weight, dtype=_numpy.float64)
    selected = mask_weight > 0.0
    if int(_numpy.count_nonzero(selected)) == 0:
        return 1.0
    luminance = _numpy.asarray(LUMINANCE, dtype=_numpy.float64)
    reference_values = (_numpy.maximum(reference, 0.0) @ luminance)[selected]
    candidate_values = (_numpy.maximum(candidate, 0.0) @ luminance)[selected]
    weights = mask_weight[selected]
    denominator = float(
        _numpy.sum(weights * _numpy.maximum(reference_values, candidate_values), dtype=_numpy.float64)
    )
    if denominator == 0.0:
        return 1.0
    excess = float(
        _numpy.sum(weights * _numpy.maximum(candidate_values - reference_values, 0.0), dtype=_numpy.float64)
    )
    return clamp01(1.0 - excess / denominator)


def occlusion_leak_similarity(reference: Any, candidate: Any, mask: Any) -> float:
    mask_weight = _numpy.rint(mask.astype(_numpy.float64) * 4.0 / 255.0) / 4.0
    return occlusion_leak_similarity_weights(reference, candidate, mask_weight)


def worst_patch_similarity(flip_map: Any, tile_size: int, percentile: float) -> float:
    values = _numpy.asarray(flip_map, dtype=_numpy.float64).squeeze()
    if values.ndim != 2 or values.size == 0 or not _numpy.all(_numpy.isfinite(values)):
        raise EvaluationError("FLIP map 无效")
    tile_means = [
        float(_numpy.mean(values[y:y + tile_size, x:x + tile_size], dtype=_numpy.float64))
        for y in range(0, values.shape[0], tile_size)
        for x in range(0, values.shape[1], tile_size)
    ]
    return clamp01(1.0 - float(_numpy.quantile(tile_means, percentile)))


def weighted_score(flip_score: float, indirect_score: float) -> float:
    if flip_score <= 0.0 or indirect_score <= 0.0:
        return 0.0
    return clamp01(math.exp(0.7 * math.log(flip_score) + 0.3 * math.log(indirect_score)))


def score_case(
    arguments: tuple[str, int, Path, Path, dict[str, Any]]
) -> dict[str, float | str]:
    load_dependencies()
    case_name, index, realtime_root, reference_root, config = arguments
    case_id = f"case-{index:04d}"
    realtime = realtime_root / "cases" / case_name
    reference = reference_root / "cases" / case_name
    offline_png = require_file(reference / "offline.png", f"{case_id} offline.png")
    realtime_png = require_file(realtime / "realtime.png", f"{case_id} realtime.png")
    flip_map, mean_flip, parameters = _flip_evaluator.evaluate(
        str(offline_png),
        str(realtime_png),
        "LDR",
        applyMagma=False,
        parameters={"ppd": float(config["flip"]["pixelsPerDegree"])},
    )
    if not math.isclose(
        float(parameters["ppd"]), float(config["flip"]["pixelsPerDegree"]), rel_tol=0.0, abs_tol=1.0e-12
    ):
        raise EvaluationError(f"{case_id} FLIP ppd 不一致")
    flip_score = clamp01(1.0 - float(mean_flip))
    worst_config = config["flip"]["worstPatch"]
    worst_score = worst_patch_similarity(
        flip_map, int(worst_config["tileSize"]), float(worst_config["percentile"])
    )
    offline_indirect = read_pfm(
        require_file(reference / "offline-indirect-linear.pfm", f"{case_id} offline indirect")
    )
    realtime_indirect = read_pfm(
        require_file(realtime / "indirect-linear.pfm", f"{case_id} realtime indirect")
    )
    diagnostic = config["diagnosticResolution"]
    diagnostic_width = int(diagnostic["width"])
    diagnostic_height = int(diagnostic["height"])
    expected_shape = (diagnostic_height, diagnostic_width, 3)
    if offline_indirect.shape != expected_shape:
        raise EvaluationError(
            f"{case_id} offline indirect resolution 必须为 "
            f"{diagnostic_width}x{diagnostic_height}"
        )
    realtime_indirect = downsample_linear_area(
        realtime_indirect,
        diagnostic_width,
        diagnostic_height,
        f"{case_id} realtime indirect",
    )
    mask_weight = read_occlusion_mask_weights(
        reference_root / OCCLUSION_MASK_WEIGHTS_NAME,
        index - 1,
        diagnostic_width,
        diagnostic_height,
    )
    indirect_score = symmetric_l1_similarity(offline_indirect, realtime_indirect)
    occlusion_score = occlusion_leak_similarity_weights(
        offline_indirect, realtime_indirect, mask_weight
    )
    return {
        "id": case_id,
        "total": weighted_score(flip_score, indirect_score),
        "flip": flip_score,
        "worst": worst_score,
        "indirect": indirect_score,
        "occlusion": occlusion_score,
    }


def score_all_cases(
    realtime_root: Path,
    reference_root: Path,
    config: dict[str, Any],
    selected_cases: list[tuple[str, int]],
) -> list[dict[str, float | str]]:
    workers = min(4, max(1, (os.cpu_count() or 2) // 2))
    arguments = [
        (case_name, index, realtime_root, reference_root, config)
        for case_name, index in selected_cases
    ]
    if workers == 1:
        return [score_case(argument) for argument in arguments]
    context = multiprocessing.get_context("spawn")
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=workers, mp_context=context
    ) as executor:
        return list(executor.map(score_case, arguments, chunksize=1))


def compare_scores(
    baseline: list[dict[str, Any]], candidate: list[dict[str, Any]]
) -> dict[str, Any]:
    if len(baseline) != len(candidate) or not baseline:
        raise EvaluationError("A/B case 集合不一致")
    total_deltas: list[float] = []
    flip_deltas: list[float] = []
    worst_deltas: list[float] = []
    for before, after in zip(baseline, candidate):
        if before["id"] != after["id"]:
            raise EvaluationError("A/B case id 不一致")
        total_deltas.append(float(after["total"]) - float(before["total"]))
        flip_deltas.append(float(after["flip"]) - float(before["flip"]))
        worst_deltas.append(float(after["worst"]) - float(before["worst"]))
    average_a = statistics.fmean(float(case["total"]) for case in baseline)
    average_b = statistics.fmean(float(case["total"]) for case in candidate)
    mean_delta = statistics.fmean(total_deltas)
    headroom = statistics.fmean(1.0 - float(case["total"]) for case in baseline)
    flip_median = float(statistics.median(flip_deltas))
    worst_median = float(statistics.median(worst_deltas))
    gates_passed = mean_delta > 0.0 and flip_median > 0.0 and worst_median > 0.0
    normalized = clamp01(mean_delta / headroom) if gates_passed and headroom > 0.0 else 0.0
    return {
        "decision": "success" if gates_passed else (
            "failure" if mean_delta <= 0.0 else "failed-regression"
        ),
        "score": normalized,
        "averageA": average_a,
        "averageB": average_b,
        "meanDelta": mean_delta,
        "flipMedian": flip_median,
        "flipImproved": sum(value > 0.0 for value in flip_deltas),
        "flipWorse": sum(value < 0.0 for value in flip_deltas),
        "worstMedian": worst_median,
        "worstImproved": sum(value > 0.0 for value in worst_deltas),
        "worstWorse": sum(value < 0.0 for value in worst_deltas),
        "indirect": statistics.fmean(float(case["indirect"]) for case in candidate),
        "occlusion": statistics.fmean(float(case["occlusion"]) for case in candidate),
    }


def determine_resolved(tests_passed: bool, comparison: dict[str, Any]) -> bool:
    """只有 public tests、regression gates 和正分同时满足才算 resolved。"""
    return bool(
        tests_passed
        and comparison["decision"] == "success"
        and float(comparison["score"]) > 0.0
    )


def evaluate() -> dict[str, Any]:
    require_directory(TEST_FILES, "test_files")
    contract = read_json(require_file(TEST_FILES / "realtime-render-contract.json", "trusted contract"))
    candidate_contract = read_json(require_file(WORKSPACE / "realtime-render-contract.json", "workspace contract"))
    validate_contract(candidate_contract, contract)
    config = read_json(require_file(TEST_FILES / "render-score-config.json", "score config"))
    validate_config(config)
    test_set = require_file(TEST_FILES / "cases.jsonl", "hidden test set")
    states = parse_test_set(test_set, contract)
    load_dependencies()

    if RUNTIME_ROOT.exists():
        shutil.rmtree(RUNTIME_ROOT)
    RUNTIME_ROOT.mkdir(parents=True)
    reference_root = resolve_references()
    validate_reference_bundle(reference_root, config, len(states))
    reference_cases = discover_reference_cases(reference_root, len(states))
    case_indices = [index for _, index in reference_cases]
    selected_cases = [
        (case_name, index, states[index - 1])
        for case_name, index in reference_cases
    ]
    candidate_source = RUNTIME_ROOT / "candidate-source"
    candidate_build = RUNTIME_ROOT / "candidate-build"
    candidate_realtime = RUNTIME_ROOT / "candidate-realtime"
    copy_source_repository(WORKSPACE, candidate_source, "workspace")
    candidate_executable, tests_passed = build_renderer(
        candidate_source, candidate_build, run_tests=True
    )
    capture_cases(
        candidate_executable,
        candidate_source,
        candidate_realtime,
        selected_cases,
        contract,
    )

    baseline_repository = TEST_FILES / "baseline_workspace"
    if baseline_repository.is_dir():
        baseline_contract = read_json(
            require_file(
                baseline_repository / "realtime-render-contract.json",
                "baseline workspace contract",
            )
        )
        validate_contract(baseline_contract, contract)
        baseline_source = RUNTIME_ROOT / "baseline-source"
        baseline_build = RUNTIME_ROOT / "baseline-build"
        baseline_realtime = RUNTIME_ROOT / "baseline-realtime"
        copy_source_repository(
            baseline_repository, baseline_source, "baseline workspace"
        )
        baseline_executable, _ = build_renderer(
            baseline_source, baseline_build, run_tests=False
        )
        capture_cases(
            baseline_executable,
            baseline_source,
            baseline_realtime,
            selected_cases,
            contract,
        )
        baseline_full = score_all_cases(
            baseline_realtime, reference_root, config, reference_cases
        )
        baseline = [
            {
                "id": case["id"],
                "total": case["total"],
                "flip": case["flip"],
                "worst": case["worst"],
            }
            for case in baseline_full
        ]
        baseline_mode = "same-container"
    else:
        baseline_report = read_json(
            require_file(
                TEST_FILES / "baseline-score-report.json", "baseline score report"
            )
        )
        baseline = validate_baseline(
            baseline_report, states, config, case_indices
        )
        baseline_mode = "precomputed"

    candidate = score_all_cases(
        candidate_realtime, reference_root, config, reference_cases
    )
    comparison = compare_scores(baseline, candidate)
    resolved = determine_resolved(tests_passed, comparison)
    reason = (
        f"{comparison['decision']}; baseline={baseline_mode}; "
        f"public_tests={'passed' if tests_passed else 'failed'}; "
        f"cases={len(reference_cases)}; strict={comparison['averageB']:.8f}; "
        f"mean_delta={comparison['meanDelta']:+.8f}; "
        f"flip_median={comparison['flipMedian']:+.8f} "
        f"({comparison['flipImproved']} improved/{comparison['flipWorse']} worse); "
        f"worst_patch_median={comparison['worstMedian']:+.8f} "
        f"({comparison['worstImproved']} improved/{comparison['worstWorse']} worse); "
        f"indirect={comparison['indirect']:.8f}; occlusion_diagnostic={comparison['occlusion']:.8f}"
    )
    return {"resolved": resolved, "score": comparison["score"], "reason": reason}


def main() -> int:
    try:
        result = evaluate()
    except BaseException as error:
        result = {
            "resolved": False,
            "score": 0.0,
            "reason": f"evaluation_error: {type(error).__name__}: {error}",
        }
    try:
        write_result(result)
    except BaseException:
        return 2
    try:
        if RUNTIME_ROOT.is_dir():
            shutil.rmtree(RUNTIME_ROOT)
    except OSError:
        # code_result.json 已原子发布；临时目录清理失败不改变评分结果。
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
