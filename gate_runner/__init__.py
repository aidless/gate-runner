"""gate_runner — 把一组判据变成有退出码的机器闸。

核心承诺：给定候选产物目录 + 一组规则，输出逐条 PASS/FAIL、
总体退出码（0 全过 / 1 有 FAIL / 2 spec 非法），并且注入违规必须变红。
"""
from __future__ import annotations

__all__ = ["__version__"]
__version__ = "0.1.0"