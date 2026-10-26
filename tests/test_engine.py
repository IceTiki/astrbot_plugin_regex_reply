import unittest

from astrbot_plugin_regex_reply.engine import compile_rules, match_rule, render_reply


class RegexReplyEngineTests(unittest.TestCase):
    def rule(self, **overrides):
        item = {
            "name": "greeting",
            "pattern": "^(hello|hi)$",
            "reply": "Hey {1}!",
            "enabled": True,
            "ignore_case": True,
            "match_mode": "fullmatch",
            "scope": "all",
            "priority": 0,
        }
        item.update(overrides)
        return item

    def test_fullmatch_case_insensitive_and_placeholder(self):
        rules, warnings = compile_rules([self.rule()])
        self.assertEqual(warnings, [])
        found = match_rule(rules, "HELLO", is_group=False)
        self.assertIsNotNone(found)
        rule, match = found
        self.assertEqual(render_reply(rule.reply, match), "Hey HELLO!")

    def test_search_mode(self):
        rules, _ = compile_rules([self.rule(pattern="tired", match_mode="search", reply="rest")])
        self.assertIsNotNone(match_rule(rules, "I am tired today", is_group=True))

    def test_scope(self):
        rules, _ = compile_rules([self.rule(scope="private")])
        self.assertIsNone(match_rule(rules, "hello", is_group=True))
        self.assertIsNotNone(match_rule(rules, "hello", is_group=False))

    def test_priority_first_match(self):
        rules, _ = compile_rules([
            self.rule(name="low", pattern="hello", match_mode="search", priority=1, reply="low"),
            self.rule(name="high", pattern="hello", match_mode="search", priority=9, reply="high"),
        ])
        found = match_rule(rules, "hello", is_group=False)
        self.assertEqual(found[0].name, "high")
        self.assertEqual(render_reply(found[0].reply, found[1]), "high")

    def test_named_group(self):
        rules, _ = compile_rules([self.rule(pattern=r"^I am (?P<name>.+)$", reply="Hi {name}")])
        found = match_rule(rules, "I am Alice", is_group=False)
        self.assertEqual(render_reply(found[0].reply, found[1]), "Hi Alice")

    def test_invalid_regex_is_skipped(self):
        rules, warnings = compile_rules([self.rule(pattern="[")])
        self.assertEqual(rules, [])
        self.assertTrue(warnings)

    def test_disabled_rule_is_skipped(self):
        rules, _ = compile_rules([self.rule(enabled=False)])
        self.assertEqual(rules, [])

    def test_too_long_pattern_is_skipped(self):
        rules, warnings = compile_rules([self.rule(pattern="a" * 301)])
        self.assertEqual(rules, [])
        self.assertTrue(warnings)


if __name__ == "__main__":
    unittest.main()
