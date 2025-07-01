"""Configuration management for the PowerPoint to Jira converter."""

import os
from dataclasses import dataclass
from typing import Optional
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
    r"(?i)(?:^|\n)issue:",           # "Issue:" at start of line (case-insensitive)
    r"(?i)(?:^|\n)(bug):",           # "Bug:" at start of line (case-insensitive)
    r"(?i)(?:^|\n)db issue:",        # "DB issue:" at start of line (case-insensitive)
    r"(?i)(?:^|\n)coj issue:",        # "DB issue:" at start of line (case-insensitive)

]

# Rule-based project mapping for specific issue patterns
ISSUE_PROJECT_RULES = {
    r"(?i)(?:^|\n)db issue:": "DB",
    r"(?i)(?:^|\n)issue:": "AP",      # Explicit rule
    r"(?i)(?:^|\n)(bug):": "AP",      # Explicit rule
    r"(?i)(?:^|\n)coj issue:": "COJ",      # Explicit rule
}

# Default project key for issues that don't match any specific rules
DEFAULT_PROJECT_KEY = "AP"


@dataclass
class ProcessingConfig:
    """Configuration for the processing pipeline."""
    # Jira settings (required)
    base_url: str
    email: str
    api_token: str
    openai_api_key: str
    
    # Optional settings with defaults
    project_key: Optional[str] = None  # Now optional - rules determine if not specified
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
            'project_key': os.getenv('JIRA_PROJECT_KEY'),  # Can be None
            'openai_api_key': os.getenv('OPENAI_API_KEY'),
            'openai_model': os.getenv('OPENAI_MODEL', DEFAULT_OPENAI_MODEL),
            'max_image_size_mb': float(os.getenv('MAX_IMAGE_SIZE_MB', DEFAULT_MAX_IMAGE_SIZE_MB)),
            'libreoffice_command': os.getenv('LIBREOFFICE_COMMAND', 'soffice'),
            'max_concurrent_requests': int(os.getenv('MAX_CONCURRENT_REQUESTS', MAX_CONCURRENT_REQUESTS))
        }
        
        # Validate required config (project_key now optional)
        required_keys = ['base_url', 'email', 'api_token', 'openai_api_key']
        missing = [k for k in required_keys if not config_dict.get(k)]
        if missing:
            raise ValueError(f"Missing required environment variables: {missing}")
        
        return cls(**config_dict) 