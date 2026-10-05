// The weekly form-learning pass (digest/propose.mjs): what the model sees, which of its proposals are kept, and the issue it files.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {MARK, brief, issueBody, proposals} from './propose.mjs';

const digest = {period: {from: '2026-10-06', to: '2026-10-12'}, thisWeek: {forms: 4}, lastWeek: {forms: 3}, versions: [], boards: [],
  weaknesses: [{id: 'cause:no_data:ashby', impact: 9, title: 'no_data on ashby: 3 required questions on 3 of 4 forms', area: 'data: …',
    byVersion: [{version: '0.8.97', per100: 7.5, forms: 4}]}, {id: 'lab:lev123abc', impact: 1, title: 'The lab could not read "Pronouns" on lever', area: 'reader: …',
    evidence: {page: 'https://jobs.lever.co/x/1/apply'}}]};

test('only proposals that cite the digest\'s own weaknesses, with a known area, are kept; at most three', () => {
  const answer = `Here: {"proposals": [
    {"weaknesses": ["cause:no_data:ashby"], "title": "Ask for notice period at setup", "area": "data", "change": "Add it.", "evidence": "9", "verify": "digest", "confidence": "high"},
    {"weaknesses": ["made-up"], "title": "Invented", "area": "data", "change": "x"},
    {"weaknesses": ["lab:lev123abc", "nope"], "title": "Read Lever titles", "area": "reader", "change": "y", "confidence": "sure"},
    {"weaknesses": ["lab:lev123abc"], "title": "Bad area", "area": "magic", "change": "z"}]}`;
  const kept = proposals(answer, digest);
  assert.deepEqual(kept.map(p => [p.title, p.weaknesses, p.confidence]), [['Ask for notice period at setup', ['cause:no_data:ashby'], 'high'], ['Read Lever titles', ['lab:lev123abc'], 'low']]);
  assert.deepEqual(proposals('not json', digest), []);
});

test('the issue quotes the digest\'s lines for its weaknesses and carries a marker to update instead of repeating', () => {
  const body = issueBody({weaknesses: ['lab:lev123abc'], title: 'Read Lever titles', area: 'reader', change: 'y', evidence: 'e', verify: 'v', confidence: 'medium'}, digest);
  assert.match(body, /`lab:lev123abc` · impact 1 · .*page: https:\/\/jobs\.lever\.co/);
  assert.ok(body.endsWith(MARK('lab:lev123abc')));
});

test('the model sees the top weaknesses and the week, nothing else', () => {
  const seen = JSON.parse(brief({...digest, daily: [{day: 'x'}], notes: ['n']}));
  assert.deepEqual(Object.keys(seen), ['period', 'thisWeek', 'lastWeek', 'versions', 'boards', 'weaknesses']);
});

test('a proposal that breaks a hard rule (submitting, ticking consents) is dropped', () => {
  const answer = JSON.stringify({proposals: [
    {weaknesses: ['cause:no_data:ashby'], title: 'Auto-check confirmation checkboxes with smart matching', area: 'operator', change: 'Tick them.'},
    {weaknesses: ['cause:no_data:ashby'], title: 'Ask for notice period', area: 'data', change: 'Add a profile field.'}]});
  assert.deepEqual(proposals(answer, digest).map(p => p.title), ['Ask for notice period']);
});
