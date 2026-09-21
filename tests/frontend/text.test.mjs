// Run with: node --test tests/frontend
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  validateQuestion, parseInline, parseAnswer, citedNumbers, formatRelativeTime, formatMetric, formatDelta, humanize, truncate,
} from '../../src/api/static/js/lib/text.js';

test('validateQuestion rejects empty, short and long input and normalizes whitespace', () => {
  assert.equal(validateQuestion('   ').ok, false);
  assert.equal(validateQuestion('hi').ok, false);
  assert.equal(validateQuestion('x'.repeat(1001)).ok, false);
  const ok = validateQuestion('  What   is\nfair use? ');
  assert.deepEqual([ok.ok, ok.value], [true, 'What is fair use?']);
  assert.equal(validateQuestion(null).ok, false);
});

test('parseInline finds citations and bold, and leaves other brackets alone', () => {
  assert.deepEqual(parseInline('See **Miranda** [1] and [a]'), [
    { type: 'text', value: 'See ' }, { type: 'bold', value: 'Miranda' }, { type: 'text', value: ' ' },
    { type: 'cite', n: 1 }, { type: 'text', value: ' and [a]' },
  ]);
});

test('parseAnswer builds paragraphs and lists and never yields HTML', () => {
  const blocks = parseAnswer('First line\ncontinues.\n\n- one [1]\n- two\n\n<script>alert(1)</script>');
  assert.equal(blocks.length, 3);
  assert.equal(blocks[0].type, 'p');
  assert.equal(blocks[1].type, 'ul');
  assert.equal(blocks[1].items.length, 2);
  assert.equal(blocks[2].parts[0].value, '<script>alert(1)</script>'); // kept as text; the UI uses textContent
  assert.deepEqual(parseAnswer(''), []);
});

test('citedNumbers returns unique numbers in order', () => {
  assert.deepEqual(citedNumbers('a [2] b [1] c [2]'), [2, 1]);
  assert.deepEqual(citedNumbers(undefined), []);
});

test('formatRelativeTime', () => {
  const now = 1_000_000_000;
  assert.equal(formatRelativeTime(now - 10_000, now), 'just now');
  assert.equal(formatRelativeTime(now - 5 * 60_000, now), '5 min ago');
  assert.equal(formatRelativeTime(now - 3 * 3_600_000, now), '3 h ago');
  assert.equal(formatRelativeTime(now - 86_400_000, now), 'yesterday');
  assert.equal(formatRelativeTime(now - 4 * 86_400_000, now), '4 days ago');
});

test('formatMetric and formatDelta use a real minus sign and handle non-numbers', () => {
  assert.equal(formatMetric(0.98512), '0.985');
  assert.equal(formatMetric(NaN), '—');
  assert.equal(formatDelta(0.015), '+0.015');
  assert.equal(formatDelta(-0.97), '−0.970');
  assert.equal(formatDelta(-0.0001), '0.000');
  assert.equal(formatDelta(undefined), '—');
});

test('humanize and truncate', () => {
  assert.equal(humanize('semantic_mismatch'), 'Semantic mismatch');
  assert.equal(truncate('abcdefghij', 5), 'abcd…');
  assert.equal(truncate('abc', 5), 'abc');
});
