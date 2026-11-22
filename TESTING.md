# 测试记录（真实输出）

环境：`/home/liuzewen/gate-runner`，Python 3.12.3，stdlib-only。采集时间：2026-11-22。

## 1. 单元测试

命令：`python3 -m unittest discover -s tests -v`

```
test_all_pass_exit_zero (test_gate.CLITests.test_all_pass_exit_zero) ... ok
test_each_rule_can_fail (test_gate.CLITests.test_each_rule_can_fail) ... ok
test_invalid_spec_exit_two (test_gate.CLITests.test_invalid_spec_exit_two) ... ok
test_missing_file_fails_not_crashes (test_gate.CLITests.test_missing_file_fails_not_crashes) ... ok
test_missing_spec_exit_two (test_gate.CLITests.test_missing_spec_exit_two) ... ok
test_selftest_exit_zero (test_gate.CLITests.test_selftest_exit_zero) ... ok
test_json_valid_positive_and_negative (test_gate.RuleFunctionTests.test_json_valid_positive_and_negative) ... ok
test_min_lines_positive_and_negative (test_gate.RuleFunctionTests.test_min_lines_positive_and_negative) ... ok
test_must_contain_positive_and_negative (test_gate.RuleFunctionTests.test_must_contain_positive_and_negative) ... ok
test_must_not_contain_positive_and_negative (test_gate.RuleFunctionTests.test_must_not_contain_positive_and_negative) ... ok
test_invalid_specs (test_gate.SpecValidationTests.test_invalid_specs) ... ok
test_valid_spec (test_gate.SpecValidationTests.test_valid_spec) ... ok

----------------------------------------------------------------------
Ran 12 tests in 0.013s

OK
```

12/12 全绿。`test_selftest_exit_zero` 内部还跑了一遍完整 selftest（见下）。

## 2. CLI `check` — 好产物（应全过，rc=0）

命令：`python3 -m gate_runner.cli check --spec examples/spec.json --target examples/good_target`

```
[PASS] rule 1 must_contain('gate-runner 示例产物') | found
[PASS] rule 2 must_not_contain('FORBIDDEN') | absent
[PASS] rule 3 min_lines(2) | lines=2
[PASS] rule 4 json_valid | valid JSON
SUMMARY total=4 pass=4 fail=0 problems=0 exit=0
```

rc = 0。

## 3. CLI `check` — 坏产物（四类全红，rc=1）

命令：`python3 -m gate_runner.cli check --spec examples/spec.json --target examples/bad_target`

```
[FAIL] rule 1 must_contain('gate-runner 示例产物') | missing required string 'gate-runner 示例产物'
[FAIL] rule 2 must_not_contain('FORBIDDEN') | found forbidden string 'FORBIDDEN'
[FAIL] rule 3 min_lines(2) | lines=1 < 2
[FAIL] rule 4 json_valid | invalid JSON: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)
SUMMARY total=4 pass=0 fail=4 problems=4 exit=1
```

rc = 1。四类判据各自独立变红，说明它们真的在判而不是装饰。

## 4. CLI `selftest`（正控 + 注入反证 + 缺/坏 spec，rc=0）

命令：`python3 -m gate_runner.cli selftest`

```
SELFTEST start
CASE positive_control           expected=0 observed=0 PASS
CASE inject_must_contain        expected=1 observed=1 PASS
CASE inject_must_not_contain    expected=1 observed=1 PASS
CASE inject_min_lines           expected=1 observed=1 PASS
CASE inject_json_valid          expected=1 observed=1 PASS
CASE missing_spec               expected=2 observed=2 PASS
CASE invalid_spec               expected=2 observed=2 PASS
SELFTEST cases=7 failed=0 exit=0
```

rc = 0。7 个用例覆盖：1 个正控全过、4 类违规注入必红（退出码 1）、缺 spec 与非法 spec 各自退出码 2。任何一类不变红，`selftest` 自身就红。

## 反证小结

- 闸从没红过？已注入 4 类违规，每类实测 rc=1。
- 摘要首行能看出问题？`SUMMARY` 行同时含 `fail=N problems=N`，非零第一行可见。
- 缺证据算通过？不会——目标文件缺失或不可读时该规则 FAIL，退出码 1。
- 用法错与 FAIL 混码？没有——spec 非法走 2，违规走 1，全过走 0。
