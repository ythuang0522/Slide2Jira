# LibreOffice Conversion Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make macOS PPTX conversion resilient to stale outputs, LibreOffice profile failures, invalid PDFs, and missing mapped pages without adding a commercial dependency.

**Architecture:** `PDFConverter` will perform up to two isolated LibreOffice attempts. Each attempt writes to its own temporary output directory, validates the generated PDF with PyMuPDF, and atomically promotes only a valid result. `ImageExtractor` will fail before extraction when an expected mapped PDF page is missing, preventing partial Jira creation.

**Tech Stack:** Python 3.8+, `unittest`, `unittest.mock`, LibreOffice CLI, PyMuPDF, `pathlib`, `tempfile`.

## Global Constraints

- Keep LibreOffice as the free, local macOS conversion backend.
- Every attempt must use a separate writable LibreOffice user profile.
- Never accept a stale, empty, malformed, or zero-page PDF.
- Preserve explicit PPTX-slide-to-PDF-page mapping for hidden slides.
- Do not modify unrelated existing worktree changes.

---

### Task 1: Harden conversion attempts and output promotion

**Files:**
- Modify: `pdf_converter.py`
- Test: `tests/test_pdf_converter.py`

**Interfaces:**
- Consumes: `PDFConverter.convert_to_pdf(pptx_path: str, output_dir: str) -> str`
- Produces: the same public interface, returning only an atomically promoted and validated PDF path.

- [ ] **Step 1: Add failing tests**

Add focused tests proving that the converter removes stale output, retries once with distinct profiles and output directories, rejects malformed PDFs through `fitz.open`, promotes a valid PDF with `Path.replace`, and logs version/duration diagnostics.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python -m unittest tests.test_pdf_converter -v`

Expected: failures because the current converter writes directly to the final directory, performs one attempt, and does not validate the PDF structure.

- [ ] **Step 3: Implement the minimal converter behavior**

Refactor internal helpers for command construction, one conversion attempt, PDF validation, and best-effort version reporting. Use `TemporaryDirectory` for both profile and attempt output, retry exactly once, and replace the final target only after validation succeeds.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `python -m unittest tests.test_pdf_converter -v`

Expected: all converter tests pass.

### Task 2: Reject missing mapped PDF pages

**Files:**
- Modify: `image_extractor.py`
- Create: `tests/test_image_extractor.py`

**Interfaces:**
- Consumes: `ImageExtractor.extract_slide_images(pdf_path, slide_page_mapping, output_dir)`
- Produces: the same return mapping, but raises `ValueError` before extraction when any mapped page is outside the PDF.

- [ ] **Step 1: Add a failing mapping-validation test**

Create a small one-page PDF and request page two. Assert that extraction raises a clear `ValueError` naming the PPTX slide, requested page, and actual PDF page count.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python -m unittest tests.test_image_extractor -v`

Expected: failure because the current extractor warns and silently continues.

- [ ] **Step 3: Implement preflight mapping validation**

Validate all mapped page numbers immediately after opening the PDF and before writing any JPEG files. Close the document reliably with a context manager.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `python -m unittest tests.test_image_extractor -v`

Expected: the mapping test passes.

### Task 3: End-to-end verification

**Files:**
- Verify: `pdf_converter.py`, `image_extractor.py`, and all tests.

**Interfaces:**
- Consumes: the repository's existing `main.py` pipeline and a local real PPTX deck.
- Produces: verification evidence without creating duplicate Jira issues.

- [ ] **Step 1: Run the complete unit suite**

Run: `python -m unittest discover -s tests -v`

Expected: all tests pass.

- [ ] **Step 2: Run formatting and syntax checks**

Run: `python -m compileall -q .` and `git diff --check`

Expected: both commands exit zero.

- [ ] **Step 3: Run a real conversion-only smoke test**

Run the converter against `20260717_tNGS issues.pptx` in a temporary output directory. Verify exit status zero, a non-empty PDF, and a readable positive PyMuPDF page count. Do not run Jira creation.

- [ ] **Step 4: Review the final diff**

Confirm only the planned converter, extractor, tests, and plan files changed in this task; preserve pre-existing `AGENTS.md` edits.
