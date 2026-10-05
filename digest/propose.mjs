#!/usr/bin/env node
// Weekly: read the form-filling learning digest (the site's /admin/form-filling/digest.json: efficiency per day and release, and
// weaknesses ranked by impact with their evidence) and ask a small model for the top 3 improvements. Each proposal must cite the
// digest's own weakness ids (anything else is dropped), say the area of the fix and how to prove it; it is filed as an issue
// here (label form-learning), and a proposal already open for the same weaknesses is updated instead of repeated.
// One call, capped at --budget dollars. The digest holds counts and the forms' public wording only (no user data).
//   node digest/propose.mjs [--site URL] [--budget 0.05] [--out result.json] [--dry]      env: LAB_KEY, ANTHROPIC_API_KEY, GH_TOKEN
import {execFileSync} from 'node:child_process';
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
import {MODEL, costUsd} from '../proposer/proposer-lib.mjs';

export const SYSTEM = `You improve a browser extension that fills job application forms for its user. Each week you get its learning digest:
how well it filled forms (per day, per release, per job board) and its weaknesses ranked by impact, each with an id, the area a fix belongs
to, counts this week and last, the rate per release, and evidence (a question's public wording, a public form page, a widget's kind).
Propose the 3 changes that would remove the most lost questions next week. Prefer the highest impact; prefer a fix that helps many boards;
say when a weakness is already improving in the latest release (then propose something else). Never invent numbers or ids.
Answer with JSON only: {"proposals": [{"weaknesses": ["<id>", ...], "title": "<imperative, under 70 chars>", "area": "reader|data|AI|AI availability|operator|validation",
"change": "<what to change, concretely, 2-4 sentences>", "evidence": "<the numbers from the digest that justify it>",
"verify": "<how to prove it: a replay fixture, a lab page, the digest number that must move>", "confidence": "high|medium|low"}]}`;

export const AREAS = ['reader', 'data', 'AI', 'AI availability', 'operator', 'validation'];
export const MARK = id => `<!-- form-learning:${id} -->`;

// The part of the digest the model sees: the week's numbers, releases, and the top weaknesses with their evidence.
export function brief(digest, top = 12) {
  return JSON.stringify({period: digest.period, thisWeek: digest.thisWeek, lastWeek: digest.lastWeek, versions: (digest.versions || []).slice(-6),
    boards: (digest.boards || []).slice(0, 8), weaknesses: (digest.weaknesses || []).slice(0, top)}, null, 1);
}

// The model's answer, kept only where it holds: known weakness ids, a known area, the fields filled in; at most 3.
export function proposals(text, digest) {
  let parsed = null;
  try { parsed = JSON.parse(String(text).replace(/^[^{]*/, '').replace(/[^}]*$/, '')); } catch { return []; }
  const known = new Set((digest.weaknesses || []).map(w => w.id));
  return (Array.isArray(parsed?.proposals) ? parsed.proposals : []).map(p => ({...p, weaknesses: (Array.isArray(p?.weaknesses) ? p.weaknesses : []).filter(id => known.has(id))}))
    .filter(p => p.weaknesses.length && AREAS.includes(p.area) && typeof p.title === 'string' && p.title.trim() && typeof p.change === 'string')
    .slice(0, 3).map(p => ({weaknesses: p.weaknesses, title: p.title.trim().slice(0, 90), area: p.area, change: String(p.change).slice(0, 1200),
      evidence: String(p.evidence || '').slice(0, 800), verify: String(p.verify || '').slice(0, 600), confidence: ['high', 'medium', 'low'].includes(p.confidence) ? p.confidence : 'low'}));
}

// The issue for a proposal: the change, its evidence, the digest's own lines for each weakness, and how to prove it.
export function issueBody(p, digest) {
  const lines = p.weaknesses.map(id => digest.weaknesses.find(w => w.id === id)).filter(Boolean).map(w =>
    `- \`${w.id}\` · impact ${w.impact} · ${w.title}${w.byVersion?.length ? ` · per release: ${w.byVersion.map(v => `${v.version} ${v.per100 ?? '–'}`).join(', ')}` : ''}${w.evidence?.page ? ` · page: ${w.evidence.page}` : ''}`);
  return [`**Area:** ${p.area} · **confidence:** ${p.confidence} · digest ${digest.period.from} → ${digest.period.to}`, '', `## Change`, p.change, '',
    `## Evidence`, p.evidence, '', ...lines, '', `## How to prove it`, p.verify,
    '', 'A reading failure gets a replay fixture first (public repo: `node tools/fill-fixture.mjs <triage issue> --repo GarryOne/job-pilotto-internal`), red until fixed.',
    '', `_Proposed by the weekly form-learning pass (${MODEL}); a person decides._`, '', MARK(p.weaknesses.slice().sort().join('|'))].join('\n');
}

async function ask(apiKey, digest, fetcher = fetch) {
  const body = JSON.stringify({model: MODEL, max_tokens: 1500, temperature: 0, system: SYSTEM, messages: [{role: 'user', content: brief(digest)}]});
  for (let attempt = 0; attempt < 2; attempt++) {
    const response = await fetcher('https://api.anthropic.com/v1/messages', {method: 'POST', body,
      headers: {'x-api-key': apiKey, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'}});
    if (response.ok) { const data = await response.json(); return {text: data.content?.[0]?.text || '', usage: data.usage || {}}; }
    if (![429, 500, 502, 503, 529].includes(response.status)) throw new Error(`Anthropic ${response.status}`);
    await new Promise(resolve => setTimeout(resolve, 2000));
  }
  throw new Error('Anthropic busy');
}

const gh = (...args) => execFileSync('gh', args, {encoding: 'utf8'});
function file(p, digest, repo, dry) {
  const marker = MARK(p.weaknesses.slice().sort().join('|')), body = issueBody(p, digest);
  if (dry) return `[dry] ${p.title}`;
  const open = JSON.parse(gh('issue', 'list', '--repo', repo, '--label', 'form-learning', '--state', 'open', '--json', 'number,body', '--limit', '100'));
  const same = open.find(issue => issue.body.includes(marker));
  if (same) { gh('issue', 'comment', String(same.number), '--repo', repo, '--body', `Still a top weakness this week.\n\n${body}`); return `updated #${same.number}: ${p.title}`; }
  try { gh('label', 'create', 'form-learning', '--repo', repo, '--color', '5319e7', '--description', 'Weekly form-filling improvement proposal'); } catch { /* exists */ }
  return `new: ${gh('issue', 'create', '--repo', repo, '--title', p.title, '--label', 'form-learning', '--body', body).trim()}`;
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  const args = process.argv.slice(2), option = (name, fallback) => { const i = args.indexOf(`--${name}`); return i >= 0 ? args[i + 1] : fallback; };
  const site = option('site', 'https://www.jobpilotto.workers.dev'), dry = args.includes('--dry'), budget = Number(option('budget', '0.05'));
  const repo = process.env.GITHUB_REPOSITORY || 'GarryOne/job-pilotto-internal';
  const result = {usd: 0, calls: 0, proposals: [], filed: []};
  const save = () => option('out') && fs.writeFileSync(option('out'), JSON.stringify(result, null, 1));
  const response = await fetch(`${site}/admin/form-filling/digest.json`, {headers: {Authorization: `Bearer ${process.env.LAB_KEY}`, 'User-Agent': 'job-pilotto-internal-form-learning'}});
  if (!response.ok) { console.log(`digest: HTTP ${response.status}`); save(); process.exit(1); }
  const digest = await response.json();
  console.log(`digest ${digest.period.from} → ${digest.period.to}: ${digest.thisWeek.forms} forms, ${digest.weaknesses.length} weaknesses`);
  if (!digest.weaknesses.length) { console.log('Nothing ranked: no model call.'); save(); process.exit(0); }
  const {text, usage} = await ask(process.env.ANTHROPIC_API_KEY, digest);
  result.usd = costUsd(usage); result.calls = 1;
  if (result.usd > budget) console.log(`::warning::one call cost $${result.usd.toFixed(4)}, above the $${budget} budget`);
  result.proposals = proposals(text, digest);
  console.log(`${result.proposals.length} proposal(s), $${result.usd.toFixed(4)}`);
  for (const p of result.proposals) { const line = file(p, digest, repo, dry); result.filed.push(line); console.log(line); }
  save();
}
