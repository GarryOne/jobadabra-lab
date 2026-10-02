#!/usr/bin/env node
// "Claude as teacher": when a Claude session had to operate a control by hand that the extension's operators could not, it records HOW as a
// recipe and files it here as a CANDIDATE, through the same validator and the same path as the proposer. The form lab then tries it on real
// public pages and the canary decides, so a hand-made recipe earns its place like any other.
//   node teach/teach.mjs --extension ../public/extension --fingerprint 1d2pcapx18 --kind toggle-group \
//        --params '{"option":"div.choice","onAttr":"data-state","onValue":"checked"}' [--note "Ashby Yes/No"] [--dry]
// Env: LAB_KEY (the site's owner key). The fingerprint is the one the extension reports for the control (results[].fp).
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {OPERATOR_OF} from '../proposer/proposer-lib.mjs';

const SITE = 'https://www.jobpilotto.workers.dev';

// -> {ok, recipe} or {ok: false, error}. `known` are the versions already on the site for this fingerprint.
export function build({fingerprint, kind, params, known = [], validateRecipe}) {
  const operator = OPERATOR_OF[kind];
  if (!operator) return {ok: false, error: `unknown kind "${kind}" (toggle-group, custom-select or date)`};
  const checked = validateRecipe({fingerprint, version: Math.max(0, ...known) + 1, operator, params, candidates: []});
  if (!checked.ok) return {ok: false, error: checked.error};
  if (!Object.keys(checked.recipe.params).length) return {ok: false, error: 'no parameters: the built-in operator already does that'};
  return {ok: true, recipe: checked.recipe};
}

export async function teach({site = SITE, ownerKey, fingerprint, kind, params, note = '', dry = false, validateRecipe, fetcher = fetch}) {
  const owner = {Authorization: `Bearer ${ownerKey}`, 'content-type': 'application/json'};
  const listed = await fetcher(`${site}/api/recipes?status=candidate`, {headers: owner});
  const running = await fetcher(`${site}/api/recipes`, {headers: owner});
  const known = [...(listed.ok ? (await listed.json()).recipes || [] : []), ...(running.ok ? (await running.json()).recipes || [] : [])]
    .filter(recipe => recipe.fingerprint === fingerprint).map(recipe => recipe.version);
  const made = build({fingerprint, kind, params, known, validateRecipe});
  if (!made.ok || dry) return made;
  const put = await fetcher(`${site}/api/recipes`, {method: 'PUT', headers: owner, body: JSON.stringify({recipe: made.recipe, status: 'candidate', source: 'claude', note: note.slice(0, 150)})});
  return put.ok ? made : {ok: false, error: `site refused: HTTP ${put.status}`};
}

if (import.meta.url === pathToFileURL(process.argv[1] || '').href) {
  const args = process.argv.slice(2);
  const option = (name, fallback = '') => { const i = args.indexOf(`--${name}`); return i >= 0 && args[i + 1] ? args[i + 1] : fallback; };
  const dir = option('extension');
  if (!dir || !fs.existsSync(path.join(dir, 'recipe-schema.js'))) { console.error('Pass --extension <the public repo\'s extension/ folder>.'); process.exit(2); }
  if (!process.env.LAB_KEY) { console.error('LAB_KEY is needed.'); process.exit(2); }
  const {validateRecipe} = await import(pathToFileURL(path.resolve(dir, 'recipe-schema.js')).href);
  let params;
  try { params = JSON.parse(option('params', '{}')); } catch { console.error('--params must be JSON.'); process.exit(2); }
  const result = await teach({site: option('site', SITE).replace(/\/$/, ''), ownerKey: process.env.LAB_KEY, fingerprint: option('fingerprint'), kind: option('kind'),
    params, note: option('note'), dry: args.includes('--dry'), validateRecipe});
  console.log(result.ok ? `[teach] ${args.includes('--dry') ? 'valid (dry)' : 'filed as a candidate'}: ${JSON.stringify(result.recipe)}` : `[teach] refused: ${result.error}`);
  process.exit(result.ok ? 0 : 1);
}
