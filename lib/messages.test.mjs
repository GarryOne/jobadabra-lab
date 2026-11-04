// Guard: money — the lab's AI jobs must reach the model only through the AI broker relay, never with an API key; a broker "no" is final (no retry), so one run cannot ask twice.
// Why (3 Nov 2026, owner: "We should not use API Keys at all anymore. Everything should be around the ai-broker"): the three jobs called api.anthropic.com with ANTHROPIC_API_KEY.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {askMessages, relayUrl} from './messages.mjs';

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const code = file => fs.readFileSync(path.join(root, file), 'utf8').split('\n').filter(line => !/^\s*(#|\/\/)/.test(line)).join('\n');

test('without the relay the job stops and says why; with it the call goes to the relay with no key header', async () => {
  assert.throws(() => relayUrl({}), /JOBADABRA_AI_BASE_URL is not set/);
  let seen;
  const fetcher = async (url, init) => { seen = {url, init}; return {ok: true, status: 200, json: async () => ({content: [{type: 'thinking'}, {type: 'text', text: 'hi'}], usage: {input_tokens: 1}})}; };
  const answer = await askMessages(fetcher, '{}', {JOBADABRA_AI_BASE_URL: 'http://127.0.0.1:5/'});
  assert.deepEqual([seen.url, answer.text, Object.keys(seen.init.headers)], ['http://127.0.0.1:5/v1/messages', 'hi', ['content-type']]);
});

test('a broker no is one call and an error: never retried', async () => {
  let calls = 0;
  const fetcher = async () => { calls++; return {ok: false, status: 429}; };
  await assert.rejects(askMessages(fetcher, '{}', {JOBADABRA_AI_BASE_URL: 'http://127.0.0.1:5'}), /AI broker 429/);
  assert.equal(calls, 1);
});

test('no lab workflow or script names an Anthropic key or address', () => {
  const files = ['proposer/proposer.mjs', 'aliases/proposer.mjs', 'digest/propose.mjs', '.github/workflows/proposer.yml', '.github/workflows/aliases.yml', '.github/workflows/form-learning.yml', 'README.md'];
  for (const file of files) assert.doesNotMatch(code(file), /ANTHROPIC|api\.anthropic\.com|x-api-key/i, `${file} must not use an API key or the Anthropic address`);
  for (const file of files.filter(name => name.endsWith('.yml'))) assert.match(code(file), /broker-relay-run\.mjs/, `${file} runs its script behind the relay`);
});
