---
name: "scrappe-advanced"
description: "Advanced anti-blocking web scraper with CAPTCHA solving, stealth/fingerprint spoofing, Cloudflare bypass, and automatic proxy harvesting. Full-featured production-ready scraping solution."
version: "2.0.0"
author: "Agent Zero + User"
tags: ["scraping", "web-scraping", "anti-blocking", "proxy", "captcha", "stealth", "cloudflare"]
trigger_patterns:
  - "scrape"
  - "web scraper"
  - "scrappe"
  - "anti-blocking"
  - "proxy scraping"
  - "captcha solver"
  - "cloudflare bypass"
  - "harvest proxies"
allowed_tools: ["code_execution_tool", "input"]
---

# 🕷️ Scrappe-Advanced: Anti-Blocking Web Scraper

This is a production-ready web scraper with advanced anti-blocking features including CAPTCHA solving, stealth/fingerprint spoofing, Cloudflare bypass, and automatic proxy harvesting.

## 🎯 When To Use This Skill

Use this skill when you need to:
- Scrape websites with bot protection
- Bypass CAPTCHAs automatically
- Handle JavaScript-rendered content
- Rotate through multiple proxies
- Avoid detection with stealth techniques
- Bypass Cloudflare challenges

## 📦 Features

| Feature | Description |
|---------|-------------|
| **CAPTCHA Solving** | API-based (2captcha, Anti-Captcha) + OCR fallback |
| **Stealth/Spoofing** | Randomize fingerprint, canvas, WebGL, WebRTC, timezone |
| **Cloudflare Bypass** | Auto-detect and bypass Turnstile challenges |
| **Proxy Harvesting** | Auto-scrape free proxies from 6+ sources |
| **Rate Limiting** | Configurable request limits per minute |
| **JavaScript Rendering** | Playwright-based headless browser |
| **Cookie Persistence** | Save and reuse cookies |
| **Observability** | Prometheus + Grafana monitoring |

## 🚀 Quick Start

### Step 1: Navigate to Skill Directory

Always work from the skill directory:

```bash
cd /a0/skills/scrappe-advanced
```

### Step 2: Configure Your Target

Edit `config.yml` and add your target:

```yaml
targets:
  - name: "my_target"
    urls:
      - "https://example.com"
    render_js: true
    enable_stealth: true
    enable_captcha_solver: true
    enable_cloudflare_bypass: true
    extract:
      title: "h1"
      content: ".content"
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Run Scraper

```bash
python scripts/run_scraper.py --target my_target
```

Or with Docker:

```bash
docker-compose up -d
```

## 📖 Detailed Usage

### CAPTCHA Solving

The scraper supports two CAPTCHA solving methods:

1. **API-based (Recommended)**: Use 2captcha, Anti-Captcha, or CapMonster
2. **OCR-based (Free)**: Use pytesseract for text-based CAPTCHAs

Configure in `config.yml`:

```yaml
captcha_solver:
  enabled: true
  api_enabled: true
  api_type: "2captcha"
  api_key: "YOUR_API_KEY"
  ocr_enabled: true  # Free fallback
```

### Stealth & Fingerprint Spoofing

Spoof browser fingerprints to avoid detection:

```yaml
stealth:
  enabled: true
  randomize_fingerprint: true
  randomize_canvas: true
  randomize_webgl: true
  human_like_mouse: true
  headless: false  # Headless is more detectable
```

### Cloudflare Bypass

Automatically detect and bypass Cloudflare challenges:

```yaml
cloudflare_bypass:
  enabled: true
  max_wait_time: 120
  auto_bypass_on_detection: true
```

### Proxy Harvesting

Automatically collect and validate free proxies:

```yaml
proxy_harvesting:
  enabled: true
  harvest_interval_hours: 24
  max_proxies_per_harvest: 1000
  validate_proxies: true
```

## 🛠️ Available Scripts

| Script | Description |
|--------|-------------|
| `scripts/run_scraper.py` | Main scraper runner |
| `scraper/proxy/harvester.py` | Proxy harvesting utility |
| `scraper/captcha/solver.py` | CAPTCHA solving logic |
| `scraper/bypass/cloudflare.py` | Cloudflare bypass logic |

## 📝 Project Structure

```
scraper/
├── captcha/          # CAPTCHA solving modules
├── stealth/          # Fingerprint spoofing
├── bypass/           # Bot challenge bypass
├── proxy/            # Proxy management
├── rendering/        # JavaScript rendering
├── network/          # HTTP client & rate limiting
├── extractors/       # Data extraction
├── storage/          # Output writers
├── monitoring/       # Metrics & observability
└── engine.py         # Main scraping engine
```

## 🔧 Configuration

All configuration is done via `config.yml`:

- **Scraper settings**: Run mode, intervals, concurrency
- **Targets**: URLs to scrape, extraction rules
- **Proxies**: Proxy sources, validation settings
- **CAPTCHA**: API keys, OCR settings
- **Stealth**: Fingerprint randomization options
- **Bypass**: Cloudflare settings

## 🐳 Docker Deployment

Build and run with Docker:

```bash
# Build image
docker build -t scrappe:latest .

# Run with compose
docker-compose up -d

# Scale instances
docker-compose up -d --scale scraper=5
```

## 📊 Monitoring

Enable Prometheus + Grafana monitoring:

```yaml
monitoring:
  enabled: true
  prometheus_port: 9108
  grafana_port: 3000
```

Access dashboard at: `http://localhost:3000`

## 🐛 Troubleshooting

### Import Errors
```bash
pip install playwright
playwright install chromium
```

### Tesseract Not Found
```bash
sudo apt-get install tesseract-ocr tesseract-ocr-eng
```

### Proxies Not Working
- Check `logs/scraper.log` for details
- Verify proxy harvesting is enabled
- Test proxy manually: `curl -x http://proxy:port http://httpbin.org/ip`

## 📚 Resources

- Full user guide: `USER_GUIDE.md`
- Project README: `README.md`
- Configuration example: `config.yml`

## ⚠️ Legal & Ethical

Always respect robots.txt, terms of service, and rate limits. This tool is for educational purposes and legitimate data collection only.

## 🔄 Workflow Example

```bash
# 1. Navigate to skill
cd /a0/skills/scrappe-advanced

# 2. Configure target
vi config.yml

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run scraper
python scripts/run_scraper.py --target my_target

# 5. Monitor logs
tail -f logs/scraper.log

# 6. Check output
ls -lh data/output/
```
