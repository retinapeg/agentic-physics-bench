"""V3's turn-2 section strings are V2's own, except the one new denial string."""
import json
import unittest

import fixtures_v3 as F
import agent_v2
import policy_v3 as P
import run_v2
import tools

CASE, KEY = run_v2.load_task("dev", "d1-01")          # a V2 development task, to drive V2's own loop


def v2_section(condition, *replies):
    _, prompt1, template2 = run_v2.render_prompts(CASE, condition)
    it = iter(replies)
    return agent_v2.run_episode_v2(CASE, condition, prompt1, template2, lambda p, t: next(it))["tool_section"]


class SectionTests(unittest.TestCase):
    def test_imported_strings_are_v2s(self):
        self.assertEqual(P.SECTION_FINAL, agent_v2.SECTIONS[("optional_tool", "final")])
        self.assertEqual(P.SECTION_UNPARSED, agent_v2.SECTIONS[("optional_tool", "unparsed")])
        self.assertEqual(P.SECTION_FINAL, v2_section("optional_tool", F.final(1.0), F.final(1.0)))
        self.assertEqual(P.SECTION_UNPARSED, v2_section("optional_tool", "not json", F.final(1.0)))

    def test_copied_strings_equal_v2s_loop_output(self):
        self.assertEqual(P.section_invalid("wrong_case_id"),
                         v2_section("optional_tool", F.request("d1-02"), F.final(1.0)))
        self.assertEqual(P.section_invalid("unknown_tool"),
                         v2_section("optional_tool", F.request(CASE["id"], name="shell"), F.final(1.0)))
        self.assertEqual(P.section_result(tools.fit_line(CASE)), v2_section("optional_tool", F.request(CASE["id"]), F.final(1.0)))
        original = tools.TOOLS["fit_line"]
        tools.TOOLS["fit_line"] = lambda case: 1 / 0
        try:
            self.assertEqual(P.section_failed(), v2_section("optional_tool", F.request(CASE["id"]), F.final(1.0)))
        finally:
            tools.TOOLS["fit_line"] = original

    def test_denied_string_is_shared_and_reason_free(self):
        self.assertEqual(P.SECTION_DENIED, "The tool request was not executed, so there is no tool result. No further tool use is available.")
        self.assertTrue(P.SECTION_DENIED.endswith(agent_v2.NO_FURTHER))
        for word in ("permitted", "prohibited", "TOOL_PERMISSION", "because", "not allowed"):
            self.assertNotIn(word, P.SECTION_DENIED)
        self.assertEqual(P.turn2_template(), (F.ROOT / "prompts" / "v2" / "turn2.txt").read_text())
        json.dumps(P.section_result({"slope": 1.0}))


if __name__ == "__main__":
    unittest.main()
