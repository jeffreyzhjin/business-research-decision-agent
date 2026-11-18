"""No-network regression checks for the two research modes."""

import unittest

from pydantic import ValidationError

from src.models import ResearchRequest
from src.synthesizer import build_fallback_brief
from src.workflow import build_planner_prompt


class ResearchModeTests(unittest.TestCase):
    def test_legacy_decision_mode_default(self):
        request = ResearchRequest(question="Should we enter the market?")
        self.assertEqual(request.mode, "decision")
        self.assertIn("本地市场", build_planner_prompt(request))

    def test_industry_plan_does_not_force_local_market(self):
        request = ResearchRequest(
            question="中国商业银行行业的竞争格局如何？",
            mode="industry",
        )
        prompt = build_planner_prompt(request)
        self.assertIn("行业研究主题", prompt)
        self.assertIn("产业链", prompt)
        self.assertIn("不强制本地市场检索", prompt)
        self.assertNotIn("2个针对具体本地市场", prompt)

    def test_invalid_mode_rejected(self):
        with self.assertRaises(ValidationError):
            ResearchRequest(
                question="中国商业银行行业的竞争格局如何？",
                mode="unsupported",
            )

    def test_industry_fallback_is_conservative(self):
        brief = build_fallback_brief([], mode="industry")
        self.assertEqual(brief.confidence, "low")
        self.assertIn("证据不足", brief.recommendation)
        self.assertIn("统计口径", " ".join(brief.next_steps))

    def test_decision_fallback_preserved(self):
        brief = build_fallback_brief([], mode="decision")
        self.assertIn("不可逆决策", brief.recommendation)


if __name__ == "__main__":
    unittest.main()
