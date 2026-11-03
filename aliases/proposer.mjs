#!/usr/bin/env node
// The alias proposer: for question wordings several installs report and no alias places, ask a small model which profile field each means,
// check it with a second pass and the shared validator, and file it on the site. Confirmed, non-sensitive aliases with enough independent
// reports start a 5% canary (the site grows or halts it from real outcomes); everything else waits as a candidate for the owner.
// Capped at --max questions and --budget dollars a run; every decision is logged (the wording is the form's public text, never user data).
//   node aliases/proposer.mjs --extension ../public/extension [--site URL] [--max 25] [--budget 0.3] [--dry] [--out result.json]
// Env: LAB_KEY, JOBADABRA_AI_BASE_URL (the AI broker relay: run behind public/desktop/e2e/broker-relay-run.mjs; no API key since 3 Nov 2026).
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {askMessages, relayUrl} from '../lib/messages.mjs';
import {AUTO_APPROVE, BUTTON_SYSTEM, BUTTON_VERIFY, MODEL, SYSTEM, UPLOAD_SYSTEM, UPLOAD_VERIFY, VERIFY, askMessage, buttonMessage, costUsd, decide, decideButton, decideUpload, parseJson, uploadMessage, verifyMessage} from './aliases-lib.mjs';

const SITE = 'https://www.jobadabra.top';
const log = (...parts) => console.log(`[aliases] ${parts.join(' ')}`);

async function ask(fetcher, system, content) {
  // As the recipe proposer (7f6bb32): Haiku 5.5 rejects temperature (400) and thinks first, so room for that and the text block is read
  // (9 Oct 2026: every alias call failed with Anthropic 400 once the learner had targets to ask about).
  const body = JSON.stringify({model: MODEL, max_tokens: 1500, output_config: {effort: 'low'}, system, messages: [{role: 'user', content}]});
  return askMessages(fetcher, body);
}

export async function run({site = SITE, ownerKey, max = 25, budget = 0.3, dry = false, schema, fetcher = fetch}) {
  const owner = {Authorization: `Bearer ${ownerKey}`, 'content-type': 'application/json'};
  const list = async mode => {
    const listed = await fetcher(`${site}/api/aliases?targets=${mode}`, {headers: owner});
    if (!listed.ok) throw new Error(`targets: HTTP ${listed.status}`);
    return listed.json();
  };
  const questions = await list('1'), buttons = await list('buttons'), uploads = await list('uploads').catch(() => ({targets: []})), fixes = await list('fixes').catch(() => ({targets: []}));
  const summary = {considered: 0, canary: 0, candidate: 0, skipped: 0, spent: 0, results: []};
  const reviewed = [];
  log(`${questions.targets?.length || 0} question(s) and ${buttons.targets?.length || 0} button text(s) without a meaning, ${fixes.targets?.length || 0} answer(s) people keep changing, budget $${budget}${dry ? ' (dry: nothing is filed)' : ''}`);
  const work = [...(questions.targets || []).map(target => ({target, kind: 'question'})), ...(buttons.targets || []).map(target => ({target, kind: 'button'})), ...(uploads.targets || []).map(target => ({target, kind: 'upload'})),
    ...(fixes.targets || []).map(target => ({target: {...target, installs: 3}, kind: 'question', fix: true}))].slice(0, max);
  for (const {target, kind, fix} of work) {
    if (summary.spent >= budget) { log(`budget reached at $${summary.spent.toFixed(4)}: stopping`); break; }
    summary.considered++;
    let decision, cost = 0;
    try {
      if (kind === 'upload') {
        const first = await ask(fetcher, UPLOAD_SYSTEM, uploadMessage(target));
        cost += costUsd(first.usage);
        const proposal = parseJson(first.text);
        let verdict = null;
        if (['resume', 'cover_letter'].includes(proposal?.file)) {
          const second = await ask(fetcher, UPLOAD_VERIFY, uploadMessage(target, proposal.file));
          cost += costUsd(second.usage);
          verdict = parseJson(second.text);
        }
        decision = decideUpload({target, proposal, verdict, validateAlias: schema.validateAlias});
      } else if (kind === 'button') {
        const first = await ask(fetcher, BUTTON_SYSTEM, buttonMessage(target));
        cost += costUsd(first.usage);
        const proposal = parseJson(first.text);
        let verdict = null;
        if (proposal?.apply === true) {
          const second = await ask(fetcher, BUTTON_VERIFY, buttonMessage(target));
          cost += costUsd(second.usage);
          verdict = parseJson(second.text);
        }
        decision = decideButton({target, proposal, verdict, validateAlias: schema.validateAlias});
      } else {
        const first = await ask(fetcher, SYSTEM, askMessage(target));
        cost += costUsd(first.usage);
        const proposal = parseJson(first.text);
        let verdict = null;
        if (proposal && !proposal.none && proposal.key) {
          const second = await ask(fetcher, VERIFY, verifyMessage(target, proposal.key));
          cost += costUsd(second.usage);
          verdict = parseJson(second.text);
        }
        decision = decide({target, proposal, verdict, sensitive: questions.sensitive || [], validateAlias: schema.validateAlias, aliasKey: schema.aliasKey});
      }
    } catch (error) { decision = {action: 'skip', why: `error: ${error.message}`}; }
    summary.spent += cost;
    // A wording people keep correcting is only ever a candidate for the owner, never a canary; and the same meaning as today's is a value-format matter, not a mapping one.
    if (fix && decision.alias) decision = decision.alias.key === target.current ? {action: 'skip', why: `same field as now (${target.current}): the value, not the mapping, is what people change`}
      : {...decision, action: 'candidate', why: `${target.corrected} of ${target.n} fills were changed by hand (was: ${target.current || 'no alias'})`};
    if (fix && !decision.alias) reviewed.push({label: target.label});
    if (decision.action === 'skip' && /^(model:|invalid alias|the phrase is not)/.test(decision.why || '')) reviewed.push({label: target.label});   // not looked at again for a month
    if (decision.alias && !dry) {
      const put = await fetcher(`${site}/api/aliases`, {method: 'PUT', headers: owner, body: JSON.stringify({items: [decision.alias], source: 'proposer',
        status: decision.action === 'canary' ? 'canary' : 'candidate', rollout: 5, ...(decision.action === 'canary' && AUTO_APPROVE() ? {approved: true} : {}), note: (decision.why || `${target.installs} installs, ${target.n} times`).slice(0, 150)})});
      if (!put.ok) decision = {action: 'skip', why: `site refused: HTTP ${put.status}`};
    }
    summary[decision.action === 'skip' ? 'skipped' : decision.action]++;
    summary.results.push({kind, label: target.label, installs: target.installs, action: decision.action, ...(decision.alias ? {alias: decision.alias} : {}), ...(decision.why ? {why: decision.why} : {}), cost: Number(cost.toFixed(5))});
    log(kind, `"${target.label}"`, `${target.installs} installs`, decision.action, decision.alias ? `${decision.alias.key} <- "${decision.alias.phrase}"` : `(${decision.why})`, `$${cost.toFixed(5)}`);
  }
  if (reviewed.length && !dry) await fetcher(`${site}/api/aliases`, {method: 'PUT', headers: owner, body: JSON.stringify({reviewed})}).catch(() => {});
  log(`done: ${summary.canary} canary, ${summary.candidate} candidate, ${summary.skipped} skipped, $${summary.spent.toFixed(4)} spent`);
  return summary;
}

if (import.meta.url === pathToFileURL(process.argv[1] || '').href) {
  const args = process.argv.slice(2);
  const option = (name, fallback = '') => { const i = args.indexOf(`--${name}`); return i >= 0 && args[i + 1] ? args[i + 1] : fallback; };
  const dir = option('extension');
  if (!dir || !fs.existsSync(path.join(dir, 'alias-schema.js'))) { console.error('Pass --extension <the public repo\'s extension/ folder>.'); process.exit(2); }
  const schema = await import(pathToFileURL(path.resolve(dir, 'alias-schema.js')).href);
  const ownerKey = process.env.LAB_KEY;
  if (!ownerKey) { console.error('LAB_KEY is needed.'); process.exit(2); }
  try { relayUrl(); } catch (error) { console.error(error.message); process.exit(2); }
  const summary = await run({site: option('site', SITE).replace(/\/$/, ''), ownerKey, max: Number(option('max', '25')) || 25,
    budget: Number(option('budget', '0.3')) || 0.3, dry: args.includes('--dry'), schema});
  if (option('out')) fs.writeFileSync(option('out'), JSON.stringify(summary, null, 2));
}
