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
    """Run full preprocessing pipeline on a PIL Image and return a PIL Image."""
    # 1. to OpenCV
    cv = _to_cv2(img)
    # 2. Grayscale + denoise
    gray = cv2.cvtColor(cv, cv2.COLOR_BGR2GRAY) if cv.ndim == 3 else cv
    denoised = cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)
    # 3. Deskew
    denoised = cv2.cvtColor(denoised, cv2.COLOR_GRAY2BGR)
    deskewed = _deskew(denoised)
    gray2 = cv2.cvtColor(deskewed, cv2.COLOR_BGR2GRAY)
    # 4. Binarization (adaptive)
    bin_img = cv2.adaptiveThreshold(
        gray2, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 3
    )
    # 5. Despeckle (median blur)
    clean = cv2.medianBlur(bin_img, 3)
    return _to_pil(clean)
