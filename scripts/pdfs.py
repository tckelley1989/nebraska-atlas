"""Render one PDF per profile page with headless Chromium, next to its HTML.

Run after build.py:  python scripts/pdfs.py [--only system/24-0001 ...]
Uses the print stylesheet in site.css. Serves _site over local HTTP so fonts and
relative links resolve the same way they do on Pages.
"""
import argparse
import asyncio
import functools
import http.server
import socketserver
import sys
import threading
import time
from pathlib import Path

from playwright.async_api import async_playwright

OUT = Path(__file__).resolve().parents[1] / "_site"
WORKERS = 6


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    handler = functools.partial(Quiet, directory=str(OUT))
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


async def render(paths, port):
    q = asyncio.Queue()
    for p in paths:
        q.put_nowait(p)
    failed = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()

        async def worker():
            page = await browser.new_page()
            await page.emulate_media(media="print")
            while not q.empty():
                rel = q.get_nowait()
                try:
                    await page.goto(f"http://127.0.0.1:{port}/{rel}.html", wait_until="networkidle", timeout=60000)
                    await page.evaluate("document.fonts.ready")
                    await page.pdf(path=str(OUT / f"{rel}.pdf"), format="Letter", print_background=True,
                                   prefer_css_page_size=True, display_header_footer=True,
                                   header_template="<span></span>",
                                   footer_template='<div style="font:8px Arial;color:#5e5a54;width:100%;text-align:center">'
                                                   'The Nebraska Ledger · page <span class="pageNumber"></span> of <span class="totalPages"></span></div>')
                except Exception as e:  # noqa: BLE001
                    failed.append((rel, str(e)[:200]))
            await page.close()

        await asyncio.gather(*(worker() for _ in range(WORKERS)))
        await browser.close()
    return failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="paths like system/24-0001")
    args = ap.parse_args()
    paths = args.only or sorted(str(p.relative_to(OUT).with_suffix("")) for d in ("system", "county") for p in (OUT / d).glob("*.html"))
    httpd, port = serve()
    t = time.time()
    failed = asyncio.run(render(paths, port))
    httpd.shutdown()
    print(f"Rendered {len(paths) - len(failed)} of {len(paths)} PDFs in {time.time() - t:.0f}s")
    for rel, err in failed:
        print("FAILED", rel, err)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
