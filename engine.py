"""Regex rule compilation and matching for the AstrBot auto-reply plugin."""
from __future__ import annotations

from dataclasses import dataclass
import re as std_re
from typing import Any

try:
    import regex as regex_engine
    HAS_REGEX_TIMEOUT = True
except ImportError:  # pragma: no cover - normally installed from requirements.txt
    import re as regex_engine  # type: ignore[no-redef]
    HAS_REGEX_TIMEOUT = False

MAX_PATTERN_CHARS = 300
MAX_REPLY_CHARS = 4000
MAX_RULES = 100


@dataclass(frozen=True)
class CompiledRule:
    name: str
    pattern_text: str
    reply: str
    mode: str
    scope: str
    priority: int
    order: int
    compiled: Any


def compile_rules(raw_rules: Any) -> tuple[list[CompiledRule], list[str]]:
    """Compile valid enabled rules and return (rules, warnings)."""
    warnings: list[str] = []
    compiled_rules: list[CompiledRule] = []

    if not isinstance(raw_rules, list):
        return [], ["rules 配置不是列表，已忽略全部规则。"]

    if len(raw_rules) > MAX_RULES:
        warnings.append(f"规则超过 {MAX_RULES} 条，仅加载前 {MAX_RULES} 条。")
        raw_rules = raw_rules[:MAX_RULES]

    for index, raw in enumerate(raw_rules):
        if not isinstance(raw, dict):
            warnings.append(f"第 {index + 1} 条规则格式错误，已跳过。")
            continue
        if not bool(raw.get("enabled", True)):
            continue

        name = str(raw.get("name") or f"规则 {index + 1}").strip()[:80]
        pattern_text = str(raw.get("pattern") or "").strip()
        reply = str(raw.get("reply") or "")
        if not pattern_text:
            warnings.append(f"{name}：正则为空，已跳过。")
            continue
        if len(pattern_text) > MAX_PATTERN_CHARS:
            warnings.append(f"{name}：正则超过 {MAX_PATTERN_CHARS} 个字符，已跳过。")
            continue
        if not reply.strip():
            warnings.append(f"{name}：回复内容为空，已跳过。")
            continue
        if len(reply) > MAX_REPLY_CHARS:
            warnings.append(f"{name}：回复内容超过 {MAX_REPLY_CHARS} 个字符，已截断。")
            reply = reply[:MAX_REPLY_CHARS]

        mode = str(raw.get("match_mode") or "fullmatch").lower()
        if mode not in {"fullmatch", "search", "match"}:
            warnings.append(f"{name}：匹配方式无效，已使用 fullmatch。")
            mode = "fullmatch"

        scope = str(raw.get("scope") or "all").lower()
        if scope not in {"all", "group", "private"}:
            warnings.append(f"{name}：生效范围无效，已使用 all。")
            scope = "all"

        try:
            priority = int(raw.get("priority", 0))
        except (TypeError, ValueError):
            priority = 0
        priority = max(-1000, min(1000, priority))

        flags = regex_engine.IGNORECASE if bool(raw.get("ignore_case", True)) else 0
        try:
            compiled = regex_engine.compile(pattern_text, flags)
        except Exception as exc:
            warnings.append(f"{name}：正则编译失败（{exc}），已跳过。")
            continue

        compiled_rules.append(
            CompiledRule(
                name=name,
                pattern_text=pattern_text,
                reply=reply,
                mode=mode,
                scope=scope,
                priority=priority,
                order=index,
                compiled=compiled,
            )
        )

    compiled_rules.sort(key=lambda rule: (-rule.priority, rule.order))
    return compiled_rules, warnings


def match_rule(
    rules: list[CompiledRule], text: str, is_group: bool, timeout_seconds: float = 0.03
) -> tuple[CompiledRule, Any] | None:
    """Return the first matching rule and match object; timed-out rules are skipped."""
    for rule in rules:
        if rule.scope == "group" and not is_group:
            continue
        if rule.scope == "private" and is_group:
            continue

        kwargs = {"timeout": timeout_seconds} if HAS_REGEX_TIMEOUT else {}
        try:
            if rule.mode == "search":
                match = rule.compiled.search(text, **kwargs)
            elif rule.mode == "match":
                match = rule.compiled.match(text, **kwargs)
            else:
                match = rule.compiled.fullmatch(text, **kwargs)
        except TimeoutError:
            continue
        except Exception:
            continue

        if match is not None:
            return rule, match
    return None


def render_reply(template: str, match: Any) -> str:
    """Expand {0}, {1}, ... and {named_group} placeholders safely."""
    def replace_placeholder(token: Any) -> str:
        key = token.group(1)
        try:
            value = match.group(int(key)) if key.isdigit() else match.group(key)
        except (IndexError, KeyError, TypeError):
            return token.group(0)
        return "" if value is None else str(value)

    return std_re.sub(r"\{([A-Za-z_][A-Za-z0-9_]*|\d+)\}", replace_placeholder, template)
