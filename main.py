"""AstrBot plugin: match incoming messages with regex and send preset replies."""
from __future__ import annotations

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star

from .engine import compile_rules, match_rule, render_reply


class RegexAutoReply(Star):
    """Regex-based preset auto replies, without requiring an LLM call."""

    def __init__(self, context: Context, config: AstrBotConfig | None = None):
        super().__init__(context)
        self.config = config or {}
        self.enabled = bool(self.config.get("enabled", True))
        self.stop_event_on_match = bool(self.config.get("stop_event_on_match", True))
        self.ignore_command_prefix = bool(self.config.get("ignore_command_prefix", True))
        self.command_prefixes = str(self.config.get("command_prefixes", "/／!！"))
        try:
            self.max_message_chars = int(self.config.get("max_message_chars", 2000))
        except (TypeError, ValueError):
            self.max_message_chars = 2000
        self.max_message_chars = max(100, min(10000, self.max_message_chars))

        self.rules, warnings = compile_rules(self.config.get("rules", []))
        for warning in warnings:
            logger.warning(f"[正则自动回复] {warning}")
        logger.info(
            f"[正则自动回复] 已加载 {len(self.rules)} 条有效规则；"
            f"启用状态={self.enabled}，命中后停止后续处理={self.stop_event_on_match}。"
        )

    @filter.event_message_type(filter.EventMessageType.ALL, priority=50)
    async def on_message(self, event: AstrMessageEvent):
        if not self.enabled or not self.rules:
            return

        text = str(getattr(event, "message_str", "") or "").strip()
        if not text or len(text) > self.max_message_chars:
            return

        # Avoid swallowing normal slash-style AstrBot/plugin commands.
        if self.ignore_command_prefix and self.command_prefixes and text[0] in self.command_prefixes:
            return

        message_obj = getattr(event, "message_obj", None)
        group_id = str(getattr(message_obj, "group_id", "") or "")
        matched = match_rule(self.rules, text, is_group=bool(group_id))
        if matched is None:
            return

        rule, match = matched
        reply = render_reply(rule.reply, match).strip()
        if not reply:
            return

        logger.info(f"[正则自动回复] 命中规则：{rule.name}")
        yield event.plain_result(reply)
        if self.stop_event_on_match:
            event.stop_event()
