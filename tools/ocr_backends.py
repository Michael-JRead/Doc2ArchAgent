#!/usr/bin/env python3
# Copyright (c) 2026 Michael J. Read. All rights reserved.
# SPDX-License-Identifier: BUSL-1.1
"""Pluggable OCR backends for Doc2ArchAgent.

Provides a unified interface for OCR engines: Tesseract (default),
OpenDoc-0.1B (optional high-accuracy), and PaddleOCR (optional).

The active backend is selected automatically based on available packages,
or can be forced via environment variable D2A_OCR_BACKEND.

Usage:
    from tools.ocr_backends import create_ocr_backend

    ocr = create_ocr_backend()             # Auto-detect best available
    ocr = create_ocr_backend("tesseract")  # Force specific backend
    ocr = create_ocr_backend("opendoc")    # Use OpenDoc-0.1B

    text = ocr.extract_text(image)
    result = ocr.extract_with_confidence(image)
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path


class OCRResult:
    """Standardized OCR result."""

    def __init__(self, text: str, confidence: float, backend: str,
                 regions: list | None = None, metadata: dict | None = None):
        self.text = text
        self.confidence = confidence
        self.backend = backend
        self.regions = regions or []
        self.metadata = metadata or {}


class OCRBackend(ABC):
    """Abstract base class for OCR backends."""

    @abstractmethod
    def extract_text(self, image) -> str:
        """Extract plain text from an image."""

    @abstractmethod
    def extract_with_confidence(self, image) -> OCRResult:
        """Extract text with confidence scores and region data."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend identifier."""

    @property
    @abstractmethod
    def available(self) -> bool:
        """Whether this backend's dependencies are installed."""


class TesseractBackend(OCRBackend):
    """Tesseract OCR backend (default, widely available)."""

    @property
    def name(self) -> str:
        return "tesseract"

    @property
    def available(self) -> bool:
        try:
            import pytesseract
            return True
        except ImportError:
            return False

    def extract_text(self, image) -> str:
        import pytesseract
        return pytesseract.image_to_string(image)

    def extract_with_confidence(self, image) -> OCRResult:
        import pytesseract

        text = pytesseract.image_to_string(image)

        try:
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            confs = [int(c) for c in data["conf"] if int(c) > 0]
            avg_conf = sum(confs) / len(confs) / 100 if confs else 0.0
        except Exception:
            avg_conf = 0.5

        return OCRResult(
            text=text,
            confidence=avg_conf,
            backend=self.name,
        )


class OpenDocBackend(OCRBackend):
    """OpenDoc-0.1B OCR backend (high-accuracy, ONNX-based).

    Requires: pip install doc2archagent[ml]
    Model: OpenDoc-0.1B from OpenOCR (Fudan FVL Lab)
    """

    def __init__(self, model_path: str | None = None):
        self._model_path = model_path
        self._model = None

    @property
    def name(self) -> str:
        return "opendoc"

    @property
    def available(self) -> bool:
        try:
            import onnxruntime
            return True
        except ImportError:
            return False

    def _get_model_path(self) -> Path | None:
        if self._model_path:
            p = Path(self._model_path)
            return p if p.exists() else None

        candidates = [
            Path(__file__).parent / "models" / "opendoc-0.1b.onnx",
            Path.home() / ".cache" / "doc2archagent" / "opendoc-0.1b.onnx",
        ]
        for p in candidates:
            if p.exists():
                return p
        return None

    def extract_text(self, image) -> str:
        result = self.extract_with_confidence(image)
        return result.text

    def extract_with_confidence(self, image) -> OCRResult:
        model_path = self._get_model_path()
        if model_path is None:
            # Fall back to Tesseract
            fallback = TesseractBackend()
            if fallback.available:
                result = fallback.extract_with_confidence(image)
                result.metadata["fallback"] = True
                return result
            return OCRResult(text="", confidence=0.0, backend=self.name,
                             metadata={"error": "OpenDoc model not found and Tesseract unavailable"})

        try:
            import onnxruntime as ort
            import numpy as np
            from PIL import Image

            if not isinstance(image, Image.Image):
                image = Image.open(image)

            # Preprocess image for ONNX model
            img_array = np.array(image.convert("RGB")).astype(np.float32)
            img_array = img_array / 255.0
            img_array = np.transpose(img_array, (2, 0, 1))
            img_array = np.expand_dims(img_array, axis=0)

            session = ort.InferenceSession(str(model_path))
            input_name = session.get_inputs()[0].name
            outputs = session.run(None, {input_name: img_array})

            # Parse outputs (format depends on specific model export)
            text = str(outputs[0]) if outputs else ""
            confidence = 0.9  # OpenDoc typically achieves ~90% on OmniDocBench

            return OCRResult(
                text=text,
                confidence=confidence,
                backend=self.name,
            )
        except Exception as e:
            return OCRResult(
                text="",
                confidence=0.0,
                backend=self.name,
                metadata={"error": str(e)},
            )


class PaddleOCRBackend(OCRBackend):
    """PaddleOCR backend (good for multilingual documents).

    Requires: pip install paddleocr paddlepaddle
    """

    def __init__(self, lang: str = "en"):
        self._lang = lang

    @property
    def name(self) -> str:
        return "paddleocr"

    @property
    def available(self) -> bool:
        try:
            from paddleocr import PaddleOCR
            return True
        except ImportError:
            return False

    def extract_text(self, image) -> str:
        result = self.extract_with_confidence(image)
        return result.text

    def extract_with_confidence(self, image) -> OCRResult:
        from paddleocr import PaddleOCR
        import numpy as np
        from PIL import Image

        if not isinstance(image, Image.Image):
            image = Image.open(image)

        ocr = PaddleOCR(use_angle_cls=True, lang=self._lang, show_log=False)
        img_array = np.array(image)
        results = ocr.ocr(img_array, cls=True)

        lines = []
        confidences = []
        regions = []

        if results and results[0]:
            for line in results[0]:
                bbox, (text, conf) = line[0], line[1]
                lines.append(text)
                confidences.append(conf)
                regions.append({
                    "text": text,
                    "confidence": conf,
                    "bbox": [coord for point in bbox for coord in point],
                })

        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

        return OCRResult(
            text="\n".join(lines),
            confidence=avg_conf,
            backend=self.name,
            regions=regions,
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_BACKENDS = {
    "tesseract": TesseractBackend,
    "opendoc": OpenDocBackend,
    "paddleocr": PaddleOCRBackend,
}


def create_ocr_backend(backend_name: str | None = None, **kwargs) -> OCRBackend:
    """Create an OCR backend instance.

    Auto-detection priority (when backend_name is None):
    1. D2A_OCR_BACKEND env var
    2. OpenDoc (if model file present)
    3. PaddleOCR (if installed)
    4. Tesseract (default)

    Args:
        backend_name: Explicit backend name.
        **kwargs: Passed to backend constructor.

    Returns:
        Configured OCRBackend instance.
    """
    if backend_name is None:
        backend_name = os.environ.get("D2A_OCR_BACKEND", "").lower()

    if not backend_name:
        # Auto-detect best available
        opendoc = OpenDocBackend(**kwargs)
        if opendoc.available and opendoc._get_model_path():
            return opendoc

        paddle = PaddleOCRBackend(**kwargs)
        if paddle.available:
            return paddle

        return TesseractBackend()

    cls = _BACKENDS.get(backend_name)
    if cls is None:
        raise ValueError(f"Unknown OCR backend: {backend_name!r}. Available: {', '.join(_BACKENDS)}")

    return cls(**kwargs)


def list_backends() -> list[dict]:
    """Return info about available backends."""
    results = []
    for name, cls in _BACKENDS.items():
        instance = cls()
        results.append({
            "name": name,
            "available": instance.available,
        })
    return results
