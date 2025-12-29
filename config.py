"""Configuration management for the PowerPoint to Jira converter."""

import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from dotenv import load_dotenv

# Image processing constants
DEFAULT_MAX_IMAGE_SIZE_MB = 2.0
DEFAULT_JPEG_QUALITY = 85
DEFAULT_IMAGE_SCALE = 1.5
MIN_JPEG_QUALITY = 60

# OpenAI constants
DEFAULT_OPENAI_MODEL = 'gpt-4.1'
DEFAULT_TIMEOUT = 30

# Gemini constants
DEFAULT_GEMINI_MODEL = 'gemini-3-flash-preview'


class AIProvider(Enum):
    """Supported AI providers."""
    OPENAI = "openai"
    GEMINI = "gemini"

# Processing constants
PDF_CONVERSION_TIMEOUT = 120
MAX_CONCURRENT_REQUESTS = 5

# Issue detection patterns
ISSUE_PATTERNS = [
    r"(?i)(?:^|\n)issue:",           # "Issue:" at start of line (case-insensitive)
    r"(?i)(?:^|\n)(bug):",           # "Bug:" at start of line (case-insensitive)
    r"(?i)(?:^|\n)db issue:",        # "DB issue:" at start of line (case-insensitive)
    r"(?i)(?:^|\n)coj issue:",        # "Cojudge issue:" at start of line (case-insensitive)
    r"(?i)(?:^|\n)aj issue:",        # "Autojudge issue:" at start of line (case-insensitive)
    r"(?i)(?:^|\n)New feature:",        # "Issue:" at start of line (case-insensitive)
]

# Rule-based project mapping for specific issue patterns
ISSUE_PROJECT_RULES = {
    r"(?i)(?:^|\n)db issue:": "DB",
    r"(?i)(?:^|\n)issue:": "AP",      # Explicit rule
    r"(?i)(?:^|\n)(bug):": "AP",      # Explicit rule
    r"(?i)(?:^|\n)coj issue:": "COJ",      # Explicit rule
    r"(?i)(?:^|\n)aj issue:": "AJ",      # Explicit rule
    r"(?i)(?:^|\n)New feature:": "AP",      # Explicit rule
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
    
    # AI provider settings
    ai_provider: AIProvider = AIProvider.GEMINI
    openai_api_key: Optional[str] = None
    openai_model: str = DEFAULT_OPENAI_MODEL
    gemini_api_key: Optional[str] = None
    gemini_model: str = DEFAULT_GEMINI_MODEL
    
    # Optional settings with defaults
    project_key: Optional[str] = None  # Now optional - rules determine if not specified
    
    # Processing settings
    max_image_size_mb: float = DEFAULT_MAX_IMAGE_SIZE_MB
    libreoffice_command: str = 'soffice'
    dry_run: bool = False
    debug: bool = False
    max_concurrent_requests: int = MAX_CONCURRENT_REQUESTS
    
    @classmethod
    def from_env(cls, provider: Optional[str] = None) -> 'ProcessingConfig':
        """Load configuration from environment variables.
        
        Args:
            provider: Optional AI provider override ('openai' or 'gemini').
                     If not specified, uses AI_PROVIDER env var or defaults to 'gemini'.
        """
        load_dotenv(override=True)
        
        # Determine AI provider
        provider_str = provider or os.getenv('AI_PROVIDER', 'gemini')
        try:
            ai_provider = AIProvider(provider_str.lower())
        except ValueError:
            raise ValueError(f"Invalid AI provider: {provider_str}. Must be 'openai' or 'gemini'")
        
        config_dict = {
            'base_url': os.getenv('JIRA_BASE_URL'),
            'email': os.getenv('JIRA_EMAIL'),
            'api_token': os.getenv('JIRA_API_TOKEN'),
            'project_key': os.getenv('JIRA_PROJECT_KEY'),  # Can be None
            'ai_provider': ai_provider,
            'openai_api_key': os.getenv('OPENAI_API_KEY'),
            'openai_model': os.getenv('OPENAI_MODEL', DEFAULT_OPENAI_MODEL),
            'gemini_api_key': os.getenv('GEMINI_API_KEY'),
            'gemini_model': os.getenv('GEMINI_MODEL', DEFAULT_GEMINI_MODEL),
            'max_image_size_mb': float(os.getenv('MAX_IMAGE_SIZE_MB', DEFAULT_MAX_IMAGE_SIZE_MB)),
            'libreoffice_command': os.getenv('LIBREOFFICE_COMMAND', 'soffice'),
            'max_concurrent_requests': int(os.getenv('MAX_CONCURRENT_REQUESTS', MAX_CONCURRENT_REQUESTS))
        }
        
        # Validate required Jira config
        required_jira_keys = ['base_url', 'email', 'api_token']
        missing = [k for k in required_jira_keys if not config_dict.get(k)]
        if missing:
            raise ValueError(f"Missing required Jira environment variables: {missing}")
        
        # Validate API key for selected provider
        if ai_provider == AIProvider.OPENAI and not config_dict.get('openai_api_key'):
            raise ValueError("OPENAI_API_KEY is required when using OpenAI provider")
        if ai_provider == AIProvider.GEMINI and not config_dict.get('gemini_api_key'):
            raise ValueError("GEMINI_API_KEY is required when using Gemini provider")
        
        config_instance = cls(**config_dict)
        config_instance.print_config()
        return config_instance
    
    def print_config(self):
        """Print configuration settings with sensitive data masked."""
        print("\n=== Configuration Settings ===")
        print(f"JIRA Base URL: {self.base_url}")
        print(f"JIRA Email: {self.email}")
        print(f"Project Key: {self.project_key or 'Not set (using rules)'}")
        print(f"AI Provider: {self.ai_provider.value}")
        if self.ai_provider == AIProvider.OPENAI:
            print(f"AI Model: {self.openai_model}")
        else:
            print(f"AI Model: {self.gemini_model}")
        print(f"Dry Run: {self.dry_run}")
        print(f"Debug: {self.debug}")
        print(f"Max Concurrent Requests: {self.max_concurrent_requests}")
        print("==============================\n")
    
    @property
    def current_model(self) -> str:
        """Get the model name for the current AI provider."""
        if self.ai_provider == AIProvider.OPENAI:
            return self.openai_model
        return self.gemini_model 