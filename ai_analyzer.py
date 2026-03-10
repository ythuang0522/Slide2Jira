"""AI analysis functionality supporting OpenAI and Gemini APIs."""

import asyncio
import base64
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, List
from dataclasses import dataclass, field
from typing import Optional

import aiofiles

from config import ProcessingConfig, AIProvider

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


class BaseAIClient(ABC):
    """Abstract base class for AI API clients."""
    
    def __init__(self, config: ProcessingConfig):
        self.config = config
    
    @abstractmethod
    async def analyze_image(self, base64_image: str, slide_num: int) -> str:
        """Analyze an image and return the raw response content."""
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name for logging."""
        pass
    
    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model name being used."""
        pass


class OpenAIClient(BaseAIClient):
    """OpenAI API client implementation."""
    
    def __init__(self, config: ProcessingConfig):
        super().__init__(config)
        import openai
        self.client = openai.AsyncOpenAI(api_key=config.openai_api_key)
    
    @property
    def provider_name(self) -> str:
        return "OpenAI"
    
    @property
    def model_name(self) -> str:
        return self.config.openai_model
    
    async def analyze_image(self, base64_image: str, slide_num: int) -> str:
        """Analyze an image using OpenAI's Chat API."""
        system_prompt = get_system_prompt()
        user_prompt = f"Analyze this slide (slide #{slide_num}) and extract issue information according to the format specified."
        
        logger.info(f"Calling OpenAI API with model: {self.model_name}")
        response = await self.client.chat.completions.create(
            model=self.model_name,
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
        return response.choices[0].message.content


class GeminiClient(BaseAIClient):
    """Google Gemini API client implementation."""
    
    def __init__(self, config: ProcessingConfig):
        super().__init__(config)
        from google import genai
        self.client = genai.Client(api_key=config.gemini_api_key)
    
    @property
    def provider_name(self) -> str:
        return "Gemini"
    
    @property
    def model_name(self) -> str:
        return self.config.gemini_model
    
    async def analyze_image(self, base64_image: str, slide_num: int) -> str:
        """Analyze an image using Google Gemini API."""
        from google.genai import types
        
        system_prompt = get_system_prompt()
        user_prompt = f"Analyze this slide (slide #{slide_num}) and extract issue information according to the format specified."
        
        logger.info(f"Calling Gemini API with model: {self.model_name}")
        
        # Decode base64 to bytes for Gemini
        image_bytes = base64.b64decode(base64_image)
        
        # Create inline data for the image
        image_part = types.Part.from_bytes(
            data=image_bytes,
            mime_type="image/png"
        )
        
        # Combine system prompt and user prompt for Gemini
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        # Run the synchronous API call in a thread pool to make it async
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.models.generate_content(
                model=self.model_name,
                contents=[full_prompt, image_part]
            )
        )
        
        return response.text


def get_system_prompt() -> str:
    """Get the system prompt for AI analysis."""
    return """You are an expert at analyzing presentation slides and extracting issue information for Jira management.

Given a slide image, extract the following information for creating a Jira issue:

## Required Fields

1. **Title** (標題)
   - 簡潔的繁體中文標題，50字以內
   - 清楚描述問題的核心

2. **Description** (描述)
   使用繁體中文撰寫，包含以下內容：
   - **問題摘要**：用專業軟體工程術語描述主要問題
   - **問題詳情**：列出投影片中所有標記為 Issue/Bug 的項目
   - **相關數據**：引用投影片中可見的數據、指標或證據
   - **建議方案**：若有提及解決方案或後續步驟，請列出
   - **相關識別碼**：僅列出 Sample ID 和 Chip ID（如有）
   
   英文縮寫和專有名詞可保留英文。

3. **Priority** (優先級)
   - High：在投影片中有明確指出High Priority
   - Medium：一般問題（預設）
   - Low：在投影片中有明確指出Low Priority

4. **Issue Type** (問題類型)
   - Bug：明確的程式錯誤或異常行為
   - Task：一般工作項目（預設）

5. **Labels** (標籤)
   - 最多 2 個最相關的英文標籤

## Output Format

回應必須為 JSON 格式：
```json
{
  "title": "問題標題（繁體中文）",
  "description": "**問題摘要**\\n描述內容...\\n\\n**問題詳情**\\n* 項目一\\n* 項目二",
  "priority": "High|Medium|Low",
  "issue_type": "Bug|Task",
  "labels": ["label1", "label2"]
}
```

**重要提醒**：標題與描述必須使用繁體中文，其他欄位使用英文。
"""


def create_ai_client(config: ProcessingConfig) -> BaseAIClient:
    """Factory function to create the appropriate AI client based on config."""
    if config.ai_provider == AIProvider.OPENAI:
        return OpenAIClient(config)
    elif config.ai_provider == AIProvider.GEMINI:
        return GeminiClient(config)
    else:
        raise ValueError(f"Unsupported AI provider: {config.ai_provider}")


class AsyncAIAnalyzer:
    """Handles async AI analysis of slide images."""
    
    def __init__(self, config: ProcessingConfig):
        self.config = config
        self.ai_client = create_ai_client(config)
        self.manual_project_key = config.project_key
        
        logger.info(f"Using {self.ai_client.provider_name} provider with model: {self.ai_client.model_name}")
        
        if self.manual_project_key:
            logger.info(f"Using manual project key: {self.manual_project_key}")
        else:
            logger.info("Using rule-based project determination from SlideDetector")
    
    async def analyze_slide(self, image_path: str, slide_num: int, predetermined_project_key: Optional[str] = None) -> SlideAnalysis:
        """Analyze slide image using AI API to extract issue details."""
        try:
            base64_image = await self._encode_image_base64_async(image_path)
            content = await self.ai_client.analyze_image(base64_image, slide_num)
            analysis_dict = self._parse_response(content, slide_num)
            
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
        """Encode image to base64 for AI API asynchronously."""
        async with aiofiles.open(image_path, "rb") as f:
            content = await f.read()
            return base64.b64encode(content).decode('utf-8')
    
    def _parse_response(self, content: str, slide_num: int) -> Dict:
        """Parse the AI response and extract JSON."""
        logger.info(f"AI analysis for slide {slide_num} completed")
        
        try:
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            json_str = content[json_start:json_end]
            parsed = json.loads(json_str)
            return parsed
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse JSON from AI response: {e}")
            return {
                "title": f"Issue from Slide {slide_num}",
                "description": content,
                "priority": "Medium",
                "issue_type": "Task",
                "labels": [f"slide-{slide_num}"]
            }
