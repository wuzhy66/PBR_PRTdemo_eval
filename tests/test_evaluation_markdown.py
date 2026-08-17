import unittest

from tools.generate_claude_execution_report import render_markdown_report


class EvaluationMarkdownTests(unittest.TestCase):
    def test_renders_score_gates_process_and_compact_tool_summary(self):
        payload = {
            "profile": {
                "title": "TEST · model · report",
                "testId": "TEST",
                "overall": "总体判断。",
                "changes": [
                    {"file": "shader.fs", "change": "修改", "goal": "目标", "assessment": "评价"}
                ],
                "good": ["优点"],
                "risks": ["风险"],
                "verdicts": [{"dimension": "效果", "rating": "成功", "detail": "说明"}],
                "phases": [
                    {"name": "实现", "start": 1, "end": 1, "action": "动作", "analysis": "分析", "evidence": "证据"}
                ],
            },
            "execution": {
                "mainModel": "model",
                "claudeVersion": "version",
                "finalResponse": "<done>",
                "tools": [
                    {
                        "index": 1,
                        "name": "Edit",
                        "status": "ok",
                        "summary": "shader | change",
                        "input": {"secret": "不得导出"},
                        "result": "不得导出",
                    }
                ],
            },
            "subagents": [],
            "git": {
                "candidate": "1234567890",
                "baseline": "abcdef0123",
                "files": [{"file": "shader.fs", "added": "2", "deleted": "1"}],
                "diffCheck": "PASS",
                "worktreeStatus": "",
            },
            "evaluation": {
                "status": "complete",
                "decision": "success",
                "caseCount": 200,
                "averageScoreA": 0.8,
                "averageScoreB": 0.9,
                "averageImprovement": 0.1,
                "normalizedImprovementScore": 0.5,
                "strictCases": 200,
                "excludedCases": 0,
                "errorCases": 0,
                "metricChanges": [
                    {
                        "label": "FLIP",
                        "weight": "70%",
                        "scoreA": 0.8,
                        "scoreB": 0.9,
                        "change": 0.1,
                        "improvedCases": 180,
                        "worseCases": 20,
                        "unchangedCases": 0,
                    }
                ],
                "regressionGates": {
                    "perceptualFlipMedian": {
                        "required": True,
                        "passed": True,
                        "medianDelta": 0.02,
                        "improvedCases": 180,
                        "worseCases": 20,
                        "unchangedCases": 0,
                    }
                },
            },
        }

        markdown = render_markdown_report(payload)

        self.assertIn("Normalized improvement：`0.50000000`", markdown)
        self.assertIn("Median FLIP delta", markdown)
        self.assertIn("#1–#1 · 实现", markdown)
        self.assertIn("shader \\| change", markdown)
        self.assertIn("&lt;done&gt;", markdown)
        self.assertNotIn("不得导出", markdown)
        self.assertNotIn("HTML", markdown)


if __name__ == "__main__":
    unittest.main()
