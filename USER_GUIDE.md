# 📘 Komplet Brugervejledning - Scraper Med Avancerede Features

Denne guide viser dig trin-for-trin hvordan du bruger din scraper med de nye avancerede funktioner.

---

## 📋 INDHOLDSFORTEGNELSE

1. [Installation](#1-installation)
2. [Grundlæggende Opsætning](#2-grundlæggende-opsætning)
3. [Konfiguration](#3-konfiguration)
4. [Avancerede Features](#4-avancerede-features)
5. [Kørsel](#5-kørsel)
6. [Docker Deployment](#6-docker-deployment)
7. [Troubleshooting](#7-troubleshooting)
8. [Eksempler](#8-eksempler)

---

<a name="1-installation"></a>
## 1. INSTALLATION

### **Trin 1.1: Klon Repository**

```bash
# Hvis du har adgang til Git
git clone https://github.com/maat001kea/scrappe.git
cd scrappe

# Eller download ZIP filen fra GitHub og unzip
```

### **Trin 1.2: Installer Python Dependencies**

```bash
# Installer requirements
pip install -r requirements.txt
```

**Hvilke pakker installeres?**
- `requests` - HTTP anmodninger
- `httpx` - Async HTTP klient
- `beautifulsoup4` - HTML parsing
- `playwright` - JavaScript rendering
- `pytesseract` - OCR til CAPTCHA løsning
- `Pillow` - Billed behandling
- `aiohttp` - Async HTTP til proxy validering

### **Trin 1.3: Installer System Dependencies**

**På Ubuntu/Debian:**
```bash
# For OCR (CAPTCHA løsning)
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng

# For Playwright (headless browsers)
playwright install chromium
```

**På macOS:**
```bash
# Installer Homebrew hvis du ikke har det
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Installer tesseract
brew install tesseract

# Installer playwright browsers
playwright install chromium
```

**På Windows:**
```bash
# Download og installer Tesseract fra:
https://github.com/UB-Mannheim/tesseract/wiki

# Installer playwright browsers
playwright install chromium
```

### **Trin 1.4: Bekræft Installation**

```bash
# Tjek Python version (kræver 3.8+)
python --version

# Tjek at Tesseract er installeret
tesseract --version

# Tjek at Playwright er installeret
playwright --version
```

---

<a name="2-grundlæggende-opsætning"></a>
## 2. GRUNDLÆGGENDE OPSÆTNING

### **Trin 2.1: Opret Nødvendige Mapper**

```bash
# Opret data og log mapper
mkdir -p data/output
mkdir -p data/backups
mkdir -p data/state
mkdir -p data/proxies
mkdir -p data/cookies
mkdir -p logs
```

### **Trin 2.2: Test Basal Opsætning**

```bash
# Kør en simpel test
python -m pytest tests/ -v

# Eller kør scraper i debug mode
python scripts/run_scraper.py --debug --target example
```

---

<a name="3-konfiguration"></a>
## 3. KONFIGURATION

### **Trin 3.1: Åbn `config.yml`**

```bash
# Filen findes i roden af projektet
vi config.yml  # eller nano, code, etc.
```

### **Trin 3.2: Grundlæggende Scraper Konfiguration**

```yaml
scraper:
  # Køretilstand:
  # - oneshot: Kør targets én gang og afslut
  # - daemon: Kør kontinuerligt (anbefalet til Docker)
  run_mode: daemon
  run_interval_seconds: 60  # Hvert minut
  
  # Rate limiting
  requests_per_minute: 600  # Maks requests per minut
  max_concurrency: 20       # Maks concurrent requests
  
  # Retry logik
  max_retries: 3
  timeout_seconds: 20
```

### **Trin 3.3: Konfigurer Dine Targets**

```yaml
targets:
  # Eksempel 1: Simpelt website
  - name: "min_hjemmeside"
    urls:
      - "https://eksempel.dk"
    render_js: false  # Ingen JavaScript
    extract:
      title_selector: "h1"
      links_selector: "a"
  
  # Eksempel 2: JavaScript tungt website
  - name: "shop_eksempel"
    urls:
      - "https://shop.eksempel.dk/products"
    render_js: true  # Kræver Playwright
    wait_for_selector: ".product-list"
    extract:
      title_selector: ".product-title"
      price_selector: ".product-price"
```

---

<a name="4-avancerede-features"></a>
## 4. AVANCEREDE FEATURES

### **4.1 CAPTCHA LØSNING**

```yaml
captcha_solver:
  enabled: true
  
  # API konfiguration
  api_enabled: true
  api_type: "2captcha"  # Muligheder: 2captcha, anti-captcha, capmonster
  api_key: "DIN_API_KEY_HER"  # Få fra https://2captcha.com/
  
  # OCR fallback (gratis men mindre pålideligt)
  ocr_enabled: true
  ocr_language: "eng"  # eller "dan" for dansk
  
  preferred_solver: "api"
  fallback_to_ocr: true
```

### **4.2 STEALTH/FINGERPRINT SPOOFING**

```yaml
stealth:
  enabled: true
  
  # Fingerprint randomisering
  randomize_fingerprint: true
  randomize_canvas: true
  randomize_webgl: true
  randomize_webrtc: true
  
  # Human-like adfærd
  human_like_mouse: true
  random_delays: true
  
  # Playwright settings
  headless: false  # Headless er mere detekterbar
```

### **4.3 CLOUDFLARE BYPASS**

```yaml
cloudflare_bypass:
  enabled: true
  
  # Challenge håndtering
  max_wait_time: 120  # Maks sekunder at vente
  human_like_waiting: true
  random_mouse_movements: true
  
  # Cookie persistence
  save_cookies: true
  auto_bypass_on_detection: true
```

### **4.4 AUTOMATISK PROXY HARVESTING**

```yaml
proxy_harvesting:
  enabled: true
  
  # Harvest indstillinger
  harvest_interval_hours: 24
  max_proxies_per_harvest: 1000
  validate_proxies: true
  
  # Automatisk refresh
  auto_refresh: true
  refresh_interval_hours: 12
```

---

<a name="5-kørsel"></a>
## 5. KØRSEL

### **5.1: Kør Scraper Lokalt**

```bash
# Grundlæggende kørsel
python scripts/run_scraper.py

# Kør specifik target
python scripts/run_scraper.py --target min_hjemmeside
# Kør i debug mode
python scripts/run_scraper.py --debug
```

### **5.2: Overvåg Scraperen**

```bash
# Følg logs i realtid
tail -f logs/scraper.log

# Se output filer
ls -lh data/output/
```

---

<a name="6-docker-deployment"></a>
## 6. DOCKER DEPLOYMENT

### **6.1: Byg Docker Image**

```bash
# Build image
docker build -t scrappe:latest .
# Eller brug docker-compose
docker-compose build
```

### **6.2: Kør Med Docker Compose**

```bash
# Start alle services
docker-compose up -d
# Se status
docker-compose ps
# Se logs
docker-compose logs -f
```

### **6.3: Skalér Med Docker**

```bash
# Skalér op til 5 containers
docker-compose up -d --scale scraper=5
```

---

<a name="7-troubleshooting"></a>
## 7. TROUBLESHOOTING

### **Problem: Import Errors**
```bash
# Fejl: ModuleNotFoundError
# Løsning:
pip install playwright
playwright install chromium
```

### **Problem: Tesseract Not Found**
```bash
# Løsning (Ubuntu/Debian):
sudo apt-get install tesseract-ocr tesseract-ocr-eng
```

### **Problem: Proxies Not Working**
```bash
# Løsninger:
1. Tjek at proxy harvesting er enabled
2. Tjek log fil: tail logs/scraper.log
3. Manual test: curl -x http://proxy:port http://httpbin.org/ip
```

### **Problem: CAPTCHA Solving Failed**
```bash
# Løsninger:
1. Tjek API key er korrekt
2. Tjek saldo på 2captcha.com
3. Brug OCR fallback
```

---

<a name="8-eksempler"></a>
## 8. EKSEMPLER

### **Eksempel 1: Simpel HTML Scraping**
```yaml
targets:
  - name: "nyheder"
    urls:
      - "https://nyhedssite.dk"
    render_js: false
    extract:
      title: "h1"
      content: ".article-content"
```

### **Eksempel 2: E-commerce Shop Med JavaScript**
```yaml
targets:
  - name: "shop"
    urls:
      - "https://shop.eksempel.dk/products"
    render_js: true
    enable_stealth: true
    extract:
      title: ".product-title"
      price: ".product-price"
```

### **Eksempel 3: Cloudflare Beskyttet Site**
```yaml
targets:
  - name: "beskyttet_site"
    urls:
      - "https://beskyttet.dk"
    render_js: true
    enable_cloudflare_bypass: true
    enable_stealth: true
    enable_captcha_solver: true
```

---

## ✅ Quick Start Checklist

- [ ] Python 3.8+ installeret
- [ ] Alle dependencies installeret
- [ ] Tesseract OCR installeret
- [ ] Playwright browsers installeret
- [ ] config.yml redigeret
- [ ] Nødvendige mapper oprettet

---

**Klar til at starte? Kør: `python scripts/run_scraper.py`** 🚀
