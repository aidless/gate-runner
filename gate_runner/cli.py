"""cli.py — gate-runner 命令行入口。

子命令：
  check --spec SPEC.json --target DIR   按 spec 对 target 逐条判，输出 PASS/FAIL + 退出码
  selftest                              生成临时夹具，跑正控 + 每类违规注入 + 缺/坏 spec

退出码约定（对齐 verification-gate 技能）：
  0  全过            PASS
  1  查出问题        FAIL（Critical）
  2  用法错/spec 非法   —（不与 FAIL 混淆）
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import rules

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2


def load_spec(path: str) -> Tuple[Optional[dict], Optional[str]]:
    """读取 spec 文件。返回 (spec, error)。"""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh), None
    except FileNotFoundError:
        return None, "spec file not found: %s" % path
    except json.JSONDecodeError as exc:
        return None, "spec is not valid JSON: %s" % exc
    except OSError as exc:
        return None, "cannot read spec: %s" % exc


def load_target_files(target: str, spec: dict) -> Dict[str, str]:
    """按 spec 引用的文件从 target 读取内容；缺失/读不出则留空，交由 evaluate 判 FAIL。"""
    files: Dict[str, str] = {}
    for rule in spec["rules"]:
        fname = rule["file"]
        if fname in files:
            continue
        p = Path(target) / fname
        try:
            files[fname] = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            pass  # 缺失在 evaluate() 中记为 FAIL
    return files


def evaluate_check(spec_path: str, target: str) -> Tuple[int, List[str]]:
    """执行一次检查，返回 (exit_code, 输出行列表)。不做打印，便于 selftest 复用。"""
    lines: List[str] = []

    spec, err = load_spec(spec_path)
    if err:
        lines.append("SPEC_ERROR %s" % err)
        lines.append("SUMMARY total=0 pass=0 fail=0 problems=0 exit=%d" % EXIT_USAGE)
        return EXIT_USAGE, lines

    problems = rules.validate_spec(spec)
    if problems:
        lines.append("SPEC_INVALID (%d problems)" % len(problems))
        for p in problems:
            lines.append("  - %s" % p)
        lines.append("SUMMARY total=0 pass=0 fail=0 problems=%d exit=%d" % (len(problems), EXIT_USAGE))
        return EXIT_USAGE, lines

    files = load_target_files(target, spec)
    results = rules.evaluate(spec, files)

    fails = 0
    for i, res in enumerate(results):
        if not res.passed:
            fails += 1
        tag = "PASS" if res.passed else "FAIL"
        lines.append("[%s] rule %d %s | %s" % (tag, i + 1, res.description, res.detail))

    total = len(results)
    rc = EXIT_FAIL if fails else EXIT_OK
    # 摘要行同时含 fail 数与 problems，任何非零都能在单一行看到
    lines.append(
        "SUMMARY total=%d pass=%d fail=%d problems=%d exit=%d"
        % (total, total - fails, fails, fails, rc)
    )
    return rc, lines


def run_check(spec_path: str, target: str, quiet: bool = False) -> int:
    """执行检查并打印；quiet=True 时只返回退出码。"""
    rc, lines = evaluate_check(spec_path, target)
    if not quiet:
        for line in lines:
            print(line)
    return rc


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def cmd_selftest() -> int:
    """自测：正控必须全过；每类规则注入违规必须变红；缺/坏 spec 必须退出 2。"""
    print("SELFTEST start")
    cases: List[Tuple[str, int, int]] = []  # (name, expected_rc, observed_rc)

    with tempfile.TemporaryDirectory(prefix="gate-runner-selftest-") as td:
        root = Path(td)

        # 正控夹具：四条规则全过
        good = root / "good"
        _write(good / "hello.md", "gate-runner selftest\nline two is present\n")
        _write(good / "meta.json", '{"ok": true}\n')
        full_spec = {
            "name": "selftest full",
            "rules": [
                {"type": "must_contain", "file": "hello.md", "value": "gate-runner selftest"},
                {"type": "must_not_contain", "file": "hello.md", "value": "FORBIDDEN"},
                {"type": "min_lines", "file": "hello.md", "minimum": 2},
                {"type": "json_valid", "file": "meta.json"},
            ],
        }
        spec_path = root / "spec.json"
        _write(spec_path, json.dumps(full_spec))

        rc = run_check(str(spec_path), str(good), quiet=True)
        cases.append(("positive_control", EXIT_OK, rc))

        # 每类规则各注入一个违规：用单规则 spec，退出码必须为 1
        injections = [
            (
                "inject_must_contain",
                {"type": "must_contain", "file": "hello.md", "value": "NEVER_PRESENT"},
                {"hello.md": "gate-runner content\n"},
            ),
            (
                "inject_must_not_contain",
                {"type": "must_not_contain", "file": "hello.md", "value": "FORBIDDEN"},
                {"hello.md": "FORBIDDEN appears here\n"},
            ),
            (
                "inject_min_lines",
                {"type": "min_lines", "file": "hello.md", "minimum": 2},
                {"hello.md": "only one line\n"},
            ),
            (
                "inject_json_valid",
                {"type": "json_valid", "file": "meta.json"},
                {"meta.json": "{not valid json\n"},
            ),
        ]
        for name, rule, contents in injections:
            d = root / name
            for fname, text in contents.items():
                _write(d / fname, text)
            p = root / (name + ".json")
            _write(p, json.dumps({"rules": [rule]}))
            rc = run_check(str(p), str(d), quiet=True)
            cases.append((name, EXIT_FAIL, rc))

        # 缺 spec 文件 → 退出 2
        rc = run_check(str(root / "does-not-exist.json"), str(good), quiet=True)
        cases.append(("missing_spec", EXIT_USAGE, rc))

        # 结构非法 spec → 退出 2
        bad_spec = root / "bad_spec.json"
        _write(bad_spec, json.dumps({"rules": [{"type": "no_such_rule", "file": "hello.md"}]}))
        rc = run_check(str(bad_spec), str(good), quiet=True)
        cases.append(("invalid_spec", EXIT_USAGE, rc))

    failed = 0
    for name, expected, observed in cases:
        ok = expected == observed
        if not ok:
            failed += 1
        print(
            "CASE %-26s expected=%d observed=%d %s"
            % (name, expected, observed, "PASS" if ok else "FAIL")
        )

    rc = EXIT_FAIL if failed else EXIT_OK
    print(
        "SELFTEST cases=%d failed=%d exit=%d" % (len(cases), failed, rc)
    )
    return rc


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="gate-runner",
        description="把一组判据变成有退出码的机器闸：候选产物 + 规则 → PASS/FAIL + 退出码。",
    )
    sub = parser.add_subparsers(dest="cmd")

    p_check = sub.add_parser("check", help="按 spec 检查目标目录")
    p_check.add_argument("--spec", required=True, help="spec JSON 文件路径")
    p_check.add_argument("--target", required=True, help="被检查的候选产物目录")

    sub.add_parser("selftest", help="运行自测夹具，验证闸会变红")

    args = parser.parse_args(argv)

    if args.cmd == "check":
        return run_check(args.spec, args.target)
    if args.cmd == "selftest":
        return cmd_selftest()

    parser.print_help()
    return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())