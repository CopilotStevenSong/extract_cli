# extract-cli

Turn messy emails, logs, or support tickets into structured JSON with an LLM.
Requires Node.js 20+ and an OpenAI API key; no runtime dependencies.

## Install

From this repository:

```sh
npm install --global .
extract --help
```

You can also run `node cli.js` without installing.

## Usage

Create `schema.json` describing the fields you want:

```json
{
  "type": "object",
  "properties": {
    "customer": { "type": ["string", "null"] },
    "issue": { "type": "string" },
    "priority": { "type": ["string", "null"], "enum": ["low", "medium", "high", null] }
  },
  "required": ["customer", "issue", "priority"],
  "additionalProperties": false
}
```

Set `OPENAI_API_KEY` securely in your environment, then run:

```sh
extract --schema schema.json ticket.txt
cat ticket.txt | extract --schema schema.json
extract --schema schema.json --model gpt-4o-mini - < ticket.txt > ticket.json
```

For input such as `Alice reports that checkout is broken. Urgent!`, an example
result is:

```json
{
  "customer": "Alice",
  "issue": "Checkout is broken",
  "priority": "high"
}
```

The schema must follow OpenAI's
[Structured Outputs supported JSON Schema subset](https://platform.openai.com/docs/guides/structured-outputs#supported-schemas).
Use an object at the root, mark every property required, and set
`additionalProperties: false` on every object. Make fields nullable when missing
information should be represented by `null`. The API enforces the schema using
strict structured outputs; unsupported schemas or models fail with an error.

Input defaults to stdin; use a filename or `-` explicitly if desired. Successful
results are pretty-printed JSON on stdout. Errors, refusals, and incomplete or
invalid responses produce an error on stderr and a nonzero exit code.
Requests time out after 60 seconds.

**Privacy:** input text and the schema are sent to OpenAI over HTTPS and may incur
API charges. Review/redact sensitive information before use. LLM extractions can
still be factually incorrect; review results before acting on them.

## Development

```sh
npm test
```

Tests use Node's built-in test runner and mocked HTTP calls, not a live API key.