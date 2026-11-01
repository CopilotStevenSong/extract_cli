"""Detect the kind (if needed), run the matching extractor, collect the result."""
import datetime
from dataclasses import dataclass, field

from pydantic import BaseModel

from .extractors import EXTRACTORS, KindDetector
from .llm import ExtractionError


@dataclass
class ExtractionResult:
    source: str
    kind: str
    record: BaseModel
    usages: list = field(default_factory=list)

    @property
    def calls(self):
        return len(self.usages)

    @property
    def total_tokens(self):
        return sum(u.total_tokens for u in self.usages if u)

    def to_dict(self):
        return {"source": self.source, "kind": self.kind, "data": self.record.model_dump(mode="json")}


class ExtractionPipeline:
    def __init__(self, llm):
        self.detector = KindDetector(llm)
        self.extractors = {cls.kind: cls(llm) for cls in EXTRACTORS}

    @property
    def kinds(self):
        return list(self.extractors)

    def run(self, source, text, kind="auto", today=None):
        if not text.strip():
            raise ExtractionError("input is empty")
        today = today or datetime.date.today().isoformat()

        usages = []
        if kind == "auto":
            kind, usage = self.detector.detect(text)
            usages.append(usage)
        if kind not in self.extractors:
            raise ExtractionError(f"unknown kind {kind!r}; expected one of {self.kinds}")

        record, usage = self.extractors[kind].extract(text, today)
        usages.append(usage)
        return ExtractionResult(source, kind, record, usages)
