#!/usr/bin/env python3
"""Headless Chrome smoke test for the source-backed POLARIS X workflow."""

from __future__ import annotations

import argparse
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright


APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
VISUAL_PAIRS = (
    (".hero-copy", ".target-hud"),
    (".hero-copy", ".scene-legend"),
    (".target-hud", ".observer-hud"),
    (".scene-side-controls", ".geospatial-hud"),
    (".scene-side-controls", ".tool-rail"),
    (".mission-summary", ".time-console"),
    (".mission-summary", ".geospatial-hud"),
    (".time-console", ".geospatial-hud"),
)


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        return


def assert_visual_contract(page, width: int, height: int) -> None:
    """Catch the stylesheet/layout collapse shown in the 11:22 reference capture."""
    state = page.evaluate(
        """() => ({
          bodyOverflow: getComputedStyle(document.body).overflow,
          topbarPosition: getComputedStyle(document.querySelector('.topbar')).position,
          activeCameraBackground: getComputedStyle(document.querySelector('.camera-active')).backgroundColor,
          relief: document.querySelector('#reliefMode').value,
          reliefBadge: document.querySelector('#reliefBadge').textContent,
          scrollWidth: document.documentElement.scrollWidth,
          scrollHeight: document.documentElement.scrollHeight,
        })"""
    )
    assert state["bodyOverflow"] == "hidden", state
    assert state["topbarPosition"] == "fixed", state
    assert state["activeCameraBackground"] not in ("rgba(0, 0, 0, 0)", "transparent"), state
    assert state["relief"] == "true", state
    assert "TRUE VERTICAL SCALE" in state["reliefBadge"], state
    assert state["scrollWidth"] == width and state["scrollHeight"] == height, state
    for first, second in VISUAL_PAIRS:
        a = page.locator(first).bounding_box()
        b = page.locator(second).bounding_box()
        if a is None or b is None:
            continue
        horizontal = min(a["x"] + a["width"], b["x"] + b["width"]) - max(a["x"], b["x"])
        vertical = min(a["y"] + a["height"], b["y"] + b["height"]) - max(a["y"], b["y"])
        assert horizontal <= 1 or vertical <= 1, f"Layout collision {first} / {second}: {a} {b}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshot", action="store_true")
    args = parser.parse_args()
    if not CHROME.exists():
        raise SystemExit(f"Chrome not found at {CHROME}")

    handler = lambda *h_args, **h_kwargs: QuietHandler(  # noqa: E731
        *h_args, directory=str(APP), **h_kwargs
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    errors: list[str] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True, executable_path=str(CHROME)
            )
            page = browser.new_page(viewport={"width": 1512, "height": 982})
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{server.server_port}", wait_until="networkidle")
            page.locator("#dataStatus").wait_for(state="visible")
            assert page.locator("#dataStatus").inner_text() == "SOURCE-BASED · UNVALIDATED"
            page.wait_for_timeout(900)
            assert_visual_contract(page, 1512, 982)

            page.locator("#siteSelect").select_option("shackleton")
            page.wait_for_timeout(250)
            assert "pgda.gsfc.nasa.gov" in (page.locator("#terrainSource").text_content() or "")
            assert "JPL Horizons" in (page.locator("#skySource").text_content() or "")

            full_bundle = APP / "data" / "polaris-source-site01-2026-11-14-v2.json"
            page.locator("#bundleInput").set_input_files(str(full_bundle))
            page.wait_for_timeout(500)
            page.locator("#siteSelect").select_option("connecting")
            page.wait_for_timeout(250)
            options = page.locator("#terrainScenario option").all()
            assert len(options) == 6, f"Expected 6 terrain realizations, got {len(options)}"
            page.locator("#terrainScenario").select_option("clone:001")
            page.wait_for_timeout(250)
            assert "0001" in (page.locator("#terrainSource").text_content() or "")
            page.locator("#terrainScenario").select_option("default")
            page.wait_for_timeout(700)
            mesh_stats = page.locator("#meshStats").inner_text()
            assert "5 M + 80 M LOD" in mesh_stats and "640K TRIANGLES" in mesh_stats

            page.locator("#reliefMode").select_option("enhanced")
            page.wait_for_timeout(250)
            assert "RELIEF ×2.38" in page.locator("#reliefBadge").inner_text()
            page.locator("#reliefMode").select_option("true")
            page.wait_for_timeout(250)
            assert_visual_contract(page, 1512, 982)

            page.locator("#missionToggle").click()
            assert "true" == page.locator("#missionToggle").get_attribute("aria-expanded")
            page.locator("#missionClose").click()
            page.locator("#analysisToggle").click()
            assert "true" == page.locator("#analysisToggle").get_attribute("aria-expanded")
            page.locator("#analysisClose").click()
            page.wait_for_timeout(600)

            if args.screenshot:
                path = APP / "docs" / "browser-source-case.png"
                page.screenshot(path=str(path), full_page=True)
                print(f"Wrote {path.relative_to(ROOT)}")
                visual_dir = APP / "docs" / "visual-audit"
                visual_dir.mkdir(parents=True, exist_ok=True)
                visual_1512 = visual_dir / "after-1512x982.png"
                page.screenshot(path=str(visual_1512))
                print(f"Wrote {visual_1512.relative_to(ROOT)}")
                page.set_viewport_size({"width": 1920, "height": 1080})
                page.wait_for_timeout(300)
                assert_visual_contract(page, 1920, 1080)
                visual_1920 = visual_dir / "after-1920x1080.png"
                page.screenshot(path=str(visual_1920))
                print(f"Wrote {visual_1920.relative_to(ROOT)}")
                page.set_viewport_size({"width": 1512, "height": 982})
                page.wait_for_timeout(250)

            page.locator("#globeMode").evaluate("button => button.click()")
            page.locator("#globalModelStatus").get_by_text("LOADED", exact=False).wait_for(timeout=30_000)
            assert "NASA SVS LRO GLOBAL MOON" in page.locator("#renderSource").inner_text()
            assert "LOADED" in page.locator("#globalModelStatus").inner_text()
            assert "1.02M TRIANGLES" in page.locator("#meshStats").inner_text()
            global_bytes = page.locator("#moonCanvas").evaluate(
                "canvas => { window.__POLARIS_SCENE__?.render?.(); return canvas.toDataURL('image/png').length; }"
            )
            assert global_bytes > 10000, "NASA global Moon canvas appears empty"
            if args.screenshot:
                global_path = APP / "docs" / "browser-global-moon.png"
                page.screenshot(path=str(global_path), full_page=True)
                print(f"Wrote {global_path.relative_to(ROOT)}")
            page.locator("#localMode").evaluate("button => button.click()")
            page.wait_for_timeout(350)

            file_page = browser.new_page(viewport={"width": 1512, "height": 982})
            file_page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
            file_page.on("pageerror", lambda error: errors.append(str(error)))
            file_page.goto((APP / "index.html").as_uri(), wait_until="networkidle")
            file_page.locator("#dataStatus").wait_for(state="visible")
            assert file_page.locator("#dataStatus").inner_text() == "SOURCE-BASED · UNVALIDATED"
            file_page.wait_for_timeout(700)
            mesh_stats = file_page.locator("#meshStats").inner_text()
            assert "TRIANGLES" in mesh_stats and ("SOURCE GRID" in mesh_stats or "LOD" in mesh_stats)
            rendered_bytes = file_page.locator("#moonCanvas").evaluate(
                "canvas => { window.__POLARIS_SCENE__?.render?.(); return canvas.toDataURL('image/png').length; }"
            )
            assert rendered_bytes > 10000, "Direct-file WebGL canvas appears empty"
            if args.screenshot:
                file_path = APP / "docs" / "browser-file-launch.png"
                file_page.screenshot(path=str(file_path), full_page=True)
                print(f"Wrote {file_path.relative_to(ROOT)}")
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    if errors:
        raise SystemExit("Browser errors:\n" + "\n".join(errors))
    print("Browser smoke passed: localhost and direct-file models, source cache, full bundle, and clone selection")


if __name__ == "__main__":
    main()
