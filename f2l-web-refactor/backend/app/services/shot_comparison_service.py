"""
Shot Comparison Service - Compare shot versions between FTP and Local.

This service provides:
- Targeted shot comparison (no brute-force scanning)
- Version comparison for animation (v001, v002, etc.)
- File-level comparison for lighting (by filename version)
- Efficient path-based comparison
"""
import logging
import re
from typing import List, Dict, Optional, Callable
from uuid import UUID
from datetime import datetime, timezone
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.models import Endpoint, EndpointType
from app.core.ftp_manager import FTPManager, FTPConfig
from app.core.local_manager import LocalManager, LocalConfig
from app.utils.shot_path_utils import ShotPathUtils, ShotPaths

logger = logging.getLogger(__name__)


@dataclass
class ShotComparison:
    """Result of comparing a shot between FTP and Local."""
    episode: str
    sequence: str
    shot: str
    department: str  # 'anim' or 'lighting'
    
    # Paths
    ftp_path: str
    local_path: str
    
    # Version info
    ftp_version: Optional[str]
    local_version: Optional[str]
    
    # Comparison result
    needs_update: bool
    status: str  # 'up_to_date', 'update_available', 'new_download', 'ftp_missing', 'error'
    
    # Files to download
    files_to_download: List[Dict[str, any]]
    file_count: int
    total_size: int  # bytes
    
    # Error info
    error_message: Optional[str] = None


class ShotComparisonService:
    """
    Service for comparing shots between FTP and Local.
    
    Features:
    - Targeted comparison (specific shots only)
    - Version-based comparison for animation
    - File-based comparison for lighting
    - No recursive brute-force scanning
    """
    
    def __init__(self, db: AsyncSession):
        """Initialize service with database session."""
        self.db = db
    
    async def compare_shot(
        self,
        endpoint_id: UUID,
        episode: str,
        sequence: str,
        shot: str,
        department: str
    ) -> ShotComparison:
        """
        Compare a specific shot/department between FTP and Local.
        
        Args:
            endpoint_id: Endpoint UUID
            episode: Episode name (e.g., "Ep01")
            sequence: Sequence name (e.g., "sq0010")
            shot: Shot name (e.g., "SH0010")
            department: "anim" or "lighting"
        
        Returns:
            ShotComparison object with comparison results
        """
        logger.info(f"Comparing {episode}/{sequence}/{shot}/{department} for endpoint {endpoint_id}")
        
        # Get endpoint
        result = await self.db.execute(
            select(Endpoint).where(Endpoint.id == endpoint_id)
        )
        endpoint = result.scalar_one_or_none()
        
        if not endpoint:
            raise ValueError(f"Endpoint {endpoint_id} not found")
        
        # Build paths
        paths = ShotPathUtils.build_shot_paths(
            ftp_base=endpoint.remote_path.rstrip('/'),
            local_base=endpoint.local_path.rstrip('/'),
            episode=episode,
            sequence=sequence,
            shot=shot,
            department=department
        )
        
        try:
            # Get FTP content
            ftp_content = await self._get_ftp_content(endpoint, paths, department)
            
            # Get Local content
            local_content = await self._get_local_content(endpoint, paths, department)
            
            # Compare
            comparison_result = self._compare_content(ftp_content, local_content, department)
            
            return ShotComparison(
                episode=episode,
                sequence=sequence,
                shot=shot,
                department=department,
                ftp_path=paths.ftp_path,
                local_path=paths.local_path,
                ftp_version=comparison_result["ftp_version"],
                local_version=comparison_result["local_version"],
                needs_update=comparison_result["needs_update"],
                status=comparison_result["status"],
                files_to_download=comparison_result["files_to_download"],
                file_count=comparison_result["file_count"],
                total_size=comparison_result["total_size"]
            )
            
        except Exception as e:
            logger.error(f"Error comparing shot {episode}/{sequence}/{shot}/{department}: {e}")
            return ShotComparison(
                episode=episode,
                sequence=sequence,
                shot=shot,
                department=department,
                ftp_path=paths.ftp_path,
                local_path=paths.local_path,
                ftp_version=None,
                local_version=None,
                needs_update=False,
                status="error",
                files_to_download=[],
                file_count=0,
                total_size=0,
                error_message=str(e)
            )

    async def _get_ftp_content(
        self,
        endpoint: Endpoint,
        paths: ShotPaths,
        department: str
    ) -> Dict[str, any]:
        """Get content from FTP for specific path."""
        import asyncio

        # Create FTP manager
        ftp_config = FTPConfig(
            host=endpoint.host,
            username=endpoint.username,
            password=endpoint.password_encrypted,  # TODO: Decrypt password
            port=endpoint.port or 21
        )
        ftp_manager = FTPManager(ftp_config)

        try:
            if not ftp_manager.connect():
                return {"exists": False, "error": "Failed to connect to FTP"}

            loop = asyncio.get_event_loop()

            if department == "anim":
                # List version directories: v001, v002, v003, etc.
                try:
                    files = await loop.run_in_executor(None, ftp_manager.list_files, paths.ftp_path, False)
                    versions = [
                        f["name"] for f in files
                        if not f.get("is_file", True) and re.match(r'^v\d+$', f["name"])
                    ]

                    if not versions:
                        return {"exists": False, "error": "No version directories found"}

                    latest_version = ShotPathUtils.get_latest_version(versions)
                    version_path = f"{paths.ftp_path}/{latest_version}"

                    # List files in latest version
                    version_files = await loop.run_in_executor(None, ftp_manager.list_files, version_path, True)

                    return {
                        "exists": True,
                        "version": latest_version,
                        "files": version_files,
                        "file_count": len(version_files),
                        "total_size": sum(f.get("size", 0) for f in version_files)
                    }

                except Exception as e:
                    return {"exists": False, "error": str(e)}

            elif department == "lighting":
                # List all files in version/ directory
                try:
                    files = await loop.run_in_executor(None, ftp_manager.list_files, paths.ftp_path, False)

                    # Filter only files (not directories)
                    file_list = [f for f in files if f.get("is_file", True)]

                    # Extract versions from filenames
                    file_versions = {}
                    for f in file_list:
                        version = ShotPathUtils.extract_version_from_filename(f["name"])
                        if version:
                            file_versions[f["name"]] = version

                    return {
                        "exists": True,
                        "version": None,  # No version directory for lighting
                        "files": file_list,
                        "file_versions": file_versions,
                        "file_count": len(file_list),
                        "total_size": sum(f.get("size", 0) for f in file_list)
                    }

                except Exception as e:
                    return {"exists": False, "error": str(e)}

        finally:
            ftp_manager.close()

    async def _get_local_content(
        self,
        endpoint: Endpoint,
        paths: ShotPaths,
        department: str
    ) -> Dict[str, any]:
        """Get content from Local for specific path."""
        import os

        # Create local manager
        local_config = LocalConfig(base_path=endpoint.local_path)
        local_manager = LocalManager(local_config)

        try:
            if not local_manager.connect():
                return {"exists": False, "error": "Failed to access local path"}

            if department == "anim":
                # List version directories
                try:
                    if not os.path.exists(paths.local_path):
                        return {"exists": False, "error": "Path does not exist"}

                    entries = os.listdir(paths.local_path)
                    versions = [
                        entry for entry in entries
                        if os.path.isdir(os.path.join(paths.local_path, entry)) and re.match(r'^v\d+$', entry)
                    ]

                    if not versions:
                        return {"exists": False, "error": "No version directories found"}

                    latest_version = ShotPathUtils.get_latest_version(versions)
                    version_path = os.path.join(paths.local_path, latest_version)

                    # List files in latest version
                    version_files = []
                    for root, dirs, files in os.walk(version_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            rel_path = os.path.relpath(file_path, version_path)
                            stat = os.stat(file_path)
                            version_files.append({
                                "name": rel_path,
                                "size": stat.st_size,
                                "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                                "is_file": True
                            })

                    return {
                        "exists": True,
                        "version": latest_version,
                        "files": version_files,
                        "file_count": len(version_files),
                        "total_size": sum(f["size"] for f in version_files)
                    }

                except Exception as e:
                    return {"exists": False, "error": str(e)}

            elif department == "lighting":
                # List all files in version/ directory
                try:
                    if not os.path.exists(paths.local_path):
                        return {"exists": False, "error": "Path does not exist"}

                    file_list = []
                    for entry in os.listdir(paths.local_path):
                        file_path = os.path.join(paths.local_path, entry)
                        if os.path.isfile(file_path):
                            stat = os.stat(file_path)
                            file_list.append({
                                "name": entry,
                                "size": stat.st_size,
                                "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                                "is_file": True
                            })

                    # Extract versions from filenames
                    file_versions = {}
                    for f in file_list:
                        version = ShotPathUtils.extract_version_from_filename(f["name"])
                        if version:
                            file_versions[f["name"]] = version

                    return {
                        "exists": True,
                        "version": None,
                        "files": file_list,
                        "file_versions": file_versions,
                        "file_count": len(file_list),
                        "total_size": sum(f["size"] for f in file_list)
                    }

                except Exception as e:
                    return {"exists": False, "error": str(e)}

        finally:
            local_manager.close()

    def _compare_content(
        self,
        ftp_content: Dict[str, any],
        local_content: Dict[str, any],
        department: str
    ) -> Dict[str, any]:
        """Compare FTP vs Local content and determine what needs to be downloaded."""

        # FTP doesn't exist
        if not ftp_content.get("exists"):
            return {
                "ftp_version": None,
                "local_version": local_content.get("version"),
                "needs_update": False,
                "files_to_download": [],
                "file_count": 0,
                "total_size": 0,
                "status": "ftp_missing"
            }

        # Local doesn't exist - need to download everything
        if not local_content.get("exists"):
            return {
                "ftp_version": ftp_content.get("version"),
                "local_version": None,
                "needs_update": True,
                "files_to_download": ftp_content.get("files", []),
                "file_count": ftp_content.get("file_count", 0),
                "total_size": ftp_content.get("total_size", 0),
                "status": "new_download"
            }

        # Both exist - compare based on department
        if department == "anim":
            return self._compare_anim_versions(ftp_content, local_content)
        elif department == "lighting":
            return self._compare_lighting_files(ftp_content, local_content)
        else:
            return {
                "ftp_version": None,
                "local_version": None,
                "needs_update": False,
                "files_to_download": [],
                "file_count": 0,
                "total_size": 0,
                "status": "error"
            }

    def _compare_anim_versions(
        self,
        ftp_content: Dict[str, any],
        local_content: Dict[str, any]
    ) -> Dict[str, any]:
        """Compare animation versions (v001, v002, etc.)."""
        ftp_ver = ftp_content.get("version")
        local_ver = local_content.get("version")

        # Compare version numbers
        comparison = ShotPathUtils.compare_versions(ftp_ver, local_ver)

        if comparison > 0:
            # FTP version is newer
            return {
                "ftp_version": ftp_ver,
                "local_version": local_ver,
                "needs_update": True,
                "files_to_download": ftp_content.get("files", []),
                "file_count": ftp_content.get("file_count", 0),
                "total_size": ftp_content.get("total_size", 0),
                "status": "update_available"
            }
        else:
            # Local is up-to-date or newer
            return {
                "ftp_version": ftp_ver,
                "local_version": local_ver,
                "needs_update": False,
                "files_to_download": [],
                "file_count": 0,
                "total_size": 0,
                "status": "up_to_date"
            }

    def _compare_lighting_files(
        self,
        ftp_content: Dict[str, any],
        local_content: Dict[str, any]
    ) -> Dict[str, any]:
        """Compare lighting files by version in filename."""
        ftp_files = {f["name"]: f for f in ftp_content.get("files", [])}
        local_files = {f["name"]: f for f in local_content.get("files", [])}

        ftp_versions = ftp_content.get("file_versions", {})
        local_versions = local_content.get("file_versions", {})

        files_to_download = []

        for filename, ftp_file in ftp_files.items():
            # File doesn't exist locally - download it
            if filename not in local_files:
                files_to_download.append(ftp_file)
                continue

            # File exists - compare versions
            ftp_ver = ftp_versions.get(filename)
            local_ver = local_versions.get(filename)

            if ftp_ver and local_ver:
                # Both have versions - compare
                if ftp_ver > local_ver:
                    files_to_download.append(ftp_file)
            else:
                # No version info - compare modification time
                local_file = local_files[filename]
                ftp_modified = ftp_file.get("modified")
                local_modified = local_file.get("modified")

                if ftp_modified and local_modified and ftp_modified > local_modified:
                    files_to_download.append(ftp_file)

        if files_to_download:
            return {
                "ftp_version": None,
                "local_version": None,
                "needs_update": True,
                "files_to_download": files_to_download,
                "file_count": len(files_to_download),
                "total_size": sum(f.get("size", 0) for f in files_to_download),
                "status": "update_available"
            }
        else:
            return {
                "ftp_version": None,
                "local_version": None,
                "needs_update": False,
                "files_to_download": [],
                "file_count": 0,
                "total_size": 0,
                "status": "up_to_date"
            }

    async def compare_multiple_shots(
        self,
        endpoint_id: UUID,
        shots: List[Dict[str, str]],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[ShotComparison]:
        """
        Compare multiple shots efficiently.

        Args:
            endpoint_id: Endpoint UUID
            shots: List of dicts with 'episode', 'sequence', 'shot' keys
            progress_callback: Optional callback(completed, total)

        Returns:
            List of ShotComparison objects
        """
        results = []
        total = len(shots) * 2  # 2 departments per shot
        completed = 0

        for shot in shots:
            # Compare anim
            anim_comparison = await self.compare_shot(
                endpoint_id,
                shot["episode"],
                shot["sequence"],
                shot["shot"],
                "anim"
            )
            results.append(anim_comparison)
            completed += 1

            if progress_callback:
                progress_callback(completed, total)

            # Compare lighting
            lighting_comparison = await self.compare_shot(
                endpoint_id,
                shot["episode"],
                shot["sequence"],
                shot["shot"],
                "lighting"
            )
            results.append(lighting_comparison)
            completed += 1

            if progress_callback:
                progress_callback(completed, total)

        return results



