"""Hermes chat sessions in the e2e Desktop: profile switching, sending, reading the transcript.

Shared by the stage 3 use cases (UC23 to UC26), which drive Rung's agent tools from real Hermes
sessions of the isolated home's `coder` profile through the deterministic stub model.
"""

from __future__ import annotations

import json
import time
import urllib.request

import harness as H

STUB = "http://127.0.0.1:18765/v1"
COMPOSER = "[contenteditable=true][aria-label=Message]"


def model_calls() -> int:
    """Every completion the stub model has answered so far (not capped)."""
    with urllib.request.urlopen(STUB + "/count", timeout=5) as r:
        return int(json.load(r)["count"])


def use_profile(page, name: str) -> None:
    """Switch the Desktop to a Hermes profile of the isolated home and wait until it is active."""
    if name == "default":
        loc = page.locator("button[aria-label='Switch to default']")
        if loc.count():
            loc.first.click()
        H.wait_until(lambda: page.locator("button[aria-label='Switch to default']").count() == 0, timeout=60,
                     msg="back on the default profile")
    else:
        sel = f"button[aria-label={json.dumps(name)}]"
        page.locator(sel).first.wait_for(timeout=30000)
        if page.locator(sel).first.get_attribute("aria-pressed") != "true":
            page.locator(sel).first.click()
        H.wait_until(lambda: page.locator(sel).first.get_attribute("aria-pressed") == "true", timeout=60,
                     msg=f"profile {name} active")
    page.locator(COMPOSER).first.wait_for(timeout=60000)
    H.wait_until(lambda: not waking(page), timeout=120, msg=f"{name} backend up")


def waking(page) -> bool:
    """A visible "Waking up <profile>" indicator: the profile's backend is still starting."""
    return page.evaluate("""() => [...document.querySelectorAll('body *')].some(el => el.children.length === 0
        && /Waking up/.test(el.textContent || '') && el.getClientRects().length > 0
        && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).opacity !== '0')""")


def new_session(page) -> None:
    page.evaluate("location.hash = '#/'")
    H.dismiss_toasts(page)
    page.get_by_text("New session", exact=True).first.click()
    page.locator(COMPOSER).first.wait_for(timeout=30000)
    time.sleep(0.5)


def chat(page, text: str) -> None:
    box = page.locator(COMPOSER).first
    box.wait_for(timeout=30000)
    box.click()
    page.keyboard.type(text)
    page.keyboard.press("Enter")


def transcript(page) -> str:
    """Text of the session pane that holds the composer (the chat transcript)."""
    return page.evaluate("""() => {
        const box = document.querySelector('[contenteditable=true][aria-label=Message]');
        const pane = box && box.closest('.isolate.h-full');
        return pane ? pane.innerText : document.body.innerText;
    }""")


def count(page, needle: str) -> int:
    return transcript(page).lower().count(needle.lower())


def turn(page, text: str, timeout: float = 90) -> str:
    """Send one message and wait for the stub's reply after the tool result ("Done: ..."). Returns the
    transcript text added by this turn."""
    before = transcript(page)
    n = before.count("Done: ")
    calls = model_calls()
    chat(page, text)
    H.wait_until(lambda: transcript(page).count("Done: ") > n and model_calls() >= calls + 2, timeout=timeout,
                 msg=f"reply to {text!r}: {transcript(page)[-400:]!r}")
    time.sleep(0.5)
    now = transcript(page)
    # The turn starts at the first occurrence of the message that was not there before (the tool result
    # can quote the message again, as a claim's chat title does).
    i = -1
    for _ in range(before.count(text) + 1):
        i = now.find(text, i + 1)
        if i < 0:
            break
    return now[i:] if i >= 0 else now[len(before):]


def route(page) -> str:
    return page.evaluate("location.hash")


def go(page, hash_: str) -> None:
    page.evaluate(f"location.hash = {json.dumps(hash_)}")
    page.locator(COMPOSER).first.wait_for(timeout=30000)
    time.sleep(0.5)
