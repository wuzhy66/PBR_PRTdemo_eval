from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("test_by_code_module", ROOT / "test_by_code.py")
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TestByCodeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_numpy = MODULE._numpy
        MODULE._numpy = np

    def tearDown(self) -> None:
        MODULE._numpy = self.original_numpy

    def test_fixed_container_roots(self) -> None:
        self.assertEqual(MODULE.WORKSPACE, Path("/workspace"))
        self.assertEqual(MODULE.TEST_FILES, Path("/test_files"))
        self.assertEqual(MODULE.RESULT_PATH, Path("/eval/code_result.json"))

    @unittest.skipUnless(os.name == "posix", "POSIX compatibility flag only applies on Linux")
    def test_linux_build_environment_includes_unistd(self) -> None:
        self.assertIn("-include unistd.h", MODULE.build_environment()["CXXFLAGS"])

    def test_result_has_exact_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            original_root = MODULE.EVAL_ROOT
            original_result = MODULE.RESULT_PATH
            try:
                MODULE.EVAL_ROOT = Path(directory)
                MODULE.RESULT_PATH = Path(directory) / "code_result.json"
                MODULE.write_result(
                    {"resolved": True, "score": 0.75, "reason": "all checks passed"}
                )
                payload = json.loads(MODULE.RESULT_PATH.read_text(encoding="utf-8"))
                self.assertEqual(set(payload), {"resolved", "score", "reason"})
                self.assertIs(payload["resolved"], True)
                self.assertEqual(payload["score"], 0.75)
                self.assertIsInstance(payload["reason"], str)
            finally:
                MODULE.EVAL_ROOT = original_root
                MODULE.RESULT_PATH = original_result

    def test_result_forces_unresolved_when_score_is_zero(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            original_root = MODULE.EVAL_ROOT
            original_result = MODULE.RESULT_PATH
            try:
                MODULE.EVAL_ROOT = Path(directory)
                MODULE.RESULT_PATH = Path(directory) / "code_result.json"
                MODULE.write_result(
                    {"resolved": True, "score": 0.0, "reason": "zero score"}
                )
                payload = json.loads(MODULE.RESULT_PATH.read_text(encoding="utf-8"))
                self.assertIs(payload["resolved"], False)
                self.assertEqual(payload["score"], 0.0)
            finally:
                MODULE.EVAL_ROOT = original_root
                MODULE.RESULT_PATH = original_result

    def test_positive_mean_and_medians_pass(self) -> None:
        baseline = [
            {"id": "case-0001", "total": 0.5, "flip": 0.5, "worst": 0.5},
            {"id": "case-0002", "total": 0.5, "flip": 0.5, "worst": 0.5},
        ]
        candidate = [
            {
                "id": "case-0001", "total": 0.7, "flip": 0.7, "worst": 0.6,
                "indirect": 0.8, "occlusion": 0.9,
            },
            {
                "id": "case-0002", "total": 0.6, "flip": 0.6, "worst": 0.7,
                "indirect": 0.7, "occlusion": 0.8,
            },
        ]
        result = MODULE.compare_scores(baseline, candidate)
        self.assertEqual(result["decision"], "success")
        self.assertAlmostEqual(result["score"], 0.3)

    def test_negative_worst_patch_median_fails_gate(self) -> None:
        baseline = [
            {"id": "case-0001", "total": 0.5, "flip": 0.5, "worst": 0.6},
            {"id": "case-0002", "total": 0.5, "flip": 0.5, "worst": 0.6},
        ]
        candidate = [
            {
                "id": "case-0001", "total": 0.8, "flip": 0.7, "worst": 0.5,
                "indirect": 0.8, "occlusion": 0.9,
            },
            {
                "id": "case-0002", "total": 0.7, "flip": 0.6, "worst": 0.5,
                "indirect": 0.7, "occlusion": 0.8,
            },
        ]
        result = MODULE.compare_scores(baseline, candidate)
        self.assertEqual(result["decision"], "failed-regression")
        self.assertEqual(result["score"], 0.0)

    def test_non_positive_score_is_not_resolved(self) -> None:
        comparison = {"decision": "success", "score": 0.0}
        self.assertFalse(MODULE.determine_resolved(True, comparison))

    def test_positive_score_and_success_are_resolved(self) -> None:
        comparison = {"decision": "success", "score": 0.01}
        self.assertTrue(MODULE.determine_resolved(True, comparison))

    def test_linear_area_downsample_preserves_block_average(self) -> None:
        image = np.arange(4 * 4 * 3, dtype=np.float64).reshape((4, 4, 3))
        actual = MODULE.downsample_linear_area(image, 2, 2, "fixture")
        expected = image.reshape((2, 2, 2, 2, 3)).mean(axis=(1, 3))
        np.testing.assert_allclose(actual, expected, rtol=0.0, atol=0.0)

    def test_linear_area_downsample_rejects_non_integral_ratio(self) -> None:
        image = np.zeros((5, 4, 3), dtype=np.float64)
        with self.assertRaisesRegex(MODULE.EvaluationError, "无法从"):
            MODULE.downsample_linear_area(image, 2, 2, "fixture")

    def test_consolidated_mask_reader_uses_case_major_offsets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / MODULE.OCCLUSION_MASK_WEIGHTS_NAME
            np.asarray(
                [0.0, 0.25, 0.5, 0.75, 1.0, 0.5, 0.25, 0.0], dtype="<f4"
            ).tofile(path)
            first = MODULE.read_occlusion_mask_weights(path, 0, 2, 2)
            second = MODULE.read_occlusion_mask_weights(path, 1, 2, 2)
            np.testing.assert_allclose(first, [[0.0, 0.25], [0.5, 0.75]])
            np.testing.assert_allclose(second, [[1.0, 0.5], [0.25, 0.0]])

    def test_baseline_rejects_mismatched_diagnostic_resolution(self) -> None:
        config = {
            "diagnosticResolution": {
                "width": 200,
                "height": 150,
                "downsample": "linear-area-average",
            },
            "weights": {},
            "regressionGates": {},
        }
        report = {
            "schemaVersion": 1,
            "diagnosticResolution": {
                "width": 800,
                "height": 600,
                "downsample": "none",
            },
        }
        with self.assertRaisesRegex(MODULE.EvaluationError, "diagnostic resolution"):
            MODULE.validate_baseline(report, [], config, [])

    def test_reference_discovery_accepts_any_case_prefix_with_numeric_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            reference_root = Path(directory)
            cases_root = reference_root / "cases"
            cases_root.mkdir()
            for name in ("case_7", "case-0002"):
                case = cases_root / name
                case.mkdir()
                (case / "offline.png").touch()
                (case / "offline-indirect-linear.pfm").touch()
            (cases_root / "notes").mkdir()
            self.assertEqual(
                MODULE.discover_reference_cases(reference_root, 10),
                [("case-0002", 2), ("case_7", 7)],
            )

    def test_reference_discovery_rejects_case_without_numeric_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cases_root = Path(directory) / "cases"
            (cases_root / "case-blue").mkdir(parents=True)
            with self.assertRaisesRegex(MODULE.EvaluationError, "numeric id"):
                MODULE.discover_reference_cases(Path(directory), 10)

    def test_reference_discovery_rejects_empty_selection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cases_root = Path(directory) / "cases"
            (cases_root / "notes").mkdir(parents=True)
            with self.assertRaisesRegex(MODULE.EvaluationError, "为空"):
                MODULE.discover_reference_cases(Path(directory), 10)

    def test_baseline_selects_only_requested_case_ids(self) -> None:
        states = [{"value": 1}, {"value": 2}, {"value": 3}]
        config = {
            "diagnosticResolution": {
                "width": 200,
                "height": 150,
                "downsample": "linear-area-average",
            },
            "weights": {"perceptualFlip": 0.7},
            "regressionGates": {"required": True},
        }
        report_cases = []
        for index, state in enumerate(states, 1):
            report_cases.append(
                {
                    "id": f"case-{index:04d}",
                    "definitionFingerprint": MODULE.canonical_hash(state),
                    "mode": "strict",
                    "scores": {"perceptualFlip": 0.5 + index * 0.01},
                    "diagnosticScores": {"worstPatchFlip": 0.4},
                    "totalScore": 0.6,
                }
            )
        report = {
            "schemaVersion": 1,
            "diagnosticResolution": config["diagnosticResolution"],
            "weights": config["weights"],
            "regressionGates": config["regressionGates"],
            "cases": report_cases,
        }
        selected = MODULE.validate_baseline(report, states, config, [1, 3])
        self.assertEqual([case["id"] for case in selected], ["case-0001", "case-0003"])


if __name__ == "__main__":
    unittest.main()
