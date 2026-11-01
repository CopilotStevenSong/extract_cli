# extract_cli

Turn a messy email, log or support ticket into structured data (JSON, JSONL or CSV) with an LLM.

## Tech stack

- [Python](https://www.python.org/)
- [Typer](https://typer.tiangolo.com/) for the CLI
- [OpenAI Python SDK](https://github.com/openai/openai-python) for any OpenAI-compatible API
- [Pydantic](https://docs.pydantic.dev/) for the output schemas
- [Ollama](https://ollama.com/) with [gpt-oss:20b](https://ollama.com/library/gpt-oss) as the default local model

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
ollama pull gpt-oss:20b
```

## Run

```bash
python extract_cli.py samples/email.txt
python extract_cli.py samples/ticket.txt --format csv -o out.csv
python extract_cli.py samples/app.log --type log
```

| Option | Default | |
| --- | --- | --- |
| `--type` | `auto` | `auto`, `email`, `log`, `ticket` |
| `--format` | `json` | `json`, `jsonl`, `csv` |
| `-o` | stdout | Output file |
| `--model` | `gpt-oss:20b` | Model name |
| `--base-url` | `http://localhost:11434/v1` | API endpoint |
| `--api-key` | `ollama` | Or set `OPENAI_API_KEY` |
| `--reasoning-effort` | `low` | `low`, `medium`, `high`; low is fastest, high is more accurate |
| `--input-price` / `--output-price` | `0.30` / `1.20` | USD per 1M tokens ([DeepSeek V4 Flash](https://api-docs.deepseek.com/quick_start/pricing)); prints each call's cost to stderr |

## Switching models

Use any model on any OpenAI-compatible server. It must support structured outputs.

```bash
# another Ollama model
python extract_cli.py samples/email.txt --model qwen3:8b

# OpenAI (reads OPENAI_API_KEY)
python extract_cli.py samples/email.txt --base-url https://api.openai.com/v1 --model gpt-5
```

## How it works

1. **Detect:** with `--type auto`, the LLM classifies the text as email, log or ticket.
2. **Extract:** the matching extractor asks the LLM for a reply that fits a Pydantic schema (`extraction/schemas.py`).
3. **Write:** the result is printed or saved as JSON, JSONL or CSV.

## Sample

`python extract_cli.py samples/email.txt` gives:

```json
{
  "source": "samples\\email.txt",
  "kind": "email",
  "data": {
    "sender": "Maria Lopez",
    "subject": "URGENT!!! app crashing - drivers stuck",
    "intent": "request",
    "organizations": ["Acme Logistics"],
    "action_items": [
      { "task": "roll out fix", "owner": "support", "due_date": "2026-11-06" }
    ]
  }
}
```

The output above is trimmed. More inputs are in [samples/](samples/).
