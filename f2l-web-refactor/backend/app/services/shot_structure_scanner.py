"""
Shot Structure Scanner Service - Scan and cache Episodes/Sequences/Shots directory structure.

This service provides:
- Lightweight directory structure scanning (Episodes → Sequences → Shots)
- Smart caching with 24-hour TTL
- Incremental updates for new episodes/sequences
- No file-level caching (only directory names)
"""
import logging
import re
from typing import List, Dict, Optional, Set
from uuid import UUID
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

from app.database.models import (
    Endpoint, EndpointType,
    ShotStructureCache, ShotCacheMetadata
)
from app.core.ftp_manager import FTPManager, FTPConfig
from app.core.local_manager import LocalManager, LocalConfig
from app.utils.shot_path_utils import ShotPathUtils

logger = logging.getLogger(__name__)


class ShotStructureScanner:
    """
    Service for scanning and caching shot directory structure.
    
    Features:
    - Lightweight caching (directory names only, no files)
    - 24-hour cache TTL
    - Incremental updates
    - Efficient querying
    """
    
    CACHE_TTL_HOURS = 24
    
    def __init__(self, db: AsyncSession):
        """Initialize scanner with database session."""
        self.db = db
    
    async def get_cache_metadata(self, endpoint_id: UUID) -> Optional[ShotCacheMetadata]:
        """Get cache metadata for an endpoint."""
        result = await self.db.execute(
            select(ShotCacheMetadata).where(ShotCacheMetadata.endpoint_id == endpoint_id)
        )
        return result.scalar_one_or_none()
    
    async def is_cache_valid(self, endpoint_id: UUID) -> bool:
        """Check if cache is still valid (not expired)."""
        metadata = await self.get_cache_metadata(endpoint_id)
        
        if not metadata or not metadata.last_full_scan:
            return False
        
        # Check if next_full_scan is in the future
        if metadata.next_full_scan and metadata.next_full_scan > datetime.now(timezone.utc):
            return True
        
        return False
    
    async def get_cached_episodes(self, endpoint_id: UUID) -> List[str]:
        """Get cached episode list for an endpoint."""
        result = await self.db.execute(
            select(ShotStructureCache.episode)
            .where(ShotStructureCache.endpoint_id == endpoint_id)
            .distinct()
            .order_by(ShotStructureCache.episode)
        )
        return [row[0] for row in result.all()]
    
    async def get_cached_sequences(
        self, 
        endpoint_id: UUID, 
        episodes: Optional[List[str]] = None
    ) -> List[Dict[str, str]]:
        """
        Get cached sequences for an endpoint, optionally filtered by episodes.
        
        Returns:
            List of dicts with 'episode' and 'sequence' keys
        """
        query = select(
            ShotStructureCache.episode,
            ShotStructureCache.sequence
        ).where(
            ShotStructureCache.endpoint_id == endpoint_id
        ).distinct()
        
        if episodes:
            query = query.where(ShotStructureCache.episode.in_(episodes))
        
        query = query.order_by(
            ShotStructureCache.episode,
            ShotStructureCache.sequence
        )
        
        result = await self.db.execute(query)
        return [
            {"episode": row[0], "sequence": row[1]}
            for row in result.all()
        ]
    
    async def get_cached_shots(
        self,
        endpoint_id: UUID,
        episodes: Optional[List[str]] = None,
        sequences: Optional[List[str]] = None
    ) -> List[Dict[str, str]]:
        """
        Get cached shots for an endpoint, optionally filtered by episodes/sequences.
        
        Returns:
            List of dicts with 'episode', 'sequence', 'shot', 'has_anim', 'has_lighting' keys
        """
        query = select(ShotStructureCache).where(
            ShotStructureCache.endpoint_id == endpoint_id
        )
        
        if episodes:
            query = query.where(ShotStructureCache.episode.in_(episodes))
        
        if sequences:
            query = query.where(ShotStructureCache.sequence.in_(sequences))
        
        query = query.order_by(
            ShotStructureCache.episode,
            ShotStructureCache.sequence,
            ShotStructureCache.shot
        )
        
        result = await self.db.execute(query)
        shots = result.scalars().all()
        
        return [
            {
                "episode": shot.episode,
                "sequence": shot.sequence,
                "shot": shot.shot,
                "has_anim": shot.has_anim,
                "has_lighting": shot.has_lighting,
                "exists_on_ftp": shot.exists_on_ftp,
                "exists_locally": shot.exists_locally
            }
            for shot in shots
        ]

    async def scan_endpoint_structure(
        self,
        endpoint_id: UUID,
        force_refresh: bool = False
    ) -> Dict[str, any]:
        """
        Scan endpoint directory structure and cache Episodes/Sequences/Shots.

        Args:
            endpoint_id: Endpoint UUID to scan
            force_refresh: Force rescan even if cache is valid

        Returns:
            Dict with scan results and statistics
        """
        start_time = datetime.now(timezone.utc)

        # Check if cache is valid
        if not force_refresh and await self.is_cache_valid(endpoint_id):
            logger.info(f"Cache is valid for endpoint {endpoint_id}, skipping scan")
            metadata = await self.get_cache_metadata(endpoint_id)
            return {
                "status": "cached",
                "message": "Using cached data",
                "total_episodes": metadata.total_episodes if metadata else 0,
                "total_sequences": metadata.total_sequences if metadata else 0,
                "total_shots": metadata.total_shots if metadata else 0,
                "last_scan": metadata.last_full_scan if metadata else None
            }

        # Get endpoint
        result = await self.db.execute(
            select(Endpoint).where(Endpoint.id == endpoint_id)
        )
        endpoint = result.scalar_one_or_none()

        if not endpoint:
            raise ValueError(f"Endpoint {endpoint_id} not found")

        logger.info(f"Starting structure scan for endpoint {endpoint.name} ({endpoint_id})")

        # Scan based on endpoint type
        if endpoint.endpoint_type == EndpointType.FTP:
            shots_data = await self._scan_ftp_structure(endpoint)
        elif endpoint.endpoint_type == EndpointType.LOCAL:
            shots_data = await self._scan_local_structure(endpoint)
        else:
            raise ValueError(f"Unsupported endpoint type: {endpoint.endpoint_type}")

        # Clear old cache
        await self.db.execute(
            delete(ShotStructureCache).where(ShotStructureCache.endpoint_id == endpoint_id)
        )

        # Insert new cache entries
        cache_expires_at = datetime.now(timezone.utc) + timedelta(hours=self.CACHE_TTL_HOURS)

        for shot_data in shots_data:
            cache_entry = ShotStructureCache(
                endpoint_id=endpoint_id,
                episode=shot_data["episode"],
                sequence=shot_data["sequence"],
                shot=shot_data["shot"],
                exists_on_ftp=shot_data.get("exists_on_ftp", False),
                exists_locally=shot_data.get("exists_locally", False),
                has_anim=shot_data.get("has_anim", False),
                has_lighting=shot_data.get("has_lighting", False),
                cache_expires_at=cache_expires_at
            )
            self.db.add(cache_entry)

        # Update metadata
        metadata = await self.get_cache_metadata(endpoint_id)
        if not metadata:
            metadata = ShotCacheMetadata(endpoint_id=endpoint_id)
            self.db.add(metadata)

        # Calculate statistics
        episodes = set(s["episode"] for s in shots_data)
        sequences = set((s["episode"], s["sequence"]) for s in shots_data)

        metadata.last_full_scan = start_time
        metadata.next_full_scan = cache_expires_at
        metadata.total_episodes = len(episodes)
        metadata.total_sequences = len(sequences)
        metadata.total_shots = len(shots_data)
        metadata.scan_duration_seconds = int((datetime.now(timezone.utc) - start_time).total_seconds())

        await self.db.commit()

        logger.info(
            f"Scan completed for endpoint {endpoint.name}: "
            f"{metadata.total_episodes} episodes, "
            f"{metadata.total_sequences} sequences, "
            f"{metadata.total_shots} shots "
            f"in {metadata.scan_duration_seconds}s"
        )

        return {
            "status": "scanned",
            "message": "Structure scan completed",
            "total_episodes": metadata.total_episodes,
            "total_sequences": metadata.total_sequences,
            "total_shots": metadata.total_shots,
            "scan_duration_seconds": metadata.scan_duration_seconds
        }

    async def _scan_ftp_structure(self, endpoint: Endpoint) -> List[Dict[str, any]]:
        """
        Scan FTP endpoint for shot structure.

        Returns:
            List of shot data dicts
        """
        logger.info(f"Scanning FTP structure at {endpoint.host}:{endpoint.remote_path}")

        # Create FTP manager
        ftp_config = FTPConfig(
            host=endpoint.host,
            username=endpoint.username,
            password=endpoint.password_encrypted,  # TODO: Decrypt password
            port=endpoint.port or 21
        )
        ftp_manager = FTPManager(ftp_config)

        try:
            # Connect
            if not ftp_manager.connect():
                raise ConnectionError(f"Failed to connect to FTP endpoint {endpoint.name}")

            base_path = endpoint.remote_path.rstrip('/')
            shots_data = []

            # List episodes (Ep01, Ep02, etc.)
            episodes = await self._list_ftp_directories(ftp_manager, base_path, r'^Ep\d+$')
            logger.info(f"Found {len(episodes)} episodes")

            for episode in episodes:
                episode_path = f"{base_path}/{episode}"

                # List sequences (sq0010, sq0020, etc.)
                sequences = await self._list_ftp_directories(ftp_manager, episode_path, r'^sq\d+$')
                logger.debug(f"Found {len(sequences)} sequences in {episode}")

                for sequence in sequences:
                    sequence_path = f"{episode_path}/{sequence}"

                    # List shots (SH0010, SH0020, etc.)
                    shots = await self._list_ftp_directories(ftp_manager, sequence_path, r'^SH\d+$')
                    logger.debug(f"Found {len(shots)} shots in {episode}/{sequence}")

                    for shot in shots:
                        shot_path = f"{sequence_path}/{shot}"

                        # Check for anim and lighting directories
                        has_anim = await self._ftp_path_exists(ftp_manager, f"{shot_path}/anim/publish")
                        has_lighting = await self._ftp_path_exists(ftp_manager, f"{shot_path}/lighting/version")

                        shots_data.append({
                            "episode": episode,
                            "sequence": sequence,
                            "shot": shot,
                            "exists_on_ftp": True,
                            "exists_locally": False,  # Will check local separately
                            "has_anim": has_anim,
                            "has_lighting": has_lighting
                        })

            return shots_data

        finally:
            ftp_manager.close()

    async def _scan_local_structure(self, endpoint: Endpoint) -> List[Dict[str, any]]:
        """
        Scan local endpoint for shot structure.

        Returns:
            List of shot data dicts
        """
        logger.info(f"Scanning local structure at {endpoint.local_path}")

        # Create local manager
        local_config = LocalConfig(base_path=endpoint.local_path)
        local_manager = LocalManager(local_config)

        try:
            # Connect (validate path)
            if not local_manager.connect():
                raise ConnectionError(f"Failed to access local path {endpoint.local_path}")

            base_path = endpoint.local_path.rstrip('/')
            shots_data = []

            # List episodes
            episodes = await self._list_local_directories(local_manager, base_path, r'^Ep\d+$')
            logger.info(f"Found {len(episodes)} episodes")

            for episode in episodes:
                episode_path = f"{base_path}/{episode}"

                # List sequences
                sequences = await self._list_local_directories(local_manager, episode_path, r'^sq\d+$')
                logger.debug(f"Found {len(sequences)} sequences in {episode}")

                for sequence in sequences:
                    sequence_path = f"{episode_path}/{sequence}"

                    # List shots
                    shots = await self._list_local_directories(local_manager, sequence_path, r'^SH\d+$')
                    logger.debug(f"Found {len(shots)} shots in {episode}/{sequence}")

                    for shot in shots:
                        shot_path = f"{sequence_path}/{shot}"

                        # Check for anim and lighting directories
                        has_anim = await self._local_path_exists(local_manager, f"{shot_path}/anim/publish")
                        has_lighting = await self._local_path_exists(local_manager, f"{shot_path}/lighting/version")

                        shots_data.append({
                            "episode": episode,
                            "sequence": sequence,
                            "shot": shot,
                            "exists_on_ftp": False,  # Will check FTP separately
                            "exists_locally": True,
                            "has_anim": has_anim,
                            "has_lighting": has_lighting
                        })

            return shots_data

        finally:
            local_manager.close()

    async def _list_ftp_directories(
        self,
        ftp_manager: FTPManager,
        path: str,
        pattern: str
    ) -> List[str]:
        """List directories in FTP path matching pattern."""
        import asyncio
        loop = asyncio.get_event_loop()

        try:
            files = await loop.run_in_executor(None, ftp_manager.list_files, path, False)
            directories = [
                f["name"] for f in files
                if not f.get("is_file", True) and re.match(pattern, f["name"])
            ]
            return sorted(directories)
        except Exception as e:
            logger.warning(f"Failed to list FTP directories at {path}: {e}")
            return []

    async def _list_local_directories(
        self,
        local_manager: LocalManager,
        path: str,
        pattern: str
    ) -> List[str]:
        """List directories in local path matching pattern."""
        import os

        try:
            if not os.path.exists(path):
                return []

            entries = os.listdir(path)
            directories = [
                entry for entry in entries
                if os.path.isdir(os.path.join(path, entry)) and re.match(pattern, entry)
            ]
            return sorted(directories)
        except Exception as e:
            logger.warning(f"Failed to list local directories at {path}: {e}")
            return []

    async def _ftp_path_exists(self, ftp_manager: FTPManager, path: str) -> bool:
        """Check if path exists on FTP."""
        import asyncio
        loop = asyncio.get_event_loop()

        try:
            await loop.run_in_executor(None, ftp_manager.list_files, path, False)
            return True
        except:
            return False

    async def _local_path_exists(self, local_manager: LocalManager, path: str) -> bool:
        """Check if path exists locally."""
        import os
        return os.path.exists(path) and os.path.isdir(path)



