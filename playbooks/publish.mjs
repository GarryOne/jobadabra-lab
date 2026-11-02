#!/usr/bin/env node
// Publishes the private playbooks to the site (PUT /api/playbook, one board per file): playbooks/apply/<board>.md is what a Claude
// application session reads for that board, delivered by the public engine's `apply_run --context`. Run by playbooks.yml on every change.
//   LAB_KEY=… node playbooks/publish.mjs [--site URL] [--dry]
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const dir = path.join(path.dirname(fileURLToPath(import.meta.url)), 'apply');
const args = process.argv.slice(2);
const option = (name, fallback) => { const i = args.indexOf(`--${name}`); return i >= 0 && args[i + 1] ? args[i + 1] : fallback; };
const site = option('site', 'https://www.jobadabra.top').replace(/\/$/, '');
const dry = args.includes('--dry');
const key = process.env.LAB_KEY;
if (!key && !dry) { console.error('LAB_KEY is needed.'); process.exit(2); }

let failed = 0;
for (const file of fs.readdirSync(dir).filter(name => name.endsWith('.md')).sort()) {
  const board = file.replace(/\.md$/, ''), text = fs.readFileSync(path.join(dir, file), 'utf8');
  if (dry) { console.log(`[playbooks] ${board}: ${text.length} chars (dry)`); continue; }
  const response = await fetch(`${site}/api/playbook`, {method: 'PUT', headers: {Authorization: `Bearer ${key}`, 'content-type': 'application/json'}, body: JSON.stringify({board, text})});
  console.log(`[playbooks] ${board}: ${text.length} chars -> HTTP ${response.status}`);
  if (!response.ok) failed++;
}
process.exit(failed ? 1 : 0);
