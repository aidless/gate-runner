# gate-runner

[![CI](https://github.com/aidless/gate-runner/actions/workflows/ci.yml/badge.svg)](https://github.com/aidless/gate-runner/actions/workflows/ci.yml)

把用户已有的判据思想收进一个统一产品壳：给一个候选产物目录 + 一组规则，跑出逐条 PASS/FAIL、总体退出码和会变红的自测反证，能直接接 CI。纯 Python 标准库、无依赖、Python ≥3.9。

## 一句话定位

**判据不是注释，是退出码**：候选产物 + 规则集 → 逐条 PASS/FAIL + 总体 rc（0 全过 / 1 有 FAIL / 2 spec 非法），注入违规必须红。

## 使用命令

```bash
# 用仓库自带示例，检查"好"产物：全过，rc=0
python3 -m gate_runner.cli check --spec examples/spec.json --target examples/good_target

# 检查"坏"产物：逐条 FAIL，rc=1
python3 -m gate_runner.cli check --spec examples/spec.json --target examples/bad_target

# 自测：正控 + 四类违规注入 + 缺 spec + 坏 spec，rc=0 表示闸确实会红
python3 -m gate_runner.cli selftest

# 跑单元测试
python3 -m unittest discover -s tests -v
```

装成命令行入口（可选，stdlib-only）：

```bash
python3 -m pip install -e .
gate-runner check --spec examples/spec.json --target examples/good_target
gate-runner selftest
```

CI 用法：把 `check` 的退出码直接交给流水线，`rc=1` 即红、`rc=2` 即用法/spec 错。

## 判据类型（4 类内置）

| 类型 | 参数 | 含义 |
|---|---|---|
| `must_contain` | `file`, `value` | 指定文件必须含某字符串 |
| `must_not_contain` | `file`, `value` | 指定文件不得含某字符串（禁止串） |
| `min_lines` | `file`, `minimum` | 指定文件最少行数（按 `splitlines()`） |
| `json_valid` | `file` | 指定文件必须是合法 JSON |

规则可任意组合。spec 是 JSON，形状见 `examples/spec.json`：

```json
{
  "name": "optional",
  "rules": [
    {"type": "must_contain", "file": "hello.md", "value": "gate-runner"},
    {"type": "must_not_contain", "file": "hello.md", "value": "FORBIDDEN"},
    {"type": "min_lines", "file": "hello.md", "minimum": 2},
    {"type": "json_valid", "file": "meta.json"}
  ]
}
```

## 退出码与摘要

摘要行同时带 `fail` 与 `problems`，任何非零在第一行就能看见：

```
SUMMARY total=4 pass=4 fail=0 problems=0 exit=0
SUMMARY total=4 pass=0 fail=4 problems=4 exit=1
```

- `0`：全部规则通过。
- `1`：至少一条规则 FAIL（含目标文件缺失——缺证据判红，不算通过）。
- `2`：spec 文件缺失、非法 JSON、或结构/字段非法。与 FAIL 分开，绝不混为一谈。

## `selftest` 的承诺

一道从没红过的闸证明不了什么。`selftest` 在临时目录里跑：

- 正控：四条规则全过 → `rc=0`；
- 四类注入违规：每类必须 FAIL → `rc=1`（证明闸会红）；
- 缺 spec 文件 → `rc=2`；
- 结构非法 spec → `rc=2`。

任一用例期望与实际不符，`selftest` 自身退出 `1`，并逐条打印 expected/observed。

## 目录

- `gate_runner/rules.py`：纯函数规则与 spec 校验。
- `gate_runner/cli.py`：`check` / `selftest` 子命令、退出码、摘要。
- `examples/`：可直接跑的 spec 与好坏两份产物。
- `tests/test_gate.py`：unittest，逐条规则正负两向 + CLI 退出码。
- `CENSUS.md`：建造前普查与 MUST_BUILD_NEW 判决。
- `TESTING.md`：真实测试输出。

## 来源

复用已有判据思想，不重造判据：`agent-gates`、`agent-redteam`、`r5-verify-vs-gate`、`mcp-guard`、`wse-bench-public`。详见 `CENSUS.md`。

MIT License © Liu Zewen / aidless.