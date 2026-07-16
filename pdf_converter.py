"""PDF conversion functionality."""

import logging
import subprocess
import tempfile
import time
from pathlib import Path

import fitz

from config import ProcessingConfig, PDF_CONVERSION_TIMEOUT

logger = logging.getLogger(__name__)

MAX_CONVERSION_ATTEMPTS = 2
VERSION_CHECK_TIMEOUT = 10


class PDFConverter:
    """Handle resilient PowerPoint-to-PDF conversion with LibreOffice."""

    def __init__(self, config: ProcessingConfig):
        self.config = config

    def convert_to_pdf(self, pptx_path: str, output_dir: str) -> str:
        """Convert a PPTX into a validated PDF and atomically promote it."""
        pptx_path = Path(pptx_path).resolve()
        output_dir = Path(output_dir).resolve()

        if not pptx_path.exists():
            raise FileNotFoundError(f"PowerPoint file not found: {pptx_path}")

        output_dir.mkdir(parents=True, exist_ok=True)
        final_pdf = output_dir / f"{pptx_path.stem}.pdf"
        if final_pdf.exists():
            logger.info("Removing stale PDF before conversion: %s", final_pdf)
            final_pdf.unlink()

        logger.info("Converting %s to PDF...", pptx_path.name)
        version = self._get_libreoffice_version()
        if version:
            logger.info("LibreOffice version: %s", version)

        failures = []
        for attempt in range(1, MAX_CONVERSION_ATTEMPTS + 1):
            started = time.perf_counter()
            try:
                self._convert_once(pptx_path, output_dir, final_pdf)
                duration = time.perf_counter() - started
                logger.info(
                    "LibreOffice attempt %s succeeded in %.2fs",
                    attempt,
                    duration,
                )
                logger.info("Successfully converted to: %s", final_pdf)
                return str(final_pdf)
            except FileNotFoundError as exc:
                raise RuntimeError(
                    f"LibreOffice command '{self.config.libreoffice_command}' "
                    "not found. Please install LibreOffice or configure "
                    "LIBREOFFICE_COMMAND"
                ) from exc
            except (
                subprocess.TimeoutExpired,
                subprocess.CalledProcessError,
                OSError,
                RuntimeError,
            ) as exc:
                duration = time.perf_counter() - started
                reason = self._describe_failure(exc)
                failures.append(f"attempt {attempt}: {reason}")
                logger.warning(
                    "LibreOffice attempt %s failed in %.2fs: %s",
                    attempt,
                    duration,
                    reason,
                )

        details = "; ".join(failures)
        raise RuntimeError(
            f"PDF conversion failed after {MAX_CONVERSION_ATTEMPTS} attempts: "
            f"{details}"
        )

    def _convert_once(
        self,
        pptx_path: Path,
        output_dir: Path,
        final_pdf: Path,
    ) -> None:
        """Run one isolated conversion and promote only a validated PDF."""
        attempt_prefix = f".{pptx_path.stem}_attempt_"
        with tempfile.TemporaryDirectory(
            prefix=attempt_prefix,
            dir=str(output_dir),
        ) as attempt_dir, tempfile.TemporaryDirectory(
            prefix="slide2jira_lo_profile_"
        ) as profile_dir:
            attempt_path = Path(attempt_dir)
            command = [
                self.config.libreoffice_command,
                f"-env:UserInstallation={Path(profile_dir).as_uri()}",
                "--headless",
                "--norestore",
                "--convert-to",
                "pdf",
                "--outdir",
                str(attempt_path),
                str(pptx_path),
            ]
            subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=PDF_CONVERSION_TIMEOUT,
                check=True,
            )

            candidate_pdf = attempt_path / f"{pptx_path.stem}.pdf"
            self._validate_pdf(candidate_pdf)
            candidate_pdf.replace(final_pdf)

    def _validate_pdf(self, pdf_path: Path) -> None:
        """Reject absent, empty, malformed, encrypted, or zero-page PDFs."""
        if not pdf_path.exists():
            raise RuntimeError(f"output file was not created: {pdf_path}")
        if pdf_path.stat().st_size == 0:
            raise RuntimeError(f"output file is empty: {pdf_path}")

        try:
            with fitz.open(pdf_path) as document:
                if document.needs_pass:
                    raise RuntimeError("output PDF unexpectedly requires a password")
                if document.page_count < 1:
                    raise RuntimeError("output PDF contains no pages")
                for page_index in range(document.page_count):
                    page = document.load_page(page_index)
                    page.get_displaylist()
        except Exception as exc:
            if isinstance(exc, RuntimeError) and str(exc).startswith("output PDF"):
                raise
            raise RuntimeError(f"output PDF is unreadable: {exc}") from exc

    def _get_libreoffice_version(self) -> str:
        """Return the installed LibreOffice version for diagnostics."""
        try:
            result = subprocess.run(
                [self.config.libreoffice_command, "--version"],
                capture_output=True,
                text=True,
                timeout=VERSION_CHECK_TIMEOUT,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning("Unable to read LibreOffice version: %s", exc)
            return ""

        if result.returncode != 0:
            reason = (result.stderr or result.stdout).strip()
            logger.warning(
                "Unable to read LibreOffice version: %s",
                reason or f"command exited with code {result.returncode}",
            )
            return ""

        return (result.stdout or result.stderr).strip()

    @staticmethod
    def _describe_failure(exc: Exception) -> str:
        """Produce a concise diagnostic for a failed conversion attempt."""
        if isinstance(exc, subprocess.TimeoutExpired):
            return f"timed out after {exc.timeout}s"
        if isinstance(exc, subprocess.CalledProcessError):
            stderr = (exc.stderr or "").strip()
            return stderr or f"LibreOffice exited with code {exc.returncode}"
        return str(exc)
