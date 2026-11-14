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


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        return


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

            file_page = browser.new_page(viewport={"width": 1512, "height": 982})
            file_page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
            file_page.on("pageerror", lambda error: errors.append(str(error)))
            file_page.goto((APP / "index.html").as_uri(), wait_until="networkidle")
            file_page.locator("#dataStatus").wait_for(state="visible")
            assert file_page.locator("#dataStatus").inner_text() == "SOURCE-BASED · UNVALIDATED"
            file_page.wait_for_timeout(700)
            mesh_stats = file_page.locator("#meshStats").inner_text()
            assert "TRIANGLES" in mesh_stats and "MESH" in mesh_stats
            rendered_bytes = file_page.locator("#moonCanvas").evaluate(
                "canvas => canvas.toDataURL('image/png').length"
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
