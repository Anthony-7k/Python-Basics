from __future__ import annotations

import math
from threading import Lock

from app.document_ai.parsers import TextBlock


class RapidOCRProvider:
    """CPU OCR; lazy model loading, serialized inference, no fake fallback."""

    def __init__(self):
        self._engine = None
        self._lock = Lock()

    def recognize(self, payload: bytes) -> list[TextBlock]:
        with self._lock:
            if self._engine is None:
                try:
                    from rapidocr import RapidOCR
                except ImportError as exc:
                    raise RuntimeError("Install docflow-ai[ocr] before using RapidOCR") from exc
                self._engine = RapidOCR(params={"EngineConfig.onnxruntime.intra_op_num_threads": 2,
                                               "EngineConfig.onnxruntime.inter_op_num_threads": 1})
            result = self._engine(payload)
        if result.txts is None or result.boxes is None or result.scores is None:
            return []
        blocks = []
        for text, polygon, score in zip(result.txts, result.boxes, result.scores, strict=True):
            if not text.strip():
                continue
            points = [[float(value) for value in point] for point in polygon]
            confidence = float(score)
            if not all(math.isfinite(value) for point in points for value in point) or not 0 <= confidence <= 1:
                raise ValueError("invalid OCR coordinates or confidence")
            blocks.append(TextBlock(text.strip(), [min(p[0] for p in points), min(p[1] for p in points),
                                                   max(p[0] for p in points), max(p[1] for p in points)],
                                    confidence))
        return blocks
