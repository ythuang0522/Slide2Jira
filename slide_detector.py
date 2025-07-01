"""Slide detection functionality."""

import re
import logging
from typing import List, Generator, Tuple, Optional
from pptx import Presentation

from config import ISSUE_PATTERNS, ISSUE_PROJECT_RULES, DEFAULT_PROJECT_KEY

logger = logging.getLogger(__name__)


class SlideDetector:
    """Handles detection of issue slides in presentations."""
    
    def __init__(self, patterns: List[str] = None):
        self.patterns = patterns or ISSUE_PATTERNS
    
    def find_issue_slides(self, pptx_path: str) -> Generator[Tuple[int, object, Optional[str]], None, None]:
        """Generator that yields issue slides with slide index (1-based), slide object, and determined project key."""
        try:
            prs = Presentation(pptx_path)
            logger.info(f"Processing {len(prs.slides)} slides from {pptx_path}")
            
            for idx, slide in enumerate(prs.slides, start=1):
                project_key = self._detect_issue_and_project(slide)
                if project_key is not None:  # Found an issue
                    logger.info(f"Found issue slide: {idx} → project: {project_key}")
                    yield idx, slide, project_key
        except Exception as e:
            logger.error(f"Error processing presentation: {e}")
            raise
    
    def _detect_issue_and_project(self, slide) -> Optional[str]:
        """Detect issue slides and determine project key based on text patterns."""
        slide_text = self._extract_slide_text(slide)
        
        # First check if it's an issue slide at all
        if not any(re.search(pattern, slide_text) for pattern in self.patterns):
            return None  # Not an issue slide
        
        # It's an issue slide, now determine the project
        for pattern, project_key in ISSUE_PROJECT_RULES.items():
            if re.search(pattern, slide_text):
                logger.debug(f"Project rule matched: '{pattern}' → {project_key}")
                return project_key
        
        # Default project if no specific rules match
        logger.debug(f"No project rule matched, using default: {DEFAULT_PROJECT_KEY}")
        return DEFAULT_PROJECT_KEY
    
    def _extract_slide_text(self, slide) -> str:
        """Extract all text from a slide."""
        texts = []
        for shp in slide.shapes:
            if hasattr(shp, "text") and shp.text.strip():
                texts.append(shp.text.strip())
        return "\n".join(texts) 