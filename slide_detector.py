"""Slide detection functionality."""

import re
import logging
from typing import List, Generator, Tuple
from pptx import Presentation

from config import ISSUE_PATTERNS

logger = logging.getLogger(__name__)


class SlideDetector:
    """Handles detection of issue slides in presentations."""
    
    def __init__(self, patterns: List[str] = None):
        self.patterns = patterns or ISSUE_PATTERNS
    
    def find_issue_slides(self, pptx_path: str) -> Generator[Tuple[int, object], None, None]:
        """Generator that yields issue slides with slide index (1-based)."""
        try:
            prs = Presentation(pptx_path)
            logger.info(f"Processing {len(prs.slides)} slides from {pptx_path}")
            
            for idx, slide in enumerate(prs.slides, start=1):
                if self._looks_like_issue(slide):
                    logger.info(f"Found issue slide: {idx}")
                    yield idx, slide
        except Exception as e:
            logger.error(f"Error processing presentation: {e}")
            raise
    
    def _looks_like_issue(self, slide) -> bool:
        """Detect issue slides using multiple patterns."""
        for shp in slide.shapes:
            if hasattr(shp, "text") and shp.text.strip():
                text = shp.text.strip()
                if any(re.search(pattern, text) for pattern in self.patterns):
                    return True
        return False 