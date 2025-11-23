"""Jira API client functionality."""

import asyncio
import logging
from pathlib import Path
from typing import Dict, List

import aiofiles
import aiohttp

from config import ProcessingConfig, DEFAULT_TIMEOUT
from ai_analyzer import SlideAnalysis

logger = logging.getLogger(__name__)


class AsyncJiraClient:
    """Handles async Jira API operations."""
    
    def __init__(self, config: ProcessingConfig):
        self.config = config
        self.auth = aiohttp.BasicAuth(config.email, config.api_token)
    
    async def create_issue(self, analysis: SlideAnalysis, session: aiohttp.ClientSession) -> str:
        """Create Jira issue from analysis asynchronously."""
        labels = list(analysis.labels)  # Copy to avoid modifying original
        labels.append(f"slide-{analysis.slide_number}")
        
        # Validate project key is set
        if not analysis.project_key:
            raise ValueError(f"No project key specified for slide {analysis.slide_number}")
        
        payload = {
            "fields": {
                "project": {"key": analysis.project_key},  # Use per-analysis project key
                "issuetype": {"name": analysis.issue_type},
                "summary": analysis.title[:200],
                "description": self._create_adf_content(analysis.description),
                "priority": {"name": analysis.priority},  # Set priority from AI analysis
                "labels": labels,
            }
        }
        
        try:
            async with session.post(
                f"{self.config.base_url}/rest/api/3/issue",
                json=payload,
                auth=self.auth,
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)
            ) as response:
                response.raise_for_status()
                result = await response.json()
                issue_key = result['key']
                logger.info(f"Created Jira issue {issue_key} in project {analysis.project_key} for slide {analysis.slide_number}")
                return issue_key
                
        except aiohttp.ClientError as e:
            logger.error(f"Error creating Jira issue for slide {analysis.slide_number} in project {analysis.project_key}: {e}")
            raise
    
    async def attach_image(self, issue_key: str, image_path: str, session: aiohttp.ClientSession):
        """Attach slide image to Jira issue asynchronously."""
        try:
            img_path = Path(image_path)
            
            # Read file asynchronously
            async with aiofiles.open(image_path, 'rb') as f:
                file_content = await f.read()
            
            # Create multipart data
            data = aiohttp.FormData()
            data.add_field('file', file_content, filename=img_path.name, content_type='image/jpeg')
            
            async with session.post(
                f"{self.config.base_url}/rest/api/3/issue/{issue_key}/attachments",
                data=data,
                auth=self.auth,
                headers={'X-Atlassian-Token': 'no-check'},
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)
            ) as response:
                response.raise_for_status()
                logger.info(f"Attached slide image {img_path.name} to {issue_key}")
                
        except Exception as e:
            logger.warning(f"Failed to attach slide image to {issue_key}: {e}")
    
    async def create_issues_batch(self, analyses: List[SlideAnalysis]) -> List[SlideAnalysis]:
        """Create multiple Jira issues in parallel."""
        semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)
        
        async with aiohttp.ClientSession() as session:
            async def create_with_semaphore(analysis: SlideAnalysis) -> SlideAnalysis:
                async with semaphore:
                    try:
                        issue_key = await self.create_issue(analysis, session)
                        analysis.jira_key = issue_key
                        return analysis
                    except Exception as e:
                        logger.error(f"Failed to create issue for slide {analysis.slide_number}: {e}")
                        return analysis
            
            tasks = [create_with_semaphore(analysis) for analysis in analyses]
            logger.info(f"Creating {len(tasks)} Jira issues in parallel (max {self.config.max_concurrent_requests} concurrent)")
            return await asyncio.gather(*tasks)
    
    async def attach_images_batch(self, analyses: List[SlideAnalysis], slide_images: Dict[int, str]):
        """Attach images to multiple Jira issues in parallel."""
        semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)
        
        async with aiohttp.ClientSession() as session:
            async def attach_with_semaphore(analysis: SlideAnalysis):
                if analysis.jira_key and analysis.slide_number in slide_images:
                    async with semaphore:
                        await self.attach_image(
                            analysis.jira_key, 
                            slide_images[analysis.slide_number], 
                            session
                        )
            
            valid_analyses = [a for a in analyses if a.jira_key and a.slide_number in slide_images]
            tasks = [attach_with_semaphore(analysis) for analysis in valid_analyses]
            
            if tasks:
                logger.info(f"Attaching {len(tasks)} images in parallel")
                await asyncio.gather(*tasks, return_exceptions=True)
    
    def _create_adf_content(self, text: str) -> Dict:
        """Convert markdown text to Atlassian Document Format."""
        if not text.strip():
            return {"type": "doc", "version": 1, "content": []}
        
        paragraphs = text.split('\n\n')
        content = []
        
        for para in paragraphs:
            if para.strip():
                if para.strip().startswith('# '):
                    content.append({
                        "type": "heading",
                        "attrs": {"level": 1},
                        "content": [{"type": "text", "text": para.strip()[2:]}]
                    })
                elif para.strip().startswith('## '):
                    content.append({
                        "type": "heading", 
                        "attrs": {"level": 2},
                        "content": [{"type": "text", "text": para.strip()[3:]}]
                    })
                elif para.strip().startswith('**') and para.strip().endswith('**'):
                    content.append({
                        "type": "paragraph",
                        "content": [{
                            "type": "text",
                            "text": para.strip()[2:-2],
                            "marks": [{"type": "strong"}]
                        }]
                    })
                else:
                    content.append({
                        "type": "paragraph",
                        "content": [{"type": "text", "text": para.strip()}]
                    })
        
        return {"type": "doc", "version": 1, "content": content} 