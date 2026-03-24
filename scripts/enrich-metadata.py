#!/usr/bin/env python3
"""
Enrich episode metadata from the YouTube Data API.

For each episode in data/episodes/ that is missing metadata (empty video_id),
searches Lenny's Podcast YouTube channel for a matching video by guest name,
then fills in title, youtube_url, video_id, publish_date, description,
duration_seconds, duration, and view_count.

Usage:
    YOUTUBE_API_KEY=your_key python3 scripts/enrich-metadata.py

    # Dry run (print what would change without writing):
    YOUTUBE_API_KEY=your_key python3 scripts/enrich-metadata.py --dry-run

    # Re-fetch full descriptions for episodes with truncated descriptions:
    YOUTUBE_API_KEY=your_key python3 scripts/enrich-metadata.py --refresh-descriptions

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
import urllib.request
import urllib.parse
from pathlib import Path

import certifi
import yaml

CHANNEL_ID = "UC6t1O76G0jYXOAoYCm153dA"
API_BASE = "https://www.googleapis.com/youtube/v3"
EPISODES_DIR = Path(os.environ.get("EPISODES_DIR", "data/episodes"))

SSL_CTX = ssl.create_default_context(cafile=certifi.where())


def get_api_key():
    key = os.environ.get("YOUTUBE_API_KEY", "")
    if not key:
        print("Error: YOUTUBE_API_KEY environment variable is required", file=sys.stderr)
        sys.exit(1)
    return key


def youtube_get(endpoint: str, params: dict) -> dict:
    url = f"{API_BASE}/{endpoint}?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, context=SSL_CTX) as resp:
        return json.loads(resp.read())


def search_video(api_key: str, guest_name: str) -> str | None:
    """Search Lenny's channel for a video matching the guest name. Returns video ID or None."""
    data = youtube_get("search", {
        "part": "snippet",
        "channelId": CHANNEL_ID,
        "q": guest_name,
        "type": "video",
        "maxResults": 1,
        "key": api_key,
    })
    items = data.get("items", [])
    if not items:
        return None
    return items[0]["id"].get("videoId")


def get_video_details(api_key: str, video_id: str) -> dict | None:
    """Fetch full video details from YouTube."""
    data = youtube_get("videos", {
        "part": "snippet,contentDetails,statistics",
        "id": video_id,
        "key": api_key,
    })
    items = data.get("items", [])
    if not items:
        return None
    return items[0]


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


def needs_enrichment(fm: dict) -> bool:
    """Check if an episode is missing key metadata."""
    return not fm.get("video_id")


def has_truncated_description(fm: dict) -> bool:
    """Detect descriptions truncated by YouTube's Search API (end with '...')."""
    desc = (fm.get("description") or "").strip()
    if not desc:
        return False
    return desc.endswith("...")


def enrich_episode(fm: dict, video_details: dict) -> dict:
    """Merge YouTube video details into the frontmatter dict."""
    snippet = video_details["snippet"]
    content = video_details["contentDetails"]
    stats = video_details.get("statistics", {})

    video_id = video_details["id"]
    duration_secs, duration_human = parse_iso_duration(content.get("duration", ""))
    publish_date = snippet.get("publishedAt", "")[:10]

    fm["title"] = snippet.get("title", fm.get("title", ""))
    fm["youtube_url"] = f"https://www.youtube.com/watch?v={video_id}"
    fm["video_id"] = video_id
    fm["publish_date"] = publish_date
    fm["description"] = snippet.get("description", fm.get("description", ""))
    fm["duration_seconds"] = float(duration_secs)
    fm["duration"] = duration_human
    fm["view_count"] = int(stats.get("viewCount", 0))

    return fm


def refresh_descriptions(dry_run: bool, api_key: str):
    """Re-fetch full descriptions for episodes with truncated descriptions."""
    if not EPISODES_DIR.is_dir():
        print(f"Error: {EPISODES_DIR} not found", file=sys.stderr)
        sys.exit(1)

    episode_dirs = sorted(EPISODES_DIR.iterdir())
    total = 0
    refreshed = 0
    skipped = 0
    failed = 0

    for ep_dir in episode_dirs:
        transcript_path = ep_dir / "transcript.md"
        if not transcript_path.is_file():
            continue

        total += 1
        fm, transcript = read_episode(transcript_path)

        if not has_truncated_description(fm):
            skipped += 1
            continue

        video_id = fm.get("video_id")
        if not video_id:
            skipped += 1
            continue

        old_desc = (fm.get("description") or "").strip()
        print(f"Refreshing: {ep_dir.name}")
        print(f"  Old (truncated): {old_desc[:80]}...")

        try:
            details = get_video_details(api_key, video_id)
            if not details:
                print(f"  Could not fetch details for video {video_id}, skipping")
                failed += 1
                continue

            new_desc = details["snippet"].get("description", "")
            if not new_desc or new_desc.strip() == old_desc:
                print(f"  No change (YouTube returned same text), skipping")
                skipped += 1
                continue

            fm["description"] = new_desc
            print(f"  New: {new_desc[:80]}... ({len(new_desc)} chars)")

            if not dry_run:
                write_episode(transcript_path, fm, transcript)

            refreshed += 1

        except Exception as e:
            print(f"  Error: {e}", file=sys.stderr)
            failed += 1

        time.sleep(0.2)

    print()
    print("Description refresh complete.")
    print(f"  Total episodes:     {total}")
    print(f"  Already complete:   {skipped}")
    print(f"  Refreshed:          {refreshed}")
    print(f"  Failed/skipped:     {failed}")
    if dry_run:
        print("  (dry run -- no files were modified)")


def build_video_id_index(episode_dirs: list[Path]) -> dict[str, str]:
    """Map existing video_id → episode slug for collision detection."""
    index = {}
    for ep_dir in episode_dirs:
        transcript_path = ep_dir / "transcript.md"
        if not transcript_path.is_file():
            continue
        fm, _ = read_episode(transcript_path)
        vid = fm.get("video_id", "")
        if vid:
            index[vid] = ep_dir.name
    return index


def guest_matches_title(guest: str, title: str) -> bool:
    """Check whether the guest name (or a significant part) appears in the video title."""
    if not guest or not title:
        return False
    guest_lower = guest.lower().strip('"').strip()
    title_lower = title.lower()
    if guest_lower in title_lower:
        return True
    words = [w for w in guest_lower.split() if len(w) > 2]
    if words:
        matches = sum(1 for w in words if w in title_lower)
        return matches >= len(words) / 2
    return False


def main():
    dry_run = "--dry-run" in sys.argv
    refresh_mode = "--refresh-descriptions" in sys.argv
    api_key = get_api_key()

    if refresh_mode:
        refresh_descriptions(dry_run, api_key)
        return

    if not EPISODES_DIR.is_dir():
        print(f"Error: {EPISODES_DIR} not found", file=sys.stderr)
        sys.exit(1)

    episode_dirs = sorted(EPISODES_DIR.iterdir())
    used_video_ids = build_video_id_index(episode_dirs)

    total = 0
    enriched = 0
    skipped = 0
    failed = 0

    for ep_dir in episode_dirs:
        transcript_path = ep_dir / "transcript.md"
        if not transcript_path.is_file():
            continue

        total += 1
        fm, transcript = read_episode(transcript_path)

        if not needs_enrichment(fm):
            skipped += 1
            continue

        guest = fm.get("guest", ep_dir.name)
        print(f"Enriching: {ep_dir.name} (guest: {guest})")

        try:
            video_id = search_video(api_key, guest)
            if not video_id:
                print(f"  No YouTube match found for '{guest}', skipping")
                failed += 1
                continue

            if video_id in used_video_ids:
                owner = used_video_ids[video_id]
                print(f"  video_id {video_id} already assigned to '{owner}', skipping")
                failed += 1
                continue

            details = get_video_details(api_key, video_id)
            if not details:
                print(f"  Could not fetch details for video {video_id}, skipping")
                failed += 1
                continue

            title = details.get("snippet", {}).get("title", "")
            if not guest_matches_title(guest, title):
                print(f"  Title mismatch: '{title}' doesn't match guest '{guest}', skipping")
                failed += 1
                continue

            fm = enrich_episode(fm, details)
            print(f"  Found: {fm['title']}")
            print(f"  Video: {fm['youtube_url']}")
            print(f"  Date:  {fm['publish_date']}")

            if not dry_run:
                write_episode(transcript_path, fm, transcript)

            used_video_ids[video_id] = ep_dir.name
            enriched += 1

        except Exception as e:
            print(f"  Error: {e}", file=sys.stderr)
            failed += 1

        time.sleep(0.2)

    print()
    print("Enrichment complete.")
    print(f"  Total episodes:  {total}")
    print(f"  Already had data: {skipped}")
    print(f"  Enriched:        {enriched}")
    print(f"  Failed/skipped:  {failed}")
    if dry_run:
        print("  (dry run -- no files were modified)")


if __name__ == "__main__":
    main()
