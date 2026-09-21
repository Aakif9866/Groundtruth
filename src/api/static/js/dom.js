// Small DOM helpers. Elements are built with createElement/textContent, never innerHTML with data.

const SVG_NS = 'http://www.w3.org/2000/svg';

/** h('button', { class: 'btn', onclick }, 'Label', icon('copy')) */
export function h(tag, props = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(props ?? {})) {
    if (value == null || value === false) continue;
    if (key === 'class') el.className = value;
    else if (key === 'dataset') Object.assign(el.dataset, value);
    else if (key.startsWith('on') && typeof value === 'function') el.addEventListener(key.slice(2), value);
    else if (value === true) el.setAttribute(key, '');
    else el.setAttribute(key, value);
  }
  append(el, children);
  return el;
}

export function append(el, children) {
  for (const child of children.flat(Infinity)) {
    if (child == null || child === false) continue;
    el.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return el;
}

export function clear(el) {
  el.replaceChildren();
  return el;
}

const ICONS = {
  send: [['path', { d: 'M12 19V5' }], ['path', { d: 'M5 12l7-7 7 7' }]],
  copy: [['rect', { x: 9, y: 9, width: 11, height: 11, rx: 2 }], ['path', { d: 'M5 15V6a2 2 0 0 1 2-2h9' }]],
  refresh: [['path', { d: 'M20 12a8 8 0 1 1-2.4-5.7' }], ['path', { d: 'M20 4v5h-5' }]],
  x: [['path', { d: 'M18 6L6 18' }], ['path', { d: 'M6 6l12 12' }]],
  menu: [['path', { d: 'M4 6h16' }], ['path', { d: 'M4 12h16' }], ['path', { d: 'M4 18h16' }]],
  stop: [['rect', { x: 6, y: 6, width: 12, height: 12, rx: 2 }]],
  check: [['path', { d: 'M20 6L9 17l-5-5' }]],
  alert: [['circle', { cx: 12, cy: 12, r: 9 }], ['path', { d: 'M12 8v5' }], ['path', { d: 'M12 16.5h.01' }]],
  info: [['circle', { cx: 12, cy: 12, r: 9 }], ['path', { d: 'M12 11v5' }], ['path', { d: 'M12 8h.01' }]],
  doc: [['path', { d: 'M7 3h7l4 4v14H7z' }], ['path', { d: 'M14 3v5h4' }]],
};

export function icon(name, size = 16) {
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('width', size);
  svg.setAttribute('height', size);
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '2');
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');
  svg.setAttribute('aria-hidden', 'true');
  svg.classList.add('icon');
  for (const [tag, attrs] of ICONS[name] ?? []) {
    const node = document.createElementNS(SVG_NS, tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    svg.append(node);
  }
  return svg;
}

/** Copy text to the clipboard, with a fallback for non-secure contexts. Resolves to true on success. */
export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const area = h('textarea', { 'aria-hidden': 'true', style: 'position:fixed;opacity:0;top:0' });
    area.value = text;
    document.body.append(area);
    area.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch { /* ignored */ }
    area.remove();
    return ok;
  }
}

export const nextFrame = () => new Promise((resolve) => requestAnimationFrame(resolve));
export const prefersReducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
