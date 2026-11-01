"""Detect the kind (if needed), run the matching extractor, collect the result."""
import datetime
from dataclasses import dataclass, field

from pydantic import BaseModel

from .cost import CallCost
from .extractors import EXTRACTORS, KindDetector
from .llm import ExtractionError


@dataclass
class ExtractionResult:
    source: str
    kind: str
    record: BaseModel
    calls: list[CallCost] = field(default_factory=list)

    @property
    def total_tokens(self):
        return sum(c.total_tokens for c in self.calls)

    @property
    def total_cost(self):
        return sum(c.cost for c in self.calls)

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

        calls = []
        if kind == "auto":
            kind, call = self.detector.detect(text)
            calls.append(call)
        if kind not in self.extractors:
            raise ExtractionError(f"unknown kind {kind!r}; expected one of {self.kinds}")

        record, call = self.extractors[kind].extract(text, today)
        calls.append(call)
        return ExtractionResult(source, kind, record, calls)
