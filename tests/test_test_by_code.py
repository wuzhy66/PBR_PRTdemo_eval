from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("test_by_code_module", ROOT / "test_by_code.py")
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TestByCodeTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
