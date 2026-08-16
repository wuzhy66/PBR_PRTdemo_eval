"""生成每条渲染 case 的指标输入图、error map 与图解总览。"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont


LUMINANCE = np.asarray([0.2126, 0.7152, 0.0722], dtype=np.float64)


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


def mask_weights(mask: np.ndarray) -> np.ndarray:
    """把 8-bit 2x2 SSAA coverage 还原为 0、1/4、2/4、3/4、1。"""
    return np.rint(mask.astype(np.float64) * 4.0 / 255.0) / 4.0


def linear_to_display(linear: np.ndarray) -> np.ndarray:
    """使用评测协议的 Reinhard + sRGB transform 生成可浏览的 8-bit RGB。"""
    value = np.maximum(np.asarray(linear, dtype=np.float64), 0.0)
    value = value / (1.0 + value)
    value = np.where(
        value <= 0.0031308,
        12.92 * value,
        1.055 * np.power(value, 1.0 / 2.4) - 0.055,
    )
    return np.clip(np.rint(value * 255.0), 0.0, 255.0).astype(np.uint8)


def save_rgb(path: Path, pixels: np.ndarray) -> None:
    value = np.asarray(pixels)
    if np.issubdtype(value.dtype, np.floating):
        value = np.clip(np.rint(value * 255.0), 0.0, 255.0).astype(np.uint8)
    else:
        value = np.clip(value, 0, 255).astype(np.uint8)
    if value.ndim == 2:
        value = np.repeat(value[:, :, None], 3, axis=2)
    Image.fromarray(value, mode="RGB").save(path)


def valid_rgb(path: Path, shape: tuple[int, int]) -> bool:
    """检查共享 metric PNG 是否完整，避免并行评分读取半写入文件。"""
    if not path.is_file():
        return False
    try:
        with Image.open(path) as image:
            if image.size != (shape[1], shape[0]):
                return False
            image.verify()
        return True
    except (OSError, ValueError):
        return False


def ensure_rgb(path: Path, pixels: np.ndarray) -> None:
    """仅在缺失/损坏时通过临时文件 atomic repair 共享 PNG。"""
    shape = tuple(int(value) for value in pixels.shape[:2])
    if valid_rgb(path, shape):
        return
    temporary = path.with_name(
        f".{path.stem}.{os.getpid()}.{threading.get_ident()}.tmp{path.suffix}"
    )
    try:
        save_rgb(temporary, pixels)
        if valid_rgb(path, shape):
            return
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def error_heatmap(error: np.ndarray) -> np.ndarray:
    """把 0..1 error 映射为 black → purple → orange → yellow，颜色只用于解释。"""
    value = np.clip(np.asarray(error, dtype=np.float64), 0.0, 1.0)
    anchors = np.asarray(
        [
            [0.00, 0.00, 0.02],
            [0.22, 0.04, 0.38],
            [0.67, 0.14, 0.35],
            [0.96, 0.48, 0.12],
            [1.00, 0.95, 0.55],
        ],
        dtype=np.float64,
    )
    scaled = value * (len(anchors) - 1)
    lower = np.floor(scaled).astype(np.intp)
    upper = np.minimum(lower + 1, len(anchors) - 1)
    fraction = (scaled - lower)[..., None]
    return anchors[lower] * (1.0 - fraction) + anchors[upper] * fraction


def transport_error_map(reference: np.ndarray, candidate: np.ndarray) -> np.ndarray:
    reference = np.maximum(np.asarray(reference, dtype=np.float64), 0.0)
    candidate = np.maximum(np.asarray(candidate, dtype=np.float64), 0.0)
    numerator = np.sum(np.abs(candidate - reference), axis=2)
    denominator = np.sum(candidate + reference, axis=2)
    return np.divide(numerator, denominator, out=np.zeros_like(numerator), where=denominator > 0.0)


def leak_error_map(reference: np.ndarray, candidate: np.ndarray, mask: np.ndarray) -> np.ndarray:
    reference_luminance = np.maximum(reference, 0.0) @ LUMINANCE
    candidate_luminance = np.maximum(candidate, 0.0) @ LUMINANCE
    weights = mask_weights(mask)
    numerator = weights * np.maximum(candidate_luminance - reference_luminance, 0.0)
    denominator = weights * np.maximum(candidate_luminance, reference_luminance)
    return np.divide(numerator, denominator, out=np.zeros_like(numerator), where=denominator > 0.0)


def masked_display(linear: np.ndarray, mask: np.ndarray) -> np.ndarray:
    display = linear_to_display(linear).astype(np.float64) / 255.0
    weights = mask_weights(mask)[..., None]
    dimmed = display * 0.12
    return dimmed * (1.0 - weights) + display * weights


def prepare_reference_metric_images(reference_dir: Path) -> dict[str, str]:
    """在 offline case 中准备三个指标各自使用的 Offline 图。"""
    offline_display = reference_dir / "offline.png"
    offline_indirect_display = reference_dir / "offline-indirect.png"
    offline_indirect_linear = reference_dir / "offline-indirect-linear.pfm"
    occlusion_mask_path = reference_dir / "offline-occlusion-mask.pgm"
    for path in (
        offline_display,
        offline_indirect_linear,
        occlusion_mask_path,
    ):
        if not path.is_file():
            raise FileNotFoundError(f"缺少 reference metric image 输入：{path.name}")

    offline_linear = read_pfm(offline_indirect_linear)
    ensure_rgb(offline_indirect_display, linear_to_display(offline_linear))
    mask = np.asarray(Image.open(occlusion_mask_path).convert("L"))
    if mask.shape != offline_linear.shape[:2]:
        raise ValueError("offline occlusion mask 与 indirect AOV resolution 不一致")
    leak_offline = reference_dir / "offline-occlusion-leak.png"
    ensure_rgb(leak_offline, masked_display(offline_linear, mask))
    return {
        "perceptualFlip": offline_display.name,
        "indirectTransport": offline_indirect_display.name,
        "occlusionLeak": leak_offline.name,
    }


def _load_font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "arialbd.ttf" if bold else "arial.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _fit_image(path: Path, size: tuple[int, int]) -> Image.Image:
    image = Image.open(path).convert("RGB")
    image.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, (20, 23, 29))
    x = (size[0] - image.width) // 2
    y = (size[1] - image.height) // 2
    canvas.paste(image, (x, y))
    return canvas


def write_metric_overview(
    path: Path,
    case_id: str,
    scores: dict[str, float],
    image_rows: list[tuple[str, str, str, str, str, str]],
) -> None:
    """生成三行 Offline / Realtime / Error 的 case 指标图解。"""
    width, height = 1440, 1070
    canvas = Image.new("RGB", (width, height), (244, 246, 249))
    draw = ImageDraw.Draw(canvas)
    title_font = _load_font(32, bold=True)
    heading_font = _load_font(20, bold=True)
    body_font = _load_font(17)
    value_font = _load_font(23, bold=True)
    muted = (73, 82, 96)
    dark = (25, 30, 38)
    draw.text((28, 22), f"{case_id} render metric explanation", fill=dark, font=title_font)
    draw.text((28, 63), "Score 1 means identical under this protocol; error heatmaps use black=0, yellow=1.",
              fill=muted, font=body_font)

    label_width = 330
    image_width, image_height = 340, 255
    gap = 15
    image_x = [label_width + 28 + index * (image_width + gap) for index in range(3)]
    for x, label in zip(image_x, ("OFFLINE", "REALTIME", "ERROR")):
        draw.text((x, 102), label, fill=muted, font=heading_font)

    row_y = [140, 445, 750]
    for y, (metric, formula, note, offline_path, realtime_path, error_path) in zip(row_y, image_rows):
        draw.text((28, y + 4), metric, fill=dark, font=heading_font)
        draw.text((28, y + 40), f"score = {scores[metric]:.6f}", fill=(13, 102, 87), font=value_font)
        draw.multiline_text((28, y + 80), formula, fill=dark, font=body_font, spacing=5)
        draw.multiline_text((28, y + 145), note, fill=muted, font=body_font, spacing=5)
        for x, source in zip(image_x, (offline_path, realtime_path, error_path)):
            image = _fit_image(Path(source), (image_width, image_height))
            canvas.paste(image, (x, y))
            draw.rectangle((x, y, x + image_width - 1, y + image_height - 1), outline=(180, 186, 196), width=1)
    canvas.save(path, optimize=True)


def write_existing_metric_overview(
    reference_dir: Path,
    realtime_dir: Path,
    case_id: str,
    scores: dict[str, float],
    reference_images: dict[str, str] | None = None,
) -> None:
    """使用既有 Offline/Realtime/Error 图片刷新 case 指标总览。"""
    reference_images = reference_images or prepare_reference_metric_images(reference_dir)
    write_metric_overview(
        realtime_dir / "metrics-explained.png",
        case_id,
        scores,
        [
            (
                "perceptualFlip",
                "S = 1 - mean(FLIP error)\nWorst = 1 - p95(32x32 tile mean)",
                f"Complete displayed image; worst-patch\nscore = {scores['worstPatchFlip']:.6f} (diagnostic).",
                str(reference_dir / reference_images["perceptualFlip"]),
                str(realtime_dir / "realtime.png"),
                str(realtime_dir / "error-perceptual-flip.png"),
            ),
            (
                "indirectTransport",
                "S = 1 - sum(|C-R|)\n          / sum(C+R)",
                "Symmetric linear-HDR indirect\nenergy difference.",
                str(reference_dir / reference_images["indirectTransport"]),
                str(realtime_dir / "realtime-indirect.png"),
                str(realtime_dir / "error-indirect-transport.png"),
            ),
            (
                "occlusionLeak",
                "S = 1 - sum(M max(C-R,0))\n          / sum(M max(C,R))",
                "One-sided excess light inside\nthe offline occlusion mask.",
                str(reference_dir / reference_images["occlusionLeak"]),
                str(realtime_dir / "realtime-occlusion-leak.png"),
                str(realtime_dir / "error-occlusion-leak.png"),
            ),
        ],
    )


def write_case_metric_images(
    reference_dir: Path,
    realtime_dir: Path,
    case_id: str,
    offline_linear: np.ndarray,
    realtime_linear: np.ndarray,
    mask: np.ndarray,
    flip_colormap: np.ndarray,
    scores: dict[str, float],
) -> dict[str, Any]:
    """在 realtime case 中生成 Realtime、Error 和总览图，并返回相对 artifact 描述。"""
    reference_images = prepare_reference_metric_images(reference_dir)
    realtime_indirect = realtime_dir / "realtime-indirect.png"
    realtime_leak = realtime_dir / "realtime-occlusion-leak.png"
    flip_error = realtime_dir / "error-perceptual-flip.png"
    transport_error = realtime_dir / "error-indirect-transport.png"
    leak_error = realtime_dir / "error-occlusion-leak.png"

    save_rgb(realtime_indirect, linear_to_display(realtime_linear))
    save_rgb(realtime_leak, masked_display(realtime_linear, mask))
    save_rgb(flip_error, flip_colormap)
    save_rgb(transport_error, error_heatmap(transport_error_map(offline_linear, realtime_linear)))
    save_rgb(leak_error, error_heatmap(leak_error_map(offline_linear, realtime_linear, mask)))

    overview = realtime_dir / "metrics-explained.png"
    write_existing_metric_overview(
        reference_dir, realtime_dir, case_id, scores, reference_images
    )
    return {
        "perceptualFlip": {
            "offline": {"root": "reference-case", "path": reference_images["perceptualFlip"]},
            "realtime": {"root": "realtime-case", "path": "realtime.png"},
            "error": {"root": "realtime-case", "path": flip_error.name},
        },
        "worstPatchFlip": {
            "offline": {"root": "reference-case", "path": reference_images["perceptualFlip"]},
            "realtime": {"root": "realtime-case", "path": "realtime.png"},
            "error": {"root": "realtime-case", "path": flip_error.name},
        },
        "indirectTransport": {
            "offline": {"root": "reference-case", "path": reference_images["indirectTransport"]},
            "realtime": {"root": "realtime-case", "path": realtime_indirect.name},
            "error": {"root": "realtime-case", "path": transport_error.name},
        },
        "occlusionLeak": {
            "offline": {"root": "reference-case", "path": reference_images["occlusionLeak"]},
            "realtime": {"root": "realtime-case", "path": realtime_leak.name},
            "error": {"root": "realtime-case", "path": leak_error.name},
        },
        "overview": {"root": "realtime-case", "path": overview.name},
    }
