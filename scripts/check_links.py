"""Crawl the Space and check every link, including fragment anchors.

    python scripts/check_links.py --url https://tomscot-keel.hf.space

Exits non-zero if a link 404s, a fragment has no target, or a page fails to load.
"""

from __future__ import annotations

import argparse
import re
import urllib.error
import urllib.parse
import urllib.request

PAGES = (
    "/",
    "/access",
    "/card/m0-base",
    "/card/m1-ablation",
    "/card/m2-lora",
    "/card/heretic",
    "/verify/m2-lora",
    "/guide",
)
LINK = re.compile(r"""href=['"]([^'"]+)['"]""")


def fetch(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except Exception:  # noqa: BLE001
        return 0, ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://tomscot-keel.hf.space")
    args = parser.parse_args()
    base = args.url.rstrip("/")
    host = urllib.parse.urlparse(base).netloc

    failures: list[str] = []
    seen: dict[str, tuple[int, str]] = {}
    fragments: set[tuple[str, str]] = set()

    for page in PAGES:
        page_url = base + page
        status, html = fetch(page_url)
        if status != 200:
            failures.append(f"{page} -> {status}")
            print(f"FAIL page {page} {status}")
            continue
        print(f"ok   page {page}")
        for raw in LINK.findall(html):
            if raw.startswith(("mailto:", "javascript:")):
                continue
            target = urllib.parse.urljoin(page_url, raw)
            parsed = urllib.parse.urlparse(target)
            if parsed.netloc and parsed.netloc != host:
                continue
            path = parsed.path or "/"
            if path not in seen:
                seen[path] = fetch(base + path)
            code, body = seen[path]
            if code != 200:
                failures.append(f"{page} -> {raw} ({path}) {code}")
                print(f"FAIL link {page} -> {raw} ({code})")
            if parsed.fragment:
                fragments.add((path, parsed.fragment))

    for path, fragment in sorted(fragments):
        code, body = seen.get(path, fetch(base + path))
        ok = code == 200 and f'id="{fragment}"' in body
        if ok:
            print(f"ok   anchor {path}#{fragment}")
        else:
            failures.append(f"anchor {path}#{fragment} missing")
            print(f"FAIL anchor {path}#{fragment}")

    print(f"\n{len(seen)} links, {len(fragments)} anchors, {len(failures)} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
