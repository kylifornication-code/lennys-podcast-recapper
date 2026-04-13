#!/usr/bin/env python3
"""
Enrich episode metadata from the YouTube Data API.

Instead of searching per-guest (unreliable), fetches the complete video catalog
from Lenny's Podcast channel, then matches each episode to the correct video
by comparing guest names against video titles and descriptions.

Usage:
    YOUTUBE_API_KEY=your_key python3 scripts/enrich-metadata.py

    # Dry run (print what would change without writing):
    YOUTUBE_API_KEY=your_key python3 scripts/enrich-metadata.py --dry-run

    # Re-check existing matches and fix wrong ones:
    YOUTUBE_API_KEY=your_key python3 scripts/enrich-metadata.py --revalidate

    # Force refresh the cached video catalog:
    YOUTUBE_API_KEY=your_key python3 scripts/enrich-metadata.py --refresh-catalog

Environment variables:
    YOUTUBE_API_KEY  - Required. Your YouTube Data API v3 key.
    EPISODES_DIR     - Optional. Defaults to data/episodes.
"""

import json
import os
import re
import ssl
import sys
import time
import unicodedata
import urllib.request
import urllib.parse
from pathlib import Path

import certifi
import yaml

CHANNEL_ID = "UC6t1O76G0jYXOAoYCm153dA"
UPLOADS_PLAYLIST = "UU6t1O76G0jYXOAoYCm153dA"
API_BASE = "https://www.googleapis.com/youtube/v3"
EPISODES_DIR = Path(os.environ.get("EPISODES_DIR", "data/episodes"))
CATALOG_PATH = Path(os.environ.get("CATALOG_PATH", "data/youtube-catalog.json"))

SSL_CTX = ssl.create_default_context(cafile=certifi.where())


def get_api_key():
    key = os.environ.get("YOUTUBE_API_KEY", "")
    if not key:
        print("Error: YOUTUBE_API_KEY environment variable is required", file=sys.stderr)
        sys.exit(1)
    return key


def youtube_get(endpoint: str, params: dict, retries: int = 3) -> dict:
    url = f"{API_BASE}/{endpoint}?" + urllib.parse.urlencode(params)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, context=SSL_CTX, timeout=30) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt < retries - 1:
                wait = 2 ** (attempt + 1)
                print(f"  Retry {attempt + 1}/{retries} after {wait}s: {e}")
                time.sleep(wait)
            else:
                raise


# ---------------------------------------------------------------------------
# Catalog: fetch all videos from the channel
# ---------------------------------------------------------------------------

def fetch_channel_catalog(api_key: str) -> list[dict]:
    """Page through the uploads playlist and fetch full details for every video."""
    print("Fetching video IDs from uploads playlist...")
    video_ids: list[str] = []
    page_token = None
    page = 0
    while True:
        params: dict = {
            "part": "snippet",
            "playlistId": UPLOADS_PLAYLIST,
            "maxResults": 50,
            "key": api_key,
        }
        if page_token:
            params["pageToken"] = page_token
        data = youtube_get("playlistItems", params)
        for item in data.get("items", []):
            vid = item["snippet"]["resourceId"].get("videoId")
            if vid:
                video_ids.append(vid)
        page += 1
        print(f"  Page {page}: {len(video_ids)} video IDs so far")
        page_token = data.get("nextPageToken")
        if not page_token:
            break
        time.sleep(0.1)

    print(f"Fetching details for {len(video_ids)} videos...")
    catalog: list[dict] = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        data = youtube_get("videos", {
            "part": "snippet,contentDetails,statistics",
            "id": ",".join(batch),
            "key": api_key,
        })
        catalog.extend(data.get("items", []))
        print(f"  Fetched details: {len(catalog)}/{len(video_ids)}")
        time.sleep(0.1)

    return catalog


def save_catalog(catalog: list[dict], path: Path):
    compact = []
    for v in catalog:
        snippet = v.get("snippet", {})
        stats = v.get("statistics", {})
        content = v.get("contentDetails", {})
        compact.append({
            "video_id": v["id"],
            "title": snippet.get("title", ""),
            "description": snippet.get("description", ""),
            "published_at": snippet.get("publishedAt", ""),
            "duration": content.get("duration", ""),
            "view_count": int(stats.get("viewCount", 0)),
        })
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(compact, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Catalog saved to {path} ({len(compact)} videos)")


def load_catalog(path: Path) -> list[dict] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


# ---------------------------------------------------------------------------
# Name normalization and matching
# ---------------------------------------------------------------------------

def strip_accents(s: str) -> str:
    """Remove diacritics so 'Lütke' matches 'Lutke'."""
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalize_name(guest: str) -> list[str]:
    """Return a list of name variants to search for in video text.

    Handles: '2.0'/'3.0' suffixes, 'Dr.' prefix, multi-guest '+' separator,
    'Live' suffix, compilation/teaser placeholders.
    """
    clean = re.sub(r"\s+\d+\.\d+$", "", guest)
    clean = re.sub(r"\s+Live$", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"^Dr\.\s*", "", clean)

    skip_names = {
        "teaser_2021", "teaser", "various (year-end review)",
        "interview q compilation", "eoy review",
    }
    if clean.lower().strip() in skip_names:
        return []

    parts = [p.strip() for p in clean.split("+")]
    return [p for p in parts if p]


def normalize_text(s: str) -> str:
    """Lowercase, strip accents, normalize hyphens to spaces."""
    return strip_accents(s.lower()).replace("-", " ")


def text_contains_name(text: str, name: str) -> bool:
    """Case-insensitive, accent-insensitive, hyphen-insensitive substring check."""
    return normalize_text(name) in normalize_text(text)


def score_match(name: str, video: dict) -> int:
    """Score how well a video matches a guest name. Higher is better, 0 means no match.

    Names in the first ~500 chars of the description are almost always the featured
    guest. Names deeper in the description are usually cross-references to other episodes.
    """
    title = video.get("title", "")
    desc = video.get("description", "")

    name_parts = name.split()
    last_name = name_parts[-1] if name_parts else ""

    if text_contains_name(title, name):
        return 100

    desc_early = desc[:500]
    if text_contains_name(desc_early, name):
        return 90

    if text_contains_name(desc, name):
        return 50

    if last_name and len(last_name) > 3 and text_contains_name(title, last_name):
        return 40
    return 0


MIN_MATCH_SCORE = 80
MIN_DURATION_SECONDS = 600
YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _is_valid_youtube_id(vid: str) -> bool:
    return bool(YOUTUBE_ID_RE.match(vid))


def _video_duration_seconds(video: dict) -> int:
    iso = video.get("duration", "")
    secs, _ = parse_iso_duration(iso)
    return secs


def find_best_match(guest: str, catalog: list[dict], claimed_ids: set[str]) -> dict | None:
    """Find the best matching video for a guest name from the catalog.

    Only accepts matches scoring >= MIN_MATCH_SCORE (name in title or early description)
    and for videos longer than MIN_DURATION_SECONDS (filters out shorts/clips).
    """
    names = normalize_name(guest)
    if not names:
        return None

    candidates: list[tuple[dict, int]] = []
    for video in catalog:
        vid = video["video_id"]
        if vid in claimed_ids:
            continue
        if _video_duration_seconds(video) < MIN_DURATION_SECONDS:
            continue
        best_score = 0
        for name in names:
            s = score_match(name, video)
            best_score = max(best_score, s)
        if best_score >= MIN_MATCH_SCORE:
            candidates.append((video, best_score))

    if not candidates:
        return None

    candidates.sort(key=lambda x: (-x[1], x[0].get("published_at", "")))
    return candidates[0][0]


def validate_existing_match(guest: str, video_id: str, catalog: list[dict]) -> bool:
    """Check if an existing video_id is a valid match for this guest.

    Returns True if the guest name appears in the video's title or description.
    """
    names = normalize_name(guest)
    if not names:
        return True

    video = None
    for v in catalog:
        if v["video_id"] == video_id:
            video = v
            break

    if video is None:
        return False

    for name in names:
        if score_match(name, video) > 0:
            return True
    return False


# ---------------------------------------------------------------------------
# Episode I/O
# ---------------------------------------------------------------------------

def parse_iso_duration(iso_duration: str) -> tuple[int, str]:
    """Convert ISO 8601 duration (PT1H2M3S) to (total_seconds, 'H:MM:SS')."""
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_duration)
    if not match:
        return 0, ""
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    total = hours * 3600 + minutes * 60 + seconds
    if hours > 0:
        human = f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        human = f"{minutes}:{seconds:02d}"
    return total, human


def read_episode(transcript_path: Path) -> tuple[dict, str]:
    """Read a transcript.md file, returning (frontmatter_dict, raw_transcript_text)."""
    content = transcript_path.read_text(encoding="utf-8")
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    frontmatter = yaml.safe_load(parts[1]) or {}
    transcript = parts[2]
    return frontmatter, transcript


def write_episode(transcript_path: Path, frontmatter: dict, transcript: str):
    """Write updated frontmatter + transcript back to file."""
    field_order = [
        "guest", "title", "youtube_url", "video_id", "publish_date",
        "description", "duration_seconds", "duration", "view_count",
        "channel", "keywords",
    ]
    ordered = {}
    for key in field_order:
        if key in frontmatter:
            ordered[key] = frontmatter[key]
    for key in frontmatter:
        if key not in ordered:
            ordered[key] = frontmatter[key]

    yaml_str = yaml.dump(
        ordered,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        width=120,
    )
    transcript_path.write_text(f"---\n{yaml_str}---{transcript}", encoding="utf-8")


def enrich_from_catalog_entry(fm: dict, entry: dict) -> dict:
    """Merge a catalog entry's data into the frontmatter dict."""
    duration_iso = entry.get("duration", "")
    duration_secs, duration_human = parse_iso_duration(duration_iso)
    publish_date = entry.get("published_at", "")[:10]
    video_id = entry["video_id"]

    fm["title"] = entry.get("title", fm.get("title", ""))
    fm["youtube_url"] = f"https://www.youtube.com/watch?v={video_id}"
    fm["video_id"] = video_id
    fm["publish_date"] = publish_date
    fm["description"] = entry.get("description", fm.get("description", ""))
    fm["duration_seconds"] = float(duration_secs)
    fm["duration"] = duration_human
    fm["view_count"] = int(entry.get("view_count", 0))

    return fm


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    dry_run = "--dry-run" in sys.argv
    revalidate = "--revalidate" in sys.argv
    refresh_catalog = "--refresh-catalog" in sys.argv
    api_key = get_api_key()

    if not EPISODES_DIR.is_dir():
        print(f"Error: {EPISODES_DIR} not found", file=sys.stderr)
        sys.exit(1)

    # Load or fetch the video catalog
    catalog = None
    if not refresh_catalog:
        catalog = load_catalog(CATALOG_PATH)
        if catalog:
            print(f"Loaded cached catalog: {len(catalog)} videos from {CATALOG_PATH}")

    if catalog is None:
        raw = fetch_channel_catalog(api_key)
        save_catalog(raw, CATALOG_PATH)
        catalog = load_catalog(CATALOG_PATH)

    if not catalog:
        print("Error: could not build video catalog", file=sys.stderr)
        sys.exit(1)

    episode_dirs = sorted(EPISODES_DIR.iterdir())
    total = 0
    enriched = 0
    revalidated = 0
    skipped = 0
    failed = 0

    # First pass: identify which video_ids are already correctly claimed
    claimed_ids: set[str] = set()
    episodes_to_process: list[tuple[Path, dict, str, bool]] = []

    for ep_dir in episode_dirs:
        transcript_path = ep_dir / "transcript.md"
        if not transcript_path.is_file():
            continue

        total += 1
        fm, transcript = read_episode(transcript_path)
        existing_vid = fm.get("video_id", "")

        needs_work = False
        is_revalidation = False

        if not existing_vid:
            needs_work = True
        elif revalidate:
            guest = fm.get("guest", ep_dir.name)
            if not validate_existing_match(guest, existing_vid, catalog):
                print(f"Revalidate: {ep_dir.name} (guest: {guest}) -- current match is wrong")
                needs_work = True
                is_revalidation = True
            else:
                claimed_ids.add(existing_vid)
                skipped += 1
        else:
            claimed_ids.add(existing_vid)
            skipped += 1

        if needs_work:
            episodes_to_process.append((transcript_path, fm, transcript, is_revalidation))

    # Second pass: match episodes that need work
    for transcript_path, fm, transcript, is_reval in episodes_to_process:
        ep_dir = transcript_path.parent
        guest = fm.get("guest", ep_dir.name)
        action = "Revalidating" if is_reval else "Enriching"
        print(f"{action}: {ep_dir.name} (guest: {guest})")

        match = find_best_match(guest, catalog, claimed_ids)
        if not match:
            old_vid = fm.get("video_id", "")
            if is_reval and old_vid and not _is_valid_youtube_id(old_vid):
                print(f"  No replacement found; clearing invalid video_id '{old_vid}'")
                fm["video_id"] = ""
                fm["youtube_url"] = ""
                if not dry_run:
                    write_episode(transcript_path, fm, transcript)
                revalidated += 1
            elif is_reval and old_vid:
                print(f"  No replacement found; keeping existing video_id (may be correct)")
                claimed_ids.add(old_vid)
                skipped += 1
            else:
                print(f"  No YouTube match found for '{guest}', skipping")
                failed += 1
            continue

        claimed_ids.add(match["video_id"])
        fm = enrich_from_catalog_entry(fm, match)
        print(f"  Found: {fm['title']}")
        print(f"  Video: {fm['youtube_url']}")
        print(f"  Date:  {fm['publish_date']}")

        if not dry_run:
            write_episode(transcript_path, fm, transcript)

        if is_reval:
            revalidated += 1
        else:
            enriched += 1

    print()
    print("Enrichment complete.")
    print(f"  Total episodes:    {total}")
    print(f"  Already correct:   {skipped}")
    print(f"  Newly enriched:    {enriched}")
    print(f"  Revalidated/fixed: {revalidated}")
    print(f"  Failed/skipped:    {failed}")
    if dry_run:
        print("  (dry run -- no files were modified)")


if __name__ == "__main__":
    main()
