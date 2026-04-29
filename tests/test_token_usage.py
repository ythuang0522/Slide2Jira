import io
import unittest
from contextlib import redirect_stdout

from ai_analyzer import AIAnalysisResponse, AsyncAIAnalyzer, SlideAnalysis
from config import AIProvider, ProcessingConfig
from config import DEFAULT_OPENAI_MODEL
from main import print_results


class FakeAIClient:
    provider_name = "Fake"
    model_name = "fake-model"

    async def analyze_image(self, base64_image, slide_num):
        return AIAnalysisResponse(
            content='{"title": "測試", "description": "描述", "priority": "Medium", "issue_type": "Task", "labels": []}',
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
        )


async def fake_encode_image_base64(image_path):
    return "encoded-image"


class TokenUsageOutputTest(unittest.TestCase):
    def test_default_openai_model_is_gpt_55(self):
        self.assertEqual(DEFAULT_OPENAI_MODEL, "gpt-5.5")

    def test_print_results_includes_image_and_jira_token_totals(self):
        results = [
            SlideAnalysis(
                slide_number=1,
                title="測試問題",
                description="描述",
                project_key="AP",
                input_tokens=100,
                output_tokens=25,
                total_tokens=125,
            ),
            SlideAnalysis(
                slide_number=2,
                title="第二個問題",
                description="描述",
                project_key="DB",
                input_tokens=200,
                output_tokens=50,
                total_tokens=250,
            ),
        ]

        output = io.StringIO()
        with redirect_stdout(output):
            print_results(results, dry_run=True)

        text = output.getvalue()
        self.assertIn("Image recognition tokens: input=100, output=25, total=125", text)
        self.assertIn("Image recognition total: input=300, output=75, total=375", text)
        self.assertIn("Jira ticket creation total: 0 tokens", text)


class AnalyzerTokenUsageTest(unittest.IsolatedAsyncioTestCase):
    async def test_analyzer_accepts_provider_response_with_token_usage(self):
        config = ProcessingConfig(
            base_url="https://jira.example.com",
            email="test@example.com",
            api_token="token",
            ai_provider=AIProvider.GEMINI,
            gemini_api_key="gemini-key",
        )
        analyzer = AsyncAIAnalyzer.__new__(AsyncAIAnalyzer)
        analyzer.config = config
        analyzer.ai_client = FakeAIClient()
        analyzer.manual_project_key = None
        analyzer._encode_image_base64_async = fake_encode_image_base64

        result = await analyzer.analyze_slide("slide.png", 3, "AP")

        self.assertEqual(result.title, "測試")
        self.assertEqual(result.project_key, "AP")
        self.assertEqual(result.input_tokens, 10)
        self.assertEqual(result.output_tokens, 5)
        self.assertEqual(result.total_tokens, 15)


if __name__ == "__main__":
    unittest.main()
