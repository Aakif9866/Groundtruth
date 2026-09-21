// Pure helpers (no DOM). Kept separate so they can be unit-tested with `node --test`.

export const QUESTION_MIN = 3;
export const QUESTION_MAX = 1000;

/** Validate a question. Returns { ok, value, message }. */
export function validateQuestion(raw, { min = QUESTION_MIN, max = QUESTION_MAX } = {}) {
  const value = String(raw ?? '').replace(/\s+/g, ' ').trim();
  if (!value) return { ok: false, value, message: 'Enter a question to search the corpus.' };
  if (value.length < min) return { ok: false, value, message: `Use at least ${min} characters.` };
  if (value.length > max) return { ok: false, value, message: `Keep it under ${max} characters (currently ${value.length}).` };
  return { ok: true, value, message: '' };
}

const INLINE = /(\*\*[^*]+\*\*|\[\d+\])/g;

/** Split a line of text into inline parts: plain text, **bold**, and [n] citations. */
export function parseInline(line) {
  const parts = [];
  for (const piece of String(line).split(INLINE)) {
    if (!piece) continue;
    const cite = /^\[(\d+)\]$/.exec(piece);
    if (cite) parts.push({ type: 'cite', n: Number(cite[1]) });
    else if (piece.startsWith('**') && piece.endsWith('**') && piece.length > 4) parts.push({ type: 'bold', value: piece.slice(2, -2) });
    else parts.push({ type: 'text', value: piece });
  }
  return parts;
}

/**
 * Parse model output into blocks: paragraphs and bullet lists. Deliberately small:
 * it supports what answers actually contain, and nothing is ever inserted as raw HTML.
 */
export function parseAnswer(text) {
  const blocks = [];
  let list = null;
  let para = [];
  const flushPara = () => { if (para.length) { blocks.push({ type: 'p', parts: parseInline(para.join(' ')) }); para = []; } };
  const flushList = () => { if (list) { blocks.push({ type: 'ul', items: list }); list = null; } };

  for (const raw of String(text ?? '').split('\n')) {
    const line = raw.trim();
    const bullet = /^[-*•]\s+(.*)$/.exec(line);
    if (!line) { flushPara(); flushList(); }
    else if (bullet) { flushPara(); (list ??= []).push(parseInline(bullet[1])); }
    else { flushList(); para.push(line); }
  }
  flushPara();
  flushList();
  return blocks;
}

/** Citation numbers referenced anywhere in the text, in order of first appearance. */
export function citedNumbers(text) {
  const seen = [];
  for (const m of String(text ?? '').matchAll(/\[(\d+)\]/g)) {
    const n = Number(m[1]);
    if (!seen.includes(n)) seen.push(n);
  }
  return seen;
}

export function formatRelativeTime(ts, now = Date.now()) {
  const s = Math.max(0, Math.round((now - ts) / 1000));
  if (s < 45) return 'just now';
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h} h ago`;
  const d = Math.round(h / 24);
  return d === 1 ? 'yesterday' : `${d} days ago`;
}

export function formatMetric(value, digits = 3) {
  return Number.isFinite(value) ? value.toFixed(digits) : '—';
}

/** Signed value with a real minus sign, e.g. +0.015 / −0.970. */
export function formatDelta(value, digits = 3) {
  if (!Number.isFinite(value)) return '—';
  const rounded = Number(value.toFixed(digits));
  if (rounded === 0) return (0).toFixed(digits);
  return (rounded > 0 ? '+' : '−') + Math.abs(rounded).toFixed(digits);
}

export function humanize(snake) {
  const s = String(snake ?? '').replace(/_/g, ' ');
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function truncate(text, max) {
  const s = String(text ?? '');
  return s.length <= max ? s : s.slice(0, max - 1).trimEnd() + '…';
}
