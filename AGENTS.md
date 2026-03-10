# AGENTS.md

This file guides agentic coding assistants working in this repo.
It summarizes how to build/run, lint/test, and follow project code style.

## Repository overview

- Language: Python 3.8+
- Entry point: `main.py`
- Primary modules: `processor.py`, `ai_analyzer.py`, `jira_client.py`,
  `slide_detector.py`, `pdf_converter.py`, `image_extractor.py`, `config.py`

## Build, lint, test

There are no formal build or lint scripts defined in this repository.
Use the commands below as the current conventions for running and verifying.

### Install dependencies

```bash
pip install -r requirements.txt
```

### Run the application

```bash
python main.py "YTH Slides/presentation.pptx" -d
```

### Build

- No build step is defined (Python script execution only).

### Lint

- No linter configuration found (no `pyproject.toml`, `setup.cfg`, or `.flake8`).
- If you add a linter, prefer `ruff` or `flake8` and document it here.

### Tests

- Activate the `gemini` conda environment before running tests or verification commands:

```bash
source ~/miniforge3/etc/profile.d/conda.sh
conda activate gemini
```

- The current regression tests use the standard library `unittest` runner:

```bash
python -m unittest discover -s tests -v
```

- For future end-to-end verification, use this real deck from `YTH Slides/`:

```bash
python main.py "YTH Slides/20260306_Analysis Speedup.pptx" -d
```

- `pytest` is not currently required in the repo environment. If it is added later, document the exact commands here.

#### Running a single test (when pytest is added)

```bash
# Example: run one test file
python -m pytest tests/test_slide_detector.py

# Example: run a single test by name
python -m pytest -k "test_detects_issue" tests/test_slide_detector.py
```

## Cursor / Copilot rules

- No Cursor rules found in `.cursor/rules/` or `.cursorrules`.
- No Copilot instructions found in `.github/copilot-instructions.md`.

If these files are added later, summarize them in this section.

## Code style guidelines

Follow the patterns already present in the codebase. Consistency matters more
than personal preference.

### Imports and module layout

- Order imports as: standard library, third-party, local modules.
- Prefer explicit imports over wildcard imports.
- Example ordering from files such as `ai_analyzer.py`:
  - Standard lib: `asyncio`, `logging`, `pathlib`, `dataclasses`, `typing`.
  - Third-party: `aiohttp`, `aiofiles`, `fitz`, `PIL`.
  - Local: `config`, `processor`, `ai_analyzer` classes.

### Formatting and spacing

- Use 4 spaces for indentation; no tabs.
- Keep lines reasonably short; wrap long expressions for readability.
- Use blank lines to separate logical sections (imports, constants, classes).
- Use triple-quoted docstrings for modules, classes, and key functions.

### Types and dataclasses

- Use type hints for public function signatures when practical.
- Use `Optional[T]` for values that can be `None`.
- Use `dataclass` for structured data (see `SlideAnalysis`).
- Use `Enum` for small fixed sets (see `AIProvider`).

### Naming conventions

- Modules: `snake_case.py` (already used).
- Classes: `CamelCase` (e.g., `AsyncJiraClient`).
- Functions and methods: `snake_case`.
- Constants: `UPPER_SNAKE_CASE` (e.g., `MAX_CONCURRENT_REQUESTS`).
- Private helpers: prefix with underscore (e.g., `_parse_response`).

### Logging and diagnostics

- Use the standard `logging` module and module-level loggers.
- Prefer `logger.info` for milestones, `logger.debug` for details,
  `logger.warning` for recoverable issues, and `logger.error` for failures.
- Do not print directly except in CLI output formatting (see `main.py`).

### Error handling

- Validate inputs early; raise clear exceptions (e.g., `FileNotFoundError`).
- Catch exceptions where cleanup or logging is required, then re-raise.
- For async batch operations, log per-item failures and continue when safe.
- Use specific exception types when possible (`ValueError`, `RuntimeError`).

### Async and concurrency

- Use `asyncio` for concurrency; bound parallelism with `Semaphore`.
- For blocking libraries, use `run_in_executor` to avoid blocking the loop.
- Keep async API boundaries clear (sync entry point calls async `async_main`).

### HTTP and external APIs

- Use `aiohttp` for Jira calls with `ClientSession` and timeouts.
- Keep API payloads explicit and validate required fields (`project_key`).
- Mask or avoid logging secrets (do not log API keys or tokens).

### File and path handling

- Use `pathlib.Path` for filesystem paths.
- Resolve paths before using external commands where appropriate.
- Cleanup temp directories unless debug mode requests retention.
- Do not assume PowerPoint slide numbers match exported PDF page numbers when hidden slides exist.
- When code crosses both PPTX parsing and PDF/image extraction, carry an explicit mapping from PPTX slide number to exported PDF page number.
- Hidden slides can still be visible to `python-pptx` iteration even when they are omitted from PDF export.

### Configuration and environment

- Centralize configuration in `config.py` and load via `ProcessingConfig`.
- Validate required environment variables early and fail fast.
- Use `.env` for local development and `python-dotenv` for loading.

### Data formats

- AI responses are parsed as JSON. Keep parsing robust:
  - Locate JSON by braces, parse with `json.loads`.
  - On parse failure, return a safe fallback with defaults.
- Jira descriptions are converted to ADF via `_create_adf_content`.

### Internationalization and text

- The AI prompt expects Traditional Chinese output for title/description.
- Preserve existing prompt formatting and output requirements.

## Suggested development workflow

1. Read `README.md` and `config.py` before making changes.
2. Add or update unit tests if you modify logic-heavy modules.
3. Run the CLI in dry-run mode for manual verification:
   `python main.py "YTH Slides/presentation.pptx" -d`.

## Notes for contributors

- Do not commit secrets (API keys, tokens, `.env`).
- Keep dependencies minimal and pinned in `requirements.txt`.
- When adding new modules, follow the existing naming and logging patterns.
- When fixing slide-selection bugs, verify both the reported PPTX slide number and the extracted PDF page/image, especially if the deck contains hidden slides.
