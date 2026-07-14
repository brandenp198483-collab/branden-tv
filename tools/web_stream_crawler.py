#!/usr/bin/env python3

import argparse
import html
import json
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import requests


DIRECT_STREAM_RE = re.compile(
    r'https?://[^\s"\'<>\\]+?(?:\.m3u8|\.m3u)'
    r'(?:\?[^\s"\'<>\\]*)?',
    re.I,
)

GENERIC_URL_RE = re.compile(
    r'https?://[^\s"\'<>\\]+',
    re.I,
)

BAD_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".webp",
    ".svg", ".css", ".js", ".woff", ".woff2",
    ".ttf", ".ico", ".pdf", ".zip",
)

BAD_DOMAINS = {
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
    "facebook.com",
    "www.facebook.com",
    "instagram.com",
    "www.instagram.com",
    "tiktok.com",
    "www.tiktok.com",
}

DEFAULT_QUERIES = [
    '"{target}" m3u8',
    '"{target}" m3u',
    '"{target}" HLS stream',
    '"{target}" playlist',
    '"{target}" live stream URL',
    '"{target}" IPTV',
    '"{target}" filetype:m3u8',
    '"{target}" filetype:m3u',
    'site:github.com "{target}" m3u8',
    'site:gist.github.com "{target}"',
    'site:gitlab.com "{target}" m3u8',
    'site:pastebin.com "{target}" m3u8',
]


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "scan"


def normalize_url(value: str) -> str:
    value = html.unescape(value.strip())
    value = value.rstrip(".,);]}>\"'")

    # Decode common search redirect wrappers.
    parsed = urlparse(value)
    query = parse_qs(parsed.query)

    for key in ("q", "url", "uddg", "target"):
        if key in query and query[key]:
            candidate = unquote(query[key][0])

            if candidate.startswith(("http://", "https://")):
                value = candidate
                break

    return value


def likely_page_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except Exception:
        return False

    if parsed.scheme not in {"http", "https"}:
        return False

    host = parsed.netloc.lower().split(":")[0]

    if host in BAD_DOMAINS:
        return False

    lower_path = parsed.path.lower()

    if lower_path.endswith(BAD_EXTENSIONS):
        return False

    return True


def extract_stream_urls(text: str) -> list[str]:
    results = []

    for match in DIRECT_STREAM_RE.findall(html.unescape(text or "")):
        url = normalize_url(match)

        if url.startswith(("http://", "https://")):
            results.append(url)

    return results


def fetch_page(url: str, timeout: int) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 16) "
            "AppleWebKit/537.36 Chrome/131 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/vnd.apple.mpegurl,"
            "application/x-mpegURL,*/*"
        ),
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=timeout,
        allow_redirects=True,
    )
    response.raise_for_status()

    # Avoid downloading huge files/pages.
    content = response.content[:2_000_000]
    return content.decode(response.encoding or "utf-8", errors="ignore")


def stream_score(item: dict, target_terms: list[str]) -> int:
    text = " ".join([
        item.get("name", ""),
        item.get("source_title", ""),
        item.get("source_url", ""),
        item.get("stream_url", ""),
        item.get("snippet", ""),
    ]).lower()

    score = 0

    for term in target_terms:
        if term and term in text:
            score += 35

    url = item["stream_url"].lower()

    if ".m3u8" in url:
        score += 40

    if url.startswith("https://"):
        score += 10

    if any(host in url for host in (
        "amagi.tv",
        "cloudfront.net",
        "akamai",
        "fastly",
        "tubi.io",
        "uplynk.com",
        "wurl.com",
    )):
        score += 25

    if any(word in url for word in (
        "/live/",
        "master.m3u8",
        "playlist.m3u8",
        "index.m3u8",
    )):
        score += 15

    if any(word in text for word in (
        "radio",
        "audio only",
        "am ",
        "fm ",
    )):
        score -= 60

    return score


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Search the public web for M3U/M3U8 candidates and "
            "create an isolated BrandenTV test playlist."
        )
    )
    parser.add_argument("target")
    parser.add_argument(
        "--results-per-query",
        type=int,
        default=20,
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=100,
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=12,
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.4,
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Only inspect search-result titles, snippets and URLs.",
    )

    args = parser.parse_args()

    target = args.target.strip()
    slug = slugify(target)

    out_dir = Path("docs/web-scans")
    out_dir.mkdir(parents=True, exist_ok=True)

    json_out = out_dir / f"web-{slug}-candidates.json"
    report_out = out_dir / f"web-{slug}-report.txt"
    playlist_out = Path(f"docs/BrandenTV-Web-{slug}-Test.m3u")

    queries = [
        template.format(target=target)
        for template in DEFAULT_QUERIES
    ]

    search_results = []
    seen_result_urls = set()

    print("TARGET:", target)
    print()

    search_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 16) "
            "AppleWebKit/537.36 Chrome/131 Safari/537.36"
        )
    }

    result_re = re.compile(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        re.I | re.S,
    )

    snippet_re = re.compile(
        r'class="result__snippet"[^>]*>(.*?)</',
        re.I | re.S,
    )

    for query in queries:
        print("QUERY:", query)

        try:
            response = requests.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers=search_headers,
                timeout=args.timeout,
            )
            response.raise_for_status()
            page = response.text
        except Exception as exc:
            print("  SEARCH FAILED:", exc)
            continue

        result_matches = list(result_re.finditer(page))
        snippet_matches = list(snippet_re.finditer(page))
        added = 0

        for index, match in enumerate(
            result_matches[:args.results_per_query]
        ):
            page_url = normalize_url(
                html.unescape(match.group(1))
            )

            if not likely_page_url(page_url):
                continue

            if page_url in seen_result_urls:
                continue

            title = re.sub(
                r"<[^>]+>",
                " ",
                html.unescape(match.group(2)),
            )
            title = re.sub(r"\\s+", " ", title).strip()

            snippet = ""

            if index < len(snippet_matches):
                snippet = re.sub(
                    r"<[^>]+>",
                    " ",
                    html.unescape(
                        snippet_matches[index].group(1)
                    ),
                )
                snippet = re.sub(
                    r"\\s+",
                    " ",
                    snippet,
                ).strip()

            seen_result_urls.add(page_url)

            search_results.append({
                "query": query,
                "title": title,
                "url": page_url,
                "snippet": snippet,
            })
            added += 1

        print("  New pages:", added)
        time.sleep(args.delay)

    print()
    print("Unique result pages:", len(search_results))

    candidates = []

    # Direct streams exposed in titles/snippets/result URLs.
    for result in search_results:
        combined = "\n".join([
            result["title"],
            result["url"],
            result["snippet"],
        ])

        for stream_url in extract_stream_urls(combined):
            candidates.append({
                "name": result["title"] or target,
                "stream_url": stream_url,
                "source_url": result["url"],
                "source_title": result["title"],
                "snippet": result["snippet"],
                "query": result["query"],
                "found_in": "search result",
            })

    if not args.no_fetch:
        pages = search_results[:args.max_pages]

        for number, result in enumerate(pages, 1):
            print(
                f"[{number}/{len(pages)}] Fetching:",
                result["url"][:100],
            )

            try:
                page_text = fetch_page(
                    result["url"],
                    timeout=args.timeout,
                )
            except Exception as exc:
                print("  FAILED:", str(exc)[:160])
                continue

            streams = extract_stream_urls(page_text)

            for stream_url in streams:
                candidates.append({
                    "name": result["title"] or target,
                    "stream_url": stream_url,
                    "source_url": result["url"],
                    "source_title": result["title"],
                    "snippet": result["snippet"],
                    "query": result["query"],
                    "found_in": "page content",
                })

            print("  Streams found:", len(streams))
            time.sleep(args.delay)

    target_terms = [
        part.lower()
        for part in re.findall(r"[A-Za-z0-9]+", target)
        if len(part) >= 3
    ]

    unique = {}

    for item in candidates:
        url = normalize_url(item["stream_url"])

        if not url.startswith(("http://", "https://")):
            continue

        if ".m3u" not in url.lower():
            continue

        item["stream_url"] = url
        item["score"] = stream_score(item, target_terms)

        existing = unique.get(url)

        if existing is None or item["score"] > existing["score"]:
            unique[url] = item

    items = sorted(
        unique.values(),
        key=lambda item: (
            -item["score"],
            item["stream_url"].lower(),
        ),
    )

    payload = {
        "target": target,
        "queries": queries,
        "result_pages": len(search_results),
        "candidates": items,
    }

    json_out.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    report = [
        f"BrandenTV Web Stream Search: {target}",
        "=" * 90,
        f"Search queries: {len(queries)}",
        f"Unique result pages: {len(search_results)}",
        f"Unique stream candidates: {len(items)}",
        "",
    ]

    playlist = ["#EXTM3U"]

    for number, item in enumerate(items, 1):
        report.extend([
            "=" * 90,
            f"{number:03d}. {item['name']}",
            f"Score: {item['score']}",
            f"Found in: {item['found_in']}",
            f"Search query: {item['query']}",
            f"Source page: {item['source_url']}",
            f"URL: {item['stream_url']}",
            "",
        ])

        safe_name = item["name"].replace(",", " ").strip()
        label = f"{number:03d} - {safe_name}"

        playlist.extend([
            (
                f'#EXTINF:-1 group-title="Web {target} Test",'
                f"{label}"
            ),
            item["stream_url"],
        ])

    report_out.write_text(
        "\n".join(report) + "\n",
        encoding="utf-8",
    )

    playlist_out.write_text(
        "\n".join(playlist) + "\n",
        encoding="utf-8",
    )

    print()
    print("Unique stream candidates:", len(items))
    print("JSON:", json_out)
    print("Report:", report_out)
    print("Test playlist:", playlist_out)


if __name__ == "__main__":
    main()
