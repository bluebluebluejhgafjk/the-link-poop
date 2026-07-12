// PUT THIS AT THE MOST END OF THE 4CHANX SCRIPT right after the \/
//Main.init();

//})();
//=================

(function syncSntlMD5Directly() {
  'use strict';
  if (typeof GM_xmlhttpRequest === 'undefined' || typeof GM_getValue === 'undefined' || typeof GM_setValue === 'undefined') {
    console.error('[SNTL] Missing required GM_ functions.');
    return;
  }

  const CSV_URL = 'https://raw.githubusercontent.com/bluebluebluejhgafjk/the-link-poop/refs/heads/main/raw_end_user.csv';
  const LAST_RUN_KEY = 'SNTL_Last_Run';
  const THROTTLE_MS = 30 * 1000;

  const lastRun = GM_getValue(LAST_RUN_KEY, 0);
  const nowMs = Date.now();
  if (nowMs - lastRun < THROTTLE_MS) {
    console.log(`[SNTL] Throttled — last ran ${Math.round((nowMs - lastRun) / 1000)}s ago, skipping.`);
    return;
  }
  GM_setValue(LAST_RUN_KEY, nowMs);

  function processHashes(csvText) {
    const newHashes = csvText.split('\n').map(l => l.trim()).filter(Boolean);
    const rawValue = GM_getValue('4chan X.MD5', '""');
    let currentMD5 = "";
    try {
      currentMD5 = JSON.parse(rawValue);
    } catch (e) {
      currentMD5 = typeof rawValue === 'string' ? rawValue : "";
    }
    const existingLines = currentMD5 ? currentMD5.split('\n').map(l => l.trim()).filter(Boolean) : [];
    const existingHashes = new Set(existingLines.map(l => l.replace(/^\//, '').replace(/\/$/, '')));
    let added = 0;
    newHashes.forEach((h) => {
      if (!existingHashes.has(h)) {
        existingLines.push(`/${h}/`);
        existingHashes.add(h);
        added++;
      }
    });
    if (added > 0) {
      const newValue = existingLines.join('\n');
      GM_setValue('4chan X.MD5', JSON.stringify(newValue));
      console.log(`[SNTL] Appended ${added} new MD5 hashes successfully.`);
    } else {
      console.log('[SNTL] No new MD5 hashes to add.');
    }
  }

  function fetchCSV() {
    const csvUrl = `${CSV_URL}?nocache=${nowMs}`;
    console.log(`[SNTL] Attempting to fetch CSV from: ${csvUrl}`);

    GM_xmlhttpRequest({
      method: 'GET',
      url: csvUrl,
      timeout: 5000,
      onload: function (response) {
        if (response.status === 200) {
          processHashes(response.responseText);
        } else {
          console.error(`[SNTL] CSV fetch returned status ${response.status}.`);
        }
      },
      onerror: function () {
        console.error('[SNTL] Network error fetching CSV.');
      },
      ontimeout: function () {
        console.error('[SNTL] CSV fetch timed out.');
      }
    });
  }

  fetchCSV();
})();
