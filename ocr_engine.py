import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

from PIL import Image
import pdfplumber

try:
    from liteparse import LiteParse
    HAS_LITEPARSE = True
except ImportError:
    HAS_LITEPARSE = False

try:
    from rapidocr import RapidOCR
    HAS_RAPIDOCR = True
except ImportError:
    HAS_RAPIDOCR = False

try:
    import pypdfium2
    HAS_PYPDFIUM = True
except ImportError:
    HAS_PYPDFIUM = False

try:
    from llama_cpp import Llama
    HAS_LLAMACPP = True
except ImportError:
    HAS_LLAMACPP = False

try:
    from surya.recognition import RecognitionPredictor
    from surya.inference import SuryaInferenceManager
    HAS_SURYA = True
except ImportError:
    HAS_SURYA = False

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


class LiteParseEngine(OCREngine):
    name = "liteparse"
    priority = 95
    requires_gpu = False

    def __init__(self):
        self._available = HAS_LITEPARSE

    def is_available(self) -> bool:
        return self._available

    def process_image(self, image: Image.Image, page_num: int = 0) -> OCRPageResult:
        # LiteParse is PDF-native; fallback to empty to trigger RapidOCR for images
        return OCRPageResult(page_num=page_num, markdown="", text="", engine=self.name)

    def process_pdf(self, file_path: str, page_range: Optional[List[int]] = None) -> List[OCRPageResult]:
        if not self._available:
            return [OCRPageResult(page_num=0, markdown="", text="", engine=self.name)]

        try:
            parser = LiteParse()
            result = parser.parse(file_path)
            pages = []
            page_nums = set(page_range) if page_range else set()
            for i, page in enumerate(result.pages):
                page_num = i + 1
                if page_nums and page_num not in page_nums:
                    continue
                text = page.text or ""
                markdown = getattr(page, "markdown", None) or text
                blocks = []
                current_engine = self.name
                
                # ponytail: simple heuristic length check (< 50) for scanned pages. Upgrade path: use layout complexity analysis.
                if len(text.strip()) < 50:
                    try:
                        import pypdfium2 as pdfium
                        doc = pdfium.PdfDocument(file_path)
                        page_obj = doc[i]
                        pil_img = page_obj.render(scale=192/72).to_pil().convert("RGB")
                        doc.close()
                        
                        rapid = RapidOCREngine()
                        ocr_res = rapid.process_image(pil_img, page_num=page_num)
                        if ocr_res.text.strip():
                            text = ocr_res.text
                            markdown = ocr_res.markdown
                            blocks = ocr_res.blocks
                            current_engine = "rapidocr"
                    except Exception:
                        pass
                        
                if not blocks:
                    for item in getattr(page, "text_items", []):
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
                pages.append(OCRPageResult(
                    page_num=page_num,
                    markdown=markdown,
                    text=text,
                    engine=current_engine,
                    blocks=blocks,
                    metadata={"text_items": len(blocks), "fallback": current_engine != self.name}
                ))
            if not pages:
                pages = [OCRPageResult(page_num=1, markdown=result.text, text=result.text, engine=self.name)]
            return pages
        except Exception as e:
            return [OCRPageResult(page_num=0, markdown="", text="", engine=self.name, metadata={"error": str(e)})]


class RapidOCREngine(OCREngine):
    name = "rapidocr"
    priority = 90
    requires_gpu = False

    def __init__(self):
        self._backend = None
        self._available = HAS_RAPIDOCR

    def is_available(self) -> bool:
        return self._available

    def _get_backend(self):
        if self._backend is None and self._available:
            try:
                self._backend = RapidOCR()
            except Exception:
                self._available = False
        return self._backend

    def process_image(self, image: Image.Image, page_num: int = 0) -> OCRPageResult:
        backend = self._get_backend()
        if not backend:
            return OCRPageResult(page_num=page_num, markdown="", text="", engine=self.name)

        try:
            preprocessed = preprocess_image(image)
            result = backend(preprocessed)
            texts = result.txts if result else []
            scores = result.scores if result else []
            text = "\n".join(texts) if texts else ""
            md = result.to_markdown() if hasattr(result, "to_markdown") else text

            blocks = []
            if hasattr(result, "boxes") and result.boxes is not None:
                try:
                    import numpy as np
                    boxes = result.boxes
                    for idx, box in enumerate(boxes):
                        blocks.append({
                            "text": texts[idx] if idx < len(texts) else "",
                            "bbox": box.tolist() if hasattr(box, "tolist") else list(box),
                            "confidence": float(scores[idx]) if idx < len(scores) else 0.0,
                        })
                except Exception:
                    pass

            return OCRPageResult(
                page_num=page_num,
                markdown=md,
                text=text,
                engine=self.name,
                blocks=blocks,
                metadata={"confidence": float(sum(scores)) / len(scores) if scores else 0.0}
            )
        except Exception as e:
            return OCRPageResult(page_num=page_num, markdown="", text="", engine=self.name, metadata={"error": str(e)})

    def process_pdf(self, file_path: str, page_range: Optional[List[int]] = None) -> List[OCRPageResult]:
        import pypdfium2 as pdfium
        results = []
        try:
            doc = pdfium.PdfDocument(file_path)
            page_nums = set(page_range) if page_range else set()
            backend = self._get_backend()
            if not backend:
                doc.close()
                return [OCRPageResult(page_num=0, markdown="", text="", engine=self.name)]

            for idx in range(len(doc)):
                if page_nums and (idx + 1) not in page_nums:
                    continue
                page_obj = doc[idx]
                pil_img = page_obj.render(scale=192/72).to_pil().convert("RGB")
                result = self.process_image(pil_img, page_num=idx + 1)
                results.append(result)
            doc.close()
        except Exception as e:
            results.append(OCRPageResult(page_num=0, markdown="", text="", engine=self.name, metadata={"error": str(e)}))
        return results


class SuryaEngine(OCREngine):
    name = "surya"
    priority = 90
    requires_gpu = False

    def __init__(self):
        self._available = HAS_SURYA
        self.rec_predictor = None

    def is_available(self) -> bool:
        return self._available

    def _lazy_init(self):
        if self.rec_predictor is None:
            import torch
            device = "cpu"
            if torch.cuda.is_available():
                device = "cuda"
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                device = "mps"
            
            os.environ["TORCH_DEVICE"] = device
            manager = SuryaInferenceManager()
            self.rec_predictor = RecognitionPredictor(manager)

    def process_image(self, image: Image.Image, page_num: int = 0) -> OCRPageResult:
        try:
            self._lazy_init()
            page_results = self.rec_predictor([image], full_page=True)
            if not page_results:
                return OCRPageResult(page_num=page_num, markdown="", text="", engine=self.name)
            
            page = page_results[0]
            lines_text = []
            blocks = []
            
            import re
            for b in page.blocks:
                clean_text = re.sub(r'<[^>]*>', '', b.html).strip() if b.html else ""
                if not clean_text:
                    continue
                lines_text.append(clean_text)
                
                blocks.append({
                    "text": clean_text,
                    "bbox": b.bbox,
                    "confidence": float(b.confidence) if b.confidence is not None else 1.0,
                    "label": b.label,
                    "reading_order": b.reading_order
                })
            
            full_text = "\n".join(lines_text)
            blocks.sort(key=lambda x: x["reading_order"])
            md_lines = []
            for b in blocks:
                lbl = b["label"].lower()
                txt = b["text"]
                if "header" in lbl or "title" in lbl:
                    md_lines.append(f"## {txt}")
                elif "list" in lbl:
                    md_lines.append(f"- {txt}")
                elif "table" in lbl:
                    md_lines.append(f"\n[Table Block]\n{txt}\n")
                else:
                    md_lines.append(txt)
            
            markdown = "\n\n".join(md_lines)
            
            return OCRPageResult(
                page_num=page_num,
                markdown=markdown,
                text=full_text,
                engine=self.name,
                blocks=blocks,
                metadata={"confidence": float(sum(b["confidence"] for b in blocks)) / len(blocks) if blocks else 1.0}
            )
        except Exception as e:
            return OCRPageResult(page_num=page_num, markdown="", text="", engine=self.name, metadata={"error": str(e)})

    def process_pdf(self, file_path: str, page_range: Optional[List[int]] = None) -> List[OCRPageResult]:
        results = []
        if not HAS_PYPDFIUM:
            return results
        import pypdfium2 as pdfium
        try:
            doc = pdfium.PdfDocument(file_path)
            page_nums = set(page_range) if page_range else set(range(1, len(doc) + 1))
            for i in sorted(list(page_nums)):
                try:
                    page_obj = doc[i - 1]
                    pil_img = page_obj.render(scale=150/72).to_pil().convert("RGB")
                    res = self.process_image(pil_img, page_num=i)
                    results.append(res)
                except Exception as e:
                    results.append(OCRPageResult(page_num=i, markdown="", text="", engine=self.name, metadata={"error": str(e)}))
            doc.close()
        except Exception as e:
            results.append(OCRPageResult(page_num=0, markdown="", text="", engine=self.name, metadata={"error": str(e)}))
        return results


class OCRManager:
    def __init__(self):
        self.engines: List[OCREngine] = [
            LiteParseEngine(),
            SuryaEngine(),
            RapidOCREngine(),
        ]
        self.engines.sort(key=lambda e: -e.priority)

    def get_best_engine(self) -> Optional[OCREngine]:
        for engine in self.engines:
            if engine.is_available():
                return engine
        return None

    def get_engine_status(self) -> dict:
        return {
            "available": [e.name for e in self.engines if e.is_available()],
            "preferred": self.get_best_engine().name if self.get_best_engine() else None,
            "rapidocr": {"available": HAS_RAPIDOCR},
            "liteparse": {"available": HAS_LITEPARSE},
        }

    def process_with_fallback(self, file_path: str, ext: str) -> OCRResult:
        last_error = None
        for engine in self.engines:
            if not engine.is_available():
                continue
            try:
                result = engine.process_file(file_path, ext)
                if result.text.strip():
                    return result
                last_error = f"{engine.name} returned empty text"
            except Exception as e:
                last_error = f"{engine.name}: {str(e)}"
                continue

        return OCRResult(
            markdown="",
            text="",
            engine="none",
            metadata={"error": last_error or "No OCR engine available"}
        )


def get_ocr_manager() -> OCRManager:
    return OCRManager()
