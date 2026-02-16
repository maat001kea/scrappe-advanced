"""
Base database adapter interface
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from enum import Enum


logger = logging.getLogger(__name__)


class DatabaseType(Enum):
    POSTGRES = "postgresql"
    MONGODB = "mongodb"
    SQLITE = "sqlite"


@dataclass
class DatabaseConfig:
    """Database configuration"""
    db_type: DatabaseType
    host: str = "localhost"
    port: int = 5432
    database: str = "scrappe"
    username: Optional[str] = None
    password: Optional[str] = None
    
    # Connection settings
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600
    
    # MongoDB specific
    connection_string: Optional[str] = None
    
    # SSL
    ssl_mode: str = "prefer"
    ssl_cert: Optional[str] = None
    
    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # Batch settings
    batch_size: int = 100
    batch_timeout: float = 5.0


class BaseAdapter(ABC):
    """
    Abstract base class for database adapters
    """
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._connection = None
        self._stats: Dict[str, Any] = {
            "inserts": 0,
            "updates": 0,
            "errors": 0,
            "batch_inserts": 0
        }
    
    @abstractmethod
    async def connect(self) -> None:
        """Establish database connection"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close database connection"""
        pass
    
    @abstractmethod
    async def insert_scrape_result(
        self,
        target_name: str,
        url: str,
        result: Dict[str, Any]
    ) -> bool:
        """Insert a single scrape result"""
        pass
    
    @abstractmethod
    async def batch_insert_scrape_results(
        self,
        results: List[Dict[str, Any]]
    ) -> int:
        """Insert multiple scrape results"""
        pass
    
    @abstractmethod
    async def get_scrape_results(
        self,
        target_name: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Retrieve scrape results"""
        pass
    
    @abstractmethod
    async def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        pass
    
    @abstractmethod
    async def create_indexes(self) -> None:
        """Create database indexes for performance"""
        pass
    
    async def ensure_connected(self) -> None:
        """Ensure connection is active"""
        if self._connection is None:
            await self.connect()
    
    def get_adapter_stats(self) -> Dict[str, Any]:
        """Get adapter operation statistics"""
        return self._stats.copy()
    
    def reset_stats(self) -> None:
        """Reset statistics"""
        self._stats = {
            "inserts": 0,
            "updates": 0,
            "errors": 0,
            "batch_inserts": 0
        }
