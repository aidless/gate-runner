"""rules.py — 纯函数规则集，无 I/O、无全局状态、无副作用。

每条规则接受已加载的文本 + 参数，返回 RuleResult。所有判定逻辑集中在这里，
便于逐条单测，也便于后续扩展新规则类型而不改 CLI。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Dict, List


@dataclass(frozen=True)
class RuleResult:
    """单条规则的判定结果。"""

    passed: bool
    description: str
    detail: str


def must_contain(text: str, value: str) -> RuleResult:
    """文本必须包含指定字符串。"""
    ok = value in text
    return RuleResult(
        ok,
        "must_contain(%r)" % value,
        "found" if ok else "missing required string %r" % value,
    )


def must_not_contain(text: str, value: str) -> RuleResult:
    """文本必须不包含指定字符串（禁止串）。"""
    ok = value not in text
    return RuleResult(
        ok,
        "must_not_contain(%r)" % value,
        "absent" if ok else "found forbidden string %r" % value,
    )


def min_lines(text: str, minimum: int) -> RuleResult:
    """文本最少行数。按 splitlines() 计数，末尾换行不额外计一行。"""
    count = len(text.splitlines())
    ok = count >= minimum
    return RuleResult(
        ok,
        "min_lines(%d)" % minimum,
        "lines=%d" % count if ok else "lines=%d < %d" % (count, minimum),
    )


def json_valid(text: str) -> RuleResult:
    """文本必须是合法 JSON。"""
    try:
        json.loads(text)
    except ValueError as exc:
        return RuleResult(False, "json_valid", "invalid JSON: %s" % exc)
    return RuleResult(True, "json_valid", "valid JSON")


# 规则类型注册表：类型名 -> 纯函数
RULE_FUNCS: Dict[str, Callable[..., RuleResult]] = {
    "must_contain": must_contain,
    "must_not_contain": must_not_contain,
    "min_lines": min_lines,
    "json_valid": json_valid,
}

# 除 file 外，各规则类型必填的参数名及其可接受类型
_REQUIRED: Dict[str, Dict[str, type]] = {
    "must_contain": {"value": str},
    "must_not_contain": {"value": str},
    "min_lines": {"minimum": int},
    "json_valid": {},
}


def validate_spec(spec: object) -> List[str]:
    """校验 spec 结构，返回错误列表；空列表表示合法。

    非法一律走退出码 2（用法错），不得与 FAIL（退出码 1）混为一谈。
    """
    if not isinstance(spec, dict):
        return ["spec must be a JSON object"]

    rules = spec.get("rules")
    if not isinstance(rules, list) or not rules:
        return ["spec.rules must be a non-empty list"]

    errors: List[str] = []
    for i, rule in enumerate(rules):
        prefix = "rules[%d]" % i
        if not isinstance(rule, dict):
            errors.append("%s must be an object" % prefix)
            continue
        rtype = rule.get("type")
        if rtype not in RULE_FUNCS:
            errors.append("%s.type unknown or missing: %r" % (prefix, rtype))
            continue
        fname = rule.get("file")
        if not isinstance(fname, str) or not fname:
            errors.append("%s.file must be a non-empty string" % prefix)
        for key, typ in _REQUIRED[rtype].items():
            v = rule.get(key)
            # bool 是 int 的子类，int 字段要显式排除
            if not isinstance(v, typ) or (typ is int and isinstance(v, bool)):
                errors.append("%s.%s must be %s" % (prefix, key, typ.__name__))
                continue
            if typ is int and isinstance(v, int) and not isinstance(v, bool) and v < 0:
                errors.append("%s.%s must be >= 0" % (prefix, key))
    return errors


def evaluate(spec: dict, files: Dict[str, str]) -> List[RuleResult]:
    """把每条规则应用到已加载的文件内容映射上。纯函数，不做 I/O。

    文件缺失 → 该规则 FAIL（缺证据不算通过），而不是崩溃。
    """
    results: List[RuleResult] = []
    for rule in spec["rules"]:
        rtype = rule["type"]
        fname = rule["file"]
        if fname not in files:
            results.append(
                RuleResult(
                    False,
                    "%s(%s)" % (rtype, fname),
                    "file not found or unreadable: %s" % fname,
                )
            )
            continue
        text = files[fname]
        if rtype == "must_contain":
            results.append(must_contain(text, rule["value"]))
        elif rtype == "must_not_contain":
            results.append(must_not_contain(text, rule["value"]))
        elif rtype == "min_lines":
            results.append(min_lines(text, rule["minimum"]))
        elif rtype == "json_valid":
            results.append(json_valid(text))
    return results