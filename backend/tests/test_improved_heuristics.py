import unittest
from app.services.llm import heuristics


class ImprovedHeuristicsTests(unittest.TestCase):
    """Test that improved heuristics return better confidence for action emails."""

    def test_hackathon_confirmation_email(self):
        """Email asking to confirm hackathon participation should get >0.60 confidence."""
        subject = "Hackathon seat confirmation"
        body = "Hi, can you please confirm your participation in the hackathon by EOD tomorrow?"
        
        result = heuristics.classify_and_extract(body, subject)
        
        # Should detect awaiting_reply = True
        self.assertTrue(result["awaiting_reply"])
        # Should be high enough to generate draft (>= 0.60)
        self.assertGreaterEqual(result["confidence"], 0.60)
        # Should detect action verb "confirm"
        self.assertGreater(len(result["tasks"]), 0)
        self.assertEqual(result["category"], "WORK")
        self.assertEqual(result["priority"], "HIGH")

    def test_meeting_request_email(self):
        """Email requesting to schedule meeting should get >0.60 confidence."""
        subject = "Let's schedule a meeting"
        body = "Would you be available for a meeting next week? Please confirm your availability ASAP."
        
        result = heuristics.classify_and_extract(body, subject)
        
        self.assertTrue(result["awaiting_reply"])
        self.assertGreaterEqual(result["confidence"], 0.60)
        self.assertGreater(len(result["tasks"]), 0)

    def test_interview_availability_email(self):
        """Email asking for interview confirmation should get >0.60 confidence."""
        subject = "Interview availability confirmation"
        body = "Could you please confirm if you're available for an interview on Friday at 2pm?"
        
        result = heuristics.classify_and_extract(body, subject)
        
        self.assertTrue(result["awaiting_reply"])
        self.assertGreaterEqual(result["confidence"], 0.60)
        self.assertGreater(len(result["tasks"]), 0)
        self.assertEqual(result["category"], "WORK")

    def test_non_action_email_gets_low_confidence(self):
        """Email that doesn't require action should get <0.60 confidence."""
        subject = "FYI: Project update"
        body = "Just wanted to update you on the project status. Everything is on track."
        
        result = heuristics.classify_and_extract(body, subject)
        
        self.assertFalse(result["awaiting_reply"])
        self.assertLess(result["confidence"], 0.60)
        self.assertEqual(len(result["tasks"]), 0)


if __name__ == "__main__":
    unittest.main()
