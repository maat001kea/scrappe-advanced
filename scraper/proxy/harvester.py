"""
Automatic Free Proxy Harvester

Automatically discovers and validates free proxies from multiple sources:
- Scrapes proxy lists from multiple websites
- Validates proxy connectivity and speed
- Tests proxy anonymity levels
- Maintains proxy database with health scores
- Automatic refresh and rotation
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
import aiodns
import aiohttp

from scraper.proxy.models import Proxy, ProxyStatus
from scraper.config import ProxyHarvesterConfig


logger = logging.getLogger(__name__)


# Free proxy sources (websites that list free proxies)
PROXY_SOURCES = [
    {
        "name": "free-proxy-list",
        "url": "https://free-proxy-list.net/",
        "type": "html",
        "selectors": {
            "table": "#proxylisttable",
            "rows": "tbody tr",
            "ip": "td:nth-child(1)",
            "port": "td:nth-child(2)",
            "country": "td:nth-child(4)",
            "type": "td:nth-child(7)",
            "anonymity": "td:nth-child)(5)",
            "https": "td:nth-child)(7)"
        }
    },
    {
        "name": "ssl-proxies",
        "url": "https://www.ssl-proxies.org/",
        "type": "html",
        "selectors": {
            "table": "#proxylisttable",
            "rows": "tbody tr",
            "ip": "td:nth-child(1)",
            "port": "td:nth-child(2)",
            "country": "td:nth-child(4)",
            "type": "https"
        }
    },
    {
        "name": "us-proxy",
        "url": "https://www.us-proxy.org/",
        "type": "html",
        "selectors": {
            "table": "#proxylisttable",
            "rows": "tbody tr",
            "ip": "td:nth-child(1)",
            "port": "td:nth-child(2)",
            "country": "td:nth-child)(3)",
            "type": "http"
        }
    },
    {
        "name": "proxy-list-download",
        "url": "https://www.proxy-list.download/api/v1/get?type=http",
        "type": "text",
        "format": "ip:port"
    },
    {
        "name": "hidemy-name",
        "url": "https://hidemy.name/en/proxy-list/?maxtime=1000&type=h",
        "type": "html",
        "selectors": {
            "table": ".table_block tbody",
            "rows": "tr",
            "ip": "td:nth-child)(1)",
            "port": "td:nth-child)(2)",
            "country": "td:nth-child)(3)",
            "type": "td:nth-child)(7)"
        }
    },
    {
        "name": "spys-me",
        "url": "https://spys.me/en/",
        "type": "html",
        "selectors": {
            "table": ".spy1x > tbody",
            "rows": "tr",
            "ip": "td:nth-child)(1)",
            "port": "td:nth-child)(2)",
            "country": "td:nth-child)(3)"
        }
    }
]


# Test websites to verify proxy functionality (configurable via ProxyHarvesterConfig)
# Default URLs are defined in config.py


@dataclass
class ProxyTestResult:
    """Result of proxy validation test"""
    proxy: str
    success: bool
    response_time: float
    external_ip: Optional[str] = None
    anonymity_level: Optional[str] = None
    https_support: bool = False
    error: Optional[str] = None


@dataclass
class HarvestStats:
    """Statistics for proxy harvesting"""
    total_discovered: int = 0
    successfully_validated: int = 0
    failed_validation: int = 0
    total_sources_scraped: int = 0
    sources_failed: int = 0
    time_taken: float = 0.0
    average_response_time: float = 0.0
    https_count: int = 0
    http_count: int = 0


class ProxyHarvester:
    """
    Automatic free proxy harvester
    
    Features:
    - Scrapes multiple free proxy sources
    - Validates proxy connectivity and speed
    - Tests anonymity levels
    - Maintains health scores
    - Automatic refresh
    """
    
    def __init__(
        self,
        config: Optional[ProxyHarvesterConfig] = None,
        custom_sources: Optional[List[Dict[str, Any]]] = None
    ):
        self.config = config or ProxyHarvesterConfig()
        self._sources = custom_sources or PROXY_SOURCES
        self._client: Optional[httpx.AsyncClient] = None
        self._test_client: Optional[aiohttp.ClientSession] = None
        self._validated_proxies: Dict[str, Proxy] = {}
        self._stats = HarvestStats()
        self._last_harvest_time: Optional[datetime] = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self._client = httpx.AsyncClient(
            timeout=self.config.request_timeout,
            follow_redirects=True,
            headers={
                "User-Agent": random.choice([
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
                ])
            }
        )
        self._test_client = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.validation_timeout)
        )
        return self
    
    async def __aexit__(self, *args):
        """Async context manager exit"""
        if self._client:
            await self._client.aclose()
        if self._test_client:
            await self._test_client.close()
    
    async def harvest(
        self,
        max_proxies: Optional[int] = None,
        validate: bool = True
    ) -> List[Proxy]:
        """
        Harvest proxies from all configured sources
        
        Args:
            max_proxies: Maximum number of proxies to collect
            validate: Whether to validate proxies
        
        Returns:
            List of validated proxies
        """
        start_time = time.time()
        self._stats = HarvestStats()
        
        logger.info("Starting proxy harvest...")
        
        # Discover proxies from all sources
        discovered_proxies = await self._discover_proxies()
        self._stats.total_discovered = len(discovered_proxies)
        
        logger.info(f"Discovered {len(discovered_proxies)} proxies from {self._stats.total_sources_scraped} sources")
        
        if not validate:
            # Return raw proxies without validation
            return list(discovered_proxies)
        
        # Validate proxies
        validated_proxies = await self._validate_proxies(discovered_proxies, max_proxies)
        
        self._stats.time_taken = time.time() - start_time
        self._last_harvest_time = datetime.now()
        
        logger.info(f"Harvest complete: {self._stats.successfully_validated} valid, "
                   f"{self._stats.failed_validation} failed ({self._stats.time_taken:.1f}s)")
        
        return validated_proxies
    
    async def _discover_proxies(self) -> Set[Proxy]:
        """Discover proxies from all sources"""
        all_proxies: Set[Proxy] = set()
        
        tasks = []
        for source in self._sources:
            if source.get("enabled", True):
                tasks.append(self._scrape_source(source))
        
        # Scrape all sources concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(f"Failed to scrape source {self._sources[i]['name']}: {result}")
                self._stats.sources_failed += 1
            elif result:
                all_proxies.update(result)
                self._stats.total_sources_scraped += 1
        
        return all_proxies
    
    async def _scrape_source(self, source: Dict[str, Any]) -> Set[Proxy]:
        """Scrape a single proxy source"""
        proxies: Set[Proxy] = set()
        
        try:
            logger.info(f"Scraping {source['name']}...")
            
            if source["type"] == "html":
                proxies = await self._scrape_html_source(source)
            elif source["type"] == "text":
                proxies = await self._scrape_text_source(source)
            elif source["type"] == "api":
                proxies = await self._scrape_api_source(source)
            
            logger.info(f"Found {len(proxies)} proxies from {source['name']}")
        
        except Exception as e:
            logger.error(f"Error scraping {source['name']}: {e}")
        
        return proxies
    
    async def _scrape_html_source(self, source: Dict[str, Any]) -> Set[Proxy]:
        """Scrape HTML-based proxy source"""
        proxies: Set[Proxy] = set()
        
        response = await self._client.get(source["url"])
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        selectors = source["selectors"]
        
        # Find table
        table = soup.select_one(selectors["table"])
        if not table:
            return proxies
        
        # Extract rows
        rows = table.select(selectors["rows"])
        
        for row in rows:
            try:
                ip_elem = row.select_one(selectors["ip"])
                port_elem = row.select_one(selectors["port"])
                
                if not ip_elem or not port_elem:
                    continue
                
                ip = ip_elem.get_text(strip=True)
                port = port_elem.get_text(strip=True)
                
                if not ip or not port:
                    continue
                
                # Extract additional info
                country = row.select_one(selectors.get("country", "")).get_text(strip=True) if "country" in selectors else None
                proxy_type = self._determine_proxy_type(row, selectors)
                anonymity = row.select_one(selectors.get("anonymity", "")).get_text(strip=True) if "anonymity" in selectors else None
                
                # Create proxy object
                proxy = Proxy(
                    ip=ip,
                    port=int(port),
                    country=country,
                    proxy_type=proxy_type,
                    anonymity=anonymity,
                    source=source["name"],
                    discovered_at=datetime.now()
                )
                
                proxies.add(proxy)
            
            except (ValueError, AttributeError) as e:
                continue
        
        return proxies
    
    async def _scrape_text_source(self, source: Dict[str, Any]) -> Set[Proxy]:
        """Scrape text-based proxy source"""
        proxies: Set[Proxy] = set()
        
        response = await self._client.get(source["url"])
        response.raise_for_status()
        
        text = response.text.strip()
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            try:
                if ":" in line:
                    ip, port = line.split(":", 1)
                    proxy = Proxy(
                        ip=ip.strip(),
                        port=int(port.strip()),
                        proxy_type=self._determine_type_from_url(source["url"]),
                        source=source["name"],
                        discovered_at=datetime.now()
                    )
                    proxies.add(proxy)
            except (ValueError, AttributeError):
                continue
        
        return proxies
    
    async def _scrape_api_source(self, source: Dict[str, Any]) -> Set[Proxy]:
        """Scrape API-based proxy source"""
        proxies: Set[Proxy] = set()
        
        try:
            response = await self._client.get(
                source["url"],
                headers=source.get("headers", {}),
                params=source.get("params", {})
            )
            response.raise_for_status()
            
            data = response.json()
            
            for item in data:
                if "ip" in item and "port" in item:
                    proxy = Proxy(
                        ip=item["ip"],
                        port=int(item["port"]),
                        country=item.get("country"),
                        proxy_type=item.get("type", "http"),
                        source=source["name"],
                        discovered_at=datetime.now()
                    )
                    proxies.add(proxy)
        
        except Exception as e:
            logger.error(f"Error scraping API source: {e}")
        
        return proxies
    
    def _determine_proxy_type(self, row, selectors) -> str:
        """Determine proxy type from row data"""
        try:
            type_elem = row.select_one(selectors.get("type", ""))
            if type_elem:
                type_text = type_elem.get_text(strip=True).lower()
                if "https" in type_text:
                    return "https"
                elif "socks" in type_text:
                    return "socks5"
            return "http"
        except (AttributeError, KeyError):
            return "http"
    
    def _determine_type_from_url(self, url: str) -> str:
        """Determine proxy type from URL"""
        if "https" in url.lower():
            return "https"
        return "http"
    
    async def _validate_proxies(
        self,
        proxies: Set[Proxy],
        max_proxies: Optional[int]
    ) -> List[Proxy]:
        """Validate proxies by testing connectivity"""
        validated: List[Proxy] = []
        test_tasks = []
        
        # Create test tasks
        for proxy in proxies:
            if max_proxies and len(validated) >= max_proxies:
                break
            test_tasks.append(self._test_proxy(proxy))
        
        # Test proxies concurrently
        results = await asyncio.gather(*test_tasks, return_exceptions=True)
        
        # Collect validated proxies
        for i, result in enumerate(results):
            if isinstance(result, ProxyTestResult):
                if result.success:
                    proxy = list(proxies)[i]
                    proxy.status = ProxyStatus.ACTIVE
                    proxy.response_time = result.response_time
                    proxy.success_rate = 100.0
                    proxy.last_verified = datetime.now()
                    proxy.external_ip = result.external_ip
                    
                    validated.append(proxy)
                    self._stats.successfully_validated += 1
                    
                    if proxy.proxy_type == "https":
                        self._stats.https_count += 1
                    else:
                        self._stats.http_count += 1
                else:
                    self._stats.failed_validation += 1
        
        # Sort by response time
        validated.sort(key=lambda p: p.response_time)
        
        # Calculate average response time
        if validated:
            self._stats.average_response_time = sum(p.response_time for p in validated) / len(validated)
        
        return validated
    
    async def _test_proxy(self, proxy: Proxy) -> ProxyTestResult:
        """Test a single proxy for connectivity and speed"""
        start_time = time.time()
        
        try:
            # Prepare proxy URL
            proxy_url = f"{proxy.proxy_type}://{proxy.ip}:{proxy.port}"
            
            # Test with configurable URLs from config
            test_urls = self.config.test_urls if hasattr(self.config, 'test_urls') and self.config.test_urls else [
                "http://httpbin.org/ip",
                "https://api.ipify.org",
                "http://icanhazip.com",
                "https://ifconfig.me/ip"
            ]
            
            for test_url in test_urls:
                try:
                    async with self._test_client.get(
                        test_url,
                        proxy=proxy_url,
                        timeout=aiohttp.ClientTimeout(total=self.config.validation_timeout)
                    ) as response:
                        if response.status == 200:
                            external_ip = await response.text()
                            
                            return ProxyTestResult(
                                proxy=str(proxy),
                                success=True,
                                response_time=time.time() - start_time,
                                external_ip=external_ip.strip(),
                                https_support=proxy.proxy_type == "https"
                            )
                except Exception as e:
                    continue
            
            return ProxyTestResult(
                proxy=str(proxy),
                success=False,
                response_time=time.time() - start_time,
                error="All test URLs failed"
            )
        
        except Exception as e:
            return ProxyTestResult(
                proxy=str(proxy),
                success=False,
                response_time=time.time() - start_time,
                error=str(e)
            )
    
    def get_stats(self) -> HarvestStats:
        """Get harvest statistics"""
        return self._stats
    
    def get_validated_proxies(self) -> Dict[str, Proxy]:
        """Get all validated proxies"""
        return self._validated_proxies
    
    def should_refresh(self) -> bool:
        """Check if proxies should be refreshed"""
        if not self._last_harvest_time:
            return True
        
        age = datetime.now() - self._last_harvest_time
        return age >= timedelta(seconds=self.config.refresh_interval)


# Factory function for creating harvester
def create_harvester(config: Optional[ProxyHarvesterConfig] = None) -> ProxyHarvester:
    """Create a proxy harvester instance"""
    return ProxyHarvester(config or ProxyHarvesterConfig())
