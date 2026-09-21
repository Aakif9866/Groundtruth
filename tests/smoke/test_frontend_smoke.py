"""Browser smoke tests for the web UI (real Chrome via Playwright, real API, extractive answers).

Optional: skipped unless Playwright and a Chrome install are available. Not part of CI.

    pip install playwright
    pytest tests/smoke -m smoke -q
    SMOKE_SHOTS=/some/dir pytest tests/smoke -m smoke   # also save screenshots
"""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

pytest.importorskip("playwright")
from playwright.sync_api import Error as PlaywrightError, expect, sync_playwright  # noqa: E402

pytestmark = pytest.mark.smoke
ROOT = Path(__file__).resolve().parents[2]
SHOTS = os.environ.get("SMOKE_SHOTS")
QUESTION = "What warnings must be given to a suspect before custodial questioning?"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def base_url():
    port = _free_port()
    env = {**os.environ, "GENERATION_BACKEND": "extractive", "USE_LLM_JUDGE": "false"}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "src.api.app:app", "--port", str(port)],
                            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(90):
            try:
                urllib.request.urlopen(f"{url}/health", timeout=1)
                break
            except OSError:
                time.sleep(1)
        else:
            pytest.fail("server did not start")
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="chrome")
        except PlaywrightError:
            pytest.skip("Google Chrome is not available for Playwright")
        yield b
        b.close()


@pytest.fixture
def page(browser, base_url):
    ctx = browser.new_context(viewport={"width": 1280, "height": 800}, permissions=["clipboard-read", "clipboard-write"])
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.on("console", lambda m: pg.errors.append(m.text) if m.type == "error" else None)
    pg.goto(base_url)
    expect(pg.locator("#status-text")).to_have_text("API connected")
    yield pg
    assert pg.errors == [], f"browser errors: {pg.errors}"
    ctx.close()


def shot(page, name):
    if SHOTS:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(SHOTS) / f"{name}.png"), full_page=False)


def ask(page, text=QUESTION):
    page.fill("#question", text)
    page.keyboard.press("Enter")
    expect(page.locator(".turn").last.locator(".answer")).not_to_be_empty(timeout=60_000)
    expect(page.locator(".cursor")).to_have_count(0, timeout=10_000)


def test_initial_load_shows_intro_examples_and_nav(page):
    expect(page).to_have_title("Ask · Groundtruth")
    expect(page.locator("h1.empty__title")).to_have_text("Ask the corpus")
    expect(page.locator("#example-chips .chip")).to_have_count(4)
    expect(page.locator('.nav a[aria-current="page"]')).to_have_text("Ask")
    expect(page.locator("#history-list")).to_contain_text("Questions you ask will appear here")
    shot(page, "01-desktop-empty")


def test_input_validation(page):
    page.keyboard.press("Enter")  # empty
    page.click("#question")
    page.keyboard.press("Enter")
    expect(page.locator("#question-error")).to_contain_text("Enter a question")
    page.fill("#question", "hi")
    page.keyboard.press("Enter")
    expect(page.locator("#question-error")).to_contain_text("at least 3")
    expect(page.locator("#question")).to_have_attribute("aria-invalid", "true")
    page.fill("#question", "valid question here")  # typing clears the error
    expect(page.locator("#question-error")).to_have_text("")
    expect(page.locator(".turn")).to_have_count(0)


def test_ask_shows_answer_sources_citations_and_diagnostics(page):
    ask(page)
    turn = page.locator(".turn").last
    expect(turn.locator(".turn__question")).to_have_text(QUESTION)
    expect(turn.locator('section[aria-label="Answer"]')).to_be_visible()
    expect(turn.locator('section[aria-label="Sources"]')).to_be_visible()
    expect(turn.locator(".source")).to_have_count(5)
    expect(turn.locator(".source").first.locator(".source__title")).to_contain_text("Miranda")
    expect(turn.locator(".meter")).to_have_count(3)
    expect(turn.locator(".panel__foot").last).to_contain_text("Retrieval OK")
    assert turn.locator(".cite").count() >= 1
    shot(page, "02-desktop-answer")

    turn.locator(".cite").first.click()  # jumps to and highlights the cited source
    expect(turn.locator(".source.is-flash")).to_have_count(1)


def test_copy_answer_and_read_full_passage(page):
    ask(page)
    turn = page.locator(".turn").last
    turn.get_by_role("button", name="Copy").click()
    expect(page.locator(".toast")).to_contain_text("Answer copied")
    assert "right to remain silent" in page.evaluate("navigator.clipboard.readText()")

    turn.get_by_role("button", name="Read full passage").first.click()
    dialog = page.locator("dialog[open]")
    expect(dialog).to_be_visible()
    expect(dialog.locator(".passage-text")).to_contain_text("right to remain silent")
    shot(page, "03-desktop-passage-dialog")
    page.keyboard.press("Escape")
    expect(page.locator("dialog[open]")).to_have_count(0)


def test_regenerate_history_persists_and_reopens(page, base_url):
    ask(page)
    expect(page.locator(".history-item")).to_have_count(1)
    page.locator(".turn").last.get_by_role("button", name="Regenerate").click()
    expect(page.locator(".turn").last.locator(".answer")).not_to_be_empty(timeout=60_000)
    expect(page.locator(".history-item")).to_have_count(1)  # same entry replaced, not duplicated

    page.reload()
    expect(page.locator(".history-item")).to_have_count(1)
    expect(page.locator(".turn")).to_have_count(0)
    page.locator(".history-item__open").click()
    expect(page.locator(".turn")).to_have_count(1)
    expect(page.locator(".turn .source")).to_have_count(5)  # restored from storage, no network needed

    page.locator("#history-clear").click()
    expect(page.locator("dialog[open]")).to_contain_text("Clear history?")
    page.get_by_role("button", name="Clear history").click()
    expect(page.locator(".history-item")).to_have_count(0)
    expect(page.locator(".toast")).to_contain_text("History cleared")


def test_server_error_shows_retryable_error_state(page):
    state = {"fail": True}

    def handle(route):
        if state["fail"]:
            route.fulfill(status=500, content_type="application/json", body=json.dumps({"detail": "Retriever exploded"}))
        else:
            route.continue_()

    page.route("**/ask", handle)
    page.fill("#question", QUESTION)
    page.keyboard.press("Enter")
    banner = page.locator(".turn .banner--error")
    expect(banner).to_contain_text("Couldn’t get an answer")
    expect(banner).to_contain_text("Retriever exploded")
    shot(page, "04-desktop-error")
    state["fail"] = False
    banner.get_by_role("button", name="Try again").click()
    expect(page.locator(".turn .answer")).not_to_be_empty(timeout=60_000)
    expect(page.locator(".turn .banner--error")).to_have_count(0)
    page.expect_console_message  # errors from the deliberate 500 are expected below
    page.errors.clear()


def test_network_failure_and_stop(page):
    page.route("**/ask", lambda route: route.abort())
    page.fill("#question", QUESTION)
    page.keyboard.press("Enter")
    expect(page.locator(".turn .banner--error")).to_contain_text("Can’t reach the server")
    page.errors.clear()  # the aborted request is logged by the browser


def test_evaluation_view_data_gate_and_interactions(page):
    page.click('.nav a[data-route="evaluation"]')
    expect(page).to_have_title("Evaluation · Groundtruth")
    rows = page.locator("button.cmp-row")
    expect(rows).to_have_count(5)
    expect(page.locator(".gate")).to_contain_text("1 failing")
    broken = page.locator("button.cmp-row", has_text="broken")
    expect(broken).to_contain_text("Fail")
    expect(broken).to_contain_text("Regression")
    expect(page.locator("button.cmp-row", has_text="hybrid")).to_contain_text("Inconclusive")
    shot(page, "05-desktop-evaluation")

    page.get_by_role("button", name="MRR").click()
    expect(page.locator("button.cmp-row", has_text="reranker")).to_contain_text("Improvement")
    broken.click()
    expect(page.locator("text=Candidate pool limitation")).to_be_visible()
    expect(page.locator(".defs")).to_contain_text("40 / 0")

    page.get_by_role("button", name="Real-world").click()
    expect(page.locator(".gate")).to_contain_text("Not gated")
    expect(page.locator(".eval__lede")).to_contain_text("19 queries")


def test_evaluation_error_state_and_retry(page):
    calls = {"n": 0}

    def handle(route):
        calls["n"] += 1
        if calls["n"] == 1:
            route.fulfill(status=404, content_type="application/json", body=json.dumps({"detail": "No evaluation summary."}))
        else:
            route.continue_()

    page.route("**/api/evaluation**", handle)
    page.click('.nav a[data-route="evaluation"]')
    expect(page.locator(".banner--error")).to_contain_text("No results for this dataset yet")
    page.get_by_role("button", name="Try again").click()
    expect(page.locator("button.cmp-row")).to_have_count(5)
    page.errors.clear()


@pytest.mark.parametrize("width,height,name", [(390, 844, "mobile"), (820, 1180, "tablet")])
def test_responsive_layout_and_drawer(browser, base_url, width, height, name):
    ctx = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=2)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(base_url)
    expect(pg.locator("#status-text")).to_have_text("API connected")
    assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "horizontal overflow on empty state"
    expect(pg.locator("#menu-open")).to_be_visible()
    expect(pg.locator("#sidebar")).not_to_be_in_viewport()
    shot(pg, f"06-{name}-empty")

    pg.click("#menu-open")
    expect(pg.locator("#sidebar")).to_be_in_viewport()
    shot(pg, f"07-{name}-drawer")
    pg.keyboard.press("Escape")
    expect(pg.locator("#sidebar")).not_to_be_in_viewport()

    pg.fill("#question", QUESTION)
    pg.keyboard.press("Enter")
    expect(pg.locator(".turn .answer")).not_to_be_empty(timeout=60_000)
    expect(pg.locator(".cursor")).to_have_count(0, timeout=10_000)
    assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "horizontal overflow with an answer"
    shot(pg, f"08-{name}-answer")

    pg.click("#menu-open")
    pg.click('.nav a[data-route="evaluation"]')
    expect(pg.locator("button.cmp-row")).to_have_count(5)
    expect(pg.locator("#sidebar")).not_to_be_in_viewport()  # drawer closes on navigation
    assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "horizontal overflow on evaluation"
    shot(pg, f"09-{name}-evaluation")
    assert errors == []
    ctx.close()


def test_mock_mode_works_without_a_backend(browser, base_url):
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    pg = ctx.new_page()
    pg.goto(f"{base_url}/?mock=1")
    expect(pg.locator("#status-text")).to_have_text("Mock data (no server)")
    pg.fill("#question", "Tell me about the fourth amendment and people")
    pg.keyboard.press("Enter")
    expect(pg.locator(".turn .answer")).not_to_be_empty(timeout=15_000)
    pg.fill("#question", "trigger an error please")
    pg.keyboard.press("Enter")
    expect(pg.locator(".turn .banner--error").last).to_contain_text("Mock server error")
    ctx.close()


def test_dark_mode_renders(browser, base_url):
    ctx = browser.new_context(viewport={"width": 1280, "height": 800}, color_scheme="dark")
    pg = ctx.new_page()
    pg.goto(base_url)
    expect(pg.locator("#status-text")).to_have_text("API connected")
    bg = pg.evaluate("getComputedStyle(document.body).backgroundColor")
    assert bg == "rgb(21, 21, 18)", bg
    shot(pg, "10-desktop-dark")
    ctx.close()
