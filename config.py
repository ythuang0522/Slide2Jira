"""Configuration management for the PowerPoint to Jira converter."""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Image processing constants
DEFAULT_MAX_IMAGE_SIZE_MB = 2.0
DEFAULT_JPEG_QUALITY = 85
DEFAULT_IMAGE_SCALE = 1.5
MIN_JPEG_QUALITY = 60

# OpenAI constants
DEFAULT_OPENAI_MODEL = 'gpt-4o'
DEFAULT_TIMEOUT = 30

# Processing constants
PDF_CONVERSION_TIMEOUT = 120
MAX_CONCURRENT_REQUESTS = 5

# Issue detection patterns
ISSUE_PATTERNS = [
    r"(?i)^issue:",           # "Issue:" prefix (case-insensitive)
    r"(?i)^(bug):"            # "Bug:" prefix (case-insensitive)
]


@dataclass
class ProcessingConfig:
    """Configuration for the processing pipeline."""
    # Jira settings
    base_url: str
    email: str
    api_token: str
    project_key: str
    
    # OpenAI settings
    openai_api_key: str
    openai_model: str = DEFAULT_OPENAI_MODEL
    
    # Processing settings
    max_image_size_mb: float = DEFAULT_MAX_IMAGE_SIZE_MB
    libreoffice_command: str = 'soffice'
    dry_run: bool = False
    debug: bool = False
    max_concurrent_requests: int = MAX_CONCURRENT_REQUESTS
    
    @classmethod
    def from_env(cls) -> 'ProcessingConfig':
        """Load configuration from environment variables."""
        load_dotenv()
        
        config_dict = {
            'base_url': os.getenv('JIRA_BASE_URL'),
            'email': os.getenv('JIRA_EMAIL'),
            'api_token': os.getenv('JIRA_API_TOKEN'),
            'project_key': os.getenv('JIRA_PROJECT_KEY'),
            'openai_api_key': os.getenv('OPENAI_API_KEY'),
            'openai_model': os.getenv('OPENAI_MODEL', DEFAULT_OPENAI_MODEL),
            'max_image_size_mb': float(os.getenv('MAX_IMAGE_SIZE_MB', DEFAULT_MAX_IMAGE_SIZE_MB)),
            'libreoffice_command': os.getenv('LIBREOFFICE_COMMAND', 'soffice'),
            'max_concurrent_requests': int(os.getenv('MAX_CONCURRENT_REQUESTS', MAX_CONCURRENT_REQUESTS))
        }
        
        # Validate required config
        required_keys = ['base_url', 'email', 'api_token', 'project_key', 'openai_api_key']
        missing = [k for k in required_keys if not config_dict.get(k)]
        if missing:
            raise ValueError(f"Missing required environment variables: {missing}")
        
        return cls(**config_dict) 