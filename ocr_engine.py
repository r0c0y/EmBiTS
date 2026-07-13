import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple

from PIL import Image
import pdfplumber

try:
    from liteparse import LiteParse
    HAS_LITEPARSE = True
except ImportError:
    HAS_LITEPARSE = False

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

try:
    import pypdfium2
    HAS_PYPDFIUM = True
except ImportError:
    HAS_PYPDFIUM = False

try:
    import fitz
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

from preprocess import preprocess_image


@dataclass
class OCRPageResult:
    page_num: int
    markdown: str
    text: str
    images: List[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    engine: str = ""
    blocks: List[dict] = field(default_factory=list)


@dataclass
class OCRResult:
    markdown: str
    text: str
    pages: List[OCRPageResult] = field(default_factory=list)
    engine: str = ""
    metadata: dict = field(default_factory=dict)


class OCREngine(ABC):
    name: str = "base"
    priority: int = 0
    requires_gpu: bool = False

    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def process_image(self, image: Image.Image, page_num: int = 0) -> OCRPageResult:
        pass

    @abstractmethod
    def process_pdf(self, file_path: str, page_range: Optional[List[int]] = None) -> List[OCRPageResult]:
        pass

    def process_file(self, file_path: str, ext: str) -> OCRResult:
        if ext == ".pdf":
            pages = self.process_pdf(file_path)
            return OCRResult(
                markdown="\n\n".join(p.markdown for p in pages),
                text="\n\n".join(p.text for p in pages),
                pages=pages,
                engine=self.name,
                metadata={"page_count": len(pages)}
            )
        elif ext in (".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"):
            page = self.process_image(Image.open(file_path))
            return OCRResult(
                markdown=page.markdown,
                text=page.text,
                pages=[page],
                engine=self.name,
                metadata={"page_count": 1}
            )
        return OCRResult(markdown="", text="", engine=self.name)
import re

def clean_shadow_text(text: str) -> str:
    if not text:
        return text
    def replace_word(match):
        word = match.group(0)
        if len(word) >= 4:
            word_upper = word.upper()
            runs = []
            current_char = ""
            current_len = 0
            for i, char in enumerate(word_upper):
                if char == current_char:
                    current_len += 1
                else:
                    if current_len > 0:
                        runs.append((current_char, current_len, word[i - current_len : i]))
                    current_char = char
                    current_len = 1
            if current_len > 0:
                runs.append((current_char, current_len, word[len(word) - current_len :]))
                
            duplicated_count = sum(r[1] for r in runs if r[1] >= 2)
            if duplicated_count / len(word) >= 0.75:
                new_parts = []
                for char, length, orig_substring in runs:
                    new_len = max(1, length // 2)
                    new_parts.append(orig_substring[:new_len])
                return "".join(new_parts)
        return word

    return re.sub(r'[A-Za-z]+', replace_word, text)


def is_text_garbled(text: str) -> bool:
    cleaned = text.strip()
    if not cleaned:
        return True

    if "\ufffd" in cleaned:
        return True

    words = [w for w in cleaned.split() if w.strip()]
    if not words:
        return True

    if len(cleaned) < 200:
        avg_word_len = sum(len(w) for w in words) / len(words)
        if avg_word_len < 2.0:
            return True

    lines = [line.strip() for line in cleaned.split("\n") if line.strip()]
    if not lines:
        return True

    garbled_lines = 0
    for line in lines:
        words = line.split()
        if not words:
            continue

        if len(words) >= 4:
            alpha_chars = sum(1 for c in line if c.isalpha())
            if len(line) > 0 and alpha_chars / len(line) < 0.4:
                garbled_lines += 1
                continue

        allowed_chars = sum(1 for c in line if c.isalnum() or c.isspace() or c in "|_-+=*()[]{}@!?:;\"',.$%#&/\\<>~^")
        if len(line) > 15:
            allowed_ratio = allowed_chars / len(line)
            if allowed_ratio < 0.75:
                garbled_lines += 1
                continue

    return (garbled_lines / len(lines)) > 0.2


def _sort_blocks_by_reading_order(blocks: List[dict], line_tolerance: float = 8.0) -> List[dict]:
    if not blocks:
        return blocks

    def sort_key(b: dict) -> Tuple[float, float]:
        return (round(b.get("y", 0) / line_tolerance) * line_tolerance, b.get("x", 0))

    return sorted(blocks, key=sort_key)





class PyMuPDFEngine(OCREngine):
    name = "pymupdf"
    priority = 100
    requires_gpu = False

    def __init__(self):
        self._available = HAS_PYMUPDF

    def is_available(self) -> bool:
        return self._available

    def process_image(self, image: Image.Image, page_num: int = 0) -> OCRPageResult:
        return OCRPageResult(page_num=page_num, markdown="", text="", engine=self.name)

    def process_pdf(self, file_path: str, page_range: Optional[List[int]] = None) -> List[OCRPageResult]:
        if not self._available:
            return [OCRPageResult(page_num=0, markdown="", text="", engine=self.name)]

        try:
            doc = fitz.open(file_path)
            pages = []
            page_nums = set(page_range) if page_range else set()
            
            # Parallel page processing
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            def process_page(idx):
                page = doc[idx]
                text = page.get_text()
                markdown = text
                blocks = []
                
                for block in page.get_text("dict")["blocks"]:
                    if block["type"] == 0:  # text block
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                bbox = span["bbox"]
                                blocks.append({
                                    "x": bbox[0],
                                    "y": bbox[1],
                                    "width": bbox[2] - bbox[0],
                                    "height": bbox[3] - bbox[1],
                                    "text": span["text"],
                                    "type": "text"
                                })
                
                return OCRPageResult(
                    page_num=idx + 1,
                    markdown=markdown,
                    text=text,
                    engine=self.name,
                    blocks=blocks,
                    metadata={}
                )
            
            # Process pages in parallel (up to 8 workers)
            indices = [i for i in range(len(doc)) if not page_nums or (i + 1) in page_nums]
            with ThreadPoolExecutor(max_workers=min(8, len(indices))) as executor:
                futures = {executor.submit(process_page, idx): idx for idx in indices}
                results = {}
                for future in as_completed(futures):
                    idx = futures[future]
                    try:
                        results[idx] = future.result()
                    except Exception:
                        results[idx] = OCRPageResult(page_num=idx + 1, markdown="", text="", engine=self.name)
            
            # Sort by page number
            pages = [results[idx] for idx in sorted(results.keys())]
            doc.close()
            return pages
        except Exception as e:
            return [OCRPageResult(page_num=0, markdown="", text="", engine=self.name, metadata={"error": str(e)})]


class LiteParseEngine(OCREngine):
    name = "liteparse"
    priority = 110
    requires_gpu = False

    def __init__(self):
        self._available = HAS_LITEPARSE

    def is_available(self) -> bool:
        return self._available

    def process_image(self, image: Image.Image, page_num: int = 0) -> OCRPageResult:
        return OCRPageResult(page_num=page_num, markdown="", text="", engine=self.name)

    def process_pdf(self, file_path: str, page_range: Optional[List[int]] = None) -> List[OCRPageResult]:
        if not self._available:
            return [OCRPageResult(page_num=0, markdown="", text="", engine=self.name)]

        try:
            parser = LiteParse(ocr_enabled=False)
            result = parser.parse(file_path)
            pages = []
            page_nums = set(page_range) if page_range else set()
            
            # Open PDF fitz and pdfium once to reuse across pages
            doc_fitz = None
            if HAS_PYMUPDF:
                try:
                    doc_fitz = fitz.open(file_path)
                except Exception:
                    pass

            doc_pdfium = None
            if HAS_PYPDFIUM:
                try:
                    import pypdfium2 as pdfium
                    doc_pdfium = pdfium.PdfDocument(file_path)
                except Exception:
                    pass

            rapid_engine = None
            for i, page in enumerate(result.pages):
                page_num = i + 1
                if page_nums and page_num not in page_nums:
                    continue
                text = page.text or ""
                markdown = getattr(page, "markdown", None) or text
                blocks = []
                current_engine = self.name
                text_items = getattr(page, "text_items", [])

                # Hybrid logic: If LiteParse is empty/garbled, try native PyMuPDF first
                if is_text_garbled(text) and doc_fitz is not None:
                    try:
                        fitz_page = doc_fitz[i]
                        pymupdf_text = fitz_page.get_text()
                        if pymupdf_text.strip() and not is_text_garbled(pymupdf_text):
                            text = pymupdf_text
                            markdown = pymupdf_text
                            # Extract native blocks
                            for block in fitz_page.get_text("dict")["blocks"]:
                                if block["type"] == 0:
                                    for line in block.get("lines", []):
                                        for span in line.get("spans", []):
                                            bbox = span["bbox"]
                                            blocks.append({
                                                "x": bbox[0],
                                                "y": bbox[1],
                                                "width": bbox[2] - bbox[0],
                                                "height": bbox[3] - bbox[1],
                                                "text": span["text"],
                                                "type": "text"
                                            })
                            current_engine = "pymupdf"
                    except Exception:
                        pass

                # If still empty/garbled after native check, fall back to Tesseract OCR
                if is_text_garbled(text):
                    try:
                        if doc_pdfium is not None:
                            page_obj = doc_pdfium[i]
                            # Render at 300 DPI for high quality
                            pil_img = page_obj.render(scale=300/72).to_pil().convert("RGB")

                            if rapid_engine is None:
                                rapid_engine = TesseractEngine()
                            ocr_res = rapid_engine.process_image(pil_img, page_num=page_num)
                            if ocr_res.text.strip():
                                text = ocr_res.text
                                markdown = ocr_res.markdown
                                blocks = ocr_res.blocks
                                current_engine = "tesseract"
                    except Exception:
                        text = ""
                        markdown = ""

                if not blocks and text_items:
                    for item in text_items:
                        blocks.append({
                            "text": item.text,
                            "x": item.x,
                            "y": item.y,
                            "width": item.width,
                            "height": item.height,
                            "font_name": getattr(item, "font_name", None),
                            "font_size": getattr(item, "font_size", None),
                            "confidence": getattr(item, "confidence", None),
                        })
                    blocks = _sort_blocks_by_reading_order(blocks)

                has_real_text = bool(text.strip())
                pages.append(OCRPageResult(
                    page_num=page_num,
                    markdown=markdown,
                    text=text,
                    engine=current_engine,
                    blocks=blocks,
                    metadata={"text_items": len(blocks), "fallback": current_engine != self.name, "has_real_text": has_real_text}
                ))

            # Cleanup open documents
            if doc_fitz is not None:
                try: doc_fitz.close()
                except Exception: pass
            if doc_pdfium is not None:
                try: doc_pdfium.close()
                except Exception: pass

            if not pages:
                pages = [OCRPageResult(page_num=1, markdown=result.text, text=result.text, engine=self.name)]
            return pages
        except Exception as e:
            return [OCRPageResult(page_num=0, markdown="", text="", engine=self.name, metadata={"error": str(e)})]


class TesseractEngine(OCREngine):
    name = "tesseract"
    priority = 90
    requires_gpu = False

    def __init__(self):
        self._available = HAS_TESSERACT

    def is_available(self) -> bool:
        return self._available

    def process_image(self, image: Image.Image, page_num: int = 0) -> OCRPageResult:
        if not self._available:
            return OCRPageResult(page_num=page_num, markdown="", text="", engine=self.name)

        try:
            preprocessed = preprocess_image(image)
            text = pytesseract.image_to_string(preprocessed)
            
            blocks = []
            data = pytesseract.image_to_data(preprocessed, output_type=pytesseract.Output.DICT)
            n_boxes = len(data['text'])
            for i in range(n_boxes):
                if data['text'][i].strip():
                    blocks.append({
                        "text": data['text'][i],
                        "x": data['left'][i],
                        "y": data['top'][i],
                        "width": data['width'][i],
                        "height": data['height'][i],
                        "confidence": float(data['conf'][i]) / 100.0 if data['conf'][i] > 0 else 0.0
                    })
            
            blocks = _sort_blocks_by_reading_order(blocks)

            return OCRPageResult(
                page_num=page_num,
                markdown=text,
                text=text,
                engine=self.name,
                blocks=blocks,
                metadata={}
            )
        except Exception as e:
            return OCRPageResult(page_num=page_num, markdown="", text="", engine=self.name, metadata={"error": str(e)})

    def process_pdf(self, file_path: str, page_range: Optional[List[int]] = None) -> List[OCRPageResult]:
        results = []
        try:
            doc = pypdfium2.PdfDocument(file_path)
            page_nums = set(page_range) if page_range else set()

            for idx in range(len(doc)):
                if page_nums and (idx + 1) not in page_nums:
                    continue
                pil_img = doc[idx].render(scale=300/72).to_pil().convert("RGB")
                result = self.process_image(pil_img, page_num=idx + 1)
                results.append(result)
            doc.close()
        except Exception as e:
            results.append(OCRPageResult(page_num=0, markdown="", text="", engine=self.name, metadata={"error": str(e)}))
        return results


class OCRManager:
    def __init__(self):
        self.engines: List[OCREngine] = [
            PyMuPDFEngine(),
            LiteParseEngine(),
            TesseractEngine(),
        ]
        self.engines.sort(key=lambda e: -e.priority)

    def get_best_engine(self) -> Optional[OCREngine]:
        for engine in self.engines:
            if engine.is_available():
                return engine
        return None

    def process_image(self, image: Image.Image, page_num: int = 0) -> OCRPageResult:
        best = None
        for engine in self.engines:
            if not engine.is_available():
                continue
            try:
                result = engine.process_image(image, page_num)
                text = result.text.strip()
                if text and not is_text_garbled(text):
                    # clean shadow text
                    result.text = clean_shadow_text(result.text)
                    result.markdown = clean_shadow_text(result.markdown)
                    for block in result.blocks:
                        if "text" in block and block["text"]:
                            block["text"] = clean_shadow_text(block["text"])
                    return result
                if text and best is None:
                    best = result
            except Exception:
                continue
        if best:
            best.text = clean_shadow_text(best.text)
            best.markdown = clean_shadow_text(best.markdown)
            for block in best.blocks:
                if "text" in block and block["text"]:
                    block["text"] = clean_shadow_text(block["text"])
        return best if best else OCRPageResult(page_num=page_num, markdown="", text="", engine="none")

    def get_engine_status(self) -> dict:
        return {
            "available": [e.name for e in self.engines if e.is_available()],
            "preferred": self.get_best_engine().name if self.get_best_engine() else None,
            "pymupdf": {"available": HAS_PYMUPDF},
            "liteparse": {"available": HAS_LITEPARSE},
            "tesseract": {"available": HAS_TESSERACT},
        }

    def process_with_fallback(self, file_path: str, ext: str) -> OCRResult:
        last_error = ""
        best = None
        best_not_garbled = False
        for engine in self.engines:
            if not engine.is_available():
                continue
            try:
                result = engine.process_file(file_path, ext)
                text = result.text.strip()
                not_garbled = bool(text) and not is_text_garbled(text)
                if not_garbled:
                    # Clean shadow text
                    result.text = clean_shadow_text(result.text)
                    result.markdown = clean_shadow_text(result.markdown)
                    for page in result.pages:
                        page.text = clean_shadow_text(page.text)
                        page.markdown = clean_shadow_text(page.markdown)
                        for block in page.blocks:
                            if "text" in block and block["text"]:
                                block["text"] = clean_shadow_text(block["text"])
                    return result
                if text:
                    if best is None:
                        best = result
                        best_not_garbled = False
                if not text:
                    last_error = f"{engine.name} returned empty text"
            except Exception as e:
                last_error = f"{engine.name}: {str(e)}"
                continue

        if best:
            best.text = clean_shadow_text(best.text)
            best.markdown = clean_shadow_text(best.markdown)
            for page in best.pages:
                page.text = clean_shadow_text(page.text)
                page.markdown = clean_shadow_text(page.markdown)
                for block in page.blocks:
                    if "text" in block and block["text"]:
                        block["text"] = clean_shadow_text(block["text"])
            return best
        return OCRResult(
            markdown="",
            text="",
            engine="none",
            metadata={"error": last_error or "No OCR engine available"}
        )


def get_ocr_manager() -> OCRManager:
    return OCRManager()
