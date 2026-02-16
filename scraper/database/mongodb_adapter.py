"""
MongoDB database adapter
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base_adapter import BaseAdapter, DatabaseConfig

try:
    import motor.motor_asyncio
    from pymongo import ASCENDING, DESCENDING
    MOTOR_AVAILABLE = True
except ImportError:
    MOTOR_AVAILABLE = False


logger = logging.getLogger(__name__)


class MongoDBAdapter(BaseAdapter):
    """
    MongoDB database adapter using motor (async driver)
    
    Features:
    - Async connection pooling
    - Automatic document validation
    - Bulk operations
    - Index management
    - Schema-less storage
    """
    
    def __init__(self, config: DatabaseConfig):
        if not MOTOR_AVAILABLE:
            raise ImportError("motor is required for MongoDB adapter")
        
        super().__init__(config)
        self._client: Optional[motor.motor_asyncio.AsyncIOMotorClient] = None
        self._db = None
        self._results_collection = None
        self._errors_collection = None
    
    async def connect(self) -> None:
        """Establish MongoDB connection"""
        connection_string = self.config.connection_string or self._build_connection_string()
        
        logger.info(f"Connecting to MongoDB at {self.config.host}:{self.config.port}")
        
        self._client = motor.motor_asyncio.AsyncIOMotorClient(
            connection_string,
            maxPoolSize=self.config.pool_size,
            serverSelectionTimeoutMS=self.config.pool_timeout * 1000
        )
        
        # Ping to verify connection
        await self._client.admin.command('ping')
        
        self._db = self._client[self.config.database]
        self._results_collection = self._db.scrape_results
        self._errors_collection = self._db.scrape_errors
        
        logger.info("MongoDB connected successfully")
    
    async def disconnect(self) -> None:
        """Close MongoDB connection"""
        if self._client:
            self._client.close()
            self._client = None
            logger.info("MongoDB connection closed")
    
    async def insert_scrape_result(
        self,
        target_name: str,
        url: str,
        result: Dict[str, Any]
    ) -> bool:
        """Insert a single scrape result"""
        await self.ensure_connected()
        
        try:
            document = {
                'target_name': target_name,
                'url': url,
                'status_code': result.get('status_code'),
                'latency_seconds': result.get('latency_seconds'),
                'proxy': result.get('proxy'),
                'extracted': result.get('extracted', {}),
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc)
            }
            
            await self._results_collection.update_one(
                {'url': url},
                {'$set': document},
                upsert=True
            )
            
            self._stats['inserts'] += 1
            return True
            
        except Exception as e:
            logger.error(f"MongoDB insert failed: {e}")
            self._stats['errors'] += 1
            return False
    
    async def batch_insert_scrape_results(
        self,
        results: List[Dict[str, Any]]
    ) -> int:
        """Insert multiple scrape results using bulk operation"""
        if not results:
            return 0
        
        await self.ensure_connected()
        
        try:
            operations = []
            for r in results:
                document = {
                    'target_name': r.get('target_name'),
                    'url': r.get('url'),
                    'status_code': r.get('status_code'),
                    'latency_seconds': r.get('latency_seconds'),
                    'proxy': r.get('proxy'),
                    'extracted': r.get('extracted', {}),
                    'created_at': datetime.now(timezone.utc),
                    'updated_at': datetime.now(timezone.utc)
                }
                
                operations.append(
                    self._results_collection.update_one(
                        {'url': r.get('url')},
                        {'$set': document},
                        upsert=True
                    )
                )
            
            await asyncio.gather(*operations)
            
            self._stats['batch_inserts'] += 1
            self._stats['inserts'] += len(results)
            return len(results)
            
        except Exception as e:
            logger.error(f"MongoDB batch insert failed: {e}")
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
            query = {}
            if target_name:
                query['target_name'] = target_name
            
            cursor = (
                self._results_collection
                .find(query)
                .sort('created_at', DESCENDING)
                .skip(offset)
                .limit(limit)
            )
            
            results = await cursor.to_list(length=limit)
            
            # Convert ObjectId to string
            for r in results:
                r['_id'] = str(r['_id'])
                
            return results
            
        except Exception as e:
            logger.error(f"MongoDB query failed: {e}")
            return []
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        await self.ensure_connected()
        
        try:
            total = await self._results_collection.count_documents({})
            
            pipeline = [
                {'$group': {'_id': '$target_name', 'count': {'$sum': 1}}}
            ]
            by_target_cursor = self._results_collection.aggregate(pipeline)
            by_target_list = await by_target_cursor.to_list(length=100)
            by_target = {r['_id']: r['count'] for r in by_target_list}
            
            # Calculate average latency for successful requests
            pipeline = [
                {'$match': {'status_code': 200}},
                {'$group': {'_id': None, 'avg': {'$avg': '$latency_seconds'}}}
            ]
            avg_latency_cursor = self._results_collection.aggregate(pipeline)
            avg_latency_list = await avg_latency_cursor.to_list(length=1)
            avg_latency = float(avg_latency_list[0]['avg']) if avg_latency_list else 0.0
            
            return {
                'total_results': total,
                'by_target': by_target,
                'avg_latency': avg_latency,
                'adapter_stats': self.get_adapter_stats()
            }
            
        except Exception as e:
            logger.error(f"MongoDB stats failed: {e}")
            return {}
    
    async def create_indexes(self) -> None:
        """Create database indexes"""
        await self.ensure_connected()
        
        try:
            await self._results_collection.create_index([('target_name', ASCENDING)])
            await self._results_collection.create_index([('created_at', DESCENDING)])
            await self._results_collection.create_index([('url', ASCENDING)], unique=True)
            await self._results_collection.create_index([('status_code', ASCENDING)])
            
            await self._errors_collection.create_index([('target_name', ASCENDING)])
            await self._errors_collection.create_index([('created_at', DESCENDING)])
            
            logger.info("MongoDB indexes created")
            
        except Exception as e:
            logger.error(f"MongoDB index creation failed: {e}")
    
    def _build_connection_string(self) -> str:
        """Build MongoDB connection string from config"""
        if self.config.username and self.config.password:
            return (
                f"mongodb://{self.config.username}:{self.config.password}"
                f"@{self.config.host}:{self.config.port}/{self.config.database}"
            )
        return f"mongodb://{self.config.host}:{self.config.port}/{self.config.database}"
