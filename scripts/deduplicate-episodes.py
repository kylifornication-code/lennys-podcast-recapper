#!/usr/bin/env python3
"""
One-time cleanup script to deduplicate episodes.

Finds and resolves duplicate episodes in data/episodes/ by:
1. Identifying episodes sharing the same YouTube video_id
2. Removing true content duplicates (same transcript, different slug)
3. Clearing misassigned video_ids (different transcripts, same video_id)
4. Cleaning up invalid video_ids (non-YouTube format)

Usage:
    python3 scripts/deduplicate-episodes.py            # Dry run (default)
    python3 scripts/deduplicate-episodes.py --apply     # Actually make changes
"""

import os
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import yaml

EPISODES_DIR = Path(os.environ.get("EPISODES_DIR", "data/episodes"))

YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def read_episode(transcript_path: Path) -> tuple[dict, str]:
    content = transcript_path.read_text(encoding="utf-8")
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    frontmatter = yaml.safe_load(parts[1]) or {}
    transcript = parts[2]
    return frontmatter, transcript


def write_episode(transcript_path: Path, frontmatter: dict, transcript: str):
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


def transcript_fingerprint(transcript: str) -> str:
    """First 500 non-whitespace chars of the transcript body for comparison."""
    cleaned = re.sub(r"\s+", "", transcript)
    return cleaned[:500]


def guest_in_title(guest: str, title: str) -> tuple[float, int]:
    """Score how well a guest name matches a video title.

    Returns (match_ratio, specificity) where specificity is the length of the
    guest name — so "Melissa Tan" (len 11) outranks "Melissa" (len 7) when both
    are substring matches.
    """
    if not guest or not title:
        return (0.0, 0)
    guest_lower = guest.lower().strip('"').strip()
    title_lower = title.lower()

    if guest_lower in title_lower:
        return (1.0, len(guest_lower))

    guest_words = [w for w in guest_lower.split() if len(w) > 1]
    if not guest_words:
        return (0.0, 0)
    matches = sum(1 for w in guest_words if w in title_lower)
    return (matches / len(guest_words), len(guest_lower))


def slug_quality(slug: str) -> int:
    """Higher = better slug. Rewards descriptive names, penalizes mangled ones."""
    score = len(slug) * 10
    if slug.endswith("_"):
        score -= 200
    ascii_only = re.fullmatch(r"[a-z0-9-]+", slug)
    if not ascii_only:
        score += 100  # reward proper Unicode over mangled ASCII
    return score


def is_valid_video_id(vid: str) -> bool:
    if not vid or vid == '""':
        return False
    return bool(YOUTUBE_ID_RE.match(str(vid)))


def main():
    apply = "--apply" in sys.argv

    if not EPISODES_DIR.is_dir():
        print(f"Error: {EPISODES_DIR} not found", file=sys.stderr)
        sys.exit(1)

    episodes = {}
    for ep_dir in sorted(EPISODES_DIR.iterdir()):
        transcript_path = ep_dir / "transcript.md"
        if not transcript_path.is_file():
            continue
        fm, transcript = read_episode(transcript_path)
        episodes[ep_dir.name] = {
            "dir": ep_dir,
            "frontmatter": fm,
            "transcript": transcript,
            "fingerprint": transcript_fingerprint(transcript),
        }

    # --- Phase 1: Clean invalid video_ids ---
    invalid_ids = []
    for slug, ep in episodes.items():
        vid = str(ep["frontmatter"].get("video_id", ""))
        if vid and vid != '""' and not is_valid_video_id(vid):
            invalid_ids.append((slug, vid))

    if invalid_ids:
        print("=== Invalid video_ids ===")
        for slug, vid in invalid_ids:
            print(f"  {slug}: '{vid}' (not a valid YouTube ID)")
        print()

    # --- Phase 2: Group by video_id, find duplicates ---
    by_video_id = defaultdict(list)
    for slug, ep in episodes.items():
        vid = str(ep["frontmatter"].get("video_id", ""))
        if is_valid_video_id(vid):
            by_video_id[vid].append(slug)

    duplicates = {vid: slugs for vid, slugs in by_video_id.items() if len(slugs) > 1}

    to_remove = []
    to_clear = []

    print(f"Total episodes: {len(episodes)}")
    print(f"Duplicated video_ids: {len(duplicates)}")
    print()

    for vid, slugs in sorted(duplicates.items()):
        eps = [(s, episodes[s]) for s in slugs]
        fingerprints = {ep["fingerprint"] for _, ep in eps}
        same_content = len(fingerprints) == 1

        if same_content:
            best_slug = max(slugs, key=slug_quality)
            for slug in slugs:
                if slug != best_slug:
                    to_remove.append(slug)
                    title = eps[0][1]["frontmatter"].get("title", "")
                    print(f"DELETE {slug}")
                    print(f"  Same content as: {best_slug}")
                    print(f"  video_id: {vid}  title: {title}")
                    print()
        else:
            title = eps[0][1]["frontmatter"].get("title", "")
            scores = []
            for slug, ep in eps:
                guest = str(ep["frontmatter"].get("guest", slug)).strip('"')
                match_ratio, specificity = guest_in_title(guest, title)
                scores.append((slug, match_ratio, specificity, guest))

            scores.sort(key=lambda x: (x[1], x[2], slug_quality(x[0])), reverse=True)
            best_slug = scores[0][0]

            print(f"METADATA CONFLICT  video_id={vid}")
            print(f"  Title: {title}")
            for slug, ratio, spec, guest in scores:
                tag = "KEEP" if slug == best_slug else "CLEAR"
                print(f"  {tag}: {slug}  (guest: {guest}, match: {ratio:.0%})")

            for slug, ratio, spec, guest in scores[1:]:
                to_clear.append(slug)
            print()

    # --- Summary ---
    print("=" * 60)
    print(f"Directories to DELETE (true duplicates):  {len(to_remove)}")
    for s in sorted(to_remove):
        print(f"  rm -rf data/episodes/{s}")
    print()
    print(f"Episodes to CLEAR metadata (wrong video): {len(to_clear)}")
    for s in sorted(to_clear):
        print(f"  clear  data/episodes/{s}")
    print()
    print(f"Invalid video_ids to fix:                  {len(invalid_ids)}")
    for s, vid in invalid_ids:
        print(f"  clear  data/episodes/{s}  (was: {vid})")
    print()

    if not apply:
        print("DRY RUN — no changes made. Re-run with --apply to execute.")
        return

    # --- Apply ---
    for slug in to_remove:
        ep_dir = EPISODES_DIR / slug
        if ep_dir.is_dir():
            shutil.rmtree(ep_dir)
            print(f"Deleted: {ep_dir}")

    for slug in to_clear:
        _clear_metadata(slug)

    for slug, _ in invalid_ids:
        if slug not in to_remove:
            _clear_metadata(slug)

    remaining = len(episodes) - len(to_remove)
    print()
    print(f"Cleanup complete. {remaining} episodes remain.")


def _clear_metadata(slug: str):
    transcript_path = EPISODES_DIR / slug / "transcript.md"
    if not transcript_path.is_file():
        return
    fm, transcript = read_episode(transcript_path)
    fm["video_id"] = ""
    fm["title"] = ""
    fm["youtube_url"] = ""
    fm["publish_date"] = ""
    fm["description"] = ""
    fm["duration_seconds"] = 0
    fm["duration"] = ""
    fm["view_count"] = 0
    write_episode(transcript_path, fm, transcript)
    print(f"Cleared metadata: {slug}")


if __name__ == "__main__":
    main()
