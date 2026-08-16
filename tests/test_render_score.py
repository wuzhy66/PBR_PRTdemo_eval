import importlib.util
import json
import math
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image


MODULE_PATH = Path(__file__).parents[1] / "tools" / "Score-RenderDataset.py"
SPEC = importlib.util.spec_from_file_location("render_score", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
render_score = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(render_score)

import render_metric_images

COMPARE_MODULE_PATH = Path(__file__).parents[1] / "tools" / "Compare-RenderScores.py"
COMPARE_SPEC = importlib.util.spec_from_file_location("compare_render_scores", COMPARE_MODULE_PATH)
assert COMPARE_SPEC is not None and COMPARE_SPEC.loader is not None
compare_render_scores = importlib.util.module_from_spec(COMPARE_SPEC)
COMPARE_SPEC.loader.exec_module(compare_render_scores)


class RenderScoreTests(unittest.TestCase):
    @staticmethod
    def write_pfm(path: Path, image: np.ndarray) -> None:
        value = np.asarray(image, dtype="<f4")
        height, width, channels = value.shape
        magic = b"PF" if channels == 3 else b"Pf"
        with path.open("wb") as stream:
            stream.write(magic + b"\n")
            stream.write(f"{width} {height}\n".encode("ascii"))
            stream.write(b"-1.0\n")
            stream.write(np.flipud(value).tobytes())

    def test_report_path_never_exposes_external_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            external = Path(directory) / "score-report.json"
            self.assertEqual(render_score.report_path(external), "<external>/score-report.json")

    def test_error_message_replaces_absolute_roots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            message = f"缺少文件：{root / 'cases' / 'case-0001' / 'realtime.png'}"
            sanitized = render_score.sanitize_error_message(message, {"realtime-root": root})
            self.assertNotIn(str(root), sanitized)
            self.assertIn("<realtime-root>", sanitized)

    def test_render_state_test_set_accepts_exact_schema(self) -> None:
        state = {
            "camera": {"position": [0, 4.5, 8], "yawDegrees": -90, "pitchDegrees": -12},
            "light": {"position": [0, 5, 0], "intensity": [150, 150, 150]},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.jsonl"
            path.write_text(json.dumps(state) + "\n", encoding="utf-8")
            self.assertEqual(render_score.read_test_set(path), [state])

    def test_render_state_test_set_rejects_time_and_image_fields(self) -> None:
        state = {
            "camera": {"position": [0, 4.5, 8], "yawDegrees": -90, "pitchDegrees": -12},
            "light": {"position": [0, 5, 0], "intensity": [150, 150, 150]},
            "capturedAt": "hidden-time",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.jsonl"
            path.write_text(json.dumps(state) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "非 render-state 字段"):
                render_score.read_test_set(path)

    def test_render_state_test_set_rejects_missing_intensity(self) -> None:
        state = {
            "camera": {"position": [0, 4.5, 8], "yawDegrees": -90, "pitchDegrees": -12},
            "light": {"position": [0, 5, 0]},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.jsonl"
            path.write_text(json.dumps(state) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "light schema"):
                render_score.read_test_set(path)

    def test_render_state_test_set_rejects_out_of_range_intensity(self) -> None:
        state = {
            "camera": {"position": [0, 4.5, 8], "yawDegrees": -90, "pitchDegrees": -12},
            "light": {"position": [0, 5, 0], "intensity": [510, 510, 510]},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.jsonl"
            path.write_text(json.dumps(state) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "light intensity"):
                render_score.read_test_set(path)

    def test_replay_state_accepts_float32_round_trip(self) -> None:
        expected = {
            "camera": {
                "position": [-3.0, 5.8, 5.0],
                "yawDegrees": -26.5650512,
                "pitchDegrees": -23.2350597,
            },
            "light": {
                "position": [4.8, 4.0, -4.8],
                "intensity": [80.0, 80.0, 80.0],
            },
        }
        replayed = {
            "camera": {
                "position": [-3.0, 5.8000002, 5.0],
                "yawDegrees": -26.565052,
                "pitchDegrees": -23.2350597,
            },
            "light": {
                "position": [4.8000002, 4.0, -4.8000002],
                "intensity": [80.0, 80.0, 80.0],
            },
        }
        self.assertTrue(render_score.render_states_equivalent(expected, replayed))

    def test_replay_state_rejects_material_difference(self) -> None:
        expected = {
            "camera": {"position": [0.0, 4.5, 8.0], "yawDegrees": -90.0, "pitchDegrees": -12.0},
            "light": {"position": [0.0, 5.0, 0.0], "intensity": [150.0, 150.0, 150.0]},
        }
        replayed = json.loads(json.dumps(expected))
        replayed["camera"]["position"][0] = 0.001
        self.assertFalse(render_score.render_states_equivalent(expected, replayed))

    def test_transport_identity_is_one(self) -> None:
        image = np.asarray([[[0.0, 1.0, 2.0]]])
        score, error = render_score.symmetric_l1_similarity(image, image)
        self.assertEqual(score, 1.0)
        self.assertEqual(error, 0.0)

    def test_missing_transport_energy_is_zero(self) -> None:
        reference = np.ones((2, 2, 3))
        candidate = np.zeros_like(reference)
        score, error = render_score.symmetric_l1_similarity(reference, candidate)
        self.assertEqual(score, 0.0)
        self.assertEqual(error, 1.0)

    def test_both_black_transport_is_one(self) -> None:
        black = np.zeros((2, 2, 3))
        score, error = render_score.symmetric_l1_similarity(black, black)
        self.assertEqual(score, 1.0)
        self.assertEqual(error, 0.0)

    def test_leak_only_penalizes_excess_energy(self) -> None:
        reference = np.ones((1, 1, 3))
        mask = np.full((1, 1), 255, dtype=np.uint8)
        underlit_score, _, _ = render_score.occlusion_leak_similarity(
            reference, reference * 0.5, mask
        )
        leaked_score, leaked_ratio, _ = render_score.occlusion_leak_similarity(
            reference, reference * 2.0, mask
        )
        self.assertEqual(underlit_score, 1.0)
        self.assertAlmostEqual(leaked_score, 0.5)
        self.assertAlmostEqual(leaked_ratio, 0.5)

    def test_leak_uses_fractional_ssaa_mask_coverage(self) -> None:
        reference = np.ones((1, 2, 3))
        candidate = np.asarray([[[2.0, 2.0, 2.0], [4.0, 4.0, 4.0]]])
        # 第一个 pixel 四个 subpixel 全遮挡，第二个只有一个 subpixel 遮挡。
        mask = np.asarray([[255, 64]], dtype=np.uint8)
        score, ratio, selected = render_score.occlusion_leak_similarity(
            reference, candidate, mask
        )
        expected_ratio = (1.0 + 0.25 * 3.0) / (2.0 + 0.25 * 4.0)
        self.assertEqual(selected, 2)
        self.assertAlmostEqual(ratio, expected_ratio)
        self.assertAlmostEqual(score, 1.0 - expected_ratio)

    def test_empty_occlusion_mask_has_no_leak_penalty(self) -> None:
        reference = np.ones((2, 2, 3))
        candidate = reference * 4.0
        mask = np.zeros((2, 2), dtype=np.uint8)
        score, ratio, selected = render_score.occlusion_leak_similarity(
            reference, candidate, mask
        )
        self.assertEqual(score, 1.0)
        self.assertEqual(ratio, 0.0)
        self.assertEqual(selected, 0)

    def test_weighted_geometric_mean_respects_weights_and_zero(self) -> None:
        weights = {"a": 0.5, "b": 0.5}
        self.assertAlmostEqual(
            render_score.weighted_geometric_mean({"a": 1.0, "b": 0.25}, weights),
            0.5,
        )
        self.assertEqual(
            render_score.weighted_geometric_mean({"a": 1.0, "b": 0.0}, weights),
            0.0,
        )

    def test_worst_patch_flip_uses_tile_tail_instead_of_single_pixel_max(self) -> None:
        flip_map = np.zeros((64, 64), dtype=np.float64)
        flip_map[:32, :32] = 0.2
        flip_map[:32, 32:] = 0.4
        flip_map[32:, :32] = 0.6
        flip_map[32:, 32:] = 0.8
        score, error, tile_count = render_score.worst_patch_flip_similarity(
            flip_map, tile_size=32, percentile=0.75
        )
        self.assertEqual(tile_count, 4)
        self.assertAlmostEqual(error, 0.65)
        self.assertAlmostEqual(score, 0.35)

    def test_all_normalized_scores_stay_in_unit_interval(self) -> None:
        rng = np.random.default_rng(20260813)
        for _ in range(20):
            reference = rng.random((4, 5, 3)) * 10.0
            candidate = rng.random((4, 5, 3)) * 10.0
            mask = np.full((4, 5), 255, dtype=np.uint8)
            transport, _ = render_score.symmetric_l1_similarity(reference, candidate)
            leak, _, _ = render_score.occlusion_leak_similarity(reference, candidate, mask)
            self.assertTrue(math.isfinite(transport) and 0.0 <= transport <= 1.0)
            self.assertTrue(math.isfinite(leak) and 0.0 <= leak <= 1.0)

    def test_visual_error_maps_match_metric_direction(self) -> None:
        reference = np.ones((1, 2, 3), dtype=np.float64)
        candidate = np.asarray([[[2.0, 2.0, 2.0], [0.5, 0.5, 0.5]]])
        mask = np.full((1, 2), 255, dtype=np.uint8)
        transport = render_metric_images.transport_error_map(reference, candidate)
        leak = render_metric_images.leak_error_map(reference, candidate, mask)
        self.assertTrue(np.allclose(transport, [[1.0 / 3.0, 1.0 / 3.0]]))
        self.assertTrue(np.allclose(leak, [[0.5, 0.0]]))

    def test_case_metric_images_are_written_without_absolute_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reference_dir = root / "reference"
            realtime_dir = root / "realtime"
            reference_dir.mkdir()
            realtime_dir.mkdir()
            offline = np.ones((4, 5, 3), dtype=np.float64)
            realtime = offline * 1.25
            mask = np.zeros((4, 5), dtype=np.uint8)
            mask[2:, 1:4] = 255
            Image.fromarray(np.full((4, 5, 3), 96, dtype=np.uint8)).save(
                reference_dir / "offline.png"
            )
            Image.fromarray(np.full((4, 5, 3), 110, dtype=np.uint8)).save(
                realtime_dir / "realtime.png"
            )
            self.write_pfm(reference_dir / "offline-indirect-linear.pfm", offline)
            Image.fromarray(mask).save(reference_dir / "offline-occlusion-mask.pgm")
            artifacts = render_metric_images.write_case_metric_images(
                reference_dir,
                realtime_dir,
                "case-0001",
                offline,
                realtime,
                mask,
                np.zeros((4, 5, 3), dtype=np.float64),
                {
                    "perceptualFlip": 0.9,
                    "worstPatchFlip": 0.75,
                    "indirectTransport": 0.8,
                    "occlusionLeak": 0.7,
                },
            )
            for name in (
                "realtime-indirect.png",
                "realtime-occlusion-leak.png",
                "error-perceptual-flip.png",
                "error-indirect-transport.png",
                "error-occlusion-leak.png",
                "metrics-explained.png",
            ):
                self.assertTrue((realtime_dir / name).is_file(), name)
            self.assertTrue((reference_dir / "offline-indirect.png").is_file())
            self.assertTrue((reference_dir / "offline-occlusion-leak.png").is_file())
            serialized = json.dumps(artifacts)
            self.assertNotIn(str(root), serialized)
            self.assertEqual(artifacts["overview"]["path"], "metrics-explained.png")
            self.assertEqual(
                artifacts["worstPatchFlip"]["error"]["path"],
                "error-perceptual-flip.png",
            )

    def test_case_score_is_written_beside_realtime_capture(self) -> None:
        report = {
            "label": "baseline",
            "protocolFingerprint": "protocol",
            "evaluationSetFingerprint": "evaluation-set",
            "aggregation": "arithmetic-mean",
            "weights": {"perceptualFlip": 0.6},
            "diagnosticMetrics": ["worstPatchFlip"],
            "regressionGates": {
                "requirePositiveMedianPerceptualFlipDelta": True,
                "requirePositiveMedianWorstPatchFlipDelta": True,
            },
            "cases": [
                {
                    "id": "case-0001",
                    "mode": "strict",
                    "scores": {"perceptualFlip": 0.9},
                    "rawErrors": {"meanFlip": 0.1},
                    "totalScore": 0.9,
                }
            ],
            "errors": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            realtime_root = Path(directory) / "realtime"
            render_score.write_case_score_files(realtime_root, report)
            score = json.loads(
                (realtime_root / "cases" / "case-0001" / "score.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(score["id"], "case-0001")
            self.assertEqual(score["totalScore"], 0.9)
            self.assertEqual(score["protocolFingerprint"], "protocol")


class ImprovementScoreTests(unittest.TestCase):
    @staticmethod
    def make_report(
        scores: dict[str, float],
        *,
        perceptual_scores: dict[str, float] | None = None,
        worst_patch_scores: dict[str, float] | None = None,
    ) -> dict:
        cases = []
        for case_id, score in scores.items():
            perceptual_score = (perceptual_scores or scores)[case_id]
            worst_patch_score = (worst_patch_scores or scores)[case_id]
            cases.append(
                {
                    "id": case_id,
                    "mode": "strict",
                    "totalScore": score,
                    "scores": {"perceptualFlip": perceptual_score},
                    "diagnosticScores": {"worstPatchFlip": worst_patch_score},
                    "definitionFingerprint": f"definition-{case_id}",
                    "referenceFingerprint": f"reference-{case_id}",
                }
            )
        return {
            "label": "test",
            "protocolFingerprint": "same-protocol",
            "evaluationSetFingerprint": "same-set",
            "regressionGates": {
                "requirePositiveMedianPerceptualFlipDelta": True,
                "requirePositiveMedianWorstPatchFlipDelta": True,
            },
            "aggregate": {"errorCases": 0},
            "cases": cases,
        }

    def test_perfect_candidate_consumes_all_headroom(self) -> None:
        baseline = self.make_report({"a": 0.5, "b": 0.8})
        candidate = self.make_report({"a": 1.0, "b": 1.0})
        result = compare_render_scores.calculate_improvement(baseline, candidate)
        self.assertEqual(result["decision"], "success")
        self.assertAlmostEqual(result["normalizedImprovementScore"], 1.0)

    def test_partial_improvement_is_normalized_by_average_headroom(self) -> None:
        baseline = self.make_report({"a": 0.5, "b": 0.75})
        candidate = self.make_report({"a": 0.75, "b": 1.0})
        result = compare_render_scores.calculate_improvement(baseline, candidate)
        self.assertAlmostEqual(result["averageImprovement"], 0.25)
        self.assertAlmostEqual(result["averageBaselineHeadroom"], 0.375)
        self.assertAlmostEqual(result["normalizedImprovementScore"], 2.0 / 3.0)

    def test_non_positive_average_is_failure_and_zero(self) -> None:
        baseline = self.make_report({"a": 0.5, "b": 0.8})
        candidate = self.make_report({"a": 0.6, "b": 0.7})
        result = compare_render_scores.calculate_improvement(baseline, candidate)
        self.assertEqual(result["decision"], "failure")
        self.assertAlmostEqual(result["averageImprovement"], 0.0)
        self.assertEqual(result["normalizedImprovementScore"], 0.0)

    def test_positive_mean_fails_when_median_flip_regresses(self) -> None:
        baseline = self.make_report({"a": 0.5, "b": 0.5, "c": 0.5})
        candidate = self.make_report(
            {"a": 1.0, "b": 0.4, "c": 0.4},
            perceptual_scores={"a": 1.0, "b": 0.4, "c": 0.4},
            worst_patch_scores={"a": 1.0, "b": 0.6, "c": 0.6},
        )
        result = compare_render_scores.calculate_improvement(baseline, candidate)
        self.assertGreater(result["averageImprovement"], 0.0)
        self.assertGreater(result["ungatedNormalizedImprovementScore"], 0.0)
        self.assertEqual(result["decision"], "failed-regression")
        self.assertEqual(result["normalizedImprovementScore"], 0.0)
        self.assertFalse(result["regressionGates"]["perceptualFlipMedian"]["passed"])

    def test_positive_mean_fails_when_median_worst_patch_regresses(self) -> None:
        baseline = self.make_report({"a": 0.5, "b": 0.5, "c": 0.5})
        candidate = self.make_report(
            {"a": 0.7, "b": 0.6, "c": 0.6},
            perceptual_scores={"a": 0.7, "b": 0.6, "c": 0.6},
            worst_patch_scores={"a": 0.9, "b": 0.4, "c": 0.4},
        )
        result = compare_render_scores.calculate_improvement(baseline, candidate)
        self.assertGreater(result["averageImprovement"], 0.0)
        self.assertEqual(result["decision"], "failed-regression")
        self.assertEqual(result["normalizedImprovementScore"], 0.0)
        self.assertFalse(result["regressionGates"]["worstPatchFlipMedian"]["passed"])

    def test_reference_change_is_rejected(self) -> None:
        baseline = self.make_report({"a": 0.5})
        candidate = self.make_report({"a": 0.6})
        candidate["cases"][0]["referenceFingerprint"] = "different"
        with self.assertRaisesRegex(ValueError, "referenceFingerprint"):
            compare_render_scores.calculate_improvement(baseline, candidate)

    def test_protocol_change_is_rejected(self) -> None:
        baseline = self.make_report({"a": 0.5})
        candidate = self.make_report({"a": 0.6})
        candidate["protocolFingerprint"] = "different"
        with self.assertRaisesRegex(ValueError, "protocol"):
            compare_render_scores.calculate_improvement(baseline, candidate)


if __name__ == "__main__":
    unittest.main()
