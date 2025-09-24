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
    project_key: Optional[str] = None  # Pre-determined by SlideDetector or config-specified
    jira_key: Optional[str] = None


class AsyncAIAnalyzer:
    """Handles async AI analysis of slide images."""
    
    def __init__(self, config: ProcessingConfig):
        self.config = config
        self.client = openai.AsyncOpenAI(api_key=config.openai_api_key)
        self.manual_project_key = config.project_key
        
        if self.manual_project_key:
            logger.info(f"Using manual project key: {self.manual_project_key}")
        else:
            logger.info("Using rule-based project determination from SlideDetector")
    
    async def analyze_slide(self, image_path: str, slide_num: int, predetermined_project_key: Optional[str] = None) -> SlideAnalysis:
        """Analyze slide image using ChatGPT API to extract issue details."""
        try:
            base64_image = await self._encode_image_base64_async(image_path)
            response = await self._call_openai_api_async(base64_image, slide_num)
            analysis_dict = self._parse_response(response, slide_num)
            
            # Use manual override or pre-determined project key
            if self.manual_project_key:
                project_key = self.manual_project_key
                logger.debug(f"Using manual project key '{project_key}' for slide {slide_num}")
            else:
                project_key = predetermined_project_key
                logger.debug(f"Using pre-determined project key '{project_key}' for slide {slide_num}")
            
            return SlideAnalysis(
                slide_number=slide_num,
                title=analysis_dict.get('title', f'Issue from Slide {slide_num}'),
                description=analysis_dict.get('description', ''),
                priority=analysis_dict.get('priority', 'Medium'),
                issue_type=analysis_dict.get('issue_type', 'Task'),
                labels=analysis_dict.get('labels', []),
                project_key=project_key
            )
            
        except Exception as e:
            logger.error(f"Error analyzing slide {slide_num} with AI: {e}")
            raise
    
    async def analyze_slides_batch(self, slide_images: Dict[int, str], slide_project_mapping: Dict[int, str] = None) -> List[SlideAnalysis]:
        """Analyze multiple slides in parallel with concurrency limit."""
        semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)
        
        async def analyze_with_semaphore(slide_num: int, image_path: str) -> SlideAnalysis:
            async with semaphore:
                predetermined_project = slide_project_mapping.get(slide_num) if slide_project_mapping else None
                return await self.analyze_slide(image_path, slide_num, predetermined_project)
        
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
            ]
        )
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for AI analysis."""
        return """You are an expert at analyzing presentation slides and extracting issue information for Jira management.

Given a slide image, extract the following information for creating a Jira issue:

1. **Title**: 簡潔的繁體中文標題描述問題或新功能，100字以內**.
2. **Description**: 簡潔明瞭的描述問題或新功能，包含:
   - What the problem or feature is. 
   - The slide may contain several issues or features. The primary issue or feature is the sentence containing "Issue" or "Bug" or "New feature".
   - Any visible data, metrics, or evidence related to the primary issue or feature
   - Context or background information related to the primary issue or feature
   - Any proposed solutions or next steps mentioned related to the primary issue or feature
   - Sample ID and Chip ID if available. Do not include any other identifiers (e.g., Hospital ID, Seq ID, patient identifiers, internal tracking IDs).
   - Other relevant information related to the primary issue or feature, explicitly excluding any identifiers beyond Sample ID and Chip ID
   **務必用繁體中文輸出描述，英文縮寫和專有名詞可保留英文**.

3. **Priority**: the priority of the issue (Medium/Low) if mentioned. If not mentioned, use **Medium**.
4. **Issue Type**: Categorize as Bug or Task based on content, if not clear, use Task as default.
5. **Labels**: Add upto two most relevant labels to the issue.

**IMPORTANT**: The title and description MUST be written in Traditional Chinese (繁體中文). All other fields should remain in English.

Format your response as JSON:
```json
{
  "title": "簡潔的問題標題（繁體中文）",
  "description": "詳細的問題描述（繁體中文，使用適合在Jira中顯示的格式）",
  "priority": "Medium|Low", 
  "issue_type": "Bug|Task",
  "labels": ["label1", "label2"]
}
```
"""
    
    def _parse_response(self, response, slide_num: int) -> Dict:
        """Parse the OpenAI response and extract JSON."""
        content = response.choices[0].message.content
        logger.info(f"GPT analysis for slide {slide_num} completed")
        
        try:
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            json_str = content[json_start:json_end]
            parsed = json.loads(json_str)
            return parsed
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse JSON from GPT response: {e}")
            return {
                "title": f"Issue from Slide {slide_num}",
                "description": content,
                "priority": "Medium",
                "issue_type": "Task",
                "labels": [f"slide-{slide_num}"]
            } 