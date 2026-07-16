"""Regression tests for PDF page mapping and image extraction integrity."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import fitz

from image_extractor import ImageExtractor


class ImageExtractorTests(unittest.TestCase):
    """Prevent partial extraction from an invalid slide-to-page mapping."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.pdf_path = self.temp_path / "deck.pdf"
        with fitz.open() as document:
            document.new_page()
            document.save(self.pdf_path)
        self.extractor = ImageExtractor(
            SimpleNamespace(max_image_size_mb=2.0)
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_missing_mapped_page_fails_before_any_image_is_written(self):
        """All requested pages must exist before extraction begins."""
        mapping = {1: 1, 8: 2}

        with patch.object(
            self.extractor, "_extract_single_slide"
        ) as extract_slide:
            with self.assertRaisesRegex(
                ValueError,
                r"PPTX slide 8 expects PDF page 2.*only has 1 page",
            ):
                self.extractor.extract_slide_images(
                    str(self.pdf_path), mapping, str(self.temp_path)
                )

        extract_slide.assert_not_called()

    def test_failed_single_slide_extraction_aborts_the_pipeline(self):
        """An extraction failure must not silently create attachment-free Jira work."""
        with patch.object(
            self.extractor, "_extract_single_slide", return_value=None
        ):
            with self.assertRaisesRegex(
                RuntimeError, "Failed to extract PPTX slide 1"
            ):
                self.extractor.extract_slide_images(
                    str(self.pdf_path), {1: 1}, str(self.temp_path)
                )

    def test_valid_mapping_writes_a_nonempty_jpeg(self):
        """The strict preflight must preserve successful image extraction."""
        images = self.extractor.extract_slide_images(
            str(self.pdf_path), {1: 1}, str(self.temp_path)
        )

        image_path = Path(images[1])
        self.assertTrue(image_path.exists())
        self.assertGreater(image_path.stat().st_size, 0)
