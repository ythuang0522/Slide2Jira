# PowerPoint to Jira Issues - AI Enhanced Converter

This tool automatically detects issues mentioned in slides in PowerPoint presentations and creates Jira issues using AI-powered content analysis. 

## 📋 Prerequisites

### Software Requirements

1. **LibreOffice** (for PDF conversion)
   ```bash
   # macOS
   brew install libreoffice
   
   # Ubuntu/Debian
   sudo apt-get install libreoffice
   
   # Windows
   # Download from https://www.libreoffice.org/
   ```

2. **Python 3.8+** with required packages

### API Access

1. **Jira Cloud API Token**
   - Go to [Atlassian Account Settings](https://id.atlassian.com/manage-profile/security/api-tokens)
   - Create API token
   - Note your Jira base URL and email

2. **OpenAI API Key**
   - Get API key from [OpenAI Platform](https://platform.openai.com/api-keys)
   - Ensure you have access to GPT-4o or GPT-4-turbo

## 🛠 Installation

1. **Clone or download the project**
   ```bash
   git clone <repository-url>
   cd jira-pptx-converter
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   Edit `.env` file:
   ```bash
   # Jira Configuration
   JIRA_BASE_URL=https://yourorg.atlassian.net
   JIRA_EMAIL=your-email@company.com
   JIRA_API_TOKEN=your-api-token
   JIRA_PROJECT_KEY=PROJ    # Optional - if not set, rules determine project

   # OpenAI Configuration
   OPENAI_API_KEY=your-openai-api-key
   OPENAI_MODEL=gpt-4o

   # Processing Configuration (Optional)
   MAX_IMAGE_SIZE_MB=1.0
   MAX_CONCURRENT_REQUESTS=5
   LIBREOFFICE_COMMAND=soffice
   ```

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `JIRA_BASE_URL` | Your Jira instance URL | ✅ | - |
| `JIRA_EMAIL` | Your Jira account email | ✅ | - |
| `JIRA_API_TOKEN` | Jira API token | ✅ | - |
| `JIRA_PROJECT_KEY` | Target project key (optional - overrides rules) | ❌ | Rule-based |
| `OPENAI_API_KEY` | OpenAI API key | ✅ | - |
| `OPENAI_MODEL` | OpenAI model to use | ❌ | gpt-4o |
| `MAX_IMAGE_SIZE_MB` | Maximum image size in MB | ❌ | 1.0 |
| `MAX_CONCURRENT_REQUESTS` | Max parallel API requests | ❌ | 5 |
| `LIBREOFFICE_COMMAND` | LibreOffice executable path | ❌ | soffice |

## 🎯 Rule-Based Project Classification

When `JIRA_PROJECT_KEY` is not specified, the system uses simple text pattern matching to determine the appropriate project:

### Available Projects
| Project Key | Name | Description |
|-------------|------|-------------|
| **PGDB** | Genome Database | Issues related to genome sequences in the database, genome quality, taxonomic classification errors |
| **AP** | Software & Pipeline | Issues related to software, pipelines, algorithms, code bugs, performance optimization, autojudge rules |

### Project Determination Rules
| Issue Title Pattern | Project | Example |
|---------------------|---------|---------|
| Starts with "DB issue:" | **PGDB** | "DB issue: Streptococcus sobrinus low ANI" |
| All other patterns | **AP** | "Issue: Pipeline performance slow" |

### Project Determination Logic
- **Manual Override**: If `JIRA_PROJECT_KEY` is set in `.env` or via `-p` flag, all issues use that project
- **Rule-based Classification**: If no project specified, system checks issue title against pattern rules
- **Default**: Issues that don't match any specific pattern default to `AP`

## 🔧 Usage

### Basic Usage

```bash
# Dry run to preview what would be created
python main.py presentation.pptx --dry-run

# Create actual Jira issues
python main.py presentation.pptx

# Use a specific project key (disables AI project determination)
python main.py presentation.pptx --project-key PGDB

# Let rule-based system determine projects automatically (omit project key)
python main.py presentation.pptx

# Debug mode - keep temporary files for inspection
python main.py presentation.pptx --dry-run --debug
```

### Command Line Options

```bash
python main.py [OPTIONS] PPTX_FILE

Arguments:
  PPTX_FILE                    Path to the PowerPoint presentation

Options:
  -d, --dry-run               Show what would be created without actually creating issues
  --debug                     Keep temporary PDF and image files for debugging
  -p, --project-key           Jira project key (overrides .env and disables rule-based project determination)
  -t, --max-concurrent        Maximum concurrent API requests (default: 5)
  -h, --help                  Show help message
```

## 🏗️ Architecture Overview

```
project/
├── main.py                  # 🚀 Entry point + result display (119 lines)
├── processor.py             # 🎯 Pipeline orchestrator + temp utils (107 lines)  
├── config.py                # ⚙️ Configuration + constants (71 lines)
├── ai_analyzer.py           # 🤖 AI analysis + SlideAnalysis model (171 lines)
├── jira_client.py           # 🔗 Jira operations (160 lines)
├── slide_detector.py        # 📋 Issue slide detection (40 lines)
├── pdf_converter.py         # 📄 PDF conversion (63 lines)
├── image_extractor.py       # 🖼️  Image extraction (84 lines)
└── requirements.txt         # 📦 Dependencies
```

The application processes presentations through a clean 5-step pipeline with full parallelization:

### 🔍 Issue Detection Patterns

The tool automatically detects slides that contain issues using these patterns:

| Pattern | Description | Example |
|---------|-------------|---------|
| `Issue:` | Lines starting with "Issue:" (case-insensitive) | "Issue: Database connection fails" |
| `Bug:` | Lines starting with "Bug:" (case-insensitive) | "Bug: Login validation error" |
| `DB issue:` | Lines starting with "DB issue:" (case-insensitive) | "DB issue: Streptococcus sobrinus low ANI" |

**Detection Logic:**
- Scans all text shapes in each slide
- Uses regex pattern matching for reliable detection
- Case-insensitive matching for flexibility
- Must appear at the beginning of a line (^ anchor)

```mermaid
flowchart LR
    A["📄 PowerPoint<br/>presentation.pptx"] --> O["🎯 Pipeline Orchestrator<br/>processor.py"]
    
    O --> B["🔍 Detect Issues<br/>slide_detector.py"]
    O --> C["📄 Convert to PDF<br/>pdf_converter.py"]
    O --> D["🖼️ Extract Images<br/>image_extractor.py"]
    O --> E["🤖 AI Analysis<br/>ai_analyzer.py"]
    O --> F["🎫 Create Jira Issues<br/>jira_client.py"]
    
    B --> G["✅ Results<br/>PROJ-123, PROJ-124"]
    C --> G
    D --> G
    E --> G
    F --> G
    
    style A fill:#e1f5fe
    style O fill:#f3e5f5
    style G fill:#e8f5e8
    style E fill:#fff3e0
    style F fill:#e3f2fd
```

## 📊 Example Output

```
============================================================
Slide 6: E. coli contamination detection issue with PK-0 classification
Project: PGDB
Priority: High
Type: Bug
Jira Issue: PGDB-123
Description:
### Problem
E. coli should not be classified as PK-0 when ANI=NANI=98.17 and 
NANI_real_diff > 0.2 with Sec.hit >= 200...

### Evidence & Data
- ANI = NANI = 98.17
- PK-0: NANI_real_diff > 0.2
- sec.hit >= 200

### Proposed Next Steps
- Review contamination filtering logic
- Update PK-0 classification criteria

Labels: contamination, filtering, slide-6
============================================================
Slide 8: Pipeline performance optimization needed
Project: AP
Priority: Medium
Type: Task
Jira Issue: AP-124
Description:
### Problem
Current analysis pipeline taking 4+ hours for large datasets

### Performance Metrics
- Memory usage: 32GB+ 
- CPU utilization: 45%
- I/O bottleneck identified

### Proposed Solutions
- Implement parallel processing
- Optimize data structures
- Add progress monitoring

Labels: performance, pipeline, slide-8
============================================================
Total processing time: 17.14 seconds
```

## Project Key Determination

The system supports both manual and automatic project key determination:

### Manual Project Key (Override)
If you specify a project key via environment variable or command line, it will be used for **all** issues:
```bash
# Via environment
export JIRA_PROJECT_KEY=PROJ

# Via command line (overrides environment)
python main.py presentation.pptx --project-key PROJ
```

### Automatic Rule-Based Project Determination
If no manual project key is specified, the system uses **rule-based pattern matching** on the original slide text during issue detection:

#### Project Rules
- **PGDB Project**: Issues with text starting with `"DB issue:"` (case-insensitive)
- **AP Project**: All other detected issues (default)

#### Examples
```
"DB issue: Streptococcus sobrinus genome problematic" → PGDB project
"DB ISSUE: Database connection failed" → PGDB project  
"Issue: Frontend bug in login form" → AP project
"Bug: Memory leak in pipeline" → AP project
```

#### Pattern Detection
- Patterns must appear **at the start of a line** within the slide text
- Case-insensitive matching
- Multi-line slide text is supported

#### Adding New Rules
To add project-specific rules, modify `config.py`:

```python
ISSUE_PROJECT_RULES = {
    r"(?i)(?:^|\n)db issue:": "PGDB",     # Database issues
    r"(?i)(?:^|\n)ui issue:": "DESIGN",   # UI/Design issues  
    r"(?i)(?:^|\n)api issue:": "BACKEND", # API issues
}

DEFAULT_PROJECT_KEY = "AP"  # Fallback for unmatched patterns
```

**Note**: Rule-based determination happens during **slide detection** using the original slide text, not the AI-generated titles. This ensures accurate pattern matching on the source content.
