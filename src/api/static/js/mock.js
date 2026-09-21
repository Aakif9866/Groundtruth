// Mock backend with the same response shapes as the real API. Used with ?mock=1.
// Try: a question containing "error" fails with a 500, one containing "slow" takes 3s.
import { ApiError } from './lib/errors.js';

const PASSAGES = [
  { passage_id: 'rw002', doc_type: 'opinion', title: 'Miranda v. Arizona, 384 U.S. 436 (1966)',
    text: 'Miranda v. Arizona, 384 U.S. 436 (1966).\n\nHe must be warned prior to any questioning that he has the right to remain silent, that anything he says can be used against him in a court of law, that he has the right to the presence of an attorney, and that if he cannot afford an attorney one will be appointed for him prior to any questioning if he so desires.' },
  { passage_id: 'rw003', doc_type: 'opinion', title: 'Katz v. United States, 389 U.S. 347 (1967)',
    text: 'Katz v. United States, 389 U.S. 347 (1967).\n\nFor the Fourth Amendment protects people, not places. But what he seeks to preserve as private, even in an area accessible to the public, may be constitutionally protected.' },
  { passage_id: 'rw007', doc_type: 'opinion', title: 'Daubert v. Merrell Dow Pharmaceuticals, Inc., 509 U.S. 579 (1993)',
    text: "Daubert v. Merrell Dow Pharmaceuticals, Inc., 509 U.S. 579 (1993).\n\nthe trial judge, pursuant to Rule 104(a), must make a preliminary assessment of whether the testimony's underlying reasoning or methodology is scientifically valid" },
  { passage_id: 'rw009', doc_type: 'statute', title: 'Federal Rule of Evidence 702',
    text: "Rule 702. Testimony by Expert Witnesses. A witness who is qualified as an expert by knowledge, skill, experience, training, or education may testify in the form of an opinion or otherwise if the proponent demonstrates to the court that it is more likely than not that: (a) the expert's scientific, technical, or other specialized knowledge will help the trier of fact to understand the evidence or to determine a fact in issue; (b) the testimony is based on sufficient facts or data; (c) the testimony is the product of reliable principles and methods; and (d) the expert's opinion reflects a reliable application of the principles and methods to the facts of the case." },
  { passage_id: 'rw011', doc_type: 'statute', title: '17 U.S.C. § 107 (Fair Use)',
    text: 'The factors to be considered include: (1) the purpose and character of the use; (2) the nature of the copyrighted work; (3) the amount and substantiality of the portion used; and (4) the effect of the use upon the potential market for or value of the copyrighted work.' },
];

const EXAMPLES = [
  { query_id: 'rq002', category: 'precedent', query: 'What warnings must be given to a suspect before custodial questioning?' },
  { query_id: 'rq009', category: 'statute', query: 'What must the proponent demonstrate to the court before an expert may give opinion testimony?' },
  { query_id: 'rq010', category: 'statute', query: 'What are the four factors used to decide whether a use of a copyrighted work is fair?' },
  { query_id: 'rq017', category: 'multi_hop', query: 'How does the Supreme Court\'s gatekeeping standard for scientific testimony relate to the federal rule on expert witnesses?' },
];

const tokens = (s) => new Set(s.toLowerCase().match(/[a-z0-9]+/g) ?? []);
const wait = (ms, signal) => new Promise((resolve, reject) => {
  const t = setTimeout(resolve, ms);
  signal?.addEventListener('abort', () => { clearTimeout(t); reject(new ApiError('Request cancelled', { kind: 'aborted' })); });
});

function retrieval(payload) {
  const q = tokens(payload.query);
  const scored = PASSAGES
    .map((p) => ({ p, score: [...tokens(p.text + ' ' + p.title)].filter((t) => q.has(t)).length / (q.size || 1) }))
    .sort((a, b) => b.score - a.score)
    .slice(0, payload.top_k ?? 5);
  const results = scored.map(({ p, score }, i) => ({
    rank: i + 1, passage_id: p.passage_id, title: p.title, doc_type: p.doc_type,
    score: Number(score.toFixed(4)), snippet: p.text.slice(0, 240), text: p.text,
  }));
  const golden = EXAMPLES.find((e) => e.query === payload.query.trim());
  return {
    config: payload.config, dataset: payload.dataset, dataset_version: '1.0.0', score_type: 'cosine', results,
    ...(golden ? { golden_check: { query_id: golden.query_id, relevant_ranks: { [results[0]?.passage_id]: 1 }, all_relevant_retrieved: true } } : {}),
  };
}

function checkRequest(payload) {
  if (/error/i.test(payload.query)) throw new ApiError('Mock server error: the retriever failed to load its index.', { status: 500 });
}

export const mockApi = {
  isMock: true,
  async health(opts) {
    await wait(250, opts?.signal);
    return { status: 'ok', datasets: ['synthetic', 'real_world'], configs: ['baseline', 'broken', 'chunk_change', 'hybrid', 'reranker'] };
  },
  async examples(dataset, limit = 6, opts) {
    await wait(200, opts?.signal);
    return { dataset, examples: EXAMPLES.slice(0, limit) };
  },
  async retrieve(payload, opts) {
    await wait(500, opts?.signal);
    checkRequest(payload);
    return { retrieval: retrieval(payload) };
  },
  async ask(payload, opts) {
    await wait(/slow/i.test(payload.query) ? 3000 : 900, opts?.signal);
    checkRequest(payload);
    const block = retrieval(payload);
    const top = block.results.slice(0, 2);
    const answer = top.map((r, i) => `${r.text.split(/\n+/).pop().split('. ')[0].replace(/\.$/, '')}. [${i + 1}]`).join(' ');
    return {
      retrieval: block,
      generation: {
        answer, method: 'extractive (mock)',
        citations: top.map((r, i) => ({ passage_id: r.passage_id, source_number: i + 1 })),
        context_passage_ids: block.results.map((r) => r.passage_id),
        heuristic_metrics: { faithfulness: 1, answer_relevance: 0.62, context_relevance: 0.71 },
      },
    };
  },
  async evaluation(dataset, opts) {
    await wait(500, opts?.signal);
    const cats = { precedent: [1, 0.867, 0.901], statute: [1, 0.858, 0.895], procedural: [1, 0.756, 0.816], factual: [0.95, 0.683, 0.751], multi_hop: [0.975, 0.95, 0.932] };
    const mk = (r5, r10, mrr, ndcg, shift) => ({
      overall: { 'recall@5': r5, 'recall@10': r10, mrr, 'ndcg@10': ndcg },
      ...Object.fromEntries(Object.entries(cats).map(([c, [a, b, d]]) => [c, {
        'recall@5': a, 'recall@10': Math.min(1, a + shift), mrr: b + (mrr - 0.823), 'ndcg@10': d + (ndcg - 0.859),
      }])),
    });
    const details = (extra) => ({ chunk_size: 300, chunk_overlap: 50, retrieval_method: 'dense', embedding_model: 'sentence-transformers/all-MiniLM-L6-v2', reranker: 'off', candidate_pool: 'full', ...extra });
    const stat = (delta, lo, hi) => ({ delta, ci_low: lo, ci_high: hi, ci_level: 0.95, verdict: lo > 0 ? 'improvement: CI excludes 0' : hi < 0 ? 'regression: CI excludes 0' : 'inconclusive: CI includes 0' });
    return {
      summary: {
        dataset, dataset_version: dataset === 'synthetic' ? '1.1.0' : '1.0.0', query_count: dataset === 'synthetic' ? 100 : 19, baseline: 'baseline',
        configs: {
          baseline: { details: details({}), metrics: mk(0.975, 0.985, 0.823, 0.859, 0) },
          hybrid: { details: details({ retrieval_method: 'hybrid' }), metrics: mk(0.965, 1, 0.866, 0.896, 0.015) },
          reranker: { details: details({ reranker: 'cross-encoder/ms-marco-MiniLM-L-6-v2' }), metrics: mk(0.985, 0.995, 0.909, 0.928, 0.01) },
          broken: { details: details({ chunk_size: 40, chunk_overlap: 0, candidate_pool: 3 }), metrics: mk(0.015, 0.015, 0.02, 0.016, -0.97) },
        },
        stats: {
          hybrid: { 'recall@10': stat(0.015, 0, 0.04), mrr: stat(0.043, -0.001, 0.089), 'ndcg@10': stat(0.037, 0.004, 0.071) },
          reranker: { 'recall@10': stat(0.01, 0, 0.03), mrr: stat(0.086, 0.034, 0.14), 'ndcg@10': stat(0.069, 0.03, 0.109) },
          broken: { 'recall@10': stat(-0.97, -0.995, -0.935), mrr: stat(-0.803, -0.86, -0.742), 'ndcg@10': stat(-0.843, -0.888, -0.794) },
        },
        failures: {
          baseline: [{ type: 'semantic_mismatch', count: 12, percent: 40 }, { type: 'chunk_boundary', count: 8, percent: 26.7 }, { type: 'ranking_failure', count: 6, percent: 20 }],
          hybrid: [{ type: 'semantic_mismatch', count: 8, percent: 36.4 }, { type: 'ranking_failure', count: 8, percent: 36.4 }],
          reranker: [{ type: 'ranking_failure', count: 9, percent: 60 }],
          broken: [{ type: 'candidate_pool_limitation', count: 98, percent: 100 }],
        },
      },
      gate: dataset === 'synthetic' ? {
        baseline_recall10: 0.985, threshold: 0.01, dataset_version: '1.1.0',
        results: { baseline: { passed: true, drop: 0 }, hybrid: { passed: true, drop: 0.015 }, reranker: { passed: true, drop: 0.01 }, broken: { passed: false, drop: -0.97 } },
      } : null,
    };
  },
};
