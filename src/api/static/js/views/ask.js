// "Ask" view: composer, conversation thread, and the retrieval / generation result panels.
import { h, icon, clear, copyText, nextFrame, prefersReducedMotion } from '../dom.js';
import { api } from '../api.js';
import { toast, passageDialog } from '../ui.js';
import { history, prefs } from '../store.js';
import { validateQuestion, parseAnswer, citedNumbers, formatMetric, QUESTION_MAX } from '../lib/text.js';

const CONFIG_ORDER = ['baseline', 'hybrid', 'reranker', 'chunk_change', 'broken'];
const CONFIG_LABELS = { broken: 'broken (deliberately bad)' };
const DATASET_LABELS = { real_world: 'Real-world (public domain)', synthetic: 'Synthetic (fictional)' };
const TOP_K_CHOICES = [3, 5, 8];
const MAX_TEXTAREA_PX = 176;

let idCounter = 0;
const newId = () => `${Date.now().toString(36)}${(idCounter++).toString(36)}`;

/** Small reusable panel used for both pipeline stages. */
function panel({ stage, title, sub, actions = [], body, foot }) {
  return h('section', { class: 'panel', 'aria-label': title },
    h('header', { class: 'panel__head' },
      h('span', { class: `stage-mark${stage === 'generation' ? ' stage-mark--gen' : ''}`, 'aria-hidden': 'true' }),
      h('h3', { class: 'panel__title' }, title),
      h('span', { class: 'panel__sub' }, sub),
      actions.length ? h('div', { class: 'panel__actions' }, actions) : null),
    h('div', { class: 'panel__body' }, body),
    foot ? h('footer', { class: 'panel__foot' }, foot) : null);
}

function meter(label, value) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100);
  return h('div', { class: 'meter' },
    h('div', { class: 'meter__row' }, h('span', {}, label), h('span', { class: 'mono' }, formatMetric(value, 2))),
    h('div', { class: 'meter__track', role: 'img', 'aria-label': `${label} ${pct}%` }, h('div', { class: 'meter__fill', style: `width:${pct}%` })));
}

export function createAskView() {
  const state = {
    turns: [],
    busy: false,
    active: null,
    datasets: Object.keys(DATASET_LABELS),
    configs: CONFIG_ORDER,
    prefs: prefs.get(),
  };

  // ---------- static DOM ----------
  const thread = h('div', { class: 'view__inner ask__thread', id: 'thread' });
  const questionInput = h('textarea', {
    class: 'textarea', id: 'question', rows: 1, maxlength: QUESTION_MAX + 200,
    placeholder: 'Ask a question…', 'aria-label': 'Your question', 'aria-describedby': 'question-error question-hint',
    autocomplete: 'off', spellcheck: 'true',
  });
  const errorLine = h('p', { class: 'field__error', id: 'question-error', role: 'alert' });
  const sendLabel = h('span', { class: 'btn__label--wide' }, 'Ask');
  const sendButton = h('button', { class: 'btn btn--primary', id: 'composer-send', type: 'submit', 'aria-label': 'Ask' }, icon('send'), sendLabel);
  const counter = h('span', { class: 'composer__count', hidden: true });
  const datasetSelect = h('select', { class: 'select select--sm', id: 'opt-dataset', 'aria-label': 'Dataset' });
  const configSelect = h('select', { class: 'select select--sm', id: 'opt-config', 'aria-label': 'Retrieval configuration' });
  const topKSelect = h('select', { class: 'select select--sm', id: 'opt-topk', 'aria-label': 'Number of sources' });

  const field = (label, control) => h('label', { class: 'field' }, h('span', { class: 'field__label' }, label), control);
  const form = h('form', { class: 'composer', novalidate: true },
    h('div', { class: 'composer__main' }, questionInput, sendButton),
    errorLine,
    h('div', { class: 'composer__opts' },
      field('Dataset', datasetSelect), field('Retrieval', configSelect), field('Sources', topKSelect),
      h('span', { class: 'composer__hint', id: 'question-hint' }, counter, ' ',
        h('span', { class: 'kbd' }, 'Enter'), ' to send · ', h('span', { class: 'kbd' }, 'Shift'), '+', h('span', { class: 'kbd' }, 'Enter'), ' for a new line')));

  const el = h('section', { class: 'ask', 'aria-label': 'Ask' },
    h('div', { class: 'view ask__thread-wrap', style: 'flex:1' }, thread),
    h('div', { class: 'composer-wrap' }, h('div', { class: 'view' }, h('div', { class: 'view__inner' }, form))));

  // ---------- composer ----------
  function fillSelect(select, values, labels, selected) {
    clear(select);
    for (const v of values) select.append(h('option', { value: v, selected: String(v) === String(selected) }, labels[v] ?? v));
  }

  function refreshOptions() {
    const p = state.prefs;
    if (!state.datasets.includes(p.dataset)) p.dataset = state.datasets[0];
    if (!state.configs.includes(p.config)) p.config = state.configs[0];
    fillSelect(datasetSelect, state.datasets, DATASET_LABELS, p.dataset);
    fillSelect(configSelect, state.configs, CONFIG_LABELS, p.config);
    fillSelect(topKSelect, TOP_K_CHOICES, Object.fromEntries(TOP_K_CHOICES.map((n) => [n, `Top ${n}`])), p.topK);
  }

  function autosize() {
    questionInput.style.height = 'auto';
    questionInput.style.height = `${Math.min(questionInput.scrollHeight, MAX_TEXTAREA_PX)}px`;
  }

  function setError(message) {
    errorLine.textContent = message;
    questionInput.classList.toggle('is-invalid', Boolean(message));
    if (message) questionInput.setAttribute('aria-invalid', 'true');
    else questionInput.removeAttribute('aria-invalid');
  }

  function updateCounter() {
    const len = questionInput.value.length;
    counter.hidden = len < QUESTION_MAX * 0.8;
    counter.textContent = `${len}/${QUESTION_MAX}`;
    counter.classList.toggle('is-over', len > QUESTION_MAX);
  }

  function setBusy(busy) {
    state.busy = busy;
    sendButton.replaceChildren(icon(busy ? 'stop' : 'send'), h('span', { class: 'btn__label--wide' }, busy ? 'Stop' : 'Ask'));
    sendButton.setAttribute('aria-label', busy ? 'Stop generating' : 'Ask');
  }

  questionInput.addEventListener('input', () => { autosize(); updateCounter(); if (errorLine.textContent) setError(''); });
  questionInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); form.requestSubmit(); }
  });
  for (const [select, key, cast] of [[datasetSelect, 'dataset', String], [configSelect, 'config', String], [topKSelect, 'topK', Number]]) {
    select.addEventListener('change', () => {
      state.prefs[key] = cast(select.value);
      prefs.set({ [key]: state.prefs[key] });
      if (key === 'dataset') loadExamples();
    });
  }

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    if (state.busy) { state.active?.controller?.abort(); return; }
    const result = validateQuestion(questionInput.value);
    if (!result.ok) { setError(result.message); questionInput.focus(); return; }
    setError('');
    ask(result.value);
    questionInput.value = '';
    autosize();
    updateCounter();
  });

  // ---------- thread ----------
  const scrollBehavior = () => (prefersReducedMotion() ? 'auto' : 'smooth');

  function renderIntro() {
    const chips = h('div', { class: 'source__tags', id: 'example-chips', 'aria-live': 'polite' },
      h('span', { class: 'skeleton', style: 'width:220px;height:32px;border-radius:999px' }));
    thread.replaceChildren(h('div', { class: 'empty ask__intro', id: 'intro' },
      h('h1', { class: 'empty__title' }, 'Ask the corpus'),
      h('p', { class: 'empty__text' },
        'Every answer is shown in two parts: what was retrieved (the sources) and what was generated from them (the answer). ' +
        'If an answer is wrong, the sources tell you which stage failed.'),
      h('div', { class: 'field__label' }, 'Try one of these'),
      chips));
    loadExamples();
  }

  async function loadExamples() {
    const chips = thread.querySelector('#example-chips');
    if (!chips) return;
    try {
      const { examples } = await api.examples(state.prefs.dataset, 4);
      const target = thread.querySelector('#example-chips');
      if (!target) return;
      target.replaceChildren(...examples.map((ex) =>
        h('button', { class: 'chip', type: 'button', onclick: () => { if (!state.busy) ask(ex.query); } }, ex.query)));
    } catch {
      thread.querySelector('#example-chips')?.replaceChildren(h('span', { class: 'muted' }, 'Examples are unavailable right now.'));
    }
  }

  function removeIntro() { thread.querySelector('#intro')?.remove(); }

  function createTurn({ id = newId(), question, dataset, config, topK, ts = Date.now() }) {
    const resultEl = h('div', { class: 'turn__result', 'aria-live': 'polite' });
    const turn = { id, question, dataset, config, topK, ts, status: 'loading', data: null, error: null, controller: null, resultEl };
    turn.el = h('article', { class: 'turn', 'aria-label': 'Question and answer' },
      h('div', { class: 'turn__q' },
        h('span', { class: 'turn__label' }, 'You'),
        h('p', { class: 'turn__question' }, question),
        h('div', { class: 'turn__meta' },
          h('span', { class: 'tag' }, DATASET_LABELS[dataset]?.split(' (')[0] ?? dataset), h('span', { class: 'tag' }, config), h('span', { class: 'tag' }, `top ${topK}`))),
      resultEl);
    return turn;
  }

  function addTurn(turn) {
    removeIntro();
    state.turns.push(turn);
    thread.append(turn.el);
  }

  async function ask(question) {
    const { dataset, config, topK } = state.prefs;
    const turn = createTurn({ question, dataset, config, topK });
    addTurn(turn);
    turn.el.scrollIntoView({ behavior: scrollBehavior(), block: 'start' });
    await run(turn);
  }

  async function run(turn) {
    turn.controller?.abort();
    turn.controller = new AbortController();
    turn.status = 'loading';
    state.active = turn;
    setBusy(true);
    renderPending(turn);
    try {
      turn.data = await api.ask(
        { query: turn.question, config: turn.config, dataset: turn.dataset, top_k: turn.topK },
        { signal: turn.controller.signal });
      turn.status = 'done';
      turn.ts = Date.now();
      history.save({ id: turn.id, question: turn.question, dataset: turn.dataset, config: turn.config, topK: turn.topK, ts: turn.ts, data: turn.data });
      renderResult(turn, { animate: true });
    } catch (err) {
      turn.status = err.kind === 'aborted' ? 'stopped' : 'error';
      turn.error = err;
      renderFailure(turn);
    } finally {
      if (state.active === turn) { state.active = null; setBusy(false); }
    }
  }

  // ---------- turn states ----------
  function renderPending(turn) {
    turn.resultEl.replaceChildren(h('div', { class: 'pending' },
      h('div', { class: 'pending__status' },
        h('span', { class: 'spinner', 'aria-hidden': 'true' }),
        h('span', {}, 'Retrieving sources and generating an answer…')),
      h('div', { class: 'skeleton-stack', 'aria-hidden': 'true' },
        h('span', { class: 'skeleton', style: 'width:92%' }), h('span', { class: 'skeleton', style: 'width:100%' }),
        h('span', { class: 'skeleton', style: 'width:64%' }))));
  }

  function renderFailure(turn) {
    const stopped = turn.status === 'stopped';
    const network = turn.error?.kind === 'network';
    turn.resultEl.replaceChildren(h('div', { class: `banner ${stopped ? 'banner--info' : 'banner--error'}`, role: stopped ? 'status' : 'alert' },
      icon(stopped ? 'info' : 'alert', 18),
      h('div', { class: 'banner__body' },
        h('div', { class: 'banner__title' }, stopped ? 'Stopped' : network ? 'Can’t reach the server' : 'Couldn’t get an answer'),
        h('div', {}, stopped ? 'You stopped this request before it finished.' : turn.error?.message ?? 'Something went wrong.'),
        h('div', { class: 'banner__actions' },
          h('button', { class: 'btn btn--sm', type: 'button', onclick: () => run(turn) }, icon('refresh', 14), 'Try again')))));
  }

  function renderResult(turn, { animate }) {
    const { retrieval, generation } = turn.data;
    const results = retrieval.results ?? [];
    const cited = citedNumbers(generation.answer);

    // --- generation panel ---
    const answerEl = h('div', { class: 'answer' });
    const copyBtn = h('button', { class: 'btn btn--ghost btn--sm', type: 'button', onclick: async () => {
      const ok = await copyText(generation.answer);
      toast(ok ? 'Answer copied' : 'Could not copy — select the text instead', { type: ok ? 'info' : 'error' });
    } }, icon('copy', 14), 'Copy');
    const retryBtn = h('button', { class: 'btn btn--ghost btn--sm', type: 'button', onclick: () => run(turn) }, icon('refresh', 14), 'Regenerate');

    const checks = generation.heuristic_metrics;
    const generationPanel = panel({
      stage: 'generation', title: 'Answer', sub: `Generation · ${generation.method}`,
      actions: generation.answer ? [copyBtn, retryBtn] : [retryBtn],
      body: [
        generation.llm_error ? h('div', { class: 'banner banner--warn', role: 'status', style: 'margin-bottom:12px' }, icon('alert', 18),
          h('div', { class: 'banner__body' }, h('div', { class: 'banner__title' }, 'The language model was unavailable'),
            h('div', {}, `Showing the extractive answer instead. ${generation.llm_error}`))) : null,
        answerEl,
      ],
      foot: checks ? h('div', { class: 'checks' },
        meter('Faithfulness', checks.faithfulness), meter('Answer relevance', checks.answer_relevance), meter('Context relevance', checks.context_relevance),
        h('p', { class: 'checks__note' }, 'Lexical proxies for the answer and its context. They do not measure whether retrieval found the right passages.')) : null,
    });

    // --- retrieval panel ---
    const sources = h('ul', { class: 'sources' }, results.map((r) => sourceItem(turn, r, cited.includes(r.rank))));
    const golden = retrieval.golden_check;
    const retrievalPanel = panel({
      stage: 'retrieval', title: 'Sources', sub: `Retrieval · ${retrieval.config} · ${results.length} passage${results.length === 1 ? '' : 's'}`,
      body: results.length ? sources : h('p', { class: 'muted' }, 'No passages were retrieved for this question.'),
      foot: golden
        ? [h('span', { class: `tag ${golden.all_relevant_retrieved ? 'tag--ok' : 'tag--bad'}` }, golden.all_relevant_retrieved ? 'Retrieval OK' : 'Retrieval miss'), ' ',
           `Known question ${golden.query_id}: expected ${Object.entries(golden.relevant_ranks).map(([id, r]) => `${id} ${r ? `at rank ${r}` : 'not retrieved'}`).join(', ')}.`]
        : 'Not a golden-set question, so retrieval cannot be scored automatically. Compare the sources with the answer.',
    });

    turn.resultEl.replaceChildren(generationPanel, retrievalPanel);
    renderAnswer(turn, answerEl, generation, { animate });
  }

  function sourceItem(turn, r, isCited) {
    return h('li', { class: 'source', id: `src-${turn.id}-${r.rank}`, tabindex: '-1' },
      h('span', { class: 'source__rank', 'aria-label': `Rank ${r.rank}` }, String(r.rank)),
      h('div', { class: 'source__body' },
        h('div', { class: 'source__title' }, r.title),
        h('div', { class: 'source__tags' },
          h('span', { class: 'tag' }, r.doc_type), h('span', { class: 'tag mono' }, r.passage_id),
          h('span', { class: 'tag mono', title: 'Retrieval score' }, `${turn.data.retrieval.score_type} ${r.score.toFixed(3)}`),
          isCited ? h('span', { class: 'tag tag--accent' }, `Cited [${r.rank}]`) : null),
        h('p', { class: 'source__snippet' }, r.snippet),
        h('div', { class: 'source__actions' },
          h('button', { class: 'btn btn--ghost btn--sm', type: 'button', style: 'margin-left:-8px', onclick: () => passageDialog({
            title: r.title, passageId: r.passage_id, rank: r.rank, text: r.text ?? r.snippet,
            meta: [h('span', { class: 'tag' }, r.doc_type)],
          }) }, icon('doc', 14), 'Read full passage'))));
  }

  function focusSource(turn, n) {
    const target = document.getElementById(`src-${turn.id}-${n}`);
    if (!target) return;
    target.scrollIntoView({ behavior: scrollBehavior(), block: 'center' });
    target.focus({ preventScroll: true });
    target.classList.remove('is-flash');
    void target.offsetWidth; // restart the animation
    target.classList.add('is-flash');
  }

  /** Build the answer as a list of small append-steps so it can be revealed progressively. */
  function renderAnswer(turn, root, generation, { animate }) {
    const count = turn.data.retrieval.results?.length ?? 0;
    const blocks = parseAnswer(generation.answer);
    if (!blocks.length) {
      root.classList.add('answer--empty');
      root.textContent = 'No answer could be generated from the retrieved passages.';
      return;
    }
    const steps = [];
    const ctx = { node: null };
    const inline = (parts) => {
      for (const part of parts) {
        if (part.type === 'cite') {
          steps.push(() => ctx.node.append(part.n >= 1 && part.n <= count
            ? h('button', { class: 'cite', type: 'button', 'aria-label': `Go to source ${part.n}`, onclick: () => focusSource(turn, part.n) }, String(part.n))
            : `[${part.n}]`));
        } else if (part.type === 'bold') {
          steps.push(() => ctx.node.append(h('strong', {}, part.value)));
        } else {
          for (const word of part.value.split(/(\s+)/).filter(Boolean)) steps.push(() => ctx.node.append(word));
        }
      }
    };
    for (const block of blocks) {
      if (block.type === 'p') {
        steps.push(() => { ctx.node = h('p'); root.append(ctx.node); });
        inline(block.parts);
      } else {
        let list;
        steps.push(() => { list = h('ul'); root.append(list); });
        for (const item of block.items) {
          steps.push(() => { ctx.node = h('li'); list.append(ctx.node); });
          inline(item);
        }
      }
    }

    if (!animate || prefersReducedMotion()) { steps.forEach((s) => s()); return; }
    const cursor = h('span', { class: 'cursor', 'aria-hidden': 'true' });
    root.append(cursor);
    (async () => {
      const perFrame = Math.max(1, Math.ceil(steps.length / 70));
      for (let i = 0; i < steps.length; i += perFrame) {
        if (!root.isConnected) return;
        steps.slice(i, i + perFrame).forEach((s) => s());
        root.append(cursor); // keep the caret at the end
        await nextFrame();
      }
      cursor.remove();
    })();
  }

  // ---------- public API ----------
  refreshOptions();
  renderIntro();

  return {
    el,
    focusComposer() { questionInput.focus(); },
    /** Provide backend capabilities (from /health) so the selects match what the server offers. */
    setCapabilities({ datasets, configs }) {
      if (datasets?.length) state.datasets = [...datasets].sort((a, b) => (a === 'real_world' ? -1 : b === 'real_world' ? 1 : 0));
      if (configs?.length) state.configs = [...configs].sort((a, b) => CONFIG_ORDER.indexOf(a) - CONFIG_ORDER.indexOf(b));
      refreshOptions();
      if (!state.turns.length) loadExamples();
    },
    /** Show a saved history entry as a turn (no network, no animation). */
    openHistoryEntry(entry) {
      const existing = state.turns.find((t) => t.id === entry.id);
      if (existing) { existing.el.scrollIntoView({ behavior: scrollBehavior(), block: 'start' }); return; }
      const turn = createTurn(entry);
      turn.status = 'done';
      turn.data = entry.data;
      addTurn(turn);
      renderResult(turn, { animate: false });
      turn.el.scrollIntoView({ behavior: scrollBehavior(), block: 'start' });
    },
    newChat() {
      state.active?.controller?.abort();
      state.turns = [];
      setBusy(false);
      renderIntro();
      window.scrollTo({ top: 0 });
      questionInput.focus();
    },
  };
}
