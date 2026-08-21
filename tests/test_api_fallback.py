import unittest

from routes.api import _build_gemini_prompt


class GeminiPromptTests(unittest.TestCase):
    def test_prompt_uses_current_message_and_history(self):
        prompt = _build_gemini_prompt(
            "Explain recursion in simple terms",
            [{"role": "user", "content": "What is a function?"}],
            "Platform course catalog"
        )

        self.assertIn("Explain recursion in simple terms", prompt)
        self.assertIn("What is a function?", prompt)
        self.assertNotIn("Thanks for asking", prompt)
        self.assertNotIn("Recommended course", prompt)
        self.assertNotIn("I can help you work through it step by step", prompt)


if __name__ == "__main__":
    unittest.main()
