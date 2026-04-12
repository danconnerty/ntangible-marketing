def render_dashboard_html() -> str:
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>NTangible Content Brain</title>
    <style>
      :root {
        --bg: #f4efe6;
        --ink: #11212b;
        --muted: #5d6f79;
        --line: #d9cdbf;
        --accent: #c24f2d;
        --accent-soft: #f6d2c4;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: Georgia, "Iowan Old Style", serif;
        background:
          radial-gradient(circle at top left, rgba(194,79,45,.12), transparent 24rem),
          linear-gradient(180deg, #f8f2e9 0%, var(--bg) 100%);
        color: var(--ink);
      }
      .wrap {
        width: min(1200px, calc(100vw - 32px));
        margin: 0 auto;
        padding: 28px 0 48px;
      }
      .hero { display: grid; gap: 18px; margin-bottom: 24px; }
      h1 {
        margin: 0;
        font-size: clamp(2rem, 4vw, 3.4rem);
        line-height: 0.95;
        letter-spacing: -0.04em;
      }
      .subtitle { max-width: 72ch; color: var(--muted); font-size: 1rem; }
      .grid { display: grid; grid-template-columns: 320px minmax(0, 1fr); gap: 18px; }
      .stack { display: grid; gap: 18px; }
      .card {
        background: rgba(255,250,242,.86);
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 18px;
        box-shadow: 0 8px 24px rgba(17,33,43,.06);
        backdrop-filter: blur(8px);
      }
      .card h2 { margin: 0 0 12px; font-size: 1rem; letter-spacing: .02em; text-transform: uppercase; }
      .stats { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
      .stat {
        border: 1px solid var(--line);
        border-radius: 14px;
        padding: 12px;
        background: rgba(255,255,255,.55);
      }
      .value { font-size: 1.8rem; font-weight: 700; display: block; }
      .label, .small, .source-meta, .item-meta {
        color: var(--muted);
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        font-size: .82rem;
      }
      .source-list, .item-list { display: grid; gap: 10px; }
      button.source {
        width: 100%;
        text-align: left;
        border: 1px solid var(--line);
        border-radius: 14px;
        padding: 12px;
        background: rgba(255,255,255,.62);
        cursor: pointer;
      }
      button.source:hover { border-color: var(--accent); background: var(--accent-soft); }
      .toolbar { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; }
      input, select {
        border: 1px solid var(--line);
        border-radius: 999px;
        padding: 10px 14px;
        background: rgba(255,255,255,.75);
        color: var(--ink);
      }
      input { flex: 1 1 280px; }
      .item { border-top: 1px solid var(--line); padding: 14px 0; }
      .item:first-child { border-top: 0; padding-top: 0; }
      .item h4 { margin: 0 0 6px; font-size: 1.08rem; }
      a { color: var(--accent); }
      pre {
        margin: 0;
        padding: 14px;
        border-radius: 14px;
        background: #151d22;
        color: #d9ecec;
        overflow: auto;
        font-size: .8rem;
      }
      .pill {
        display: inline-block;
        margin-right: 6px;
        margin-bottom: 6px;
        padding: 4px 8px;
        border-radius: 999px;
        background: var(--accent-soft);
        color: var(--accent);
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        font-size: .75rem;
      }
      @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
    </style>
  </head>
  <body>
    <div class="wrap">
      <section class="hero">
        <div>
          <h1>NTangible Content Brain</h1>
          <p class="subtitle">
            This page reads the local bootstrap dataset under <code>data/content_brain</code>.
            It shows what has been collected, how it is stored, and what an agent can retrieve through the read-only API.
          </p>
        </div>
      </section>
      <section class="grid">
        <aside class="stack">
          <div class="card">
            <h2>Storage</h2>
            <div id="stats" class="stats"></div>
            <p class="small" id="storage-root"></p>
          </div>
          <div class="card">
            <h2>Latest Run</h2>
            <div id="latest-run" class="small">Loading…</div>
          </div>
          <div class="card">
            <h2>Sources</h2>
            <div id="sources" class="source-list">Loading…</div>
          </div>
          <div class="card">
            <h2>Agent Retrieval</h2>
            <p class="small">1. Query <code>/content-brain/api/items</code> with a topic or platform filter.</p>
            <p class="small">2. Pull matching titles, summaries, dates, metrics, and asset URLs.</p>
            <p class="small">3. Open a specific source via <code>/content-brain/api/source/{slug}</code>.</p>
            <p class="small">4. Use the returned text and metadata as generation context.</p>
          </div>
        </aside>
        <main class="stack">
          <div class="card">
            <h2>Search Stored Items</h2>
            <div class="toolbar">
              <input id="query" type="search" placeholder="Search titles, summaries, body text, URLs…" />
              <select id="platform">
                <option value="">All platforms</option>
                <option value="youtube">youtube</option>
                <option value="web">web</option>
              </select>
            </div>
            <div id="items" class="item-list">Loading…</div>
          </div>
          <div class="card">
            <h2>Selected Source</h2>
            <pre id="source-detail">Click any source to inspect the stored JSON payload.</pre>
          </div>
        </main>
      </section>
    </div>
    <script>
      const overviewUrl = "/content-brain/api/overview";
      const sourceBase = "/content-brain/api/source/";
      const itemsBase = "/content-brain/api/items";
      async function fetchJson(url) {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`Request failed: ${response.status}`);
        return await response.json();
      }
      function renderStats(counts) {
        const stats = document.getElementById("stats");
        stats.innerHTML = "";
        Object.entries(counts).forEach(([label, value]) => {
          const node = document.createElement("div");
          node.className = "stat";
          node.innerHTML = `<span class="value">${value}</span><span class="label">${label}</span>`;
          stats.appendChild(node);
        });
      }
      function renderLatestRun(run) {
        const node = document.getElementById("latest-run");
        if (!run) {
          node.textContent = "No run summary found yet.";
          return;
        }
        node.innerHTML = `<div><strong>Targets:</strong> ${run.target_count ?? 0}</div>
          <div><strong>Success:</strong> ${run.success_count ?? 0}</div>
          <div><strong>Failure:</strong> ${run.failure_count ?? 0}</div>`;
      }
      function renderSources(sources) {
        const node = document.getElementById("sources");
        node.innerHTML = "";
        sources.forEach((source) => {
          const button = document.createElement("button");
          button.type = "button";
          button.className = "source";
          button.innerHTML = `<strong>${source.target_slug}</strong>
            <div class="source-meta">${source.platform || "unknown"} • ${source.item_count} item(s)</div>`;
          button.addEventListener("click", async () => {
            const payload = await fetchJson(sourceBase + encodeURIComponent(source.target_slug));
            document.getElementById("source-detail").textContent = JSON.stringify(payload, null, 2);
          });
          node.appendChild(button);
        });
      }
      function renderItems(items) {
        const node = document.getElementById("items");
        node.innerHTML = "";
        if (!items.length) {
          node.textContent = "No matching items.";
          return;
        }
        items.forEach((item) => {
          const div = document.createElement("div");
          div.className = "item";
          const metrics = (item.metrics || []).map(metric => JSON.stringify(metric.payload)).join(" ");
          div.innerHTML = `<h4>${item.title || item.canonical_key}</h4>
            <div class="item-meta">${item.platform} • ${item.item_type} • ${item.target_slug || "unknown source"}</div>
            ${item.published_at ? `<div class="small">${item.published_at}</div>` : ""}
            ${item.summary ? `<p>${item.summary}</p>` : ""}
            <div>
              ${item.assets && item.assets.length ? `<span class="pill">${item.assets.length} asset refs</span>` : ""}
              ${metrics ? `<span class="pill">${metrics}</span>` : ""}
            </div>
            <div class="small"><a href="${item.url}" target="_blank" rel="noreferrer">${item.url}</a></div>`;
          node.appendChild(div);
        });
      }
      async function refreshItems() {
        const query = document.getElementById("query").value.trim();
        const platform = document.getElementById("platform").value;
        const params = new URLSearchParams();
        if (query) params.set("q", query);
        if (platform) params.set("platform", platform);
        const payload = await fetchJson(`${itemsBase}?${params.toString()}`);
        renderItems(payload.items || []);
      }
      async function boot() {
        const overview = await fetchJson(overviewUrl);
        renderStats(overview.counts || {});
        renderLatestRun(overview.latest_run);
        renderSources(overview.sources || []);
        renderItems(overview.items || []);
        document.getElementById("storage-root").textContent = overview.storage_root || "";
      }
      document.getElementById("query").addEventListener("input", refreshItems);
      document.getElementById("platform").addEventListener("change", refreshItems);
      boot();
    </script>
  </body>
</html>
"""
