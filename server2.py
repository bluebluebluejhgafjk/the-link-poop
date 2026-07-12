# /// script
# dependencies = ["flask"]
# ///
"""
Local helper server for SNTL.

Run with:  uv run server.py
UI at:     http://127.0.0.1:5000

- Paste a single MD5 (base64, 4chan-X format) -> ships instantly.
- Batch mode: '+' adds rows. Each row can be either:
    * a raw MD5 (base64)
    * a 4chan thread link (e.g. https://boards.4chan.org/b/thread/951408361)
  Thread links are resolved via the 4chan JSON API, which already
  returns the OP image's MD5 in the same base64 format used by server.csv
  -- no download/hash needed.
"""

import re
import os
import time
import json
import base64
import urllib.request
import urllib.error

from flask import Flask, request, jsonify, Response

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise ValueError("System error: GITHUB_TOKEN environment variable is not set.")

GITHUB_USERNAME = "bluebluebluejhgafjk"
GITHUB_REPO = "the-link-poop"
CSV_FILE_IN_REPO = "raw_end_user.csv"
HTTP_TIMEOUT_SEC = 15

server_data_path = "server.csv"

THREAD_RE = re.compile(r"boards\.4chan(?:nel)?\.org/([a-zA-Z0-9]+)/thread/(\d+)")
MD5_RE = re.compile(r"^[A-Za-z0-9+/]{22}==$")  # base64 of a 16-byte md5

app = Flask(__name__)


# ---------- shared state ----------

def load_known():
    known_names, known_hashes = set(), set()
    try:
        with open(server_data_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(",")
                if len(parts) >= 2:
                    known_names.add(parts[0])
                    known_hashes.add(parts[1])
    except FileNotFoundError:
        pass
    return known_names, known_hashes


known_names, known_hashes = load_known()


# ---------- 4chan thread resolution ----------

def fetch_op_md5(board, tno):
    url = f"https://a.4cdn.org/{board}/thread/{tno}.json"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
    op = data["posts"][0]
    md5 = op.get("md5")
    if not md5:
        raise ValueError("OP has no image")
    name = f"{op.get('filename', 'manual')}{op.get('ext', '.jpg')}"
    return md5, name


# ---------- github push (merge, not overwrite) ----------

def push_csv_to_github(hashes):
    api_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{GITHUB_REPO}/contents/{CSV_FILE_IN_REPO}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Python-urllib",
    }

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
    except urllib.error.URLError as e:
        print(f"network error fetching csv sha: {e.reason}")
        return False

    merged = hashes | remote_hashes
    hashes.update(remote_hashes)

    csv_content = "\n".join(sorted(merged)) + "\n"
    payload = {
        "message": f"Manual add ({len(merged)} hashes)",
        "content": base64.b64encode(csv_content.encode("utf-8")).decode("utf-8"),
    }
    if sha:
        payload["sha"] = sha

    req = urllib.request.Request(
        api_url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="PUT"
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SEC) as response:
            return response.status in (200, 201)
    except urllib.error.HTTPError as e:
        print(f"csv push failed: {e.read().decode()}")
        return False
    except urllib.error.URLError as e:
        print(f"network error pushing csv: {e.reason}")
        return False


# ---------- routes ----------

@app.route("/add", methods=["POST"])
def add():
    data = request.get_json(force=True)
    entries = data.get("entries", [])
    added, errors = [], []

    for raw in entries:
        raw = raw.strip()
        if not raw:
            continue

        m = THREAD_RE.search(raw)
        if m:
            board, tno = m.groups()
            try:
                md5, name = fetch_op_md5(board, tno)
            except Exception as e:
                errors.append(f"{raw} -> {e}")
                continue
        elif MD5_RE.match(raw):
            md5, name = raw, f"manual_{int(time.time() * 1000)}"
        else:
            errors.append(f"{raw} -> not a valid MD5 or thread link")
            continue

        if md5 in known_hashes:
            errors.append(f"{raw} -> duplicate, skipped")
            continue

        known_hashes.add(md5)
        known_names.add(name)
        added.append((name, md5))

    if added:
        with open(server_data_path, "a") as f:
            for name, md5 in added:
                f.write(f"{name},{md5}\n")
        pushed = push_csv_to_github(known_hashes)
    else:
        pushed = True

    return jsonify(added=[a[1] for a in added], errors=errors, pushed=pushed)


@app.route("/")
def index():
    return Response(PAGE, mimetype="text/html")


PAGE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>SNTL manual add</title>
<style>
body { font-family: monospace; background:#111; color:#ddd; max-width:700px; margin:40px auto; }
input, textarea { width:100%; background:#222; color:#ddd; border:1px solid #444; padding:6px; box-sizing:border-box; font-family:monospace; }
button { background:#2a2a2a; color:#ddd; border:1px solid #555; padding:6px 14px; cursor:pointer; margin-top:8px; }
button:hover { background:#3a3a3a; }
.row { display:flex; gap:6px; margin-bottom:6px; }
.row input { flex:1; }
#status { margin-top:12px; white-space:pre-wrap; font-size:13px; }
h2 { border-bottom:1px solid #444; padding-bottom:4px; }
</style></head>
<body>

<h2>Quick add</h2>
<div class="row">
  <input id="quick" placeholder="MD5 or thread link">
  <button onclick="shipQuick()">Ship</button>
</div>

<h2>Batch</h2>
<div id="rows">
  <div class="row"><input placeholder="MD5 or thread link"></div>
</div>
<button onclick="addRow()">+</button>
<button onclick="shipBatch()">Ship batch</button>

<div id="status"></div>

<script>
function addRow() {
  const rows = document.getElementById('rows');
  const div = document.createElement('div');
  div.className = 'row';
  div.innerHTML = '<input placeholder="MD5 or thread link">';
  rows.appendChild(div);
}

async function post(entries) {
  const res = await fetch('/add', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({entries})
  });
  return res.json();
}

function report(result) {
  const status = document.getElementById('status');
  let text = `added: ${result.added.length}, pushed: ${result.pushed}\\n`;
  if (result.errors.length) text += 'errors:\\n' + result.errors.join('\\n');
  status.textContent = text;
}

async function shipQuick() {
  const el = document.getElementById('quick');
  const result = await post([el.value]);
  report(result);
  if (result.added.length) el.value = '';
}

async function shipBatch() {
  const inputs = document.querySelectorAll('#rows input');
  const entries = Array.from(inputs).map(i => i.value).filter(v => v.trim());
  const result = await post(entries);
  report(result);
  if (result.added.length) {
    document.getElementById('rows').innerHTML = '<div class="row"><input placeholder="MD5 or thread link"></div>';
  }
}
</script>
</body></html>
"""

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
