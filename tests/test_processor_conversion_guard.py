"""Pipeline guards that prevent partial Jira creation."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from processor import AsyncPowerPointToJiraProcessor
from slide_detector import IssueSlideReference


class ProcessorConversionGuardTests(unittest.IsolatedAsyncioTestCase):
    """Ensure conversion and extraction failures stop external side effects."""

    async def test_extraction_failure_prevents_jira_creation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            presentation = Path(temp_dir) / "deck.pptx"
            presentation.write_bytes(b"placeholder")

            processor = AsyncPowerPointToJiraProcessor.__new__(
                AsyncPowerPointToJiraProcessor
            )
            processor.config = SimpleNamespace(debug=False, dry_run=False)
            processor.slide_detector = MagicMock()
            processor.slide_detector.find_issue_slides.return_value = [
                IssueSlideReference(
                    pptx_slide_number=8,
                    pdf_page_number=8,
                    project_key="AP",
                )
            ]
            processor.pdf_converter = MagicMock()
            processor.pdf_converter.convert_to_pdf.return_value = "deck.pdf"
            processor.image_extractor = MagicMock()
            processor.image_extractor.extract_slide_images.side_effect = ValueError(
                "Invalid PDF page mapping"
            )
            processor.ai_analyzer = MagicMock()
            processor.ai_analyzer.analyze_slides_batch = AsyncMock()
            processor.jira_client = MagicMock()
            processor.jira_client.create_issues_batch = AsyncMock()
            processor.jira_client.attach_images_batch = AsyncMock()

            with self.assertRaisesRegex(ValueError, "Invalid PDF page mapping"):
                await processor.process(str(presentation))

            processor.ai_analyzer.analyze_slides_batch.assert_not_awaited()
            processor.jira_client.create_issues_batch.assert_not_awaited()
            processor.jira_client.attach_images_batch.assert_not_awaited()
