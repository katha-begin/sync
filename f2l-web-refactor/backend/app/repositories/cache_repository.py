"""
Cache Repository - Database operations for directory scan caching.
"""
import json
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, desc, func
from datetime import datetime, timedelta

from app.database.models import ScanCache


class CacheRepository:
    """Repository for scan cache database operations."""

    def __init__(self, db: AsyncSession):
        """Initialize repository with database session."""
        self.db = db

    async def get_all(
        self, 
        endpoint_id: Optional[UUID] = None,
        path_pattern: Optional[str] = None,
        valid_only: bool = True,
        skip: int = 0,
        limit: int = 100
    ) -> List[ScanCache]:
        """
        Get all cache entries with optional filtering.
        
        Args:
            endpoint_id: Filter by endpoint ID
            path_pattern: Filter by path pattern (SQL LIKE)
            valid_only: Only return non-expired cache entries
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of ScanCache objects
        """
        query = self.db.query(ScanCache)
        
        if endpoint_id:
            query = query.filter(ScanCache.endpoint_id == endpoint_id)
        
        if path_pattern:
            query = query.filter(ScanCache.path.like(f'%{path_pattern}%'))
        
        if valid_only:
            query = query.filter(ScanCache.expires_at > datetime.utcnow())
        
        query = query.order_by(desc(ScanCache.created_at))
        result = await query.offset(skip).limit(limit).all()
        return result

    async def get_by_id(self, cache_id: UUID) -> Optional[ScanCache]:
        """
        Get cache entry by ID.
        
        Args:
            cache_id: Cache UUID
            
        Returns:
            ScanCache object or None if not found
        """
        result = await self.db.query(ScanCache).filter(ScanCache.id == cache_id).first()
        return result

    async def get_by_key(
        self, 
        endpoint_id: UUID, 
        path: str, 
        scan_options: Optional[Dict[str, Any]] = None
    ) -> Optional[ScanCache]:
        """
        Get cache entry by endpoint, path, and scan options.
        
        Args:
            endpoint_id: Endpoint UUID
            path: Directory path
            scan_options: Optional scan options for cache key
            
        Returns:
            Valid ScanCache object or None if not found/expired
        """
        cache_key = self._generate_cache_key(endpoint_id, path, scan_options)
        
        result = await self.db.query(ScanCache).filter(
            and_(
                ScanCache.cache_key == cache_key,
                ScanCache.expires_at > datetime.utcnow()
            )
        ).first()
        
        return result

    async def create(self, cache_data: dict) -> ScanCache:
        """
        Create new cache entry.
        
        Args:
            cache_data: Dictionary with cache data
            
        Returns:
            Created ScanCache object
        """
        # Generate cache key if not provided
        if 'cache_key' not in cache_data:
            cache_data['cache_key'] = self._generate_cache_key(
                cache_data['endpoint_id'],
                cache_data['path'],
                cache_data.get('scan_options')
            )
        
        # Serialize scan_data if it's a dict
        if 'scan_data' in cache_data and isinstance(cache_data['scan_data'], dict):
            cache_data['scan_data'] = json.dumps(cache_data['scan_data'])
        
        cache_entry = ScanCache(**cache_data)
        self.db.add(cache_entry)
        await self.db.flush()  # Get ID without committing
        await self.db.refresh(cache_entry)
        return cache_entry

    async def update(self, cache_id: UUID, update_data: dict) -> Optional[ScanCache]:
        """
        Update cache entry.
        
        Args:
            cache_id: Cache UUID
            update_data: Dictionary with fields to update
            
        Returns:
            Updated ScanCache object or None if not found
        """
        cache_entry = await self.get_by_id(cache_id)
        if not cache_entry:
            return None
        
        # Serialize scan_data if it's a dict
        if 'scan_data' in update_data and isinstance(update_data['scan_data'], dict):
            update_data['scan_data'] = json.dumps(update_data['scan_data'])
        
        for field, value in update_data.items():
            if hasattr(cache_entry, field):
                setattr(cache_entry, field, value)
        
        await self.db.flush()
        await self.db.refresh(cache_entry)
        return cache_entry

    async def delete(self, cache_id: UUID) -> bool:
        """
        Delete cache entry.
        
        Args:
            cache_id: Cache UUID
            
        Returns:
            True if deleted, False if not found
        """
        cache_entry = await self.get_by_id(cache_id)
        if not cache_entry:
            return False
        
        await self.db.delete(cache_entry)
        return True

    async def cache_directory_scan(
        self,
        endpoint_id: UUID,
        path: str,
        scan_data: Dict[str, Any],
        ttl_hours: int = 1,
        scan_options: Optional[Dict[str, Any]] = None
    ) -> ScanCache:
        """
        Cache directory scan results.
        
        Args:
            endpoint_id: Endpoint UUID
            path: Directory path
            scan_data: Scan results to cache
            ttl_hours: Time to live in hours
            scan_options: Optional scan options
            
        Returns:
            Created ScanCache object
        """
        expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
        
        cache_data = {
            'endpoint_id': endpoint_id,
            'path': path,
            'scan_data': scan_data,
            'expires_at': expires_at,
            'scan_options': json.dumps(scan_options) if scan_options else None,
            'file_count': len(scan_data.get('files', [])),
            'directory_count': len(scan_data.get('directories', [])),
            'total_size': sum(f.get('size', 0) for f in scan_data.get('files', []))
        }
        
        return await self.create(cache_data)

    async def get_cached_scan(
        self,
        endpoint_id: UUID,
        path: str,
        scan_options: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached directory scan results.
        
        Args:
            endpoint_id: Endpoint UUID
            path: Directory path
            scan_options: Optional scan options
            
        Returns:
            Cached scan data or None if not found/expired
        """
        cache_entry = await self.get_by_key(endpoint_id, path, scan_options)
        
        if not cache_entry:
            return None
        
        try:
            # Deserialize scan_data
            if isinstance(cache_entry.scan_data, str):
                scan_data = json.loads(cache_entry.scan_data)
            else:
                scan_data = cache_entry.scan_data
            
            return scan_data
            
        except (json.JSONDecodeError, TypeError) as e:
            # Invalid cache data, delete entry
            await self.delete(cache_entry.id)
            return None

    async def invalidate_cache(
        self,
        endpoint_id: Optional[UUID] = None,
        path_pattern: Optional[str] = None
    ) -> int:
        """
        Invalidate cache entries.
        
        Args:
            endpoint_id: Optional endpoint ID to filter by
            path_pattern: Optional path pattern to filter by
            
        Returns:
            Number of invalidated cache entries
        """
        query = self.db.query(ScanCache)
        
        if endpoint_id:
            query = query.filter(ScanCache.endpoint_id == endpoint_id)
        
        if path_pattern:
            query = query.filter(ScanCache.path.like(f'%{path_pattern}%'))
        
        # Set expiry to past time to invalidate
        result = await query.update(
            {'expires_at': datetime.utcnow() - timedelta(seconds=1)},
            synchronize_session=False
        )
        
        return result

    async def cleanup_expired_cache(self) -> int:
        """
        Clean up expired cache entries.
        
        Returns:
            Number of deleted cache entries
        """
        result = await self.db.query(ScanCache).filter(
            ScanCache.expires_at <= datetime.utcnow()
        ).delete(synchronize_session=False)
        
        return result

    async def get_cache_statistics(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        # Total cache entries
        total_entries = await self.db.query(func.count(ScanCache.id)).scalar()
        
        # Valid cache entries
        valid_entries = await self.db.query(func.count(ScanCache.id)).filter(
            ScanCache.expires_at > datetime.utcnow()
        ).scalar()
        
        # Expired cache entries
        expired_entries = total_entries - valid_entries
        
        # Cache by endpoint
        endpoint_stats = await self.db.query(
            ScanCache.endpoint_id,
            func.count(ScanCache.id).label('count'),
            func.sum(ScanCache.total_size).label('total_size')
        ).filter(
            ScanCache.expires_at > datetime.utcnow()
        ).group_by(ScanCache.endpoint_id).all()
        
        # Average cache age
        avg_age_query = await self.db.query(
            func.avg(
                func.extract('epoch', datetime.utcnow() - ScanCache.created_at)
            ).label('avg_age_seconds')
        ).filter(
            ScanCache.expires_at > datetime.utcnow()
        ).first()
        
        avg_age_hours = (avg_age_query.avg_age_seconds / 3600) if avg_age_query.avg_age_seconds else 0
        
        stats = {
            'total_cache_entries': total_entries or 0,
            'valid_cache_entries': valid_entries or 0,
            'expired_cache_entries': expired_entries or 0,
            'cache_hit_potential': round((valid_entries / total_entries * 100), 2) if total_entries > 0 else 0,
            'average_cache_age_hours': round(avg_age_hours, 2),
            'cache_by_endpoint': [
                {
                    'endpoint_id': str(endpoint_id),
                    'cache_entries': count,
                    'total_cached_size_bytes': total_size or 0
                }
                for endpoint_id, count, total_size in endpoint_stats
            ]
        }
        
        return stats

    async def get_cache_performance_metrics(
        self, 
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get cache performance metrics.
        
        Args:
            hours: Hours to look back
            
        Returns:
            Dictionary with performance metrics
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        # Cache entries created in time period
        new_entries = await self.db.query(func.count(ScanCache.id)).filter(
            ScanCache.created_at >= cutoff_time
        ).scalar()
        
        # Cache entries that would have been hits
        potential_hits = await self.db.query(func.count(ScanCache.id)).filter(
            and_(
                ScanCache.created_at >= cutoff_time,
                ScanCache.expires_at > datetime.utcnow()
            )
        ).scalar()
        
        # Average file count per cache entry
        avg_files = await self.db.query(
            func.avg(ScanCache.file_count).label('avg_files')
        ).filter(
            ScanCache.created_at >= cutoff_time
        ).first()
        
        metrics = {
            'time_period_hours': hours,
            'new_cache_entries': new_entries or 0,
            'potential_cache_hits': potential_hits or 0,
            'cache_efficiency_percent': round((potential_hits / new_entries * 100), 2) if new_entries > 0 else 0,
            'average_files_per_cache': round(avg_files.avg_files, 2) if avg_files.avg_files else 0
        }
        
        return metrics

    def _generate_cache_key(
        self, 
        endpoint_id: UUID, 
        path: str, 
        scan_options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate cache key for endpoint, path, and options.
        
        Args:
            endpoint_id: Endpoint UUID
            path: Directory path
            scan_options: Optional scan options
            
        Returns:
            Cache key string
        """
        import hashlib
        
        # Normalize path
        normalized_path = path.strip('/').lower()
        
        # Create key components
        key_parts = [str(endpoint_id), normalized_path]
        
        if scan_options:
            # Sort options for consistent key generation
            sorted_options = json.dumps(scan_options, sort_keys=True)
            key_parts.append(sorted_options)
        
        # Generate hash
        key_string = '|'.join(key_parts)
        cache_key = hashlib.md5(key_string.encode()).hexdigest()
        
        return cache_key

    async def refresh_cache_entry(
        self,
        cache_id: UUID,
        new_scan_data: Dict[str, Any],
        ttl_hours: int = 1
    ) -> Optional[ScanCache]:
        """
        Refresh existing cache entry with new data.
        
        Args:
            cache_id: Cache UUID
            new_scan_data: New scan data
            ttl_hours: New TTL in hours
            
        Returns:
            Updated ScanCache object or None if not found
        """
        new_expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
        
        update_data = {
            'scan_data': new_scan_data,
            'expires_at': new_expires_at,
            'file_count': len(new_scan_data.get('files', [])),
            'directory_count': len(new_scan_data.get('directories', [])),
            'total_size': sum(f.get('size', 0) for f in new_scan_data.get('files', []))
        }
        
        return await self.update(cache_id, update_data)
