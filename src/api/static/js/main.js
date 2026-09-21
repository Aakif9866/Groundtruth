// App shell: routing, sidebar (history, status), and view lifecycle.
import { h, icon, clear } from './dom.js';
import { api } from './api.js';
import { history } from './store.js';
import { confirmDialog, toast } from './ui.js';
import { formatRelativeTime, truncate } from './lib/text.js';
import { createAskView } from './views/ask.js';
import { createEvaluationView } from './views/evaluation.js';

const $ = (id) => document.getElementById(id);
const app = $('app');
const viewHost = $('view');

const ROUTES = {
  ask: { title: 'Ask', view: createAskView() },
  evaluation: { title: 'Evaluation', view: createEvaluationView() },
};
for (const { view } of Object.values(ROUTES)) { view.el.hidden = true; viewHost.append(view.el); }

// ---------- navigation drawer (below 1024px) ----------
const menuOpen = $('menu-open');
$('menu-open').append(icon('menu', 18));
$('menu-close').append(icon('x', 16));
function setNav(open) {
  app.classList.toggle('nav-open', open);
  menuOpen.setAttribute('aria-expanded', String(open));
  $('sidebar').toggleAttribute('inert', !open && window.matchMedia('(max-width: 1023px)').matches);
}
menuOpen.addEventListener('click', () => { setNav(true); $('menu-close').focus(); });
$('menu-close').addEventListener('click', () => { setNav(false); menuOpen.focus(); });
$('scrim').addEventListener('click', () => setNav(false));
window.matchMedia('(max-width: 1023px)').addEventListener('change', () => setNav(false));
setNav(false);

// ---------- routing ----------
function currentRoute() {
  const name = location.hash.replace(/^#\/?/, '').split('?')[0];
  return ROUTES[name] ? name : 'ask';
}

function route() {
  const name = currentRoute();
  for (const [key, r] of Object.entries(ROUTES)) r.view.el.hidden = key !== name;
  document.querySelectorAll('.nav a').forEach((a) => {
    if (a.dataset.route === name) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
  });
  $('topbar-title').textContent = ROUTES[name].title;
  document.title = `${ROUTES[name].title} · Groundtruth`;
  ROUTES[name].view.onShow?.();
  setNav(false);
  window.scrollTo({ top: 0 });
}
window.addEventListener('hashchange', route);

// ---------- history sidebar ----------
const ask = ROUTES.ask.view;
const list = $('history-list');
const clearBtn = $('history-clear');

function renderHistory() {
  const entries = history.all();
  clearBtn.hidden = entries.length === 0;
  clear(list);
  if (!entries.length) { list.append(h('li', { class: 'history__empty' }, 'Questions you ask will appear here.')); return; }
  for (const e of entries) {
    list.append(h('li', { class: 'history-item' },
      h('button', { class: 'history-item__open', type: 'button', onclick: () => { location.hash = '#/ask'; ask.openHistoryEntry(e); setNav(false); } },
        h('span', { class: 'history-item__q' }, truncate(e.question, 120)),
        h('span', { class: 'history-item__meta' }, `${e.config} · ${formatRelativeTime(e.ts)}`)),
      h('button', { class: 'btn btn--ghost btn--icon btn--sm history-item__del', type: 'button', 'aria-label': `Remove “${truncate(e.question, 40)}” from history`,
        onclick: () => { history.remove(e.id); } }, icon('x', 14))));
  }
}
history.subscribe(renderHistory);
clearBtn.addEventListener('click', async () => {
  if (await confirmDialog({ title: 'Clear history?', message: 'This removes all saved questions and answers from this browser.', confirmLabel: 'Clear history', danger: true })) {
    history.clear();
    toast('History cleared');
  }
});
renderHistory();

// ---------- API status ----------
async function checkHealth() {
  const dot = $('status-dot');
  try {
    const health = await api.health();
    dot.dataset.state = 'ok';
    $('status-text').textContent = api.isMock ? 'Mock data (no server)' : 'API connected';
    ask.setCapabilities(health);
  } catch {
    dot.dataset.state = 'down';
    $('status-text').textContent = 'API unreachable';
  }
}

// ---------- global shortcuts ----------
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && app.classList.contains('nav-open')) { setNav(false); menuOpen.focus(); }
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName ?? '');
  if (e.key === '/' && !typing && !e.metaKey && !e.ctrlKey && currentRoute() === 'ask') { e.preventDefault(); ask.focusComposer(); }
});

// "New chat" lives on the Ask nav link when already on that view.
document.querySelector('.nav a[data-route="ask"]').addEventListener('click', () => { if (currentRoute() === 'ask') ask.newChat(); });

route();
checkHealth();
setInterval(() => { if (!document.hidden) renderHistory(); }, 60_000); // keep "5 min ago" fresh
