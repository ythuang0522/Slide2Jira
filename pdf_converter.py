"""PDF conversion functionality."""

import subprocess
import logging
from pathlib import Path

from config import ProcessingConfig, PDF_CONVERSION_TIMEOUT

logger = logging.getLogger(__name__)


class PDFConverter:
    """Handles PowerPoint to PDF conversion."""
    
    def __init__(self, config: ProcessingConfig):
        self.config = config
    
    def convert_to_pdf(self, pptx_path: str, output_dir: str) -> str:
        """Convert PowerPoint to PDF using LibreOffice headless mode."""
        pptx_path = Path(pptx_path).resolve()
        output_dir = Path(output_dir).resolve()
        
        if not pptx_path.exists():
            raise FileNotFoundError(f"PowerPoint file not found: {pptx_path}")
        
        logger.info(f"Converting {pptx_path.name} to PDF...")
        
        cmd = [
            self.config.libreoffice_command,
            "--headless",
            "--convert-to", "pdf",
            "--outdir", str(output_dir),
            str(pptx_path)
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=PDF_CONVERSION_TIMEOUT,
                check=True
            )
            
            pdf_name = pptx_path.stem + ".pdf"
            pdf_path = output_dir / pdf_name
            
            if not pdf_path.exists():
                raise RuntimeError(f"PDF conversion failed - output file not found: {pdf_path}")
            
            logger.info(f"Successfully converted to: {pdf_path}")
            return str(pdf_path)
            
        except subprocess.TimeoutExpired:
            raise RuntimeError("LibreOffice conversion timed out")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"LibreOffice conversion failed: {e.stderr}")
        except FileNotFoundError:
            raise RuntimeError(
                f"LibreOffice command '{self.config.libreoffice_command}' not found. "
                "Please install LibreOffice or configure LIBREOFFICE_COMMAND"
            ) 