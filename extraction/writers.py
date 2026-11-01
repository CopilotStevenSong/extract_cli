"""Output formats (strategy pattern): each writer turns a result dict into text."""
import csv
import json
from abc import ABC, abstractmethod


class OutputWriter(ABC):
    @abstractmethod
    def write(self, result, out):
        """Write `result` (an ExtractionResult.to_dict()) to the text stream `out`."""


class JsonWriter(OutputWriter):
    def write(self, result, out):
        out.write(json.dumps(result, indent=2, ensure_ascii=False) + "\n")


class JsonlWriter(OutputWriter):
    def write(self, result, out):
        out.write(json.dumps(result, ensure_ascii=False) + "\n")


class CsvWriter(OutputWriter):
    @staticmethod
    def cell(value):
        # CSV cells hold scalars as-is and lists / objects as JSON
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False)
        return value

    def write(self, result, out):
        row = {"source": result["source"], "kind": result["kind"]}
        row.update({k: self.cell(v) for k, v in result["data"].items()})
        writer = csv.DictWriter(out, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)


WRITERS = {"json": JsonWriter, "jsonl": JsonlWriter, "csv": CsvWriter}


def get_writer(fmt):
    return WRITERS[fmt]()
