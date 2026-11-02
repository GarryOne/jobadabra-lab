#!/usr/bin/env node
// The owner's decision on an alias that waits as a candidate (a sensitive field, or too few reports): start its canary, or disable it.
//   LAB_KEY=… node aliases/approve.mjs --phrase "ort der herkunft" --status canary [--rollout 5] [--approve]   (sensitive fields need --approve)
//   LAB_KEY=… node aliases/approve.mjs --list                                                                    (the candidates waiting)
const SITE = 'https://www.jobadabra.top';

export async function decide({site = SITE, ownerKey, phrase, status, rollout = 5, approved = false, fetcher = fetch}) {
  const owner = {Authorization: `Bearer ${ownerKey}`, 'content-type': 'application/json'};
  const listed = await fetcher(`${site}/api/aliases`, {headers: owner});
  if (!listed.ok) return {ok: false, error: `list: HTTP ${listed.status}`};
  const found = ((await listed.json()).aliases || []).find(item => item.phrase === String(phrase).toLowerCase().trim());
  if (!found) return {ok: false, error: `no alias "${phrase}"`};
  if (!['canary', 'verified', 'disabled'].includes(status)) return {ok: false, error: 'status must be canary, verified or disabled'};
  const put = await fetcher(`${site}/api/aliases`, {method: 'PUT', headers: owner, body: JSON.stringify({items: [{key: found.key, phrase: found.phrase}], status, rollout, approved, source: 'owner', note: 'owner decision'})});
  const body = await put.json().catch(() => ({}));
  return put.ok && body.stored ? {ok: true, key: found.key, status} : {ok: false, error: (body.refused || [`HTTP ${put.status}`]).join(', ')};
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].split('/').pop())) {
  const args = process.argv.slice(2);
  const option = (name, fallback = '') => { const i = args.indexOf(`--${name}`); return i >= 0 && args[i + 1] ? args[i + 1] : fallback; };
  const ownerKey = process.env.LAB_KEY;
  if (!ownerKey) { console.error('LAB_KEY is needed.'); process.exit(2); }
  const site = option('site', SITE).replace(/\/$/, '');
  if (args.includes('--list')) {
    const body = await (await fetch(`${site}/api/aliases?status=candidate`, {headers: {Authorization: `Bearer ${ownerKey}`}})).json();
    for (const item of body.aliases || []) console.log(`${item.key.padEnd(16)} "${item.phrase}"  (${item.note || item.source})`);
    process.exit(0);
  }
  const result = await decide({site, ownerKey, phrase: option('phrase'), status: option('status'), rollout: Number(option('rollout', '5')) || 5, approved: args.includes('--approve')});
  console.log(result.ok ? `[aliases] "${option('phrase')}" -> ${result.status}` : `[aliases] refused: ${result.error}`);
  process.exit(result.ok ? 0 : 1);
}
