// Shared UI patterns: toasts and dialogs.
import { h, icon, copyText } from './dom.js';

const TOAST_MS = 3500;

/** Brief, non-blocking notification. type: 'info' | 'error'. */
export function toast(message, { type = 'info' } = {}) {
  const host = document.getElementById('toasts');
  const el = h('div', { class: `toast${type === 'error' ? ' toast--error' : ''}` },
    icon(type === 'error' ? 'alert' : 'check'), h('span', {}, message));
  host.append(el);
  setTimeout(() => {
    el.classList.add('is-leaving');
    setTimeout(() => el.remove(), 180);
  }, TOAST_MS);
}

function openDialog(dialog) {
  document.body.append(dialog);
  dialog.addEventListener('close', () => dialog.remove());
  // Click on the backdrop (the dialog element itself) closes it.
  dialog.addEventListener('click', (e) => { if (e.target === dialog) dialog.close(); });
  dialog.showModal();
}

/** Confirmation dialog. Resolves to true if confirmed. */
export function confirmDialog({ title, message, confirmLabel = 'Confirm', danger = false }) {
  return new Promise((resolve) => {
    let result = false;
    const dialog = h('dialog', { class: 'dialog dialog--sm', 'aria-labelledby': 'dlg-title' },
      h('div', { class: 'dialog__head' }, h('h2', { class: 'dialog__title', id: 'dlg-title' }, title)),
      h('div', { class: 'dialog__body' }, h('p', {}, message)),
      h('div', { class: 'dialog__foot' },
        h('button', { class: 'btn', type: 'button', onclick: () => dialog.close() }, 'Cancel'),
        h('button', { class: `btn ${danger ? 'btn--danger' : 'btn--primary'}`, type: 'button', autofocus: true,
          onclick: () => { result = true; dialog.close(); } }, confirmLabel)));
    dialog.addEventListener('close', () => resolve(result));
    openDialog(dialog);
  });
}

/** Full-text view of a retrieved passage. */
export function passageDialog({ title, passageId, rank, text, meta }) {
  const dialog = h('dialog', { class: 'dialog', 'aria-labelledby': 'dlg-title' },
    h('div', { class: 'dialog__head' },
      h('h2', { class: 'dialog__title', id: 'dlg-title' }, title),
      h('button', { class: 'btn btn--ghost btn--icon btn--sm', type: 'button', 'aria-label': 'Close', style: 'margin-left:auto',
        onclick: () => dialog.close() }, icon('x'))),
    h('div', { class: 'dialog__body' },
      h('div', { class: 'source__tags', style: 'margin-bottom:12px' },
        h('span', { class: 'tag' }, `Rank ${rank}`), h('span', { class: 'tag mono' }, passageId), ...(meta ?? [])),
      h('p', { class: 'passage-text' }, text)),
    h('div', { class: 'dialog__foot' },
      h('button', { class: 'btn', type: 'button', onclick: async (e) => {
        const ok = await copyText(text);
        toast(ok ? 'Passage copied' : 'Could not copy', { type: ok ? 'info' : 'error' });
        e.currentTarget.blur();
      } }, icon('copy'), 'Copy passage'),
      h('button', { class: 'btn btn--primary', type: 'button', onclick: () => dialog.close() }, 'Done')));
  openDialog(dialog);
}
