import hashlib
import base64
import time
import os
import json
import urllib.request
import urllib.error
from os import scandir, remove
from os.path import join

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise ValueError("System error: GITHUB_TOKEN environment variable is not set.")

GITHUB_USERNAME = "bluebluebluejhgafjk"
GITHUB_REPO = "the-link-poop"
CSV_FILE_IN_REPO = "raw_end_user.csv"

inf_path = "inf.txt"
server_data_path = "server.csv"

SCAN_INTERVAL_SEC = 5
PUSH_CSV_EVERY_SEC = 60   # commit cadence — stays well clear of both the
                          # numeric API quota and any "looks automated"
                          # abuse heuristics on frequent commits

HTTP_TIMEOUT_SEC = 15     # hard cap on any single GitHub API call so a
                          # stalled connection can't freeze the whole loop


def load_known():
    """Load the full known-names/known-hashes state ONCE at startup.
    After this, the in-memory sets are the source of truth."""
    known_names = set()
    known_hashes = set()
    line_count = 0
    try:
        with open(server_data_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(',')
                if len(parts) >= 2:
                    known_names.add(parts[0])
                    known_hashes.add(parts[1])
                    line_count += 1
    except FileNotFoundError:
        pass
    return known_names, known_hashes, line_count


def hash_file(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return base64.b64encode(h.digest()).decode("ascii")


def push_csv_to_github(known_hashes):
    """Commit raw_end_user.csv straight to the repo, merging with whatever
    is already there so a stale/behind local state can't clobber it."""
    api_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{GITHUB_REPO}/contents/{CSV_FILE_IN_REPO}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Python-urllib"
    }

    # get existing file sha + content (needed to update rather than create,
    # and to merge instead of overwrite)
    sha = None
    remote_hashes = set()
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SEC) as response:
            data = json.loads(response.read().decode())
            sha = data.get("sha")
            remote_content = base64.b64decode(data.get("content", "")).decode("utf-8")
            remote_hashes = {line.strip() for line in remote_content.splitlines() if line.strip()}
    except urllib.error.HTTPError as e:
        if e.code != 404:
            print(f"error fetching csv sha: {e.read().decode()}")
            return False
        # 404 is fine — file doesn't exist yet, sha stays None
    except urllib.error.URLError as e:
        print(f"network error fetching csv sha (will retry next cycle): {e.reason}")
        return False

    merged_hashes = known_hashes | remote_hashes
    known_hashes.update(remote_hashes)  # keep in-memory state consistent too

    csv_content = "\n".join(sorted(merged_hashes)) + "\n"
    encoded_content = base64.b64encode(csv_content.encode("utf-8")).decode("utf-8")
    payload = {
        "message": f"Auto-update raw_end_user.csv ({len(merged_hashes)} hashes)",
        "content": encoded_content
    }
    if sha:
        payload["sha"] = sha

    data_payload = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(api_url, data=data_payload, headers=headers, method="PUT")

    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SEC) as response:
            if response.status in (200, 201):
                print(f"pushed raw_end_user.csv ({len(merged_hashes)} hashes) to github")
                return True
    except urllib.error.HTTPError as e:
        print(f"csv push failed: {e.read().decode()}")
        return False
    except urllib.error.URLError as e:
        print(f"network error pushing csv (will retry next cycle): {e.reason}")
        return False


def main():
    known_names, known_hashes, line_count = load_known()
    last_csv_push = 0.0

    while True:
        try:
            only_files = [entry.name for entry in scandir("images") if entry.is_file()]
        except FileNotFoundError:
            print("images/ directory not found, skipping this cycle.")
            time.sleep(SCAN_INTERVAL_SEC)
            continue

        new_entries = []
        for name in only_files:
            if name in known_names:
                continue

            path = join("images", name)
            try:
                b64_hash = hash_file(path)
            except (FileNotFoundError, PermissionError) as e:
                print(f"skipping {name}, couldn't read ({e})")
                continue

            if b64_hash in known_hashes:
                print(f"duplicate content, deleting {name}")
                try:
                    remove(path)
                except FileNotFoundError:
                    pass
                continue

            print(f"added file {name} teehee")
            known_names.add(name)
            known_hashes.add(b64_hash)
            new_entries.append((name, b64_hash))

        if new_entries:
            with open(server_data_path, 'a') as server_data:
                for name, h in new_entries:
                    server_data.write(f"{name},{h}\n")
            line_count += len(new_entries)

        # local record of total count — no longer shipped anywhere,
        # just useful for your own visibility
        with open(inf_path, 'w') as info_file:
            info_file.write(str(line_count))

        now = time.time()
        if new_entries and (now - last_csv_push >= PUSH_CSV_EVERY_SEC):
            if push_csv_to_github(known_hashes):
                last_csv_push = now

        time.sleep(SCAN_INTERVAL_SEC)


if __name__ == "__main__":
    main()