// One Messages call for the lab's AI jobs (recipe proposer, alias proposer, form learning), answered by the AI broker through the local relay.
// Why (3 Nov 2026, owner: "We should not use API Keys at all anymore. Everything should be around the ai-broker"): these three jobs called api.anthropic.com with ANTHROPIC_API_KEY. Each workflow now
// runs its script behind the public repo's relay (`node public/desktop/e2e/broker-relay-run.mjs --job <name> --cap <calls> -- node <script>`), which sets JOBADABRA_AI_BASE_URL and answers on the Codex plan
// (the scheduled lane: it stops at 70% of the Codex week, web #348; a refusal is final for the run). No key, no api.anthropic.com, no fallback: without the relay the job stops and says so.
// Why no retry (3 Nov 2026): a broker "no" (cap, login, down) is final for the run (the relay answers it with `x-should-retry: false`, and the repo rule is never to retry a 429); the next scheduled run asks again.
// Guard: lib/messages.test.mjs (also: no lab workflow or script names an Anthropic key).

/** The relay's Messages address, or a thrown reason when the job was not started behind the relay. */
export function relayUrl(env = process.env) {
  const base = String(env.JOBADABRA_AI_BASE_URL || '').replace(/\/$/, '');
  if (!base) throw new Error('JOBADABRA_AI_BASE_URL is not set: start this job behind public/desktop/e2e/broker-relay-run.mjs (the AI broker relay)');
  return `${base}/v1/messages`;
}

/** Takes a fetch and a Messages request body (a JSON string); returns {text, usage} of the answer, or throws "AI broker <status>". */
export async function askMessages(fetcher, body, env = process.env) {
  const response = await fetcher(relayUrl(env), {method: 'POST', body, headers: {'content-type': 'application/json'}});
  if (!response.ok) throw new Error(`AI broker ${response.status}`);
  const data = await response.json();
  return {text: data.content?.find(block => block.type === 'text')?.text || '', usage: data.usage || {}};
}
