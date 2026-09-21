// "Evaluation" view: compare retrieval configurations, see confidence intervals, gate status and failure types.
import { h, icon, clear } from '../dom.js';
import { api } from '../api.js';
import { formatMetric, formatDelta, humanize } from '../lib/text.js';

const METRICS = [
  { key: 'recall@10', label: 'Recall@10' },
  { key: 'mrr', label: 'MRR' },
  { key: 'ndcg@10', label: 'nDCG@10' },
  { key: 'recall@5', label: 'Recall@5' },
];
const DATASET_TABS = [{ key: 'synthetic', label: 'Synthetic' }, { key: 'real_world', label: 'Real-world' }];
const CATEGORIES = ['precedent', 'statute', 'procedural', 'factual', 'multi_hop'];

const READING = {
  improvement: { label: 'Improvement', cls: 'tag--ok' },
  regression: { label: 'Regression', cls: 'tag--bad' },
  inconclusive: { label: 'Inconclusive', cls: '' },
};
const readingOf = (verdict) => READING[String(verdict).split(':')[0]] ?? READING.inconclusive;

export function createEvaluationView() {
  const state = { dataset: 'synthetic', metric: 'recall@10', selected: null, cache: new Map(), loading: false };
  const body = h('div', { class: 'eval__body' });
  const el = h('section', { class: 'view eval', 'aria-label': 'Evaluation' }, h('div', { class: 'view__inner' }, body));

  function segmented(options, current, onPick, label) {
    return h('div', { class: 'seg', role: 'group', 'aria-label': label },
      options.map((o) => h('button', { type: 'button', 'aria-pressed': String(o.key === current), onclick: () => onPick(o.key) }, o.label)));
  }

  function header(summary) {
    return h('header', { class: 'eval__head' },
      h('div', {},
        h('h1', { class: 'eval__title' }, 'Evaluation'),
        h('p', { class: 'eval__lede' },
          'How each retrieval configuration performs on a fixed set of questions with known answers. ',
          summary ? `Dataset ${summary.dataset_version}, ${summary.query_count} queries.` : '')),
      segmented(DATASET_TABS, state.dataset, (key) => { state.dataset = key; state.selected = null; load(); }, 'Dataset'));
  }

  function skeleton() {
    return h('div', {}, header(null), h('div', { class: 'skeleton-stack', 'aria-busy': 'true', 'aria-label': 'Loading results' },
      ...[100, 100, 100, 100, 100].map(() => h('span', { class: 'skeleton', style: 'height:52px;border-radius:8px' }))));
  }

  function failure(err) {
    return h('div', {}, header(null), h('div', { class: 'banner banner--error', role: 'alert' }, icon('alert', 18),
      h('div', { class: 'banner__body' },
        h('div', { class: 'banner__title' }, err.status === 404 ? 'No results for this dataset yet' : 'Couldn’t load results'),
        h('div', {}, err.message),
        h('div', { class: 'banner__actions' }, h('button', { class: 'btn btn--sm', type: 'button', onclick: () => load(true) }, icon('refresh', 14), 'Try again')))));
  }

  function gateCard(summary, gate) {
    if (!gate) {
      return h('div', { class: 'gate' }, h('div', { class: 'section-title', style: 'margin:0' }, h('h2', {}, 'Regression gate'), h('span', { class: 'tag' }, 'Not gated')),
        h('p', { class: 'note' }, 'This dataset is a small generalization check. CI gates on the synthetic dataset only, so nothing here can pass or fail the build.'));
    }
    if (gate.error) {
      return h('div', { class: 'gate' }, h('div', { class: 'banner banner--warn' }, icon('alert', 18), h('div', {}, gate.error)));
    }
    const failing = Object.entries(gate.results).filter(([, r]) => !r.passed).map(([n]) => n);
    return h('div', { class: 'gate' },
      h('div', { class: 'section-title', style: 'margin:0' }, h('h2', {}, 'Regression gate'),
        h('span', { class: `tag ${failing.length ? 'tag--bad' : 'tag--ok'}` }, failing.length ? `${failing.length} failing` : 'All passing')),
      h('div', { class: 'gate__row' },
        stat('Approved baseline Recall@10', formatMetric(gate.baseline_recall10)),
        stat('Allowed drop', formatMetric(gate.threshold)),
        stat('Baseline dataset', `v${gate.dataset_version}`)),
      h('p', { class: 'note' }, failing.length
        ? `${failing.join(', ')} would fail CI: Recall@10 dropped by more than the allowed amount. The “broken” configuration is deliberately bad, to show the gate works.`
        : 'Every configuration is within the allowed drop from the approved baseline.'));
  }

  const stat = (label, value) => h('div', { class: 'stat' }, h('span', { class: 'stat__label' }, label), h('span', { class: 'stat__value' }, value));

  function comparison(summary, gate) {
    const metric = state.metric;
    const names = Object.keys(summary.configs);
    const base = summary.configs[summary.baseline].metrics.overall[metric];
    const rows = names.map((name) => {
      const cfg = summary.configs[name];
      const value = cfg.metrics.overall[metric];
      const st = summary.stats[name]?.[metric];
      const isBase = name === summary.baseline;
      const reading = st ? readingOf(st.verdict) : null;
      const verdict = gate?.results?.[name];
      return h('button', { class: 'cmp-row', type: 'button', 'aria-pressed': String(state.selected === name), onclick: () => { state.selected = name; render(); } },
        h('span', { class: 'cmp-name' }, name, h('small', {}, `${cfg.details.retrieval_method}${cfg.details.reranker !== 'off' ? ' + rerank' : ''} · ${cfg.details.chunk_size}`)),
        h('span', { class: 'bar', role: 'img', 'aria-label': `${METRICS.find((m) => m.key === metric).label} ${formatMetric(value)}` },
          h('span', { class: 'bar__fill', style: `width:${Math.max(0, Math.min(1, value)) * 100}%` }),
          isBase ? null : h('span', { class: 'bar__base', style: `left:${base * 100}%`, title: 'Baseline' })),
        h('span', { class: 'cmp-num' }, formatMetric(value)),
        h('span', { class: `cmp-num ${isBase ? '' : st && st.delta > 0 ? 'delta--pos' : st && st.delta < 0 ? 'delta--neg' : ''}` }, isBase ? 'baseline' : formatDelta(value - base)),
        h('span', { class: 'cmp-ci' }, st ? `[${formatDelta(st.ci_low)}, ${formatDelta(st.ci_high)}]` : '—'),
        h('span', {}, reading ? h('span', { class: `tag ${reading.cls}` }, reading.label) : null),
        h('span', {}, metric === 'recall@10' && verdict ? h('span', { class: `tag ${verdict.passed ? 'tag--ok' : 'tag--bad'}` }, verdict.passed ? 'Pass' : 'Fail') : null));
    });
    return h('div', { class: 'cmp', role: 'group', 'aria-label': 'Configuration comparison; select a row for details' },
      h('div', { class: 'cmp-row cmp-head', 'aria-hidden': 'true' },
        h('span', {}, 'Configuration'), h('span', {}, 'Score'), h('span', { class: 'cmp-num' }, 'Value'), h('span', { class: 'cmp-num' }, 'Δ baseline'),
        h('span', {}, '95% CI'), h('span', {}, 'Reading'), h('span', {}, metric === 'recall@10' && gate ? 'Gate' : '')),
      rows);
  }

  function detail(summary) {
    const name = state.selected;
    const cfg = summary.configs[name];
    const failures = summary.failures[name] ?? [];
    const d = cfg.details;
    return h('div', { class: 'eval__section' },
      h('div', { class: 'section-title' }, h('h2', {}, 'Details'), h('span', { class: 'tag tag--accent' }, name)),
      h('div', { class: 'detail-grid' },
        h('section', { class: 'panel', 'aria-label': 'By category' },
          h('header', { class: 'panel__head' }, h('h3', { class: 'panel__title' }, 'By question type')),
          h('table', { class: 'table' },
            h('thead', {}, h('tr', {}, h('th', {}, 'Category'), h('th', {}, 'Recall@10'), h('th', {}, 'MRR'), h('th', {}, 'nDCG@10'))),
            h('tbody', {}, CATEGORIES.filter((c) => cfg.metrics[c]).map((c) => h('tr', {},
              h('td', {}, humanize(c)), h('td', {}, formatMetric(cfg.metrics[c]['recall@10'])),
              h('td', {}, formatMetric(cfg.metrics[c].mrr)), h('td', {}, formatMetric(cfg.metrics[c]['ndcg@10']))))))),
        h('section', { class: 'panel', 'aria-label': 'Failure types' },
          h('header', { class: 'panel__head' }, h('h3', { class: 'panel__title' }, 'Why queries fell short'),
            h('span', { class: 'panel__sub' }, failures.length ? `${failures.reduce((n, f) => n + f.count, 0)} imperfect` : '')),
          h('div', { class: 'panel__body' }, failures.length
            ? failures.map((f) => h('div', { class: 'fail-row' }, h('span', {}, humanize(f.type)),
              h('span', { class: 'bar', role: 'img', 'aria-label': `${f.percent}%` }, h('span', { class: 'bar__fill', style: `width:${f.percent}%` })),
              h('span', { class: 'cmp-num' }, `${f.count} · ${Math.round(f.percent)}%`)))
            : h('p', { class: 'muted' }, 'Every query was retrieved perfectly.'))),
        h('section', { class: 'panel', 'aria-label': 'Settings', style: 'grid-column:1/-1' },
          h('header', { class: 'panel__head' }, h('h3', { class: 'panel__title' }, 'Settings')),
          h('dl', { class: 'panel__body defs' },
            ...[['Retrieval', d.retrieval_method], ['Chunk size / overlap', `${d.chunk_size} / ${d.chunk_overlap}`],
              ['Embedding model', d.embedding_model], ['Reranker', d.reranker], ['Candidate pool', d.candidate_pool]]
              .flatMap(([k, v]) => [h('dt', {}, k), h('dd', {}, String(v))])))));
  }

  function render() {
    const data = state.cache.get(state.dataset);
    if (!data) return;
    const { summary, gate } = data;
    state.selected ??= summary.baseline;
    clear(body).append(
      header(summary),
      h('div', { class: 'eval__section' }, gateCard(summary, gate)),
      h('div', { class: 'eval__section' },
        h('div', { class: 'section-title' }, h('h2', {}, 'Compare configurations'),
          segmented(METRICS, state.metric, (key) => { state.metric = key; render(); }, 'Metric')),
        comparison(summary, gate),
        h('p', { class: 'note', style: 'margin-top:12px' },
          'The dark tick on each bar marks the baseline. A difference counts only if its 95% confidence interval (paired bootstrap over queries) excludes zero; ' +
          '“Inconclusive” means the data cannot separate the two, not that they are equal.')),
      detail(summary));
  }

  async function load(force = false) {
    const dataset = state.dataset;
    if (!force && state.cache.has(dataset)) { render(); return; }
    clear(body).append(skeleton());
    try {
      state.cache.set(dataset, await api.evaluation(dataset));
      if (dataset === state.dataset) render();
    } catch (err) {
      if (dataset === state.dataset) clear(body).append(failure(err));
    }
  }

  return { el, onShow() { if (!state.cache.has(state.dataset)) load(); } };
}
