"""gate-runner 单元测试。

覆盖：每条规则的正负两向、spec 校验、CLI 各退出码、selftest 退出码。
运行：python3 -m unittest discover -s tests -v
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gate_runner import rules
from gate_runner.cli import (
    cmd_selftest,
    evaluate_check,
    EXIT_FAIL,
    EXIT_OK,
    EXIT_USAGE,
)


class RuleFunctionTests(unittest.TestCase):
    """每条规则的正负两向（纯函数）。"""

    def test_must_contain_positive_and_negative(self):
        self.assertTrue(rules.must_contain("hello gate", "gate").passed)
        self.assertFalse(rules.must_contain("hello gate", "missing").passed)

    def test_must_not_contain_positive_and_negative(self):
        self.assertTrue(rules.must_not_contain("hello gate", "TODO").passed)
        self.assertFalse(rules.must_not_contain("hello TODO", "TODO").passed)

    def test_min_lines_positive_and_negative(self):
        self.assertTrue(rules.min_lines("a\nb\nc", 2).passed)
        self.assertFalse(rules.min_lines("a\n", 2).passed)
        # 恰好等于下限也算过
        self.assertTrue(rules.min_lines("a\nb", 2).passed)

    def test_json_valid_positive_and_negative(self):
        self.assertTrue(rules.json_valid('{"a": 1}').passed)
        self.assertFalse(rules.json_valid("{oops").passed)


class SpecValidationTests(unittest.TestCase):
    """spec 结构校验：合法返回空列表，非法返回错误。"""

    def test_valid_spec(self):
        spec = {
            "rules": [
                {"type": "must_contain", "file": "hello.md", "value": "x"},
                {"type": "min_lines", "file": "hello.md", "minimum": 1},
            ]
        }
        self.assertEqual(rules.validate_spec(spec), [])

    def test_invalid_specs(self):
        # 空 rules
        self.assertTrue(rules.validate_spec({"rules": []}))
        # 未知类型
        self.assertTrue(rules.validate_spec({"rules": [{"type": "nope", "file": "a"}]}))
        # minimum 类型错
        self.assertTrue(
            rules.validate_spec(
                {"rules": [{"type": "min_lines", "file": "a", "minimum": "x"}]}
            )
        )
        # 缺 value
        self.assertTrue(
            rules.validate_spec(
                {"rules": [{"type": "must_contain", "file": "a"}]}
            )
        )
        # file 空
        self.assertTrue(
            rules.validate_spec(
                {"rules": [{"type": "json_valid", "file": ""}]}
            )
        )


class CLITests(unittest.TestCase):
    """CLI 端到端：通过 tempdir 夹具走真实 check 路径。"""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory(prefix="gate-runner-test-")
        self.root = Path(self._td.name)
        self.target = self.root / "target"
        self.target.mkdir()
        (self.target / "hello.md").write_text(
            "gate-runner\nsecond line\n", encoding="utf-8"
        )
        (self.target / "meta.json").write_text('{"ok": true}\n', encoding="utf-8")
        self.spec = {
            "rules": [
                {"type": "must_contain", "file": "hello.md", "value": "gate-runner"},
                {"type": "must_not_contain", "file": "hello.md", "value": "FORBIDDEN"},
                {"type": "min_lines", "file": "hello.md", "minimum": 2},
                {"type": "json_valid", "file": "meta.json"},
            ]
        }
        self.spec_path = self.root / "spec.json"
        self.spec_path.write_text(json.dumps(self.spec), encoding="utf-8")

    def tearDown(self):
        self._td.cleanup()

    def test_all_pass_exit_zero(self):
        rc, lines = evaluate_check(str(self.spec_path), str(self.target))
        self.assertEqual(rc, EXIT_OK)
        self.assertTrue(
            any(line.startswith("SUMMARY") and "fail=0" in line for line in lines)
        )

    def test_each_rule_can_fail(self):
        cases = [
            ({"type": "must_contain", "file": "hello.md", "value": "ABSENT"}, "hello.md", "plain\n"),
            ({"type": "must_not_contain", "file": "hello.md", "value": "FORBIDDEN"}, "hello.md", "FORBIDDEN\n"),
            ({"type": "min_lines", "file": "hello.md", "minimum": 2}, "hello.md", "one\n"),
            ({"type": "json_valid", "file": "meta.json"}, "meta.json", "{bad\n"),
        ]
        for rule, fname, content in cases:
            with self.subTest(rule=rule):
                d = self.root / ("bad_" + rule["type"])
                d.mkdir(exist_ok=True)
                (d / fname).write_text(content, encoding="utf-8")
                p = self.root / ("spec_" + rule["type"] + ".json")
                p.write_text(json.dumps({"rules": [rule]}), encoding="utf-8")
                rc, lines = evaluate_check(str(p), str(d))
                self.assertEqual(rc, EXIT_FAIL)
                self.assertTrue(any(line.startswith("[FAIL]") for line in lines))

    def test_missing_file_fails_not_crashes(self):
        spec = {"rules": [{"type": "json_valid", "file": "nope.json"}]}
        p = self.root / "spec_missing_file.json"
        p.write_text(json.dumps(spec), encoding="utf-8")
        rc, lines = evaluate_check(str(p), str(self.target))
        self.assertEqual(rc, EXIT_FAIL)
        self.assertTrue(any("file not found" in line for line in lines))

    def test_missing_spec_exit_two(self):
        rc, lines = evaluate_check(str(self.root / "missing.json"), str(self.target))
        self.assertEqual(rc, EXIT_USAGE)
        self.assertTrue(any("SPEC_ERROR" in line for line in lines))

    def test_invalid_spec_exit_two(self):
        p = self.root / "invalid.json"
        p.write_text(
            json.dumps({"rules": [{"type": "unknown", "file": "hello.md"}]}),
            encoding="utf-8",
        )
        rc, _ = evaluate_check(str(p), str(self.target))
        self.assertEqual(rc, EXIT_USAGE)

    def test_selftest_exit_zero(self):
        self.assertEqual(cmd_selftest(), EXIT_OK)


if __name__ == "__main__":
    unittest.main()