#!/usr/bin/env node
// The recipe proposer: for the controls that fail and have no recipe yet, ask a small model for a recipe, check it with the shared
// validator, and file it as a CANDIDATE (the form lab then tries it on real pages, the canary rolls it out). It spends money, so it is
// capped: at most --max controls and --budget dollars per run, and every decision is logged (fingerprint, outcome, tokens, cost):
// never the page's text. Design: Notion "Self-improving form filling".
//   node proposer/proposer.mjs --extension ../public/extension [--site URL] [--max 20] [--budget 0.5] [--dry] [--out result.json]
// Env: LAB_KEY (the site's owner key), ANTHROPIC_API_KEY.
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {MODEL, OPERATOR_OF, SYSTEM, buildMessage, costUsd, decide, parseAnswer} from './proposer-lib.mjs';

const SITE = 'https://www.jobadabra.top';
const log = (...parts) => console.log(`[proposer] ${parts.join(' ')}`);

async function ask(fetcher, apiKey, target) {
  const body = JSON.stringify({model: MODEL, max_tokens: 1500, output_config: {effort: 'low'}, system: SYSTEM, messages: [{role: 'user', content: buildMessage(target)}]});
  for (let attempt = 0; attempt < 2; attempt++) {
    const response = await fetcher('https://api.anthropic.com/v1/messages', {method: 'POST', body,
      headers: {'x-api-key': apiKey, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'}});
    if (response.ok) { const data = await response.json(); return {text: data.content?.find(block => block.type === 'text')?.text || '', usage: data.usage || {}}; }
    if (![429, 500, 502, 503, 529].includes(response.status)) throw new Error(`Anthropic ${response.status}`);
    await new Promise(resolve => setTimeout(resolve, 1500));
  }
  throw new Error('Anthropic busy');
}

// -> {considered, submitted, skipped, spent, results: [{fingerprint, kind, action, why?, cost}]}
export async function run({site = SITE, ownerKey, apiKey, max = 20, budget = 0.5, dry = false, validateRecipe, fetcher = fetch}) {
  const owner = {Authorization: `Bearer ${ownerKey}`, 'content-type': 'application/json'};
  const listed = await fetcher(`${site}/api/recipes/targets?limit=${max}`, {headers: owner});
  if (!listed.ok) throw new Error(`targets: HTTP ${listed.status}`);
  const targets = (await listed.json()).targets || [];
  const summary = {considered: 0, submitted: 0, skipped: 0, spent: 0, results: []};
  log(`${targets.length} control(s) without a recipe, budget $${budget}${dry ? ' (dry: nothing is filed)' : ''}`);
  for (const target of targets.slice(0, max)) {
    if (summary.spent >= budget) { log(`budget reached at $${summary.spent.toFixed(4)}: stopping`); break; }
    summary.considered++;
    let decision, cost = 0;
    // A kind no operator handles (an unread question from the reading check, a switch) cannot get a recipe: no model call.
    if (!OPERATOR_OF[target.kind]) {
      summary.skipped++;
      summary.results.push({fingerprint: target.fingerprint, kind: target.kind, action: 'skip', why: `no operator for kind ${target.kind}`, cost: 0});
      log(target.fingerprint, target.kind, `skipped (no operator for this kind, no model call)`);
      continue;
    }
    try {
      const {text, usage} = await ask(fetcher, apiKey, target);
      cost = costUsd(usage);
      decision = decide({target, answer: parseAnswer(text), validateRecipe});
    } catch (error) { decision = {action: 'skip', why: `error: ${error.message}`}; }
    summary.spent += cost;
    if (decision.action === 'submit' && !dry) {
      const put = await fetcher(`${site}/api/recipes`, {method: 'PUT', headers: owner,
        body: JSON.stringify({recipe: decision.recipe, status: 'candidate', source: 'proposer', note: decision.note})});
      if (!put.ok) decision = {action: 'skip', why: `site refused: HTTP ${put.status}`};
    }
    if (decision.action === 'submit') summary.submitted++; else summary.skipped++;
    summary.results.push({fingerprint: target.fingerprint, kind: target.kind, action: decision.action, ...(decision.why ? {why: decision.why} : {}),
      ...(decision.action === 'submit' ? {recipe: {operator: decision.recipe.operator, params: decision.recipe.params}} : {}), cost: Number(cost.toFixed(5))});
    log(target.fingerprint, target.kind, decision.action === 'submit' ? `filed v${target.version}` : `skipped (${decision.why})`, `$${cost.toFixed(5)}`, 'users', target.userFailed, 'lab', target.labFailed);
  }
  log(`done: ${summary.submitted} filed, ${summary.skipped} skipped, $${summary.spent.toFixed(4)} spent`);
  return summary;
}

if (import.meta.url === pathToFileURL(process.argv[1] || '').href) {
  const args = process.argv.slice(2);
  const option = (name, fallback = '') => { const i = args.indexOf(`--${name}`); return i >= 0 && args[i + 1] ? args[i + 1] : fallback; };
  const dir = option('extension');
  if (!dir || !fs.existsSync(path.join(dir, 'recipe-schema.js'))) { console.error('Pass --extension <the public repo\'s extension/ folder>.'); process.exit(2); }
  const {validateRecipe} = await import(pathToFileURL(path.resolve(dir, 'recipe-schema.js')).href);
  const ownerKey = process.env.LAB_KEY, apiKey = process.env.ANTHROPIC_API_KEY;
  if (!ownerKey || !apiKey) { console.error('LAB_KEY and ANTHROPIC_API_KEY are needed.'); process.exit(2); }
  const summary = await run({site: option('site', SITE).replace(/\/$/, ''), ownerKey, apiKey, max: Number(option('max', '20')) || 20,
    budget: Number(option('budget', '0.5')) || 0.5, dry: args.includes('--dry'), validateRecipe});
  if (option('out')) fs.writeFileSync(option('out'), JSON.stringify(summary, null, 2));
}
