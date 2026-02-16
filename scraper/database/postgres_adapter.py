"""
PostgreSQL database adapter
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict

from .base_adapter import BaseAdapter, DatabaseConfig

try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False


logger = logging.getLogger(__name__)


class PostgreSQLAdapter(BaseAdapter):
    """
    PostgreSQL database adapter using asyncpg
    
    Features:
    - Async connection pooling
    - Automatic JSON serialization
    - Batch inserts
    - Index management
    - Connection retry
    """
    
    def __init__(self, config: DatabaseConfig):
        if not ASYNCPG_AVAILABLE:
            raise ImportError("asyncpg is required for PostgreSQL adapter")
        
        super().__init__(config)
        self._pool: Optional[asyncpg.Pool] = None
    
    async def connect(self) -> None:
        """Establish PostgreSQL connection pool"""
        dsn = self._build_dsn()
        
        logger.info(f"Connecting to PostgreSQL at {self.config.host}:{self.config.port}")
        
        self._pool = await asyncpg.create_pool(
            dsn,
            min_size=1,
            max_size=self.config.pool_size,
            max_queries=self.config.max_overflow,
            max_inactive_connection_lifetime=self.config.pool_recycle,
            command_timeout=self.config.pool_timeout
        )
        
        logger.info("PostgreSQL connection pool created")
    
    async def disconnect(self) -> None:
        """Close connection pool"""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("PostgreSQL connection pool closed")
    
    async def insert_scrape_result(
        self,
        target_name: str,
        url: str,
        result: Dict[str, Any]
    ) -> bool:
        """Insert a single scrape result"""
        await self.ensure_connected()
        
        try:
            async with self._pool.acquire() as conn:
                await conn.execute('''
                    INSERT INTO scrape_results (
                        target_name, url, status_code, latency_seconds,
                        proxy, extracted, created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (url) DO UPDATE SET
                        status_code = EXCLUDED.status_code,
                        latency_seconds = EXCLUDED.latency_seconds,
                        proxy = EXCLUDED.proxy,
                        extracted = EXCLUDED.extracted,
                        updated_at = NOW()
                ''',
                    target_name,
                    url,
                    result.get('status_code'),
                    result.get('latency_seconds'),
                    result.get('proxy'),
                    json.dumps(result.get('extracted', {})),
                    datetime.now(timezone.utc)
                )
                
                self._stats['inserts'] += 1
                return True
                
        except Exception as e:
            logger.error(f"PostgreSQL insert failed: {e}")
            self._stats['errors'] += 1
            return False
    
    async def batch_insert_scrape_results(
        self,
        results: List[Dict[str, Any]]
    ) -> int:
        """Insert multiple scrape results"""
        if not results:
            return 0
        
        await self.ensure_connected()
        
        try:
            async with self._pool.acquire() as conn:
                records = [
                    (
                        r.get('target_name'),
                        r.get('url'),
                        r.get('status_code'),
                        r.get('latency_seconds'),
                        r.get('proxy'),
                        json.dumps(r.get('extracted', {})),
                        datetime.now(timezone.utc)
                    )
                    for r in results
                ]
                
                await conn.executemany('''
                    INSERT INTO scrape_results (
                        target_name, url, status_code, latency_seconds,
                        proxy, extracted, created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (url) DO UPDATE SET
                        status_code = EXCLUDED.status_code,
                        latency_seconds = EXCLUDED.latency_seconds,
                        proxy = EXCLUDED.proxy,
                        extracted = EXCLUDED.extracted,
                        updated_at = NOW()
                ''', records)
                
                self._stats['batch_inserts'] += 1
                self._stats['inserts'] += len(results)
                return len(results)
                
        except Exception as e:
            logger.error(f"PostgreSQL batch insert failed: {e}")
            self._stats['errors'] += 1
            return 0
    
    async def get_scrape_results(
        self,
        target_name: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Retrieve scrape results"""
        await self.ensure_connected()
        
        try:
            async with self._pool.acquire() as conn:
                if target_name:
                    rows = await conn.fetch('''
                        SELECT * FROM scrape_results
                        WHERE target_name = $1
                        ORDER BY created_at DESC
                        LIMIT $2 OFFSET $3
                    ''', target_name, limit, offset)
                else:
                    rows = await conn.fetch('''
                        SELECT * FROM scrape_results
                        ORDER BY created_at DESC
                        LIMIT $1 OFFSET $2
                    ''', limit, offset)
                
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"PostgreSQL query failed: {e}")
            return []
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        await self.ensure_connected()
        
        try:
            async with self._pool.acquire() as conn:
                total = await conn.fetchval('SELECT COUNT(*) FROM scrape_results')
                by_target = await conn.fetch('''
                    SELECT target_name, COUNT(*) as count
                    FROM scrape_results
                    GROUP BY target_name
                ''')
                avg_latency = await conn.fetchval('''
                    SELECT AVG(latency_seconds) FROM scrape_results
                    WHERE status_code = 200
                ''')
                
                return {
                    'total_results': total,
                    'by_target': {r['target_name']: r['count'] for r in by_target},
                    'avg_latency': float(avg_latency) if avg_latency else 0.0,
                    'adapter_stats': self.get_adapter_stats()
                }
                
        except Exception as e:
            logger.error(f"PostgreSQL stats failed: {e}")
            return {}
    
    async def create_indexes(self) -> None:
        """Create database indexes"""
        await self.ensure_connected()
        
        try:
            async with self._pool.acquire() as conn:
                await conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_scrape_results_target
                    ON scrape_results(target_name)
                ''')
                await conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_scrape_results_created
                    ON scrape_results(created_at DESC)
                ''')
                await conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_scrape_results_url
                    ON scrape_results(url)
                ''')
                await conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_scrape_results_status
                    ON scrape_results(status_code)
                ''')
                
                logger.info("PostgreSQL indexes created")
                
        except Exception as e:
            logger.error(f"PostgreSQL index creation failed: {e}")
    
    async def initialize_schema(self) -> None:
        """Initialize database schema"""
        await self.ensure_connected()
        
        try:
            async with self._pool.acquire() as conn:
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS scrape_results (
                        id BIGSERIAL PRIMARY KEY,
                        target_name VARCHAR(255) NOT NULL,
                        url TEXT NOT NULL UNIQUE,
                        status_code INTEGER,
                        latency_seconds FLOAT,
                        proxy TEXT,
                        extracted JSONB,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE
                    )
                ''')
                
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS scrape_errors (
                        id BIGSERIAL PRIMARY KEY,
                        target_name VARCHAR(255) NOT NULL,
                        url TEXT NOT NULL,
                        error_type VARCHAR(100),
                        error_message TEXT,
                        status_code INTEGER,
                        proxy TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                ''')
                
                logger.info("PostgreSQL schema initialized")
                
        except Exception as e:
            logger.error(f"PostgreSQL schema initialization failed: {e}")
    
    def _build_dsn(self) -> str:
        """Build PostgreSQL DSN from config"""
        if self.config.username and self.config.password:
            return (
                f"postgresql://{self.config.username}:{self.config.password}"
                f"@{self.config.host}:{self.config.port}/{self.config.database}"
            )
        return (
            f"postgresql://{self.config.host}:{self.config.port}"
            f"/{self.config.database}"
        )
