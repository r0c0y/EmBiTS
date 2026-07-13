"""Image preprocessing for OCR pipeline.

Steps:
  1. Grayscale + denoise
  2. Deskew (detect text angle, rotate)
  3. Binarization (adaptive threshold)
  4. Despeckle (median blur)

Designed to be fast and dependency-light (opencv + PIL).
"""

import cv2
import numpy as np
from PIL import Image


def _to_cv2(img: Image.Image) -> np.ndarray:
    arr = np.array(img)
    if arr.ndim == 3 and arr.shape[2] == 4:
        arr = cv2.cvtColor(arr, cv2.COLOR_RGBA2RGB)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR) if arr.ndim == 3 else arr


def _to_pil(arr: np.ndarray) -> Image.Image:
    if arr.ndim == 2:
        arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2RGB)
    else:
        arr = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(arr)


def _deskew(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    coords = np.column_stack(np.where(binary == 0))
    if coords.size == 0:
        return image
    angle = cv2.minAreaRect(coords)[-1]
    if angle > 45:
        angle = 90 - angle
    if angle < -45:
        angle = 90 + angle
    if abs(angle) < 0.5:
        return image
    (h, w) = image.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def preprocess_image(img: Image.Image) -> Image.Image:
    """Run professional preprocessing on a PIL Image for maximum Tesseract OCR accuracy.

    Steps:
      1. Correctly blend transparency/alpha channel with a white background.
      2. Convert to grayscale.
      3. Deskew the text layout.
      4. De-noise using bilateral filtering (preserves text edges).
      5. Adaptive thresholding with optimal block size to handle uneven illumination.
      6. Despeckle using a median blur.
    """
    # 1. Correctly handle transparency / alpha channel
    if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
        background = Image.new("RGBA", img.size, (255, 255, 255, 255))
        background.paste(img)
        img = background.convert("RGB")
    else:
        img = img.convert("RGB")
        
    # 2. Convert to OpenCV
    arr = np.array(img)
    cv_img = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    
    # 3. Grayscale
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    
    # 4. Deskew
    gray = _deskew(gray)
    
    # 5. Denoise with Bilateral Filter (preserves text edges better than fastNlMeans)
    denoised = cv2.bilateralFilter(gray, 9, 75, 75)
    
    # 6. Adaptive Thresholding with a larger window size (25) to prevent thin character erosion
    bin_img = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 25, 9
    )
    
    # 7. Despeckle with median blur
    clean = cv2.medianBlur(bin_img, 3)
    
    return Image.fromarray(clean)
