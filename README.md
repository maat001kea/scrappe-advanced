# Production Scraper (Docker + Playwright)

A production-oriented scraping runner with:
- proxy rotation + health scoring
- requests + Playwright rendering (JS/SPAs)
- rate limiting, concurrency, retries + exponential backoff
- structured JSON logging
- Prometheus metrics + health endpoint
- JSONL + CSV storage with deduplication + backups

## Important
This project is designed for **authorized** scraping (sites you own or have permission to access) and for reliability/observability.

It **detects** CAPTCHAs/bot challenges and fails fast by default. It does **not** include code to bypass access controls.

## Quickstart (Docker)

1. Configure `config.yml`

2. Start the scraper:

```bash
# Use a project name to avoid interacting with other compose projects/containers.
docker compose --project-name scrappe_scraper up -d --build scraper
```

3. Health + metrics:
- Health: `http://localhost:8080/health`
- Metrics: `http://localhost:9108/metrics`
- Web UI: `http://localhost:8080/ui`

### Optional monitoring stack

```bash
docker compose --profile monitoring up --build
```

- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000` (admin/admin)

### Optional database

```bash
docker compose --profile db up -d
```

## Local Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m scraper.app
```

## Configuration

Edit `config.yml`.

Key settings:
- `scraper.run_mode`: `daemon` (default) or `oneshot`.
- `scraper.run_interval_seconds`: seconds to sleep between runs in `daemon` mode.
- `scraper.requests_per_minute`: global rate limit.
- `scraper.max_concurrency`: number of worker tasks.
- `scraper.autoscale_enabled`: auto-scale workers inside the container based on queue depth.
- `proxies.enabled`: enable/disable proxy usage.
- `proxies.sources`: load proxies from files or env vars.
- `proxies.selection_strategy`: `weighted` or `thompson` (Bayesian success-probability prediction).
- `targets`: list of scrape targets. Each target supports `url` or `urls`.
- `targets[].render_js`: use Playwright for JS-heavy pages.
- `targets[].wait_for_selector`: wait for an element before extracting.

## Proxies

Proxy list formats supported:
- `host:port`
- `http://host:port`
- `http://user:pass@host:port`

If you enable proxies and all proxies become unhealthy, the engine will error and log the failure.

## Output

Files are written to `data/output/`:
- `<target>.jsonl`: one JSON record per successful URL
- `<target>.csv`: lightweight CSV export
- `<target>_errors.jsonl`: structured error events (one per failed attempt)

State and backups:
- Deduplication keys: `data/state/dedupe.json`
- Backups: `data/backups/`
- Playwright session state (cookies/localStorage): `data/state/playwright_<target>.json`
- CAPTCHA artifacts (HTML snapshots): `data/output/artifacts/captcha/`

## How It Works

- `scraper/engine.py` runs an async queue of `ScrapeTask` items.
- Each task gets a random User-Agent from `scraper/network/user_agents.py` and headers from `scraper/network/headers.py`.
- Proxy selection uses `scraper/proxy/pool.py` scoring (success-rate + latency) and disables bad proxies.
- Fetch path:
  - `render_js: false` -> `requests` via `scraper/network/http_client.py`
  - `render_js: true` -> Playwright via `scraper/rendering/playwright_renderer.py`
- CAPTCHA/challenge detection uses `scraper/captcha/detector.py`.
- Extraction uses `scraper/extractors/basic.py` (title + links) and is easy to replace.
- Storage writes JSONL + CSV via `scraper/storage/writer.py` with dedupe.
- Monitoring exposes `/health` and `/metrics` via `scraper/monitoring/server.py`.

## Tests

### Run All Unit Tests (Local)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

### Run All Unit Tests (Docker)

```bash
docker compose --profile dev run --rm tests
```

### Test Individual Components

```bash
# Proxy pool scoring/cooldowns
pytest tests/test_proxy_pool.py

# CAPTCHA/challenge detector
pytest tests/test_captcha_detector.py

# Rate limiter
pytest tests/test_rate_limiter.py

# Exponential backoff
pytest tests/test_backoff.py

# Deduplication state
pytest tests/test_dedupe.py
```

Tests live in `tests/` and run with:

```bash
pytest
```
