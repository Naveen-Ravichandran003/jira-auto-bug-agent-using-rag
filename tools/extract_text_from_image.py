import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from loguru import logger

try:
    import pytesseract
    from PIL import Image, ImageEnhance, ImageFilter
    import cv2
    import numpy as np

    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logger.warning("Core OCR dependencies not installed (pytesseract, Pillow, opencv-python)")

# EasyOCR fallback
try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False
    logger.debug("EasyOCR not installed — fallback unavailable")

from src.config import settings

# Global easyocr reader to avoid reloading models on every call
_easy_reader = None

def _get_easy_reader():
    global _easy_reader
    if _easy_reader is None and EASYOCR_AVAILABLE:
        logger.info("Initializing EasyOCR reader (this may take a moment to load models)...")
        # Initialize reader for English
        _easy_reader = easyocr.Reader(['en'], gpu=False) # Keep it on CPU to avoid CUDA dependency issues
    return _easy_reader


def _configure_tesseract():
    """Set Tesseract executable path from config."""
    if os.path.exists(settings.tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_path
        logger.debug(f"Tesseract configured at: {settings.tesseract_path}")
        return True
    else:
        logger.warning(
            f"Tesseract not found at {settings.tesseract_path}. "
            "Ensure Tesseract is installed and path is correct."
        )
        return False


def _preprocess_image(image_path: str) -> "np.ndarray":
    """
    Preprocessing pipeline for OCR accuracy:
    1. Load image
    2. Convert to grayscale
    3. Resize to ensure DPI ≥ 300
    4. Apply adaptive thresholding
    5. Noise removal
    6. Return processed image
    """
    # Load with OpenCV
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Cannot read image: {image_path}")

    logger.debug(f"Original image size: {img.shape}")

    # Step 1: Grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Step 2: Resize if too small (ensure ~300 DPI equivalent)
    height, width = gray.shape
    if width < 1000 or height < 1000:
        scale_factor = max(1000 / width, 1000 / height, 1.5)
        gray = cv2.resize(
            gray, None, fx=scale_factor, fy=scale_factor,
            interpolation=cv2.INTER_CUBIC
        )
        logger.debug(f"Resized image to: {gray.shape}")

    # Step 3: Adaptive thresholding for text separation
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2
    )

    # Step 4: Noise removal
    denoised = cv2.medianBlur(thresh, 3)

    return denoised


def extract_text(image_path: str, lang: str = "eng") -> dict:
    """
    Extract text from an image using Tesseract OCR or EasyOCR fallback.

    Args:
        image_path: Path to the image file
        lang: Tesseract language code (default: eng)

    Returns:
        dict with 'success', 'text', and 'confidence' keys
    """
    if not OCR_AVAILABLE and not EASYOCR_AVAILABLE:
        return {
            "success": False,
            "text": "",
            "error": "OCR dependencies not installed. Ensure Tesseract is installed or try running: pip install easyocr",
        }

    if not os.path.exists(image_path):
        return {"success": False, "text": "", "error": f"File not found: {image_path}"}

    # Attempt Tesseract first if available
    if OCR_AVAILABLE:
        tesseract_configured = _configure_tesseract()
        if tesseract_configured:
            try:
                logger.info(f"Extracting text (Tesseract) from: {os.path.basename(image_path)}")
                processed_img = _preprocess_image(image_path)
                custom_config = f"--oem 3 --psm 6 -l {lang}"
                text = pytesseract.image_to_string(processed_img, config=custom_config)
                detail_data = pytesseract.image_to_data(
                    processed_img, config=custom_config, output_type=pytesseract.Output.DICT
                )
                confidences = [
                    int(c) for c in detail_data.get("conf", [])
                    if str(c).lstrip('-').isdigit() and int(c) > 0
                ]
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
                cleaned_text = text.strip()
                if cleaned_text:
                    logger.info(f"OCR (Tesseract) complete — {len(cleaned_text)} chars")
                    return {
                        "success": True,
                        "text": cleaned_text,
                        "confidence": round(avg_confidence / 100.0, 3),
                        "char_count": len(cleaned_text),
                        "engine": "tesseract"
                    }
            except Exception as e:
                logger.warning(f"Tesseract OCR failed, attempting fallback: {str(e)}")

    # Fallback to EasyOCR
    if EASYOCR_AVAILABLE:
        try:
            logger.info(f"Extracting text (EasyOCR) from: {os.path.basename(image_path)}")
            reader = _get_easy_reader()
            if reader:
                # Get result with paragraph=True for easier text joining
                results = reader.readtext(image_path, paragraph=True)
                # results is a list of [bbox, text] if paragraph=True
                text_parts = [res[1] for res in results]
                text = " ".join(text_parts).strip()
                
                # Confidence is harder to average here without more detail, 
                # but readtext returns confidence if paragraph=False
                # For now, let's provide a default or do a more detailed read
                
                if text:
                    logger.info(f"OCR (EasyOCR) complete — {len(text)} chars")
                    return {
                        "success": True,
                        "text": text,
                        "confidence": 0.8,  # Default for easyocr successful read
                        "char_count": len(text),
                        "engine": "easyocr"
                    }
                else:
                    logger.warning("EasyOCR extracted no text")
        except Exception as e:
            logger.error(f"Fallback EasyOCR extraction failed: {str(e)}")
            return {"success": False, "text": "", "error": f"OCR failed on all engines: {str(e)}"}

    return {
        "success": False,
        "text": "",
        "error": "OCR failed. Tesseract is missing and EasyOCR could not be initialized."
    }


def extract_text_simple(image_path: str) -> str:
    """
    Simplified text extraction — returns just the text string.
    For use in the RAG pipeline.
    """
    result = extract_text(image_path)
    return result.get("text", "")
