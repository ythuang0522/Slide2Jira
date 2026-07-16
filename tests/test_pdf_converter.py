"""Regression tests for resilient LibreOffice PDF conversion."""

import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import fitz

from pdf_converter import PDFConverter


class PDFConverterTests(unittest.TestCase):
    """Verify conversion isolation, retry, validation, and promotion."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.presentation = self.temp_path / "deck.pptx"
        self.presentation.write_bytes(b"placeholder")
        self.output_dir = self.temp_path / "output"
        self.output_dir.mkdir()
        self.final_pdf = self.output_dir / "deck.pdf"
        self.converter = PDFConverter(
            SimpleNamespace(libreoffice_command="soffice")
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def _write_valid_pdf(path: Path, page_count: int = 1):
        path.parent.mkdir(parents=True, exist_ok=True)
        with fitz.open() as document:
            for _ in range(page_count):
                document.new_page()
            document.save(path)

    def _run_stub(self, convert_callback):
        def run(command, **_kwargs):
            if "--version" in command:
                return subprocess.CompletedProcess(
                    command, 0, "LibreOffice 26.2.0.1\n", ""
                )
            return convert_callback(command)

        return run

    @staticmethod
    def _conversion_output_dir(command):
        return Path(command[command.index("--outdir") + 1])

    def test_conversion_uses_isolated_profile_and_attempt_directory(self):
        """Desktop profile and final output directory must not be used directly."""
        commands = []

        def convert(command):
            commands.append(command)
            attempt_dir = self._conversion_output_dir(command)
            self._write_valid_pdf(attempt_dir / "deck.pdf")
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch(
            "pdf_converter.subprocess.run",
            side_effect=self._run_stub(convert),
        ):
            result = self.converter.convert_to_pdf(
                str(self.presentation), str(self.output_dir)
            )

        self.assertEqual(result, str(self.final_pdf.resolve()))
        self.assertEqual(len(commands), 1)
        self.assertTrue(
            any(
                part.startswith("-env:UserInstallation=file:")
                for part in commands[0]
            )
        )
        self.assertNotEqual(
            self._conversion_output_dir(commands[0]).resolve(),
            self.output_dir.resolve(),
        )

    def test_stale_final_pdf_is_removed_before_conversion(self):
        """A prior PDF must never satisfy validation for a failed new attempt."""
        self.final_pdf.write_bytes(b"stale")

        def convert(command):
            self.assertFalse(self.final_pdf.exists())
            attempt_dir = self._conversion_output_dir(command)
            self._write_valid_pdf(attempt_dir / "deck.pdf")
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch(
            "pdf_converter.subprocess.run",
            side_effect=self._run_stub(convert),
        ):
            self.converter.convert_to_pdf(
                str(self.presentation), str(self.output_dir)
            )

        with fitz.open(self.final_pdf) as document:
            self.assertEqual(len(document), 1)

    def test_invalid_first_pdf_retries_with_fresh_profile_and_output(self):
        """A malformed result should trigger one fully isolated retry."""
        commands = []

        def convert(command):
            commands.append(command)
            candidate = self._conversion_output_dir(command) / "deck.pdf"
            if len(commands) == 1:
                candidate.write_bytes(b"not a PDF")
            else:
                self._write_valid_pdf(candidate, page_count=2)
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch(
            "pdf_converter.subprocess.run",
            side_effect=self._run_stub(convert),
        ):
            self.converter.convert_to_pdf(
                str(self.presentation), str(self.output_dir)
            )

        self.assertEqual(len(commands), 2)
        profiles = [
            next(
                part
                for part in command
                if part.startswith("-env:UserInstallation=file:")
            )
            for command in commands
        ]
        attempt_dirs = [self._conversion_output_dir(command) for command in commands]
        self.assertEqual(len(set(profiles)), 2)
        self.assertEqual(len(set(attempt_dirs)), 2)
        with fitz.open(self.final_pdf) as document:
            self.assertEqual(len(document), 2)

    def test_two_malformed_results_raise_and_leave_no_final_pdf(self):
        """No output is promoted after both validated attempts fail."""
        attempts = 0

        def convert(command):
            nonlocal attempts
            attempts += 1
            candidate = self._conversion_output_dir(command) / "deck.pdf"
            candidate.write_bytes(b"not a PDF")
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch(
            "pdf_converter.subprocess.run",
            side_effect=self._run_stub(convert),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "failed after 2 attempts"
            ):
                self.converter.convert_to_pdf(
                    str(self.presentation), str(self.output_dir)
                )

        self.assertEqual(attempts, 2)
        self.assertFalse(self.final_pdf.exists())

    def test_timeout_retries_and_cleans_attempt_directories(self):
        """A timeout should retry cleanly without leaving attempt artifacts."""
        attempt_dirs = []

        def convert(command):
            attempt_dir = self._conversion_output_dir(command)
            attempt_dirs.append(attempt_dir)
            if len(attempt_dirs) == 1:
                raise subprocess.TimeoutExpired(command, 120)
            self._write_valid_pdf(attempt_dir / "deck.pdf")
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch(
            "pdf_converter.subprocess.run",
            side_effect=self._run_stub(convert),
        ):
            self.converter.convert_to_pdf(
                str(self.presentation), str(self.output_dir)
            )

        self.assertEqual(len(attempt_dirs), 2)
        self.assertTrue(self.final_pdf.exists())
        self.assertTrue(all(not path.exists() for path in attempt_dirs))

    def test_missing_outputs_are_retried_but_never_promoted(self):
        """Successful process exits without a PDF must still fail validation."""
        attempts = 0

        def convert(command):
            nonlocal attempts
            attempts += 1
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch(
            "pdf_converter.subprocess.run",
            side_effect=self._run_stub(convert),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "output file was not created"
            ):
                self.converter.convert_to_pdf(
                    str(self.presentation), str(self.output_dir)
                )

        self.assertEqual(attempts, 2)
        self.assertFalse(self.final_pdf.exists())

    def test_empty_outputs_are_retried_but_never_promoted(self):
        """Zero-byte PDFs must not survive either conversion attempt."""
        attempts = 0

        def convert(command):
            nonlocal attempts
            attempts += 1
            candidate = self._conversion_output_dir(command) / "deck.pdf"
            candidate.write_bytes(b"")
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch(
            "pdf_converter.subprocess.run",
            side_effect=self._run_stub(convert),
        ):
            with self.assertRaisesRegex(RuntimeError, "output file is empty"):
                self.converter.convert_to_pdf(
                    str(self.presentation), str(self.output_dir)
                )

        self.assertEqual(attempts, 2)
        self.assertFalse(self.final_pdf.exists())

    def test_logs_libreoffice_version_and_success_duration(self):
        """Conversion diagnostics should identify the renderer and attempt time."""
        def convert(command):
            candidate = self._conversion_output_dir(command) / "deck.pdf"
            self._write_valid_pdf(candidate)
            return subprocess.CompletedProcess(command, 0, "", "")

        with self.assertLogs("pdf_converter", level="INFO") as logs:
            with patch(
                "pdf_converter.subprocess.run",
                side_effect=self._run_stub(convert),
            ):
                self.converter.convert_to_pdf(
                    str(self.presentation), str(self.output_dir)
                )

        output = "\n".join(logs.output)
        self.assertIn("LibreOffice version: LibreOffice 26.2.0.1", output)
        self.assertRegex(output, r"attempt 1 succeeded in \d+\.\d{2}s")

    def test_validation_parses_every_pdf_page(self):
        """Damage after the first page must be detected before promotion."""
        document = MagicMock()
        document.__enter__.return_value = document
        document.__exit__.return_value = False
        document.needs_pass = False
        document.page_count = 3
        pages = [MagicMock(), MagicMock(), MagicMock()]
        document.load_page.side_effect = pages
        candidate = self.temp_path / "candidate.pdf"
        candidate.write_bytes(b"%PDF-placeholder")

        with patch("pdf_converter.fitz.open", return_value=document):
            self.converter._validate_pdf(candidate)

        self.assertEqual(document.load_page.call_args_list, [call(0), call(1), call(2)])
        for page in pages:
            page.get_displaylist.assert_called_once_with()

    def test_nonzero_version_command_is_not_reported_as_a_version(self):
        """An error response from --version must be logged as unavailable."""
        def run(command, **_kwargs):
            return subprocess.CompletedProcess(
                command, 1, "", "LibreOffice startup failed"
            )

        with self.assertLogs("pdf_converter", level="WARNING") as logs:
            with patch("pdf_converter.subprocess.run", side_effect=run):
                version = self.converter._get_libreoffice_version()

        output = "\n".join(logs.output)
        self.assertEqual(version, "")
        self.assertIn("Unable to read LibreOffice version", output)
