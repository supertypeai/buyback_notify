import json
import os
from datetime import datetime

from config import KEYWORD, SEEN_FILE
from idx_client import fetch_announcements, filter_keyword
from notifier import send_email


def load_seen() -> set:
    """Load previously seen announcement IDs from disk"""
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen(seen: set):
    """Persist seen announcement IDs to disk"""
    with open(SEEN_FILE, "w") as f:
        json.dump(sorted(seen), f, indent=2)


def main():
    print(
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
        f"Checking IDX announcements for '{KEYWORD}'..."
    )

    announcements = fetch_announcements()
    if not announcements:
        print("No announcements fetched, exiting")
        return

    matches = filter_keyword(announcements, KEYWORD)
    print(f"Found {len(matches)} announcement(s) matching '{KEYWORD}'")

    seen = load_seen()
    new_matches = [a for a in matches if a["id"] not in seen]
    print(f"{len(new_matches)} are new (not previously notified)")

    if new_matches:
        send_email(new_matches)
        for a in new_matches:
            seen.add(a["id"])
        save_seen(seen)
    else:
        print("No new matches, no email sent")

    print("Done")


if __name__ == "__main__":
    main()
