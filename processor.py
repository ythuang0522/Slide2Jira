"""Main processor that orchestrates the entire pipeline."""

import asyncio
import logging
import shutil
from typing import List
from pathlib import Path
from contextlib import contextmanager
from config import ProcessingConfig
from ai_analyzer import SlideAnalysis
from slide_detector import SlideDetector
from pdf_converter import PDFConverter
from image_extractor import ImageExtractor
from ai_analyzer import AsyncAIAnalyzer
from jira_client import AsyncJiraClient

logger = logging.getLogger(__name__)


@contextmanager
def temp_workdir(pptx_path: str, debug: bool = False):
    """Context manager for temporary directory with automatic cleanup."""
    pptx_file = Path(pptx_path)
    pptx_stem = pptx_file.stem
    pptx_dir = pptx_file.parent
    
    workdir = pptx_dir / f"{pptx_stem}_debug"
    workdir.mkdir(exist_ok=True)
    workdir = str(workdir)
    
    logger.info(f"Created temp directory: {workdir}")
    
    try:
        yield workdir
    finally:
        if not debug:
            shutil.rmtree(workdir, ignore_errors=True)
            logger.info(f"Cleaned up temp directory: {workdir}")
        else:
            logger.info(f"Debug mode: Keeping temp files in {workdir}")


class AsyncPowerPointToJiraProcessor:
    """Main processor that orchestrates the entire pipeline with async support."""
    
    def __init__(self, config: ProcessingConfig):
        self.config = config
        self.slide_detector = SlideDetector()
        self.pdf_converter = PDFConverter(config)
        self.image_extractor = ImageExtractor(config)
        self.ai_analyzer = AsyncAIAnalyzer(config)
        self.jira_client = AsyncJiraClient(config)
    
    async def process(self, pptx_path: str) -> List[SlideAnalysis]:
        """Main processing pipeline with async support."""
        results = []
        
        with temp_workdir(pptx_path, self.config.debug) as workdir:
            try:
                # Step 1: Find issue slides (synchronous)
                issue_slides = list(self.slide_detector.find_issue_slides(pptx_path))
                if not issue_slides:
                    logger.info("No issue slides found")
                    return results
                
                issue_slide_numbers = [idx for idx, _ in issue_slides]
                logger.info(f"Found {len(issue_slide_numbers)} issue slides: {issue_slide_numbers}")
                
                # Step 2: Convert to PDF (synchronous)
                pdf_path = self.pdf_converter.convert_to_pdf(pptx_path, workdir)
                
                # Step 3: Extract slide images (synchronous)
                slide_images = self.image_extractor.extract_slide_images(
                    pdf_path, issue_slide_numbers, workdir
                )
                
                # Step 4: Analyze all slides in parallel (asynchronous)
                logger.info("Starting parallel AI analysis...")
                start_time = asyncio.get_event_loop().time()
                
                analyses = await self.ai_analyzer.analyze_slides_batch(slide_images)
                
                analysis_time = asyncio.get_event_loop().time() - start_time
                logger.info(f"Completed AI analysis in {analysis_time:.2f} seconds")
                
                # Step 5: Create Jira issues in parallel (if not dry run)
                if not self.config.dry_run and analyses:
                    logger.info("Starting parallel Jira issue creation...")
                    start_time = asyncio.get_event_loop().time()
                    
                    analyses = await self.jira_client.create_issues_batch(analyses)
                    
                    # Step 6: Attach images in parallel
                    await self.jira_client.attach_images_batch(analyses, slide_images)
                    
                    jira_time = asyncio.get_event_loop().time() - start_time
                    logger.info(f"Completed Jira operations in {jira_time:.2f} seconds")
                
                return analyses
                
            except Exception as e:
                logger.error(f"Error in processing pipeline: {e}")
                raise 