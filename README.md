# extract_cli

Turn a messy email, log excerpt or support ticket into structured data (JSON, JSONL or CSV) using an LLM.

```text
samples/email.txt  ──►  extract_cli  ──►  { "sender": ..., "intent": "request", "action_items": [...] }
```

- Detects the kind of input automatically (or you set it with `--type`)
- Fills a fixed schema per kind, so the output always has the same fields
- Runs on a local model through [Ollama](https://ollama.com) by default; **you can switch to any model or any OpenAI-compatible API** with one flag (see [Switching models](#switching-models))

## Tech stack

| Component | Role |
| --- | --- |
| [Python 3](https://www.python.org/) | Language (developed on 3.14) |
| [Typer](https://typer.tiangolo.com/) | Command-line interface, options and help text |
| [OpenAI Python SDK](https://github.com/openai/openai-python) | Client for any OpenAI-compatible chat endpoint, with [structured outputs](https://platform.openai.com/docs/guides/structured-outputs) |
| [Pydantic](https://docs.pydantic.dev/) | Output schemas; validates the model's reply |
| [Ollama](https://ollama.com/) | Default local model server |
| [gpt-oss:20b](https://ollama.com/library/gpt-oss) | Default model |

## Install

Requires Python 3.10+ and, for the default setup, [Ollama](https://ollama.com/download).

### Windows (PowerShell)

```powershell
git clone <repo-url> extract_cli
cd extract_cli
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### macOS / Linux

```bash
git clone <repo-url> extract_cli
cd extract_cli
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Pull the default model** (once), and make sure Ollama is running:

```bash
ollama pull gpt-oss:20b
```

## Run

```bash
python extract_cli.py <file> [options]
```

| Option | Default | Description |
| --- | --- | --- |
| `--type` | `auto` | `auto`, `email`, `log` or `ticket`. `auto` asks the model to classify the input first |
| `--format` | `json` | `json` (pretty), `jsonl` (one line) or `csv` (one row; lists/objects stored as JSON) |
| `-o`, `--output` | stdout | Write to a file instead of stdout |
| `--model` | `gpt-oss:20b` | Model name, as the server knows it |
| `--base-url` | `http://localhost:11434/v1` | OpenAI-compatible API endpoint |
| `--api-key` | `ollama` | API key; also read from `OPENAI_API_KEY`. Ollama ignores it |
| `--today` | today's date | Reference date for relative dates like "next Friday" |

Examples:

```bash
python extract_cli.py samples/email.txt
python extract_cli.py samples/ticket.txt --format csv -o out.csv
python extract_cli.py samples/app.log --type log --format jsonl
```

The extracted data goes to stdout (or `-o`); a status line goes to stderr, so you can pipe the output safely:

```text
[ok] samples\email.txt: email (2 call(s), 1785 tokens)
```

On failure (server not running, model refused, reply cut off, empty input) it prints `[error] ...` and exits with code 1.

## Switching models

The model and the backend are just options, so you can swap them per run without touching code.

### Another local Ollama model

```bash
ollama pull qwen3:8b
python extract_cli.py samples/email.txt --model qwen3:8b
```

### OpenAI

```bash
# PowerShell: $env:OPENAI_API_KEY = "sk-..."
export OPENAI_API_KEY=sk-...
python extract_cli.py samples/email.txt --base-url https://api.openai.com/v1 --model gpt-5
```

**Any other OpenAI-compatible server** (e.g. [LM Studio](https://lmstudio.ai/), [vLLM](https://docs.vllm.ai/)):

```bash
python extract_cli.py samples/email.txt --base-url http://localhost:1234/v1 --model <model-name>
```

The model must support structured outputs (a `json_schema` response format). Smaller models work but tend to be less accurate; check the output before relying on it.

To change the defaults permanently, edit `DEFAULT_MODEL` and `DEFAULT_BASE_URL` in [extraction/llm.py](extraction/llm.py).

## How it works

```text
input file
    │
    ▼
ExtractionPipeline.run()
    │
    ├─ --type auto?  ──► KindDetector: classify the first 2000 chars as email | log | ticket   (LLM call 1)
    │
    ├─ pick the Extractor for that kind (EmailExtractor / LogExtractor / TicketExtractor)
    │
    ├─ Extractor ──► LLMClient.parse(prompt, text, PydanticSchema)                               (LLM call 2)
    │                   └─ the schema becomes a strict JSON-schema response format;
    │                      the reply is validated back into the Pydantic model
    │
    ▼
ExtractionResult { source, kind, data }  ──►  OutputWriter (json | jsonl | csv)  ──►  stdout / file
```

1. **Detect.** With `--type auto`, one short LLM call classifies the text. Passing `--type` skips this call.
2. **Extract.** The matching extractor sends the text with its prompt plus shared rules (today's date for relative dates, one-sentence summaries, `null` instead of guessing). The OpenAI SDK's `chat.completions.parse()` forces the reply to match the kind's Pydantic schema.
3. **Write.** The validated record is wrapped with `source` and `kind` and written in the chosen format.

### Project layout

| File | Contents |
| --- | --- |
| [extract_cli.py](extract_cli.py) | CLI entry point (Typer) |
| [extraction/schemas.py](extraction/schemas.py) | Pydantic models: `EmailRecord`, `TicketRecord`, `LogRecord`, `DocKind` |
| [extraction/llm.py](extraction/llm.py) | `LLMClient`, default model and URL, error handling |
| [extraction/extractors.py](extraction/extractors.py) | One `Extractor` per kind, plus `KindDetector` |
| [extraction/pipeline.py](extraction/pipeline.py) | `ExtractionPipeline` and `ExtractionResult` |
| [extraction/writers.py](extraction/writers.py) | One `OutputWriter` per output format |

### Extracted fields

| Kind | Fields |
| --- | --- |
| `email` | sender, recipients, subject, sent_date, summary, intent (`request`/`complaint`/`info`/`scheduling`/`other`), people, organizations, action_items |
| `ticket` | customer_name, product, category, summary, priority (`low`/`medium`/`high`/`urgent`), sentiment_score (1–5), steps_to_reproduce, action_items |
| `log` | summary, events (timestamp, level, component, message, error_code), probable_root_cause |

Each action item has `task`, `owner` and `due_date`.

### Adding a new kind

1. Add a Pydantic model in `extraction/schemas.py` and the kind name to `DocKind`.
2. Subclass `Extractor` in `extraction/extractors.py` with `kind`, `schema` and `prompt`.
3. Add it to `EXTRACTORS` and to the `InputType` enum in `extract_cli.py`.

## Samples

The [samples/](samples/) folder has one input of each kind. The outputs below are real runs with the default model (`gpt-oss:20b`). LLM output varies between runs and models.

### Email: [samples/email.txt](samples/email.txt)

```bash
python extract_cli.py samples/email.txt
```

```json
{
  "source": "samples\\email.txt",
  "kind": "email",
  "data": {
    "sender": "Maria Lopez",
    "recipients": ["support@routemaster.example"],
    "subject": "URGENT!!! app crashing - drivers stuck",
    "sent_date": "2026-10-30T08:14:22+01:00",
    "summary": "Maria Lopez of Acme Logistics reports that since the update on 2026-10-29 the RouteMaster app crashes for 12 drivers, requests a callback on 2026-10-30, and asks that a fix be rolled out to all devices before 2026-11-06, with IT lead Tom Baker available to test a patched build.",
    "intent": "request",
    "people": ["Tom Baker"],
    "organizations": ["Acme Logistics"],
    "action_items": [
      { "task": "call back", "owner": "support", "due_date": "2026-10-30" },
      { "task": "roll out fix", "owner": "support", "due_date": "2026-11-06" }
    ]
  }
}
```

### Ticket: [samples/ticket.txt](samples/ticket.txt)

```bash
python extract_cli.py samples/ticket.txt --format csv -o ticket.csv
```

```csv
source,kind,customer_name,product,category,summary,priority,sentiment_score,steps_to_reproduce,action_items
samples\ticket.txt,ticket,Jenny Chen,billing portal,login problem (502 gateway error) after forced password reset on 24 October 2026,"[OPS-4471] Ticket created 29 October 2026 ...",medium,0,"[""Navigate to billing.example.com"", ""Enter email and new password"", ""Spinner for ~30s"", ""Error 502 Bad Gateway appears""]","[{""task"": ""download October invoices by 2 November 2026"", ""owner"": null, ""due_date"": ""2026-11-02""}, ...]"
```

### Log: [samples/app.log](samples/app.log)

```bash
python extract_cli.py samples/app.log --type log
```

```json
{
  "source": "samples\\app.log",
  "kind": "log",
  "data": {
    "summary": "Nightly sync completed with errors; inventory sync failed due to timeout after three attempts, and a pager was sent to the ops team.",
    "events": [
      { "timestamp": "2026-10-31T02:00:00.114Z", "level": "INFO", "component": "scheduler", "message": "nightly-sync started", "error_code": null },
      { "timestamp": "2026-10-31T02:01:39.012Z", "level": "ERROR", "component": "sync.inventory", "message": "inventory sync failed", "error_code": null },
      { "timestamp": "2026-10-31T02:01:48.002Z", "level": "CRITICAL", "component": "scheduler", "message": "nightly-sync finished with errors (1 of 3 steps failed)", "error_code": null }
    ],
    "probable_root_cause": "The inventory sync failed because the warehouse API timed out after three attempts, causing the nightly sync to finish with errors and triggering an alert to the ops team."
  }
}
```

21 events in the full output; 3 shown.
