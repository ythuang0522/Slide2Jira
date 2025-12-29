#!/usr/bin/env python3
"""
PowerPoint to Jira Issue Converter - Modular Version

This is the main entry point for the modular PowerPoint to Jira converter.
All components are separated into focused, maintainable modules.
"""

import asyncio
import argparse
import logging
from pathlib import Path
from typing import List

from config import ProcessingConfig, MAX_CONCURRENT_REQUESTS
from processor import AsyncPowerPointToJiraProcessor
from ai_analyzer import SlideAnalysis

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_results(results: List[SlideAnalysis], dry_run: bool = False):
    """Print processing results in a formatted way."""
    logger.info(f"Processed {len(results)} issue slides")
    
    for result in results:
        print(f"\n{'='*60}")
        print(f"Slide {result.slide_number}: {result.title}")
        print(f"Project: {result.project_key}")
        print(f"Priority: {result.priority}")
        print(f"Type: {result.issue_type}")
        if not dry_run and result.jira_key:
            print(f"Jira Issue: {result.jira_key}")
        print(f"Description:\n{result.description}")
        print(f"Labels: {', '.join(result.labels)}")


def create_argument_parser():
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Convert PowerPoint issues to Jira tickets using AI analysis"
    )
    parser.add_argument("pptx_file", help="Path to the PowerPoint file")
    parser.add_argument("-d", "--dry-run", action="store_true",
                       help="Show what would be created without actually creating issues")
    parser.add_argument("-v", "--debug", action="store_true",
                       help="Keep temporary PDF and image files for debugging")
    parser.add_argument("-p", "--project-key", 
                       help="Jira project key (overrides JIRA_PROJECT_KEY from .env and disables AI project determination)")
    parser.add_argument("-t", "--max-concurrent", type=int, default=MAX_CONCURRENT_REQUESTS,
                       help=f"Maximum concurrent API requests (default: {MAX_CONCURRENT_REQUESTS})")
    parser.add_argument("--provider", choices=["openai", "gemini"], default=None,
                       help="AI provider to use: 'openai' or 'gemini' (default: uses AI_PROVIDER env var or 'gemini')")
    
    return parser


async def async_main():
    """Async main entry point."""
    parser = create_argument_parser()
    args = parser.parse_args()
    
    if not Path(args.pptx_file).exists():
        logger.error(f"File not found: {args.pptx_file}")
        return 1
    
    try:
        config = ProcessingConfig.from_env(provider=args.provider)
        config.dry_run = args.dry_run
        config.debug = args.debug
        config.max_concurrent_requests = args.max_concurrent
        
        if args.project_key:
            config.project_key = args.project_key
            logger.info(f"Using manual project key from command line: {args.project_key}")
            logger.info("Rule-based project determination disabled due to manual override")
        elif config.project_key:
            logger.info(f"Using manual project key from environment: {config.project_key}")
            logger.info("Rule-based project determination disabled due to manual override")
        else:
            logger.info("No manual project key specified - using rule-based project determination")
        
        if args.dry_run:
            logger.info("DRY RUN MODE - No issues will be created")
        
        if args.debug:
            logger.info("DEBUG MODE - Temporary files will be preserved")
            
        logger.info(f"Max concurrent requests: {config.max_concurrent_requests}")
        
        # Create and run the processor
        processor = AsyncPowerPointToJiraProcessor(config)
        
        # Measure total processing time
        start_time = asyncio.get_event_loop().time()
        results = await processor.process(args.pptx_file)
        total_time = asyncio.get_event_loop().time() - start_time
        
        print_results(results, args.dry_run)
        logger.info(f"Total processing time: {total_time:.2f} seconds")
        return 0
        
    except Exception as e:
        logger.error(f"Failed to process presentation: {e}")
        return 1


def main():
    """Synchronous main entry point that runs the async version."""
    return asyncio.run(async_main())


if __name__ == "__main__":
    exit(main()) 