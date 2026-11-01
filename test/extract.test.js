import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { extract } from '../extract.js';

const schema = {
  type: 'object',
  properties: { issue: { type: 'string' } },
  required: ['issue'],
  additionalProperties: false,
};
const options = { text: 'Checkout is broken', schema, apiKey: 'test-placeholder' };
const completion = (content, finish_reason = 'stop') => ({
  ok: true,
  json: async () => ({ choices: [{ finish_reason, message: { content } }] }),
});

test('extract sends text, model, and strict schema and returns structured JSON', async () => {
  const result = await extract({ ...options, model: 'custom-model' }, async (url, request) => {
    assert.equal(url, 'https://api.openai.com/v1/chat/completions');
    assert.equal(request.method, 'POST');
    assert.equal(request.redirect, 'error');
    assert.ok(request.signal instanceof AbortSignal);
    assert.equal(request.headers.Authorization, ['Bearer', options.apiKey].join(' '));
    const body = JSON.parse(request.body);
    assert.equal(body.model, 'custom-model');
    assert.equal(body.messages[1].content, options.text);
    assert.equal(body.messages[1].role, 'user');
    assert.deepEqual(body.response_format, {
      type: 'json_schema',
      json_schema: { name: 'extraction', strict: true, schema },
    });
    return completion('{"issue":"Checkout is broken"}');
  });
  assert.deepEqual(result, { issue: 'Checkout is broken' });
});

test('invalid inputs fail without sending a request', async () => {
  const noRequest = () => assert.fail('Unexpected API request');
  for (const [override, message] of [
    [{ text: ' \n' }, /non-empty/],
    [{ apiKey: '' }, /OPENAI_API_KEY/],
    [{ model: '' }, /Model/],
    [{ schema: null }, /Schema/],
    [{ schema: { type: 'array' } }, /Schema/],
    [{ schema: { type: 'object', properties: [] } }, /Schema/],
  ]) {
    await assert.rejects(extract({ ...options, ...override }, noRequest), message);
  }
});

test('HTTP and network errors do not expose API bodies or credentials', async () => {
  await assert.rejects(extract(options, async () => ({
    ok: false, status: 401,
    json: () => assert.fail('Error body must not be read'),
  })), /HTTP 401/);
  await assert.rejects(extract(options, async () => {
    throw new Error(options.apiKey);
  }), (error) => !error.message.includes(options.apiKey) && /failed or timed out/.test(error.message));
});

test('refused, incomplete, malformed, and non-object results fail', async () => {
  const cases = [
    [{ ok: true, json: async () => { throw new Error('bad JSON'); } }, /invalid API response/],
    [{ ok: true, json: async () => null }, /incomplete/],
    [{ ok: true, json: async () => ({ choices: [{ message: { refusal: 'No' } }] }) }, /refused/],
    [completion('{}', 'length'), /incomplete/],
    [completion('{}', 'content_filter'), /incomplete/],
    [completion(null), /incomplete/],
    [completion('not JSON'), /invalid JSON/],
    [completion('null'), /JSON object/],
    [completion('[]'), /JSON object/],
    [completion('"text"'), /JSON object/],
  ];
  for (const [response, message] of cases) {
    await assert.rejects(extract(options, async () => response), message);
  }
});

const cli = new URL('../cli.js', import.meta.url);
const run = (args, input = '', env = {}, preload = []) => spawnSync(process.execPath, [...preload, cli.pathname, ...args], {
  input, encoding: 'utf8', env: { ...process.env, OPENAI_API_KEY: '', ...env },
});

test('CLI help and argument errors work without credentials', () => {
  const help = run(['--help']);
  assert.equal(help.status, 0);
  assert.match(help.stdout, /Usage: extract/);
  assert.equal(help.stderr, '');
  for (const args of [[], ['--unknown'], ['--schema'], ['--schema', 's.json', 'a', 'b']]) {
    const result = run(args);
    assert.equal(result.status, 1);
    assert.equal(result.stdout, '');
    assert.match(result.stderr, /Error:/);
  }
});

test('CLI handles schema, credential, file, and empty stdin errors', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'extract-cli-'));
  try {
    const schemaPath = join(dir, 'schema.json');
    await writeFile(schemaPath, 'not JSON');
    assert.match(run(['--schema', schemaPath]).stderr, /not valid JSON/);
    await writeFile(schemaPath, JSON.stringify(schema));
    assert.match(run(['--schema', schemaPath]).stderr, /OPENAI_API_KEY/);
    const env = { OPENAI_API_KEY: options.apiKey };
    const missing = run(['--schema', schemaPath, join(dir, 'missing.txt')], '', env);
    assert.equal(missing.status, 1);
    assert.match(missing.stderr, /Cannot read input file/);
    for (const args of [['--schema', schemaPath], ['--schema', schemaPath, '-']]) {
      const result = run(args, ' \n', env);
      assert.equal(result.status, 1);
      assert.equal(result.stdout, '');
      assert.match(result.stderr, /non-empty/);
    }
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});

test('CLI extracts file and stdin input and emits only JSON', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'extract-cli-'));
  const mock = `import assert from 'node:assert/strict';
    globalThis.fetch = async (url, request) => {
      const body = JSON.parse(request.body);
      assert.equal(body.messages[1].content, 'Checkout is broken');
      assert.equal(body.model, 'test-model');
      assert.equal(body.response_format.json_schema.strict, true);
      return {
        ok: true,
        json: async () => ({
          choices: [{
            finish_reason: 'stop',
            message: { content: '{"issue":"Checkout is broken"}' }
          }]
        })
      };
    };`;
  const preload = ['--import', `data:text/javascript,${encodeURIComponent(mock)}`];
  try {
    const schemaPath = join(dir, 'schema.json');
    const inputPath = join(dir, 'ticket.txt');
    await writeFile(schemaPath, JSON.stringify(schema));
    await writeFile(inputPath, options.text);
    for (const inputArgs of [[], ['-'], [inputPath]]) {
      const result = run(
        ['--schema', schemaPath, '--model', 'test-model', ...inputArgs],
        options.text, { OPENAI_API_KEY: options.apiKey }, preload,
      );
      assert.equal(result.status, 0, result.stderr);
      assert.equal(result.stderr, '');
      assert.deepEqual(JSON.parse(result.stdout), { issue: 'Checkout is broken' });
      assert.ok(result.stdout.endsWith('\n'));
    }
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});
