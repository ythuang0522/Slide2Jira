"""Image extraction functionality."""

import io
import logging
from pathlib import Path
from typing import Dict, Optional

import fitz  # PyMuPDF
from PIL import Image

from config import ProcessingConfig, DEFAULT_IMAGE_SCALE, DEFAULT_JPEG_QUALITY, MIN_JPEG_QUALITY

logger = logging.getLogger(__name__)


class ImageExtractor:
    """Handles extraction of slide images from PDF."""
    
    def __init__(self, config: ProcessingConfig):
        self.config = config
    
    def extract_slide_images(self, pdf_path: str, slide_page_mapping: Dict[int, int], output_dir: str) -> Dict[int, str]:
        """Extract slide images using an explicit PPTX slide to PDF page mapping."""
        slide_images = {}
        
        try:
            with fitz.open(pdf_path) as doc:
                page_count = len(doc)
                logger.info(f"PDF has {page_count} pages")

                invalid_mappings = [
                    (slide_num, pdf_page_num)
                    for slide_num, pdf_page_num in sorted(slide_page_mapping.items())
                    if pdf_page_num < 1 or pdf_page_num > page_count
                ]
                if invalid_mappings:
                    details = "; ".join(
                        f"PPTX slide {slide_num} expects PDF page {pdf_page_num}, "
                        f"but PDF only has {page_count} page(s)"
                        for slide_num, pdf_page_num in invalid_mappings
                    )
                    raise ValueError(f"Invalid PDF page mapping: {details}")

                for slide_num, pdf_page_num in sorted(slide_page_mapping.items()):
                    page_index = pdf_page_num - 1
                    img_path = self._extract_single_slide(
                        doc, slide_num, page_index, output_dir
                    )
                    if not img_path:
                        raise RuntimeError(
                            f"Failed to extract PPTX slide {slide_num} "
                            f"from PDF page {pdf_page_num}"
                        )
                    slide_images[slide_num] = img_path

            return slide_images
            
        except Exception as e:
            logger.error(f"Error extracting slide images: {e}")
            raise
    
    def _extract_single_slide(self, doc, slide_num: int, page_index: int, output_dir: str) -> Optional[str]:
        """Extract a single slide as an optimized JPEG."""
        try:
            page = doc.load_page(page_index)
            mat = fitz.Matrix(DEFAULT_IMAGE_SCALE, DEFAULT_IMAGE_SCALE)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            img_filename = f"slide_{slide_num}.jpg"
            img_path = Path(output_dir) / img_filename
            
            img_data = pix.tobytes("ppm")
            with Image.open(io.BytesIO(img_data)) as pil_img:
                quality = self._optimize_image_quality(pil_img, img_path)
                
                file_size_mb = img_path.stat().st_size / (1024 * 1024)
                logger.info(f"Extracted slide {slide_num} as JPEG ({file_size_mb:.1f}MB, quality={quality})")
            
            return str(img_path)
            
        except Exception as e:
            logger.error(f"Error extracting slide {slide_num}: {e}")
            return None
    
    def _optimize_image_quality(self, pil_img: Image.Image, img_path: Path) -> int:
        """Optimize JPEG quality to meet size constraints."""
        quality = DEFAULT_JPEG_QUALITY
        
        while quality >= MIN_JPEG_QUALITY:
            pil_img.save(img_path, "JPEG", quality=quality, optimize=True)
            
            file_size_mb = img_path.stat().st_size / (1024 * 1024)
            if file_size_mb <= self.config.max_image_size_mb:
                break
            quality -= 10
        
        return quality 
