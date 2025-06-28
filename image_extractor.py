"""Image extraction functionality."""

import io
import logging
from pathlib import Path
from typing import Dict, List, Optional

import fitz  # PyMuPDF
from PIL import Image

from config import ProcessingConfig, DEFAULT_IMAGE_SCALE, DEFAULT_JPEG_QUALITY, MIN_JPEG_QUALITY

logger = logging.getLogger(__name__)


class ImageExtractor:
    """Handles extraction of slide images from PDF."""
    
    def __init__(self, config: ProcessingConfig):
        self.config = config
    
    def extract_slide_images(self, pdf_path: str, slide_numbers: List[int], output_dir: str) -> Dict[int, str]:
        """Extract specific slides from PDF as optimized JPEG images."""
        slide_images = {}
        
        try:
            doc = fitz.open(pdf_path)
            logger.info(f"PDF has {len(doc)} pages")
            
            for slide_num in slide_numbers:
                page_index = slide_num - 1
                
                if page_index >= len(doc):
                    logger.warning(f"Slide {slide_num} not found in PDF (only {len(doc)} pages)")
                    continue
                
                img_path = self._extract_single_slide(doc, slide_num, page_index, output_dir)
                if img_path:
                    slide_images[slide_num] = img_path
            
            doc.close()
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