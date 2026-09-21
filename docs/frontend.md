# Frontend

Plain HTML, CSS and ES modules. No framework, no build step, no runtime dependencies. It lives in
`src/api/static/` and is served by the FastAPI app at `/`.

## What it does

Two views, one purpose each.

- **Ask**: a chat-style thread. Each answer is shown as two separate panels: *Answer* (generation) and
  *Sources* (retrieval), so a wrong answer can be traced to the stage that failed. Includes citations that jump
  to their source, copy, regenerate, stop, full-passage dialog, saved history, and a retrieval check when the
  question is a known golden query.
- **Evaluation**: the committed evaluation results: a comparison of configurations for a chosen metric
  with deltas and 95% intervals, regression-gate status, per-category results, failure types and settings.

## Layout of the code

```text
index.html            shell: sidebar, main, toasts
css/tokens.css        design tokens (colour, type, spacing, radii); light + dark
css/base.css          reset, typography, focus, reduced motion
css/components.css    buttons, inputs, tags, panels, banners, skeletons, toasts, dialogs
css/views.css         app shell, Ask view, Evaluation view, responsive rules
js/main.js            router, sidebar/history, health status, shortcuts
js/api.js             the only place that talks to the backend (real client)
js/mock.js            same response shapes; enabled with ?mock=1
js/store.js           localStorage (history, preferences), all access guarded
js/ui.js              toast, confirm dialog, passage dialog
js/dom.js             h() element builder, icons, clipboard
js/lib/text.js        pure helpers (validation, answer parsing, formatting), unit-tested
js/lib/errors.js      ApiError
js/views/ask.js       Ask view
js/views/evaluation.js  Evaluation view
```

## Design system

- **Palette:** warm paper background, ink text, one deep-green accent for primary actions and retrieval, and a
  muted ochre used only for the generation side so the two stages are distinguishable. Status colours
  (ok/warn/bad) are used only for meaning. No gradients (apart from the loading shimmer), no glass effects.
- **Type:** system sans for UI, a serif stack for answers and page titles (long-form reading), monospace for IDs,
  scores and numbers. No web fonts, so nothing to download.
- **Spacing/shape:** 4px scale, 5 to 12px radii, 1px borders, one small shadow.
- **Components:** `.btn` (primary/ghost/danger, sm/icon), `.field/.select/.textarea`, `.seg` (segmented control),
  `.tag/.chip`, `.panel`, `.banner` (error/warn/info), `.skeleton/.spinner`, `.empty`, `.meter`, toast, `<dialog>`.
- **States everywhere:** loading (skeleton + status line + Stop), error (specific message + Try again), empty
  (intro with examples, empty history), success (toasts), stopped.
- **Accessibility:** semantic landmarks, skip link, visible focus rings, labelled controls, `aria-live` for
  results and errors, native `<dialog>` (focus trap, Esc), `prefers-reduced-motion`, light/dark via
  `prefers-color-scheme`. Model output is rendered with `textContent`, never as HTML.
- **Responsive:** sidebar at 1024px and up; below that an off-canvas drawer with a top bar. Under 640px the
  composer compacts, panel actions move under the title and comparison rows become stacked cards. No horizontal
  scroll at 390, 820 or 1280 px (checked in the smoke tests).

## Connecting to a real backend

Everything goes through `js/api.js`:

| Method | Endpoint |
|---|---|
| `api.health()` | `GET /health` |
| `api.examples(dataset, limit)` | `GET /api/examples` |
| `api.ask(payload)` | `POST /ask` |
| `api.retrieve(payload)` | `POST /retrieve` |
| `api.evaluation(dataset)` | `GET /api/evaluation` |

Set `<meta name="api-base" content="https://your-host">` in `index.html` to use another origin (the server would need
CORS enabled). `?mock=1` swaps in `js/mock.js`, which returns the same shapes with simulated latency; a question
containing "error" fails and one containing "slow" takes three seconds.

The answer text appears progressively for readability. The API is not streaming; the full response arrives first and
is then revealed on the client.

## Testing

```bash
node --test tests/frontend                     # pure logic in js/lib/text.js
pytest tests/integration/test_api.py           # endpoints the UI depends on
pip install playwright && pytest tests/smoke -m smoke   # real-browser smoke tests (Chrome)
SMOKE_SHOTS=./shots pytest tests/smoke -m smoke          # also save screenshots
```

The smoke tests start their own server and cover: load and health, input validation, ask flow with sources and
citations, copy and passage dialog, regenerate, history persistence and clearing, server-error and network-failure
states with retry, the Evaluation view (gate, metric switching, details, dataset toggle, error/retry), mobile and
tablet layouts with the drawer, mock mode, and dark mode. They are not run in CI.
