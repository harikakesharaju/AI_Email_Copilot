import unittest
from unittest.mock import patch

from app.services.llm import classify_and_extract, classify_relationship_llm, generate_draft
from app.services.llm.client import GeminiError, parse_json_response, repair_json_text
from app.models import RelationshipType


class LlmFallbackTests(unittest.TestCase):
    @patch("app.services.llm.call_gemini", side_effect=GeminiError("unavailable"))
    def test_extracts_action_task_when_llm_is_unavailable(self, _mock_gemini):
        result = classify_and_extract(
            "Please complete the essay and ppt on corporate life topic and submit by EOD",
            "Remainder for technical writing task",
        )

        self.assertEqual(result["category"], "WORK")
        self.assertTrue(result["awaiting_reply"])
        self.assertEqual(len(result["tasks"]), 1)
        self.assertIn("essay", result["tasks"][0]["description"].lower())
        self.assertTrue(result["tasks"][0]["deadline"])
        self.assertIn("confidence", result["tasks"][0])

    @patch("app.services.llm.call_gemini", side_effect=GeminiError("unavailable"))
    def test_relationship_falls_back_to_unknown(self, _mock_gemini):
        relationship, confidence = classify_relationship_llm("Alex", "Hey, are we still on for dinner?")
        self.assertEqual(relationship, RelationshipType.unknown)
        self.assertEqual(confidence, 0.3)

    @patch("app.services.llm.call_gemini", side_effect=GeminiError("timeout"))
    def test_draft_falls_back_to_heuristic(self, _mock_gemini):
        text = generate_draft("Please send the report", "Report", {"formality": "medium"}, [])
        self.assertIn("Thanks for the reminder", text)


class JsonRepairTests(unittest.TestCase):
    def test_repairs_fenced_and_trailing_comma_json(self):
        raw = """```json
        {"category": "WORK", "priority": "HIGH",}
        ```"""
        repaired = repair_json_text(raw)
        parsed = parse_json_response(repaired, prompt_type="test")
        self.assertEqual(parsed["category"], "WORK")
        self.assertEqual(parsed["priority"], "HIGH")

    def test_rejects_non_json(self):
        with self.assertRaises(GeminiError):
            parse_json_response("not json at all", prompt_type="test")


if __name__ == "__main__":
    unittest.main()
