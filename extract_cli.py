"""Turn a messy email, log or support ticket into structured data (JSON / JSONL / CSV).

The logic lives in the `extraction` package next to this file:
    schemas.py     Pydantic models for each kind of input
    llm.py         LLMClient: OpenAI-compatible structured-output calls
    extractors.py  one Extractor per kind, plus KindDetector for --type auto
    pipeline.py    ExtractionPipeline: detect -> extract -> ExtractionResult
    writers.py     one OutputWriter per --format

Setup:
    1. Install deps:  pip install openai pydantic typer
    2. Default backend is a local Ollama server via its OpenAI-compatible endpoint:
           ollama pull gpt-oss:20b   (and make sure Ollama is running)
       Any OpenAI-compatible API works too, e.g. OpenAI:
           --base-url https://api.openai.com/v1 --model gpt-5   (reads $OPENAI_API_KEY)

Usage:
    python extract_cli.py samples\\email.txt
    python extract_cli.py samples\\ticket.txt --format csv -o out.csv
    python extract_cli.py samples\\app.log --type log
"""
import datetime
import sys
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer

from extraction import (DEFAULT_BASE_URL, DEFAULT_INPUT_PRICE, DEFAULT_MODEL, DEFAULT_OUTPUT_PRICE,
                        DEFAULT_REASONING_EFFORT, ExtractionError, ExtractionPipeline, LLMClient, Pricing, get_writer)


class InputType(str, Enum):
    auto = "auto"
    email = "email"
    log = "log"
    ticket = "ticket"


class OutputFormat(str, Enum):
    json = "json"
    jsonl = "jsonl"
    csv = "csv"


class ReasoningEffort(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


def log(msg):
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{stamp} {msg}", file=sys.stderr)


def mask(secret):
    """Hide all but the last 4 characters of an API key."""
    return "*" * max(len(secret) - 4, 0) + secret[-4:] if len(secret) > 8 else "*" * len(secret)


def main(
    file: Annotated[Path, typer.Argument(
        exists=True, dir_okay=False, readable=True, help="Input file to extract from")],
    input_type: Annotated[InputType, typer.Option(
        "--type", help="Kind of input; auto detects it")] = InputType.auto,
    output_format: Annotated[OutputFormat, typer.Option(
        "--format", help="Output format")] = OutputFormat.json,
    output: Annotated[Optional[str], typer.Option(
        "-o", "--output", help="Write to this file instead of stdout")] = None,
    model: Annotated[str, typer.Option()] = DEFAULT_MODEL,
    base_url: Annotated[str, typer.Option()] = DEFAULT_BASE_URL,
    api_key: Annotated[str, typer.Option(
        envvar="OPENAI_API_KEY", help="Ollama ignores the key")] = "ollama",
    today: Annotated[str, typer.Option(
        help="Reference date for relative dates like 'next Friday'")] = datetime.date.today().isoformat(),
    input_price: Annotated[float, typer.Option(
        min=0, help="USD per 1M input tokens (default: DeepSeek V4 Flash)")] = DEFAULT_INPUT_PRICE,
    output_price: Annotated[float, typer.Option(
        min=0, help="USD per 1M output tokens (default: DeepSeek V4 Flash)")] = DEFAULT_OUTPUT_PRICE,
    reasoning_effort: Annotated[ReasoningEffort, typer.Option(
        help="How much the model reasons before answering; low is fastest")] = ReasoningEffort(DEFAULT_REASONING_EFFORT),
):
    """Turn a messy email, log or ticket into structured data."""
    # Parameters go to stderr so stdout stays clean for piping the extracted data
    params = {
        "file": file,
        "type": input_type.value,
        "format": output_format.value,
        "output": output or "stdout",
        "model": model,
        "base_url": base_url,
        "api_key": mask(api_key),
        "today": today,
        "input_price": f"${input_price:.2f}/1M tokens",
        "output_price": f"${output_price:.2f}/1M tokens",
        "reasoning_effort": reasoning_effort.value,
    }
    width = max(map(len, params))
    for name, value in params.items():
        log(f"[param] {name:<{width}} = {value}")

    pricing =Pricing(input_per_million=input_price, output_per_million=output_price)
    pipeline = ExtractionPipeline(LLMClient(model=model, base_url=base_url, api_key=api_key, pricing=pricing,
                                            reasoning_effort=reasoning_effort.value))

    text = file.read_text(encoding="utf-8", errors="replace")
    try:
        result = pipeline.run(str(file), text, kind=input_type.value, today=today)
    except ExtractionError as e:
        log(f"[error] {file}: {e}")
        raise typer.Exit(1)

    for call in result.calls:
        log(f"[call] {call.step}: {call.model}, {call.input_tokens} in + {call.output_tokens} out tokens,"
            f" ${call.cost:.6f}, {call.duration_s:.1f}s")
    log(f"[ok] {file}: {result.kind} ({len(result.calls)} call(s), {result.total_tokens} tokens,"
        f" ${result.total_cost:.6f}, {sum(c.duration_s for c in result.calls):.1f}s)")

    writer = get_writer(output_format.value)
    if output:
        with open(output, "w", encoding="utf-8", newline="") as out:
            writer.write(result.to_dict(), out)
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        writer.write(result.to_dict(), sys.stdout)


if __name__ == "__main__":
    typer.run(main)
