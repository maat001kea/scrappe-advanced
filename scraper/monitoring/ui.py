from __future__ import annotations

# Minimal self-contained HTML UI served from the monitoring server.
# It polls /health for a JSON snapshot and renders a dashboard.

HTML = """<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
    <title>Scrape Console</title>
    <style>
      :root {
        --bg0: #070a10;
        --bg1: #0b1220;
        --card: rgba(255, 255, 255, 0.06);
        --card2: rgba(255, 255, 255, 0.09);
        --border: rgba(255, 255, 255, 0.12);
        --text: rgba(255, 255, 255, 0.92);
        --muted: rgba(255, 255, 255, 0.62);
        --muted2: rgba(255, 255, 255, 0.46);

        --good: #2dd4bf;
        --warn: #fbbf24;
        --bad: #fb7185;

        --shadow: 0 24px 70px rgba(0, 0, 0, 0.55);
        --radius: 16px;
        --radius-sm: 12px;

        --mono: "SF Mono", Menlo, Monaco, "Cascadia Mono", "Fira Mono", "Ubuntu Mono", monospace;
        --sans: "Avenir Next", Avenir, "Gill Sans", "Trebuchet MS", "Noto Sans", sans-serif;
      }

      * { box-sizing: border-box; }

      body {
        margin: 0;
        font-family: var(--sans);
        color: var(--text);
        background:
          radial-gradient(900px 560px at 12% -10%, rgba(45, 212, 191, 0.26) 0%, rgba(45, 212, 191, 0) 60%),
          radial-gradient(700px 520px at 88% 8%, rgba(251, 191, 36, 0.18) 0%, rgba(251, 191, 36, 0) 62%),
          radial-gradient(900px 720px at 50% 112%, rgba(59, 130, 246, 0.18) 0%, rgba(59, 130, 246, 0) 60%),
          linear-gradient(180deg, var(--bg1) 0%, var(--bg0) 70%);
        min-height: 100vh;
      }

      body::before {
        content: "";
        position: fixed;
        inset: 0;
        pointer-events: none;
        opacity: 0.35;
        background-image:
          linear-gradient(transparent 0%, rgba(255, 255, 255, 0.02) 50%, transparent 100%),
          repeating-linear-gradient(135deg, rgba(255, 255, 255, 0.03), rgba(255, 255, 255, 0.03) 1px, transparent 1px, transparent 10px);
        mix-blend-mode: overlay;
      }

      .wrap {
        max-width: 1180px;
        margin: 0 auto;
        padding: 22px;
      }

      .topbar {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 14px;
        margin: 6px 0 16px 0;
      }

      .brand {
        display: flex;
        flex-direction: column;
        gap: 6px;
        min-width: 220px;
      }

      .title-row {
        display: flex;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
      }

      .logo {
        margin: 0;
        font-size: 18px;
        letter-spacing: 0.4px;
        font-weight: 700;
      }

      .subtitle {
        font-size: 12px;
        color: var(--muted);
        line-height: 1.35;
      }

      .badge {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        border-radius: 999px;
        padding: 6px 10px;
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,255,255,0.12);
        font-family: var(--mono);
        font-size: 11px;
        color: var(--muted);
      }

      .dot {
        width: 9px;
        height: 9px;
        border-radius: 999px;
        background: rgba(255,255,255,0.25);
        box-shadow: 0 0 0 4px rgba(255,255,255,0.04);
      }

      .dot.good { background: var(--good); box-shadow: 0 0 0 4px rgba(45, 212, 191, 0.14); }
      .dot.warn { background: var(--warn); box-shadow: 0 0 0 4px rgba(251, 191, 36, 0.14); }
      .dot.bad { background: var(--bad); box-shadow: 0 0 0 4px rgba(251, 113, 133, 0.14); }

      .controls {
        display: flex;
        gap: 10px;
        align-items: center;
        flex-wrap: wrap;
      }

      .card {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 14px 14px;
        backdrop-filter: blur(12px);
        box-shadow: var(--shadow);
      }

      .card h2 { display: none; }

      .btn {
        cursor: pointer;
        background: rgba(255,255,255,0.07);
        border: 1px solid rgba(255,255,255,0.14);
        color: var(--text);
        padding: 9px 11px;
        border-radius: 12px;
        font-size: 12px;
        font-family: var(--mono);
        transition: transform 140ms ease, background 140ms ease, border-color 140ms ease;
      }

      .btn:hover { transform: translateY(-1px); background: rgba(255,255,255,0.10); border-color: rgba(255,255,255,0.20); }
      .btn:active { transform: translateY(0px); }

      .toggle {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 10px;
        border-radius: 12px;
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.10);
        font-family: var(--mono);
        font-size: 12px;
        color: var(--muted);
      }

      .toggle input { accent-color: var(--good); }

      .grid {
        display: grid;
        grid-template-columns: 1fr;
        gap: 14px;
      }

      @media (min-width: 980px) {
        .grid {
          grid-template-columns: 1fr 1fr;
        }
      }

      .metrics {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 12px;
        margin-bottom: 14px;
      }

      @media (min-width: 820px) {
        .metrics { grid-template-columns: repeat(6, minmax(0, 1fr)); }
      }

      .metric {
        position: relative;
        overflow: hidden;
        border-radius: var(--radius);
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.10);
        padding: 12px 12px;
        box-shadow: 0 18px 55px rgba(0, 0, 0, 0.35);
        transform: translateY(8px);
        opacity: 0;
        animation: rise 560ms ease forwards;
      }

      .metric::before {
        content: "";
        position: absolute;
        inset: -1px;
        background: radial-gradient(260px 120px at 20% 0%, rgba(45, 212, 191, 0.18) 0%, rgba(45, 212, 191, 0) 60%);
        opacity: 0.6;
        pointer-events: none;
      }

      .metric:nth-child(2)::before { background: radial-gradient(260px 120px at 20% 0%, rgba(59, 130, 246, 0.18) 0%, rgba(59, 130, 246, 0) 60%); }
      .metric:nth-child(3)::before { background: radial-gradient(260px 120px at 20% 0%, rgba(251, 191, 36, 0.18) 0%, rgba(251, 191, 36, 0) 60%); }
      .metric:nth-child(4)::before { background: radial-gradient(260px 120px at 20% 0%, rgba(251, 113, 133, 0.18) 0%, rgba(251, 113, 133, 0) 60%); }

      @keyframes rise {
        to { transform: translateY(0px); opacity: 1; }
      }

      .metric .label {
        position: relative;
        font-family: var(--mono);
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.14em;
        color: var(--muted2);
      }

      .metric .value {
        position: relative;
        margin-top: 8px;
        font-weight: 800;
        letter-spacing: 0.2px;
        font-size: 22px;
      }

      .metric .sub {
        position: relative;
        margin-top: 4px;
        font-family: var(--mono);
        color: var(--muted);
        font-size: 11px;
      }

      .section-title {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 12px;
        margin-bottom: 10px;
      }

      .section-title h3 {
        margin: 0;
        font-size: 12px;
        font-family: var(--mono);
        text-transform: uppercase;
        letter-spacing: 0.16em;
        color: var(--muted);
      }

      .section-title .hint {
        font-family: var(--mono);
        font-size: 11px;
        color: var(--muted2);
      }

      .pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 9px;
        border-radius: 999px;
        background: var(--card2);
        border: 1px solid rgba(255,255,255,0.12);
        font-family: var(--mono);
        font-size: 11px;
        color: var(--muted);
      }

      .pill.good { color: rgba(45, 212, 191, 0.95); }
      .pill.warn { color: rgba(251, 191, 36, 0.95); }
      .pill.bad { color: rgba(251, 113, 133, 0.95); }

      .table-wrap {
        overflow-x: auto;
        border-radius: var(--radius-sm);
        border: 1px solid rgba(255,255,255,0.10);
        background: rgba(0,0,0,0.16);
      }

      table {
        width: 100%;
        border-collapse: collapse;
        font-family: var(--mono);
        font-size: 12px;
        min-width: 780px;
      }

      th, td {
        text-align: left;
        padding: 10px 10px;
        border-bottom: 1px solid rgba(255,255,255,0.10);
        vertical-align: top;
      }

      th {
        color: var(--muted);
        font-weight: 600;
        position: sticky;
        top: 0;
        background: rgba(10, 14, 24, 0.92);
        backdrop-filter: blur(8px);
      }

      tr:hover td { background: rgba(255,255,255,0.03); }

      .good { color: var(--good); }
      .warn { color: var(--warn); }
      .bad { color: var(--bad); }

      .small {
        font-size: 11px;
        color: var(--muted2);
        font-family: var(--mono);
      }

      .bar {
        width: 120px;
        height: 8px;
        border-radius: 999px;
        background: rgba(255,255,255,0.07);
        border: 1px solid rgba(255,255,255,0.10);
        overflow: hidden;
      }

      .bar > span {
        display: block;
        height: 100%;
        width: 0%;
        background: linear-gradient(90deg, rgba(45, 212, 191, 0.95) 0%, rgba(59, 130, 246, 0.95) 100%);
      }

      .bar.warn > span { background: linear-gradient(90deg, rgba(251, 191, 36, 0.95) 0%, rgba(245, 158, 11, 0.95) 100%); }
      .bar.bad > span { background: linear-gradient(90deg, rgba(251, 113, 133, 0.95) 0%, rgba(244, 63, 94, 0.95) 100%); }

      details {
        border-radius: var(--radius);
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.10);
        padding: 12px;
      }

      details > summary {
        cursor: pointer;
        list-style: none;
        font-family: var(--mono);
        font-size: 12px;
        color: var(--muted);
      }

      details > summary::-webkit-details-marker { display: none; }

      pre {
        margin: 10px 0 0 0;
        white-space: pre-wrap;
        word-break: break-word;
        font-family: var(--mono);
        font-size: 11px;
        color: rgba(255,255,255,0.70);
      }

      @media (prefers-reduced-motion: reduce) {
        .metric { animation: none; opacity: 1; transform: none; }
        .btn { transition: none; }
      }
    </style>
  </head>
  <body>
    <div class=\"wrap\">
      <div class=\"topbar\">
        <div class=\"brand\">
          <div class=\"title-row\">
            <div class=\"logo\">Scrape Console</div>
            <div class=\"badge\" id=\"conn_badge\">
              <span class=\"dot\" id=\"conn_dot\"></span>
              <span id=\"conn_text\">Connecting</span>
              <span id=\"conn_meta\" class=\"small\" style=\"margin-left:6px;\">/health</span>
            </div>
          </div>
          <div class=\"subtitle\">Live status for engine, proxy pool and recent failures. Built for ops visibility, not stealth.</div>
        </div>
        <div class=\"controls\">
          <button class=\"btn\" id=\"refresh_btn\" type=\"button\">Refresh</button>
          <label class=\"toggle\"><input id=\"pause_cb\" type=\"checkbox\" /> Pause</label>
          <div class=\"pill\">poll: <span id=\"poll_ms\">2000</span>ms</div>
        </div>
      </div>

      <div class=\"metrics\">
        <div class=\"metric\" style=\"animation-delay: 0ms;\">
          <div class=\"label\">Queued</div>
          <div class=\"value\" id=\"queued\">-</div>
          <div class=\"sub\">Tasks waiting</div>
        </div>
        <div class=\"metric\" style=\"animation-delay: 40ms;\">
          <div class=\"label\">In Flight</div>
          <div class=\"value\" id=\"in_flight\">-</div>
          <div class=\"sub\">Active requests</div>
        </div>
        <div class=\"metric\" style=\"animation-delay: 80ms;\">
          <div class=\"label\">Succeeded</div>
          <div class=\"value\" id=\"succeeded\">-</div>
          <div class=\"sub\">OK fetches</div>
        </div>
        <div class=\"metric\" style=\"animation-delay: 120ms;\">
          <div class=\"label\">Failed</div>
          <div class=\"value\" id=\"failed\">-</div>
          <div class=\"sub\">Retries/errors</div>
        </div>
        <div class=\"metric\" style=\"animation-delay: 160ms;\">
          <div class=\"label\">Success Rate</div>
          <div class=\"value\" id=\"success_rate\">-</div>
          <div class=\"sub\" id=\"success_meta\">-</div>
        </div>
        <div class=\"metric\" style=\"animation-delay: 200ms;\">
          <div class=\"label\">Workers</div>
          <div class=\"value\" id=\"workers\">-</div>
          <div class=\"sub\"><span class=\"small\">UA pool:</span> <span id=\"ua_pool\">-</span></div>
        </div>
      </div>

      <div class=\"grid\">
        <section class=\"card\">
          <div class=\"section-title\">
            <h3>Engine</h3>
            <div class=\"hint\">Last refresh: <span id=\"last_refresh\">-</span> (<span id=\"last_latency\">-</span>)</div>
          </div>
          <div style=\"display:flex; gap:10px; flex-wrap:wrap;\">
            <div class=\"pill\">workers: <span id=\"workers_pill\">-</span></div>
            <div class=\"pill\">queue: <span id=\"queue_pill\">-</span></div>
            <div class=\"pill\">in_flight: <span id=\"flight_pill\">-</span></div>
          </div>
          <div class=\"small\" style=\"margin-top: 12px;\">Tip: `daemon` mode keeps the container running so `/ui` stays available.</div>
        </section>

        <section class=\"card\">
          <div class=\"section-title\">
            <h3>Proxies</h3>
            <div class=\"hint\">
              <span class=\"pill\">total: <span id=\"proxies_total\">-</span></span>
              <span class=\"pill\">healthy: <span id=\"proxies_healthy\">-</span></span>
              <span class=\"pill\">strategy: <span id=\"proxies_strategy\">-</span></span>
            </div>
          </div>
          <div class=\"table-wrap\">
            <table>
              <thead>
                <tr>
                  <th>proxy</th>
                  <th>kind</th>
                  <th>p_success</th>
                  <th>sr</th>
                  <th>lat</th>
                  <th>in_f</th>
                  <th>cooldown</th>
                  <th>blocked</th>
                </tr>
              </thead>
              <tbody id=\"proxy_rows\">
                <tr><td colspan=\"8\"><span class=\"small\">Waiting for data…</span></td></tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class=\"card\" style=\"grid-column: 1 / -1;\">
          <div class=\"section-title\">
            <h3>Recent Errors</h3>
            <div class=\"hint\"><span class=\"pill\">tail: <span id=\"error_count\">-</span></span></div>
          </div>
          <div class=\"table-wrap\">
            <table>
              <thead>
                <tr>
                  <th>time</th>
                  <th>target</th>
                  <th>reason</th>
                  <th>status</th>
                  <th>proxy</th>
                  <th>msg</th>
                </tr>
              </thead>
              <tbody id=\"error_rows\">
                <tr><td colspan=\"6\"><span class=\"small\">No errors yet</span></td></tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class=\"card\" style=\"grid-column: 1 / -1;\">
          <div class=\"section-title\">
            <h3>Raw Status</h3>
            <div class=\"hint\">
              <button class=\"btn\" id=\"copy_btn\" type=\"button\">Copy JSON</button>
              <span class=\"pill\">metrics: <span class=\"small\">/metrics</span></span>
            </div>
          </div>
          <details>
            <summary>Show JSON payload</summary>
            <pre id=\"raw\">waiting...</pre>
          </details>
        </section>
      </div>
    </div>

    <script>
      const $ = (id) => document.getElementById(id);
      const POLL_MS = 2000;

      function fmt(n, digits) {
        if (n === null || n === undefined) return "-";
        if (typeof n !== "number") return String(n);
        return n.toFixed(digits);
      }

      function fmtPct(v) {
        if (v === null || v === undefined) return "-";
        const pct = Math.max(0, Math.min(100, v * 100));
        return pct.toFixed(1) + "%";
      }

      function shortTime(iso) {
        if (!iso) return "-";
        const d = new Date(iso);
        if (isNaN(d.getTime())) return String(iso).slice(0, 19);
        return d.toLocaleTimeString();
      }

      function setText(id, value) {
        const el = $(id);
        if (el) el.textContent = value;
      }

      function setConn(state, meta) {
        const dot = $("conn_dot");
        const txt = $("conn_text");
        const metaEl = $("conn_meta");
        if (!dot || !txt) return;

        dot.classList.remove("good", "warn", "bad");
        if (state === "good") dot.classList.add("good");
        else if (state === "warn") dot.classList.add("warn");
        else if (state === "bad") dot.classList.add("bad");

        if (state === "good") txt.textContent = "Online";
        else if (state === "warn") txt.textContent = "Degraded";
        else if (state === "bad") txt.textContent = "Offline";
        else txt.textContent = "Connecting";

        if (metaEl) metaEl.textContent = meta || "/health";
      }

      function clearRows(tbodyId) {
        const tbody = $(tbodyId);
        if (!tbody) return null;
        tbody.innerHTML = "";
        return tbody;
      }

      function makeTd(content) {
        const td = document.createElement("td");
        if (content instanceof Node) td.appendChild(content);
        else td.textContent = content;
        return td;
      }

      function makePill(text, tone) {
        const s = document.createElement("span");
        s.className = "pill" + (tone ? " " + tone : "");
        s.textContent = text;
        return s;
      }

      function makeBar(value01) {
        const w = Math.max(0, Math.min(1, Number(value01 || 0)));
        const wrap = document.createElement("div");
        let tone = "";
        if (w >= 0.80) tone = "";
        else if (w >= 0.50) tone = "warn";
        else tone = "bad";
        wrap.className = "bar" + (tone ? " " + tone : "");
        const fill = document.createElement("span");
        fill.style.width = Math.round(w * 100) + "%";
        wrap.appendChild(fill);
        return wrap;
      }

      function addProxyRow(tbody, p) {
        const tr = document.createElement("tr");
        tr.appendChild(makeTd(p.proxy || "-"));
        tr.appendChild(makeTd(makePill(p.kind || "-", "")));

        const pred = typeof p.predicted_success === "number" ? p.predicted_success : null;
        const predWrap = document.createElement("div");
        predWrap.style.display = "flex";
        predWrap.style.alignItems = "center";
        predWrap.style.gap = "10px";
        predWrap.appendChild(makeBar(pred));
        predWrap.appendChild(document.createTextNode(fmt(pred, 2)));
        tr.appendChild(makeTd(predWrap));

        const sr = typeof p.success_rate === "number" ? p.success_rate : null;
        const srWrap = document.createElement("div");
        srWrap.style.display = "flex";
        srWrap.style.alignItems = "center";
        srWrap.style.gap = "10px";
        srWrap.appendChild(makeBar(sr));
        srWrap.appendChild(document.createTextNode(fmt(sr, 2)));
        tr.appendChild(makeTd(srWrap));

        tr.appendChild(makeTd(fmt(p.latency_seconds, 2)));
        tr.appendChild(makeTd(String(p.in_flight ?? "-")));
        tr.appendChild(makeTd(p.cooldown_seconds_left ? fmt(p.cooldown_seconds_left, 0) + "s" : "-"));
        tr.appendChild(makeTd(String(p.blocked ?? "0")));
        tbody.appendChild(tr);
      }

      function addErrorRow(tbody, e) {
        const tr = document.createElement("tr");
        tr.appendChild(makeTd(shortTime(e.timestamp)));
        tr.appendChild(makeTd(e.target || "-"));
        tr.appendChild(makeTd(makePill(e.reason || "-", "")));

        const sc = (e.status_code === null || e.status_code === undefined) ? null : Number(e.status_code);
        let tone = "";
        if (sc === null) tone = "";
        else if (sc >= 500) tone = "bad";
        else if (sc === 429 || sc === 403 || sc === 401) tone = "warn";
        tr.appendChild(makeTd(makePill(sc === null ? "-" : String(sc), tone)));

        tr.appendChild(makeTd(e.proxy || "-"));
        tr.appendChild(makeTd((e.error || "").slice(0, 160)));
        tbody.appendChild(tr);
      }

      async function refresh() {
        const now = new Date();
        const t0 = performance.now();
        try {
          const res = await fetch("/health", { cache: "no-store" });
          const data = await res.json();
          const dt = Math.max(0, performance.now() - t0);

          setConn("good", "/health " + Math.round(dt) + "ms");

          setText("queued", data.queued);
          setText("in_flight", data.in_flight);
          setText("succeeded", data.succeeded);
          setText("failed", data.failed);
          setText("ua_pool", data.user_agents !== undefined ? String(data.user_agents) : "-");

          const workers = data.workers_active !== undefined ? `${data.workers_active}/${data.workers_max}` : "-";
          setText("workers", workers);
          setText("workers_pill", workers);
          setText("queue_pill", String(data.queued ?? "-"));
          setText("flight_pill", String(data.in_flight ?? "-"));

          const succeeded = Number(data.succeeded || 0);
          const failed = Number(data.failed || 0);
          const total = succeeded + failed;
          const sr = total > 0 ? (succeeded / total) : null;
          setText("success_rate", sr === null ? "-" : fmtPct(sr));
          setText("success_meta", total > 0 ? `${succeeded}/${total}` : "no attempts yet");

          setText("proxies_total", data.proxies_total);
          setText("proxies_healthy", data.proxies_healthy);
          setText("proxies_strategy", data.proxies_strategy || "-");

          setText("last_refresh", now.toLocaleTimeString());
          setText("last_latency", Math.round(dt) + "ms");

          const pbody = clearRows("proxy_rows");
          const proxies = data.proxies_top || [];
          if (pbody && proxies.length) {
            for (const p of proxies) addProxyRow(pbody, p);
          } else if (pbody) {
            const tr = document.createElement("tr");
            const td = document.createElement("td");
            td.colSpan = 8;
            td.appendChild(makePill("No proxies (or proxy rotation disabled)", "warn"));
            tr.appendChild(td);
            pbody.appendChild(tr);
          }

          const ebody = clearRows("error_rows");
          const errors = data.recent_errors || [];
          setText("error_count", String(errors.length));
          if (ebody && errors.length) {
            for (const e of errors) addErrorRow(ebody, e);
          } else if (ebody) {
            const tr = document.createElement("tr");
            const td = document.createElement("td");
            td.colSpan = 6;
            td.appendChild(makePill("No recent errors", "good"));
            tr.appendChild(td);
            ebody.appendChild(tr);
          }

          const raw = $("raw");
          if (raw) raw.textContent = JSON.stringify(data, null, 2);
        } catch (err) {
          setConn("bad", "fetch failed");
          setText("last_refresh", now.toLocaleTimeString() + " (error)");
          setText("last_latency", "-");
        }
      }

      function setup() {
        setText("poll_ms", String(POLL_MS));
        const pause = $("pause_cb");
        const refreshBtn = $("refresh_btn");
        const copyBtn = $("copy_btn");

        let timer = null;

        function start() {
          if (timer) clearInterval(timer);
          timer = setInterval(() => {
            if (pause && pause.checked) return;
            refresh();
          }, POLL_MS);
        }

        if (refreshBtn) refreshBtn.addEventListener("click", () => refresh());
        if (copyBtn) {
          copyBtn.addEventListener("click", async () => {
            const raw = $("raw");
            const text = raw ? raw.textContent : "";
            try {
              await navigator.clipboard.writeText(text || "");
              copyBtn.textContent = "Copied";
              setTimeout(() => copyBtn.textContent = "Copy JSON", 900);
            } catch (_) {
              copyBtn.textContent = "Copy failed";
              setTimeout(() => copyBtn.textContent = "Copy JSON", 900);
            }
          });
        }

        setConn("warn", "warming up");
        refresh();
        start();
      }

      setup();
    </script>
  </body>
</html>"""
