#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
from typing import Sequence

import requests


STORE_PAGE_URL = "https://store.steampowered.com/app/{appid}/"
URL_PATTERN = re.compile(r"https?://[^\"'<>\\)\\s]+", re.IGNORECASE)


def extract_matches(html: str, terms: Sequence[str]) -> dict[str, list[str]]:
    urls = [match.replace("\\/", "/").replace("&amp;", "&") for match in URL_PATTERN.findall(html)]
    results: dict[str, list[str]] = {}
    for term in terms:
        lowered = term.lower()
        matches = [url for url in urls if lowered in url.lower()]
        results[term] = matches[:20]
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch and inspect a single Steam store page")
    parser.add_argument("appid", type=int)
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()

    response = requests.get(
        STORE_PAGE_URL.format(appid=args.appid),
        params={"cc": "us", "l": "english"},
        timeout=args.timeout,
        headers={
            "User-Agent": (
                "SteamRecommenderStoreDebug/1.0 "
                "(https://github.com/openai/codex)"
            )
        },
    )

    print("status:", response.status_code)
    print("url:", response.url)
    print("content-type:", response.headers.get("content-type"))
    print("length:", len(response.text))

    html = response.text
    terms = [
        "steamstatic",
        "shared.akamai.steamstatic.com",
        "library_hero",
        "library_600x900",
        "library_capsule",
        "/logo",
        "/icon.",
        "capsule",
        "header",
    ]

    print("contains:")
    for term in terms:
        print(f"  {term}: {term.lower() in html.lower()}")

    print("\nmatching urls:")
    matches = extract_matches(html, terms)
    for term, urls in matches.items():
        print(f"\n[{term}] {len(urls)}")
        for url in urls:
            print(url)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
