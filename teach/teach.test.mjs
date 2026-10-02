// "Claude as teacher": a recipe made by hand goes through the same checks as the proposer's.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {test} from 'node:test';
import {pathToFileURL} from 'node:url';
import {build, teach} from './teach.mjs';

const here = path.dirname(new URL(import.meta.url).pathname);
const dir = [process.env.EXTENSION_DIR, path.join(here, '../public/extension'), path.join(os.homedir(), 'job-pilotto/extension')].find(item => item && fs.existsSync(path.join(item, 'recipe-schema.js')));
const {validateRecipe} = await import(pathToFileURL(path.join(dir, 'recipe-schema.js')).href);
const params = {option: 'div.choice', onAttr: 'data-state', onValue: 'checked'};

test('a hand-made recipe is checked by the shared validator and takes the next version', () => {
  assert.deepEqual(build({fingerprint: '1d2pcapx18', kind: 'toggle-group', params, known: [1, 2], validateRecipe}).recipe,
    {fingerprint: '1d2pcapx18', version: 3, operator: 'toggle', params, candidates: []});
  assert.equal(build({fingerprint: '1d2pcapx18', kind: 'toggle-group', params: {option: 'button[type=submit]'}, validateRecipe}).ok, false);
  assert.equal(build({fingerprint: '1d2pcapx18', kind: 'rich-text', params, validateRecipe}).ok, false);
  assert.equal(build({fingerprint: '1d2pcapx18', kind: 'toggle-group', params: {}, validateRecipe}).ok, false);
  assert.equal(build({fingerprint: 'BAD!', kind: 'toggle-group', params, validateRecipe}).ok, false);
});

test('it files a candidate with source "claude", and a dry run files nothing', async () => {
  const puts = [];
  const fetcher = async (url, init = {}) => init.method === 'PUT' ? (puts.push(JSON.parse(init.body)), {ok: true}) : {ok: true, json: async () => ({recipes: [{fingerprint: '1d2pcapx18', version: 1}]})};
  const result = await teach({ownerKey: 'k', fingerprint: '1d2pcapx18', kind: 'toggle-group', params, note: 'Ashby Yes/No', validateRecipe, fetcher});
  assert.equal(result.recipe.version, 2);
  assert.deepEqual([puts[0].status, puts[0].source, puts[0].recipe.version], ['candidate', 'claude', 2]);
  await teach({ownerKey: 'k', fingerprint: '1d2pcapx18', kind: 'toggle-group', params, dry: true, validateRecipe, fetcher});
  assert.equal(puts.length, 1);
});
