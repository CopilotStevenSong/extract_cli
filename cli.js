#!/usr/bin/env node
import { readFile } from 'node:fs/promises';
import { parseArgs } from 'node:util';
import { extract, validateSchema } from './extract.js';

const help = `Usage: extract --schema <schema.json> [--model <model>] [input-file|-]

Extract structured JSON from emails, logs, or tickets using OpenAI.
Input defaults to stdin. Output is JSON on stdout; errors go to stderr.

Options:
  --schema <file>  JSON Schema describing the output (required)
  --model <name>   Structured-output model (default: gpt-4o-mini)
  --help, -h       Show this help

Authentication: set OPENAI_API_KEY in your environment.
`;

async function main() {
  const { values, positionals } = parseArgs({
    options: {
      schema: { type: 'string' },
      model: { type: 'string', default: 'gpt-4o-mini' },
      help: { type: 'boolean', short: 'h' },
    },
    allowPositionals: true,
  });
  if (values.help) {
    process.stdout.write(help);
    return;
  }
  if (!values.schema || positionals.length > 1) {
    throw new Error('Provide --schema <schema.json> and at most one input file. See --help.');
  }
  let schema;
  try {
    schema = JSON.parse(await readFile(values.schema, 'utf8'));
  } catch {
    throw new Error('Cannot read schema file or schema is not valid JSON.');
  }
  validateSchema(schema);
  if (!process.env.OPENAI_API_KEY?.trim()) {
    throw new Error('Set OPENAI_API_KEY to your OpenAI API key.');
  }
  let text;
  if (positionals.length && positionals[0] !== '-') {
    try {
      text = await readFile(positionals[0], 'utf8');
    } catch {
      throw new Error('Cannot read input file.');
    }
  } else {
    process.stdin.setEncoding('utf8');
    text = '';
    for await (const chunk of process.stdin) text += chunk;
  }
  const data = await extract({
    text, schema, apiKey: process.env.OPENAI_API_KEY, model: values.model,
  });
  process.stdout.write(`${JSON.stringify(data, null, 2)}\n`);
}

main().catch((error) => {
  process.stderr.write(`Error: ${error.message}\n`);
  process.exitCode = 1;
});
