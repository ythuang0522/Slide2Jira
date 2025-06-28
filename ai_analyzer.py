"""AI analysis functionality using OpenAI API."""

import asyncio
import base64
import json
import logging
from typing import Dict, List
from dataclasses import dataclass, field
from typing import Optional

import aiofiles
import openai

from config import ProcessingConfig

logger = logging.getLogger(__name__)


@dataclass
class SlideAnalysis:
    """Data class for slide analysis results."""
    slide_number: int
    title: str
    description: str
    priority: str = "Medium"
    issue_type: str = "Task"
    labels: List[str] = field(default_factory=list)
    jira_key: Optional[str] = None


class AsyncAIAnalyzer:
    """Handles async AI analysis of slide images."""
    
    def __init__(self, config: ProcessingConfig):
        self.config = config
        self.client = openai.AsyncOpenAI(api_key=config.openai_api_key)
    
    async def analyze_slide(self, image_path: str, slide_num: int) -> SlideAnalysis:
        """Analyze slide image using ChatGPT API to extract issue details."""
        try:
            base64_image = await self._encode_image_base64_async(image_path)
            response = await self._call_openai_api_async(base64_image, slide_num)
            analysis_dict = self._parse_response(response, slide_num)
            
            return SlideAnalysis(
                slide_number=slide_num,
                title=analysis_dict.get('title', f'Issue from Slide {slide_num}'),
                description=analysis_dict.get('description', ''),
                priority=analysis_dict.get('priority', 'Medium'),
                issue_type=analysis_dict.get('issue_type', 'Task'),
                labels=analysis_dict.get('labels', [])
            )
            
        except Exception as e:
            logger.error(f"Error analyzing slide {slide_num} with AI: {e}")
            raise
    
    async def analyze_slides_batch(self, slide_images: Dict[int, str]) -> List[SlideAnalysis]:
        """Analyze multiple slides in parallel with concurrency limit."""
        semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)
        
        async def analyze_with_semaphore(slide_num: int, image_path: str) -> SlideAnalysis:
            async with semaphore:
                return await self.analyze_slide(image_path, slide_num)
        
        tasks = [
            analyze_with_semaphore(slide_num, image_path)
            for slide_num, image_path in slide_images.items()
        ]
        
        logger.info(f"Starting parallel analysis of {len(tasks)} slides (max {self.config.max_concurrent_requests} concurrent)")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and log errors
        successful_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                slide_num = list(slide_images.keys())[i]
                logger.error(f"Failed to analyze slide {slide_num}: {result}")
            else:
                successful_results.append(result)
        
        return successful_results
    
    async def _encode_image_base64_async(self, image_path: str) -> str:
        """Encode image to base64 for OpenAI API asynchronously."""
        async with aiofiles.open(image_path, "rb") as f:
            content = await f.read()
            return base64.b64encode(content).decode('utf-8')
    
    async def _call_openai_api_async(self, base64_image: str, slide_num: int):
        """Make the async API call to OpenAI."""
        system_prompt = self._get_system_prompt()
        user_prompt = f"Please analyze this slide (slide #{slide_num}) and extract issue information according to the format specified."
        
        return await self.client.chat.completions.create(
            model=self.config.openai_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            max_tokens=3000,
            temperature=0.1
        )
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for AI analysis."""
        return """You are an expert at analyzing presentation slides and extracting issue information for Jira management.

Given a slide image, extract the following information for creating a Jira issue:

1. **Title/Summary**: A concise title (max 200 chars) that captures the main issue
2. **Description**: A comprehensive description of the issue, including:
   - What the problem is
   - Any visible data, metrics, or evidence related to the issue
   - Context or background information related to the issue
   - Any proposed solutions or next steps mentioned

3. **Priority**: Estimate priority based on visual cues (High/Medium/Low), if not clear, use **Medium**.
4. **Issue Type**: Categorize as Bug or Task based on content, if not clear, use Task as default.
5. **Labels**: Add upto two most relevant labels to the issue. 

Format your response as JSON:
```json
{
  "title": "Concise issue title",
  "description": "Detailed description in markdown format",
  "priority": "High|Medium|Low", 
  "issue_type": "Bug|Task",
  "labels": ["label1", "label2"]
}
```

Be thorough but concise."""
    
    def _parse_response(self, response, slide_num: int) -> Dict:
        """Parse the OpenAI response and extract JSON."""
        content = response.choices[0].message.content
        logger.info(f"GPT analysis for slide {slide_num} completed")
        
        try:
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            json_str = content[json_start:json_end]
            return json.loads(json_str)
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse JSON from GPT response: {e}")
            return {
                "title": f"Issue from Slide {slide_num}",
                "description": content,
                "priority": "Medium",
                "issue_type": "Task",
                "labels": [f"slide-{slide_num}"]
            } 