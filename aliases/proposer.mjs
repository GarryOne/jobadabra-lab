#!/usr/bin/env node
// The alias proposer: for question wordings several installs report and no alias places, ask a small model which profile field each means,
// check it with a second pass and the shared validator, and file it on the site. Confirmed, non-sensitive aliases with enough independent
// reports start a 5% canary (the site grows or halts it from real outcomes); everything else waits as a candidate for the owner.
// Capped at --max questions and --budget dollars a run; every decision is logged (the wording is the form's public text, never user data).
//   node aliases/proposer.mjs --extension ../public/extension [--site URL] [--max 25] [--budget 0.3] [--dry] [--out result.json]
// Env: LAB_KEY, ANTHROPIC_API_KEY.
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {MODEL, SYSTEM, VERIFY, askMessage, costUsd, decide, parseJson, verifyMessage} from './aliases-lib.mjs';

const SITE = 'https://www.jobpilotto.workers.dev';
const log = (...parts) => console.log(`[aliases] ${parts.join(' ')}`);

async function ask(fetcher, apiKey, system, content) {
  const body = JSON.stringify({model: MODEL, max_tokens: 200, temperature: 0, system, messages: [{role: 'user', content}]});
  for (let attempt = 0; attempt < 2; attempt++) {
    const response = await fetcher('https://api.anthropic.com/v1/messages', {method: 'POST', body,
      headers: {'x-api-key': apiKey, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'}});
    if (response.ok) { const data = await response.json(); return {text: data.content?.[0]?.text || '', usage: data.usage || {}}; }
    if (![429, 500, 502, 503, 529].includes(response.status)) throw new Error(`Anthropic ${response.status}`);
    await new Promise(resolve => setTimeout(resolve, 1500));
  }
  throw new Error('Anthropic busy');
}

export async function run({site = SITE, ownerKey, apiKey, max = 25, budget = 0.3, dry = false, schema, fetcher = fetch}) {
  const owner = {Authorization: `Bearer ${ownerKey}`, 'content-type': 'application/json'};
  const listed = await fetcher(`${site}/api/aliases?targets=1`, {headers: owner});
  if (!listed.ok) throw new Error(`targets: HTTP ${listed.status}`);
  const {targets = [], sensitive = []} = await listed.json();
  const summary = {considered: 0, canary: 0, candidate: 0, skipped: 0, spent: 0, results: []};
  log(`${targets.length} question(s) without a meaning, budget $${budget}${dry ? ' (dry: nothing is filed)' : ''}`);
  for (const target of targets.slice(0, max)) {
    if (summary.spent >= budget) { log(`budget reached at $${summary.spent.toFixed(4)}: stopping`); break; }
    summary.considered++;
    let decision, cost = 0;
    try {
      const first = await ask(fetcher, apiKey, SYSTEM, askMessage(target));
      cost += costUsd(first.usage);
      const proposal = parseJson(first.text);
      let verdict = null;
      if (proposal && !proposal.none && proposal.key) {
        const second = await ask(fetcher, apiKey, VERIFY, verifyMessage(target, proposal.key));
        cost += costUsd(second.usage);
        verdict = parseJson(second.text);
      }
      decision = decide({target, proposal, verdict, sensitive, validateAlias: schema.validateAlias, aliasKey: schema.aliasKey});
    } catch (error) { decision = {action: 'skip', why: `error: ${error.message}`}; }
    summary.spent += cost;
    if (decision.alias && !dry) {
      const put = await fetcher(`${site}/api/aliases`, {method: 'PUT', headers: owner, body: JSON.stringify({items: [decision.alias], source: 'proposer',
        status: decision.action === 'canary' ? 'canary' : 'candidate', rollout: 5, note: (decision.why || `${target.installs} installs, ${target.n} times`).slice(0, 150)})});
      if (!put.ok) decision = {action: 'skip', why: `site refused: HTTP ${put.status}`};
    }
    summary[decision.action === 'skip' ? 'skipped' : decision.action]++;
    summary.results.push({label: target.label, installs: target.installs, action: decision.action, ...(decision.alias ? {alias: decision.alias} : {}), ...(decision.why ? {why: decision.why} : {}), cost: Number(cost.toFixed(5))});
    log(`"${target.label}"`, `${target.installs} installs`, decision.action, decision.alias ? `${decision.alias.key} <- "${decision.alias.phrase}"` : `(${decision.why})`, `$${cost.toFixed(5)}`);
  }
  log(`done: ${summary.canary} canary, ${summary.candidate} candidate, ${summary.skipped} skipped, $${summary.spent.toFixed(4)} spent`);
  return summary;
}

if (import.meta.url === pathToFileURL(process.argv[1] || '').href) {
  const args = process.argv.slice(2);
  const option = (name, fallback = '') => { const i = args.indexOf(`--${name}`); return i >= 0 && args[i + 1] ? args[i + 1] : fallback; };
  const dir = option('extension');
  if (!dir || !fs.existsSync(path.join(dir, 'alias-schema.js'))) { console.error('Pass --extension <the public repo\'s extension/ folder>.'); process.exit(2); }
  const schema = await import(pathToFileURL(path.resolve(dir, 'alias-schema.js')).href);
  const ownerKey = process.env.LAB_KEY, apiKey = process.env.ANTHROPIC_API_KEY;
  if (!ownerKey || !apiKey) { console.error('LAB_KEY and ANTHROPIC_API_KEY are needed.'); process.exit(2); }
  const summary = await run({site: option('site', SITE).replace(/\/$/, ''), ownerKey, apiKey, max: Number(option('max', '25')) || 25,
    budget: Number(option('budget', '0.3')) || 0.3, dry: args.includes('--dry'), schema});
  if (option('out')) fs.writeFileSync(option('out'), JSON.stringify(summary, null, 2));
}
