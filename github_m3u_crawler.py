#!/usr/bin/env python3

import argparse
import base64
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import quote

import requests

API = "https://api.github.com"
CACHE_DIR = Path("github_m3u_cache")
REPORT_DIR = Path("docs/github-scans")

CACHE_DIR.mkdir(exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

STREAM_RE = re.compile(
    r'https?://[^\s\'"<>]+',
    re.IGNORECASE,
)

PLAYLIST_EXTENSIONS = (".m3u", ".m3u8")


def headers():
    result = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "BrandenTV-GitHub-M3U-Crawler/1.0",
        "X-GitHub-Api-Version": "2026-03-10",
    }

    token = os.environ.get("GITHUB_TOKEN", "").strip()

    if token:
        result["Authorization"] = f"Bearer {token}"

    return result


def api_get(url, params=None):
    response = requests.get(
        url,
        headers=headers(),
        params=params,
        timeout=40,
    )

    if response.status_code == 403:
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset = response.headers.get("X-RateLimit-Reset")

        raise RuntimeError(
            f"GitHub rate limit reached. Remaining={remaining}, reset={reset}"
        )

    response.raise_for_status()
    return response


def safe_filename(value):
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value)
    return value.strip("-")[:180] or "unknown"


def search_repositories(query, pages, per_page):
    repos = {}

    for page in range(1, pages + 1):
        print(f"Searching repositories, page {page}...")

        response = api_get(
            f"{API}/search/repositories",
            params={
                "q": query,
                "sort": "updated",
                "order": "desc",
                "page": page,
                "per_page": per_page,
            },
        )

        data = response.json()

        for item in data.get("items", []):
            repos[item["full_name"]] = {
                "full_name": item["full_name"],
                "default_branch": item.get("default_branch", "main"),
                "html_url": item["html_url"],
                "description": item.get("description") or "",
                "updated_at": item.get("updated_at"),
                "size": item.get("size", 0),
                "archived": item.get("archived", False),
            }

        if len(data.get("items", [])) < per_page:
            break

        time.sleep(2)

    return list(repos.values())


def get_repo_tree(repo):
    full_name = repo["full_name"]
    branch = repo["default_branch"]

    response = api_get(
        f"{API}/repos/{full_name}/git/trees/{quote(branch, safe='')}",
        params={"recursive": "1"},
    )

    return response.json().get("tree", [])


def download_blob(repo_name, path):
    response = api_get(
        f"{API}/repos/{repo_name}/contents/{quote(path, safe='/')}"
    )

    data = response.json()

    if isinstance(data, list):
        return None

    encoded = data.get("content", "")
    encoding = data.get("encoding", "")

    if encoding == "base64":
        return base64.b64decode(encoded).decode("utf-8", errors="ignore")

    download_url = data.get("download_url")

    if download_url:
        raw = requests.get(download_url, timeout=40)
        raw.raise_for_status()
        return raw.text

    return None


def parse_playlist(text, source_label):
    channels = []
    pending_name = None
    pending_info = ""

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("#EXTINF"):
            pending_info = line
            pending_name = (
                line.rsplit(",", 1)[-1].strip()
                if "," in line
                else "Unknown"
            )
            continue

        if line.startswith("#"):
            continue

        urls = STREAM_RE.findall(line)

        for url in urls:
            url = url.rstrip("),.;]")

            channels.append({
                "name": pending_name or "Unlabeled stream",
                "url": url,
                "info": pending_info,
                "source": source_label,
            })

        pending_name = None
        pending_info = ""

    return channels


def relevant_candidate(candidate, target):
    if not target:
        return True

    target_clean = re.sub(r"[^a-z0-9]+", " ", target.lower()).strip()

    haystack = " ".join([
        candidate.get("name", ""),
        candidate.get("info", ""),
        candidate.get("source", ""),
        candidate.get("url", ""),
    ]).lower()

    target_words = target_clean.split()

    return all(word in haystack for word in target_words)


def write_outputs(target, repositories, playlist_files, candidates):
    slug = safe_filename(target.lower() if target else "all")

    json_path = REPORT_DIR / f"github-{slug}-candidates.json"
    report_path = REPORT_DIR / f"github-{slug}-report.txt"
    test_path = Path("docs") / f"BrandenTV-GitHub-{slug}-Test.m3u"

    json_path.write_text(
        json.dumps(
            {
                "target": target,
                "repositories": repositories,
                "playlist_files": playlist_files,
                "candidates": candidates,
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    report = [
        f"Target: {target or 'ALL'}",
        f"Repositories scanned: {len(repositories)}",
        f"Playlist files found: {len(playlist_files)}",
        f"Candidates found: {len(candidates)}",
        "",
    ]

    for number, candidate in enumerate(candidates, 1):
        report.extend([
            "=" * 78,
            f"{number:03d}. {candidate['name']}",
            f"Repository: {candidate['repository']}",
            f"File: {candidate['file']}",
            f"URL: {candidate['url']}",
        ])

    report_path.write_text("\n".join(report) + "\n")

    m3u = ["#EXTM3U"]

    for number, candidate in enumerate(candidates, 1):
        label = candidate["name"].replace(",", " ").strip()
        repo = candidate["repository"]

        m3u.extend([
            (
                f'#EXTINF:-1 group-title="GitHub {target or "M3U"} Test",'
                f'{number:03d} - {label} [{repo}]'
            ),
            candidate["url"],
        ])

    test_path.write_text("\n".join(m3u) + "\n")

    print()
    print("JSON:", json_path)
    print("Report:", report_path)
    print("Test playlist:", test_path)


def main():
    parser = argparse.ArgumentParser(
        description="Find public GitHub M3U/M3U8 files and build a test playlist."
    )

    parser.add_argument(
        "target",
        nargs="?",
        default="",
        help='Optional channel target, such as "Discovery Channel"',
    )

    parser.add_argument(
        "--pages",
        type=int,
        default=3,
        help="Repository search pages to scan",
    )

    parser.add_argument(
        "--per-page",
        type=int,
        default=30,
        help="Repositories per page",
    )

    parser.add_argument(
        "--max-files",
        type=int,
        default=250,
        help="Maximum playlist files to download",
    )

    args = parser.parse_args()

    target = args.target.strip()

    repo_queries = [
        "m3u iptv in:name,description,readme",
        "m3u8 playlist in:name,description,readme",
        "iptv playlist in:name,description,readme",
    ]

    if target:
        repo_queries.insert(
            0,
            f'"{target}" m3u OR m3u8 in:name,description,readme',
        )

    repositories = {}

    for query in repo_queries:
        print()
        print("QUERY:", query)

        for repo in search_repositories(
            query,
            pages=args.pages,
            per_page=args.per_page,
        ):
            if repo["archived"]:
                continue

            repositories[repo["full_name"]] = repo

    repositories = list(repositories.values())

    print()
    print("Unique repositories:", len(repositories))

    playlist_files = []
    candidates = []
    seen_urls = set()
    files_downloaded = 0

    for repo_number, repo in enumerate(repositories, 1):
        if files_downloaded >= args.max_files:
            break

        print(
            f"[{repo_number}/{len(repositories)}] "
            f"Scanning {repo['full_name']}"
        )

        try:
            tree = get_repo_tree(repo)
        except Exception as exc:
            print("  TREE FAILED:", exc)
            continue

        paths = [
            item["path"]
            for item in tree
            if item.get("type") == "blob"
            and item.get("path", "").lower().endswith(PLAYLIST_EXTENSIONS)
        ]

        for path in paths:
            if files_downloaded >= args.max_files:
                break

            source_label = f"{repo['full_name']}:{path}"

            try:
                text = download_blob(repo["full_name"], path)
            except Exception as exc:
                print("  DOWNLOAD FAILED:", source_label, exc)
                continue

            if not text:
                continue

            files_downloaded += 1

            cache_name = (
                safe_filename(repo["full_name"])
                + "__"
                + safe_filename(path)
            )

            cache_path = CACHE_DIR / cache_name
            cache_path.write_text(text, errors="ignore")

            playlist_files.append({
                "repository": repo["full_name"],
                "file": path,
                "cached_as": str(cache_path),
            })

            parsed = parse_playlist(text, source_label)

            for candidate in parsed:
                if not relevant_candidate(candidate, target):
                    continue

                url = candidate["url"]

                if url in seen_urls:
                    continue

                seen_urls.add(url)

                candidate["repository"] = repo["full_name"]
                candidate["file"] = path
                candidates.append(candidate)

        time.sleep(1)

    candidates.sort(
        key=lambda item: (
            item["name"].lower(),
            item["repository"].lower(),
        )
    )

    print()
    print("Repositories scanned:", len(repositories))
    print("Playlist files downloaded:", files_downloaded)
    print("Unique matching candidates:", len(candidates))

    write_outputs(
        target,
        repositories,
        playlist_files,
        candidates,
    )


if __name__ == "__main__":
    main()
