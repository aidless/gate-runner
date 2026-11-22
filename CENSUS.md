# 建造前普查（Census）

## 谓词（可复算）

“一个 CLI：给一个候选产物目录 + 一组 JSON 规则，跑出逐条 PASS/FAIL + 总体退出码（0 全过 / 1 有 FAIL / 2 spec 非法），并提供注入违规必须变红的自测证据 + 可接 CI。”

满足此谓词的字节必须**同时**具备：
1. 统一的 `check --spec --target` 命令行入口；
2. 可组合、可枚举的规则集；
3. 显式退出码语义（PASS/FAIL/用法错分码）；
4. 自测中含注入违规必须红的反证；
5. stdlib-only 产品壳（便于 CI 直接调用）。

## 扫描域与预算

- 扫描根：`/home/liuzewen`（含字面反斜杠子目录 `/home/liuzewen/F:\deepseek`）。
- 候选 glob（原样）：
  - `/home/liuzewen/*`（顶层目录，实测 300+）
  - `/home/liuzewen/*/*.py`
  - `/home/liuzewen/*/*/*.py`
  - `/home/liuzewen/F:\deepseek/*`（字面反斜杠根，实测 320+ 顶层条目）
  - `/home/liuzewen/F:\deepseek/*/*.py`
  - `/home/liuzewen/F:\deepseek/*/*/*.py`
- 预算：候选文件数上限 1000；每文件只做路径/首部读取 + sha256（流式）；有界 `grep -l -- '--spec'` 只查前 400 个 `.py`。预算未用尽到需回退 `INCONCLUSIVE` 的程度——关键判据是“统一 CLI 产品壳”，已通过具名仓的首部读取 + 有界 `--spec` 搜索确认。

## 已落地判据资产（复用思想，不重造）

| 资产路径 | sha256 校准值（前 12） | 角色 |
|---|---|---|
| `agent-gates/eval_gate.py` | `46250022583b` | 评测涨分的假阳判据；自带 selftest 反证 |
| `agent-gates/ledger_append.py` | `c7e509e37bc0` | 台账回执行门；rc≠0 拒绝写入 |
| `agent-gates/run_all.sh` | `ec7a323007c4` | 多闸入口 |
| `F:\deepseek/r5-verify-vs-gate/audit_numbers.py` | `f55ef2d80cd7` | 正文数字对账账本，rc=1 阻止构建 |
| `mcp-guard/guard/netguard.py` 等 | — | 网络边界判定（SSRF/rebinding） |
| `agent-redteam/demo/cli.py` | `330582106d48` | 红队 demo 入口 |
| `agent-redteam/demo/harness.py` | `d95eeef94739` | 红队评测 harness |
| `F:\deepseek/wse-bench-public/_verify_gate.py` | `793a4c04eb0c` | 基准 verify 闸 |
| `F:\deepseek/wse-bench-public/_hard_gate.py` | `cceafcfc18ee` | 硬约束闸 |

这些仓各自带着成熟的、针对特定领域的判据；gate-runner 只提供统一产品壳，让这些判据思想（退出码语义、注入反证、首行摘要带 problems）能被复用到任何候选产物上，**不重造它们的具体业务判据**。

## 两遍比对结果

- 筛查遍：具名仓全部存在，且每个都自带判据逻辑 + selftest 或 rc 语义；有界 `grep -- '--spec'` 在扫描域内对 `.py` 零命中——没有现成的“spec 驱动 + 通用规则”CLI。
- 全遍：对具名资产读取首部 + 摘要校准，确认它们是领域专用闸（评测、台账、数字、网络、红队、基准），不是“给任意目录 + 一组规则跑通用 PASS/FAIL”的产品壳。
- 目录检查：普查时 `/home/liuzewen/gate-runner` 不存在。

## 判决：MUST_BUILD_NEW

缺的是**统一产品壳**，不是判据。谓词要求一个通用 `check --spec --target` CLI 把多类规则组合成单一 rc 与自测反证；域内现有资产均为单仓内的领域专用脚本，无一满足完整谓词。判决 `MUST_BUILD_NEW`，代价 1 次建造（本仓）。

## 设计约束回写（来自谓词）

新壳必须提供：四类可组合规则（`must_contain`/`must_not_contain`/`min_lines`/`json_valid`）、三类退出码（0/1/2）、首行可见问题的摘要、缺文件判红、每类违规注入反证的 selftest、stdlib-only、接 CI 友好。

## interpret_MUST_read_before_quoting

- 本普查只答“满足谓词的通用 CLI 是否存在”；判据本身已存在，gate-runner 不是判据创新而是承载壳。
- 普查绿 ≠ 可以发：本仓测试通过只证明壳工作，不证明任何具体业务判据的正确性。
- 预算未触发 `PARSE_CAPPED_INCONCLUSIVE`；具名域全数复算 + 有界全局搜索支撑本判决，不是“没扫到就等于不存在”。
