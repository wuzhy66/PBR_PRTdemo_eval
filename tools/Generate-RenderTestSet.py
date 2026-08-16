"""生成 deterministic、balanced 的 PRT render-state test set。"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CAMERA_SPECS: list[dict[str, Any]] = [
    # 保留此前手动采集的 pose；其 camera/light/150 组合由 pairing 特意保留。
    {"position": (9.4277277, 7.3449464, 9.2268810), "yaw": -141.5998993, "pitch": -50.8999863},
    {"position": (0.0, 4.5, 8.0), "target": (0.0, 2.0, 0.0)},
    {"position": (-4.5, 3.5, 8.0), "target": (-7.0, 1.0, 6.0)},
    {"position": (4.5, 3.5, 8.0), "target": (7.0, 1.0, 6.0)},
    {"position": (-8.0, 5.5, 8.0), "target": (0.0, 5.5, 0.0)},
    {"position": (0.0, 4.5, -8.0), "target": (0.0, 2.0, 0.0)},
    {"position": (-4.5, 3.5, -8.0), "target": (-7.0, 1.0, -6.0)},
    {"position": (4.5, 3.5, -8.0), "target": (7.0, 1.0, -6.0)},
    {"position": (-8.0, 5.5, -8.0), "target": (0.0, 8.0, 0.0)},
    {"position": (8.0, 5.5, -8.0), "target": (0.0, 5.5, 0.0)},
    {"position": (-8.0, 4.5, 3.0), "target": (0.0, 2.0, 0.0)},
    {"position": (-8.0, 4.5, -3.0), "target": (0.0, 7.5, 0.0)},
    {"position": (8.0, 4.5, 3.0), "target": (0.0, 7.5, 0.0)},
    {"position": (8.0, 4.5, -3.0), "target": (0.0, 2.0, 0.0)},
    {"position": (0.0, 7.8, 6.0), "target": (-7.0, 1.0, 0.0)},
    {"position": (0.0, 7.8, -6.0), "target": (7.0, 1.0, 0.0)},
    {"position": (-3.0, 7.5, 0.0), "target": (7.0, 1.0, 6.0)},
    {"position": (3.0, 7.5, 0.0), "target": (-7.0, 1.0, -6.0)},
    {"position": (0.0, 3.2, 5.0), "target": (-7.0, 1.0, 0.0)},
    {"position": (0.0, 3.2, -5.0), "target": (7.0, 1.0, 0.0)},
    {"position": (-5.0, 3.2, 3.0), "target": (7.0, 3.2, -6.0)},
    {"position": (5.0, 3.2, -3.0), "target": (-7.0, 6.5, 6.0)},
    {"position": (-3.0, 5.8, 5.0), "target": (7.0, 1.0, 0.0)},
    {"position": (3.0, 5.8, -5.0), "target": (-7.0, 5.8, 0.0)},
]

LIGHT_POSITIONS = [
    (0.0, 2.8, 0.0),
    (0.0, 5.0, 0.0),
    (0.0, 7.5, 0.0),
    (-4.8, 4.0, 4.8),
    (4.8, 4.0, 4.8),
    (6.0000010, 5.0, 7.2000017),
    (-4.8, 4.0, -4.8),
    (4.8, 4.0, -4.8),
    (-7.5, 6.0, 0.0),
    (7.5, 6.0, 0.0),
    (0.0, 3.5, -7.5),
    (0.0, 3.5, 7.5),
]

LIGHT_INTENSITIES = [80.0, 150.0, 250.0]

# 64 组高区分度场景 × 2 档既有亮度 = 128 cases。减少 brightness 维度重复，
# 将预算用于 contact shadow、cube-to-cube occlusion、近墙/近地光源与 grazing view。
TARGETED_INTENSITIES = [80.0, 250.0]
TARGETED_SCENARIOS: list[dict[str, Any]] = [
    # Cube 顶部/侧面近光源：放大 receiver bias、near plane 和 contact shadow 差异。
    {"camera": {"position": (-5.0, 2.6, 3.0), "target": (7.0, 1.0, 6.0)}, "light": (7.0, 2.35, 6.0)},
    {"camera": {"position": (-5.0, 2.6, -3.0), "target": (7.0, 1.0, -6.0)}, "light": (5.55, 1.4, -6.0)},
    {"camera": {"position": (5.0, 2.6, 3.0), "target": (-7.0, 1.0, 6.0)}, "light": (-7.0, 2.35, 6.0)},
    {"camera": {"position": (5.0, 2.6, -3.0), "target": (-7.0, 1.0, -6.0)}, "light": (-5.55, 1.4, -6.0)},
    {"camera": {"position": (0.0, 2.4, 6.0), "target": (7.0, 1.0, 6.0)}, "light": (7.0, 2.35, 4.55)},
    {"camera": {"position": (0.0, 2.4, -6.0), "target": (-7.0, 1.0, -6.0)}, "light": (-7.0, 2.35, -4.55)},
    # 跨 cube/纵深遮挡：放大 visibility-aware transport 与 light leaking 差异。
    {"camera": {"position": (-4.8, 3.2, 3.0), "target": (8.0, 1.0, -6.0)}, "light": (8.8, 1.5, -6.0)},
    {"camera": {"position": (4.8, 3.2, -3.0), "target": (-8.0, 1.0, 6.0)}, "light": (-8.8, 1.5, 6.0)},
    {"camera": {"position": (3.5, 4.0, 8.8), "target": (7.0, 1.0, -6.0)}, "light": (7.0, 3.0, -8.8)},
    {"camera": {"position": (-3.5, 4.0, -8.8), "target": (-7.0, 1.0, 6.0)}, "light": (-7.0, 3.0, 8.8)},
    # 掠射视角与近边界光源：覆盖 floor/wall shadow precision 和能量衰减。
    {"camera": {"position": (-8.8, 0.7, 3.2), "target": (7.0, 0.5, 3.2)}, "light": (0.0, 0.45, 3.2)},
    {"camera": {"position": (8.8, 0.7, -3.2), "target": (-7.0, 0.5, -3.2)}, "light": (0.0, 0.45, -3.2)},
    {"camera": {"position": (-8.8, 5.0, 0.0), "target": (7.0, 5.0, 0.0)}, "light": (-9.5, 5.0, 0.0)},
    {"camera": {"position": (8.8, 5.0, 0.5), "target": (-7.0, 5.0, 0.5)}, "light": (9.5, 5.0, 0.5)},
    # 中央 cube 与纵向两端：补齐前述六个外侧 cube 以外的接触/遮挡组合。
    {"camera": {"position": (0.0, 2.6, 2.5), "target": (7.0, 1.0, 0.0)}, "light": (7.0, 2.35, 0.0)},
    {"camera": {"position": (0.0, 2.6, -2.5), "target": (-7.0, 1.0, 0.0)}, "light": (-7.0, 2.35, 0.0)},
    {"camera": {"position": (4.0, 3.5, 8.5), "target": (7.0, 1.0, 6.0)}, "light": (8.45, 1.2, 6.0)},
    {"camera": {"position": (-4.0, 3.5, 8.5), "target": (-7.0, 1.0, 6.0)}, "light": (-8.45, 1.2, 6.0)},
    {"camera": {"position": (4.0, 3.5, -8.5), "target": (7.0, 1.0, -6.0)}, "light": (8.45, 1.2, -6.0)},
    {"camera": {"position": (-4.0, 3.5, -8.5), "target": (-7.0, 1.0, -6.0)}, "light": (-8.45, 1.2, -6.0)},
    # 高位/近天花板组合：覆盖多物体投影、长阴影和 probe visibility。
    {"camera": {"position": (0.0, 8.8, 4.0), "target": (7.0, 1.0, 0.0)}, "light": (4.5, 8.8, 0.0)},
    {"camera": {"position": (0.0, 8.8, -4.0), "target": (-7.0, 1.0, 0.0)}, "light": (-4.5, 8.8, 0.0)},
    {"camera": {"position": (-4.0, 8.5, 0.0), "target": (7.0, 1.0, -6.0)}, "light": (0.0, 9.4, -6.0)},
    {"camera": {"position": (4.0, 8.5, 0.0), "target": (-7.0, 1.0, 6.0)}, "light": (0.0, 9.4, 6.0)},
    # 四角近墙/近地组合：验证 room boundary、inverse-square falloff 与漏光。
    {"camera": {"position": (-9.4, 2.5, 8.5), "target": (-7.0, 1.0, 6.0)}, "light": (-9.4, 0.8, 9.4)},
    {"camera": {"position": (9.4, 2.5, 8.5), "target": (7.0, 1.0, 6.0)}, "light": (9.4, 0.8, 9.4)},
    {"camera": {"position": (-9.4, 2.5, -8.5), "target": (-7.0, 1.0, -6.0)}, "light": (-9.4, 0.8, -9.4)},
    {"camera": {"position": (9.4, 2.5, -8.5), "target": (7.0, 1.0, -6.0)}, "light": (9.4, 0.8, -9.4)},
]


def systematic_targeted_scenarios() -> list[dict[str, Any]]:
    """补充规则化但不重复的 cube、floor、ceiling 与 diagonal stress cases。"""

    scenarios: list[dict[str, Any]] = []
    cube_centers = [
        (-7.0, -6.0), (-7.0, 0.0), (-7.0, 6.0),
        (7.0, -6.0), (7.0, 0.0), (7.0, 6.0),
    ]
    for index, (cube_x, cube_z) in enumerate(cube_centers):
        camera_z_offset = 2.7 if cube_z <= 0.0 else -2.7
        scenarios.extend(
            [
                {
                    "camera": {
                        "position": (cube_x * 0.35, 4.4 + 0.15 * (index % 3), cube_z + camera_z_offset),
                        "target": (cube_x, 1.0, cube_z),
                    },
                    "light": (
                        cube_x + (-1.45 if cube_x > 0.0 else 1.45),
                        1.05 + 0.05 * (index % 2),
                        cube_z,
                    ),
                },
                {
                    "camera": {
                        "position": (
                            cube_x * 0.55 + 0.1 * (index - 2.5),
                            6.2,
                            -9.1 if cube_z >= 0.0 else 9.1,
                        ),
                        "target": (cube_x, 1.0, cube_z),
                    },
                    "light": (
                        cube_x,
                        2.25,
                        cube_z + (-1.45 if cube_z >= 0.0 else 1.45),
                    ),
                },
                {
                    "camera": {
                        "position": (cube_x * 0.15 + 0.1 * index, 8.9, cube_z * 0.35),
                        "target": (cube_x, 1.0, cube_z),
                    },
                    "light": (cube_x, 2.3, cube_z),
                },
            ]
        )

    grazing_z = (-8.0, -5.0, -2.0, 2.0, 5.0, 8.0)
    for index, z_value in enumerate(grazing_z):
        scenarios.append(
            {
                "camera": {
                    "position": (-9.2, 0.55 + 0.04 * index, z_value),
                    "target": (8.5, 0.5, -0.6 * z_value),
                },
                "light": (0.0, 0.4, 0.75 * z_value),
            }
        )
        scenarios.append(
            {
                "camera": {
                    "position": (9.2, 9.1 - 0.05 * index, z_value),
                    "target": (-8.0, 1.0, -0.5 * z_value),
                },
                "light": (0.0, 9.5, 0.7 * z_value),
            }
        )

    scenarios.extend(
        [
            {"camera": {"position": (-9.2, 3.0, 9.2), "target": (7.0, 1.0, -6.0)}, "light": (9.2, 1.0, -9.2)},
            {"camera": {"position": (9.2, 3.0, 9.2), "target": (-7.0, 1.0, -6.0)}, "light": (-9.2, 1.0, -9.2)},
            {"camera": {"position": (-9.2, 3.0, -9.2), "target": (7.0, 1.0, 6.0)}, "light": (9.2, 1.0, 9.2)},
            {"camera": {"position": (9.2, 3.0, -9.2), "target": (-7.0, 1.0, 6.0)}, "light": (-9.2, 1.0, 9.2)},
            {"camera": {"position": (-9.2, 7.0, 5.0), "target": (7.0, 1.0, 0.0)}, "light": (9.2, 8.0, -5.0)},
            {"camera": {"position": (9.2, 7.0, -5.0), "target": (-7.0, 1.0, 0.0)}, "light": (-9.2, 8.0, 5.0)},
        ]
    )
    if len(scenarios) != 36:
        raise ValueError(f"systematic targeted scenarios 必须为 36，实际为 {len(scenarios)}")
    return scenarios


TARGETED_SCENARIOS.extend(systematic_targeted_scenarios())
WALL_SAFETY_INSET = 0.25
GEOMETRY_SAFETY_MARGIN = 0.20


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成 balanced indoor render test set")
    parser.add_argument(
        "--contract",
        type=Path,
        default=REPO_ROOT / "realtime-render-contract.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "test-set" / "cases.jsonl",
    )
    return parser.parse_args()


def camera_angles(spec: dict[str, Any]) -> tuple[float, float]:
    if "yaw" in spec:
        return float(spec["yaw"]), float(spec["pitch"])
    position = spec["position"]
    target = spec["target"]
    direction = tuple(float(target[i]) - float(position[i]) for i in range(3))
    length = math.sqrt(sum(value * value for value in direction))
    if length <= 0.0:
        raise ValueError("camera target 不得等于 position")
    yaw = math.degrees(math.atan2(direction[2], direction[0]))
    pitch = math.degrees(math.asin(direction[1] / length))
    return yaw, pitch


def inside_room(position: tuple[float, float, float], contract: dict[str, Any]) -> bool:
    minimum = contract["scene"]["room"]["interiorMinimum"]
    maximum = contract["scene"]["room"]["interiorMaximum"]
    return all(
        float(minimum[axis]) + WALL_SAFETY_INSET <= position[axis]
        <= float(maximum[axis]) - WALL_SAFETY_INSET
        for axis in range(3)
    )


def outside_cubes(position: tuple[float, float, float], contract: dict[str, Any]) -> bool:
    half_extent = contract["scene"]["cubes"]["halfExtent"]
    for center in contract["scene"]["cubes"]["centers"]:
        inside = all(
            abs(position[axis] - float(center[axis]))
            <= float(half_extent[axis]) + GEOMETRY_SAFETY_MARGIN
            for axis in range(3)
        )
        if inside:
            return False
    return True


def formatted(value: float) -> str:
    if abs(value) < 0.00000005:
        value = 0.0
    return f"{value:.7f}"


def vector(values: tuple[float, float, float]) -> str:
    return "[" + ",".join(formatted(float(value)) for value in values) + "]"


def record(camera: dict[str, Any], light_position: tuple[float, float, float], intensity: float) -> str:
    position = tuple(float(value) for value in camera["position"])
    yaw, pitch = camera_angles(camera)
    rgb = (intensity, intensity, intensity)
    return (
        '{"camera":{"position":' + vector(position)
        + ',"yawDegrees":' + formatted(yaw)
        + ',"pitchDegrees":' + formatted(pitch)
        + '},"light":{"position":' + vector(light_position)
        + ',"intensity":' + vector(rgb) + '}}'
    )


def main() -> int:
    args = parse_args()
    contract = json.loads(args.contract.read_text(encoding="utf-8-sig"))
    if contract.get("contractId") != "prt-realtime-render-v3":
        raise ValueError("只支持 prt-realtime-render-v3")

    targeted_cameras = [scenario["camera"] for scenario in TARGETED_SCENARIOS]
    targeted_lights = [scenario["light"] for scenario in TARGETED_SCENARIOS]
    for label, positions in (
        ("camera", [tuple(float(value) for value in spec["position"]) for spec in CAMERA_SPECS + targeted_cameras]),
        ("light", LIGHT_POSITIONS + targeted_lights),
    ):
        if len(positions) != len(set(positions)):
            raise ValueError(f"{label} position 存在重复")
        for position in positions:
            if not inside_room(position, contract):
                raise ValueError(f"{label} position 不在带安全余量的室内范围：{position}")
            if not outside_cubes(position, contract):
                raise ValueError(f"{label} position 落入 cube safety volume：{position}")

    records: list[str] = []
    light_usage = [0] * len(LIGHT_POSITIONS)
    intensity_usage = [0] * len(LIGHT_INTENSITIES)
    light_intensity_usage = [
        [0] * len(LIGHT_INTENSITIES) for _ in LIGHT_POSITIONS
    ]
    for camera_index, camera in enumerate(CAMERA_SPECS):
        # 每个 camera 固定搭配一个 light position，再分别覆盖三档 brightness，
        # 使亮度差异不与 pose 差异混杂。步长 5 与 12 互质，24 个 camera
        # 恰好让每个 light position 搭配两个 camera。
        light_index = (5 + 5 * camera_index) % len(LIGHT_POSITIONS)
        for intensity_index, intensity in enumerate(LIGHT_INTENSITIES):
            records.append(record(
                camera,
                LIGHT_POSITIONS[light_index],
                intensity,
            ))
            light_usage[light_index] += 1
            intensity_usage[intensity_index] += 1
            light_intensity_usage[light_index][intensity_index] += 1

    if len(records) != len(set(records)):
        raise ValueError("生成结果包含重复 render state")
    if light_usage != [6] * len(LIGHT_POSITIONS):
        raise ValueError(f"light position coverage 不平衡：{light_usage}")
    if intensity_usage != [24] * len(LIGHT_INTENSITIES):
        raise ValueError(f"light intensity coverage 不平衡：{intensity_usage}")
    if any(usage != [2, 2, 2] for usage in light_intensity_usage):
        raise ValueError(f"light position/intensity pairing 不平衡：{light_intensity_usage}")

    targeted_start = len(records)
    for scenario in TARGETED_SCENARIOS:
        for intensity in TARGETED_INTENSITIES:
            records.append(record(scenario["camera"], scenario["light"], intensity))
    if len(records) - targeted_start != 128:
        raise ValueError("targeted case 数量必须为 128")
    if len(records) != len(set(records)):
        raise ValueError("balanced + targeted 结果包含重复 render state")

    records.sort()
    if len(records) != 200:
        raise ValueError(f"正式 test set 必须为 200 cases，实际为 {len(records)}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(records) + "\n", encoding="utf-8")
    print(
        f"Wrote {len(records)} cases：balanced={len(CAMERA_SPECS) * len(LIGHT_INTENSITIES)}, "
        f"targeted={len(TARGETED_SCENARIOS) * len(TARGETED_INTENSITIES)} -> {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
