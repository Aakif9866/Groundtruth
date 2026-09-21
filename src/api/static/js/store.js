// Persistence (localStorage). Every access is guarded: storage can be blocked or full.

const HISTORY_KEY = 'groundtruth.history.v1';
const PREFS_KEY = 'groundtruth.prefs.v1';
const HISTORY_MAX = 40;

function read(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function write(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

const listeners = new Set();
const notify = () => listeners.forEach((fn) => fn());

export const history = {
  all: () => read(HISTORY_KEY, []),
  /** Insert or replace an entry (matched by id); newest first. */
  save(entry) {
    const rest = this.all().filter((e) => e.id !== entry.id);
    write(HISTORY_KEY, [entry, ...rest].slice(0, HISTORY_MAX));
    notify();
  },
  remove(id) {
    write(HISTORY_KEY, this.all().filter((e) => e.id !== id));
    notify();
  },
  clear() {
    write(HISTORY_KEY, []);
    notify();
  },
  subscribe(fn) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  },
};

const DEFAULT_PREFS = { dataset: 'real_world', config: 'baseline', topK: 5 };
export const prefs = {
  get: () => ({ ...DEFAULT_PREFS, ...read(PREFS_KEY, {}) }),
  set: (patch) => write(PREFS_KEY, { ...prefs.get(), ...patch }),
};
