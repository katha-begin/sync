"""
Shot Path Utilities - Handle path conversion and version comparison for shot-based workflows.

This module provides utilities for:
- Converting between Episode/Sequence/Shot and file paths
- Parsing shot information from paths
- Comparing version numbers
- Extracting versions from filenames
"""
import re
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ShotInfo:
    """Shot information extracted from path or provided by user."""
    episode: str      # e.g., "Ep01"
    sequence: str     # e.g., "sq0010"
    shot: str         # e.g., "SH0010"
    department: str   # "anim" or "lighting"
    version: Optional[str] = None  # e.g., "v001" (for anim)


@dataclass
class ShotPaths:
    """FTP and Local paths for a specific shot/department."""
    ftp_path: str
    local_path: str
    relative_path: str
    department: str


class ShotPathUtils:
    """Utility class for shot path operations."""
    
    # Regex patterns
    EPISODE_PATTERN = r'(Ep\d+)'
    SEQUENCE_PATTERN = r'(sq\d+)'
    SHOT_PATTERN = r'(SH\d+)'
    VERSION_PATTERN = r'v(\d+)'
    FILENAME_VERSION_PATTERN = r'_v(\d+)'
    
    @staticmethod
    def build_shot_paths(
        ftp_base: str,
        local_base: str,
        episode: str,
        sequence: str,
        shot: str,
        department: str
    ) -> ShotPaths:
        """
        Build FTP and Local paths for a specific shot/department.
        
        Args:
            ftp_base: FTP base path (e.g., "/os10148/V/SWA/all/scene")
            local_base: Local base path (e.g., "/mnt/igloo_swa_v/SWA/all/scene")
            episode: Episode name (e.g., "Ep01")
            sequence: Sequence name (e.g., "sq0010")
            shot: Shot name (e.g., "SH0010")
            department: "anim" or "lighting"
        
        Returns:
            ShotPaths object with ftp_path, local_path, and relative_path
        
        Example:
            >>> build_shot_paths(
            ...     "/os10148/V/SWA/all/scene",
            ...     "/mnt/igloo_swa_v/SWA/all/scene",
            ...     "Ep01", "sq0010", "SH0010", "anim"
            ... )
            ShotPaths(
                ftp_path="/os10148/V/SWA/all/scene/Ep01/sq0010/SH0010/anim/publish",
                local_path="/mnt/igloo_swa_v/SWA/all/scene/Ep01/sq0010/SH0010/anim/publish",
                relative_path="Ep01/sq0010/SH0010/anim/publish",
                department="anim"
            )
        """
        # Normalize base paths (remove trailing slashes)
        ftp_base = ftp_base.rstrip('/')
        local_base = local_base.rstrip('/')
        
        # Build relative path based on department
        if department == "anim":
            relative_path = f"{episode}/{sequence}/{shot}/anim/publish"
        elif department == "lighting":
            relative_path = f"{episode}/{sequence}/{shot}/lighting/version"
        else:
            raise ValueError(f"Unknown department: {department}. Must be 'anim' or 'lighting'")
        
        # Build full paths
        ftp_path = f"{ftp_base}/{relative_path}"
        local_path = f"{local_base}/{relative_path}"
        
        logger.debug(f"Built paths for {episode}/{sequence}/{shot}/{department}")
        logger.debug(f"  FTP: {ftp_path}")
        logger.debug(f"  Local: {local_path}")
        
        return ShotPaths(
            ftp_path=ftp_path,
            local_path=local_path,
            relative_path=relative_path,
            department=department
        )
    
    @staticmethod
    def parse_shot_from_path(path: str) -> Optional[ShotInfo]:
        """
        Parse episode/sequence/shot/department from a path.
        
        Args:
            path: Full path (e.g., "/os10148/V/SWA/all/scene/Ep01/sq0010/SH0010/anim/publish/v001")
        
        Returns:
            ShotInfo object or None if path doesn't match pattern
        
        Example:
            >>> parse_shot_from_path("/os10148/V/SWA/all/scene/Ep01/sq0010/SH0010/anim/publish/v001")
            ShotInfo(episode="Ep01", sequence="sq0010", shot="SH0010", department="anim", version="v001")
        """
        # Pattern: .../EpXX/sqXXXX/SHXXXX/(anim|lighting)/...
        pattern = rf'/{ShotPathUtils.EPISODE_PATTERN}/{ShotPathUtils.SEQUENCE_PATTERN}/{ShotPathUtils.SHOT_PATTERN}/(anim|lighting)/'
        match = re.search(pattern, path)
        
        if not match:
            logger.debug(f"Path does not match shot pattern: {path}")
            return None
        
        episode = match.group(1)
        sequence = match.group(2)
        shot = match.group(3)
        department = match.group(4)
        
        # Try to extract version if present
        version = None
        version_match = re.search(rf'/{ShotPathUtils.VERSION_PATTERN}(?:/|$)', path)
        if version_match:
            version = f"v{version_match.group(1)}"
        
        return ShotInfo(
            episode=episode,
            sequence=sequence,
            shot=shot,
            department=department,
            version=version
        )

    @staticmethod
    def compare_versions(version1: str, version2: str) -> int:
        """
        Compare two version strings.

        Args:
            version1: First version (e.g., "v001", "v002")
            version2: Second version (e.g., "v001", "v003")

        Returns:
            1 if version1 > version2
            0 if version1 == version2
            -1 if version1 < version2

        Example:
            >>> compare_versions("v003", "v001")
            1
            >>> compare_versions("v001", "v003")
            -1
            >>> compare_versions("v002", "v002")
            0
        """
        if not version1 or not version2:
            return 0

        # Extract numeric part
        match1 = re.search(r'v(\d+)', version1)
        match2 = re.search(r'v(\d+)', version2)

        if not match1 or not match2:
            logger.warning(f"Invalid version format: {version1} or {version2}")
            return 0

        num1 = int(match1.group(1))
        num2 = int(match2.group(1))

        if num1 > num2:
            return 1
        elif num1 < num2:
            return -1
        else:
            return 0

    @staticmethod
    def get_latest_version(versions: list[str]) -> Optional[str]:
        """
        Get the latest version from a list of version strings.

        Args:
            versions: List of version strings (e.g., ["v001", "v002", "v003"])

        Returns:
            Latest version string or None if list is empty

        Example:
            >>> get_latest_version(["v001", "v003", "v002"])
            "v003"
        """
        if not versions:
            return None

        # Extract numeric values and find max
        version_nums = []
        for v in versions:
            match = re.search(r'v(\d+)', v)
            if match:
                version_nums.append((int(match.group(1)), v))

        if not version_nums:
            return None

        # Sort by numeric value and return the version string
        version_nums.sort(key=lambda x: x[0], reverse=True)
        return version_nums[0][1]

    @staticmethod
    def extract_version_from_filename(filename: str) -> Optional[int]:
        """
        Extract version number from filename.

        Args:
            filename: Filename (e.g., "Ep01_sq0010_SH0010_lighting_keyLight_v001.ma")

        Returns:
            Version number as integer or None if not found

        Example:
            >>> extract_version_from_filename("Ep01_sq0010_SH0010_lighting_keyLight_v001.ma")
            1
            >>> extract_version_from_filename("Ep01_sq0010_SH0010_lighting_keyLight_v023.ma")
            23
        """
        match = re.search(ShotPathUtils.FILENAME_VERSION_PATTERN, filename)
        if match:
            return int(match.group(1))
        return None

    @staticmethod
    def validate_shot_name(episode: str, sequence: str, shot: str) -> Tuple[bool, Optional[str]]:
        """
        Validate shot naming convention.

        Args:
            episode: Episode name (should match EpXX pattern)
            sequence: Sequence name (should match sqXXXX pattern)
            shot: Shot name (should match SHXXXX pattern)

        Returns:
            Tuple of (is_valid, error_message)

        Example:
            >>> validate_shot_name("Ep01", "sq0010", "SH0010")
            (True, None)
            >>> validate_shot_name("Episode01", "sq0010", "SH0010")
            (False, "Episode must match pattern EpXX (e.g., Ep01)")
        """
        # Validate episode
        if not re.match(r'^Ep\d+$', episode):
            return False, "Episode must match pattern EpXX (e.g., Ep01, Ep02)"

        # Validate sequence
        if not re.match(r'^sq\d+$', sequence):
            return False, "Sequence must match pattern sqXXXX (e.g., sq0010, sq0020)"

        # Validate shot
        if not re.match(r'^SH\d+$', shot):
            return False, "Shot must match pattern SHXXXX (e.g., SH0010, SH0020)"

        return True, None

    @staticmethod
    def normalize_path(path: str) -> str:
        """
        Normalize path by removing trailing slashes and extra slashes.

        Args:
            path: Path to normalize

        Returns:
            Normalized path

        Example:
            >>> normalize_path("/path/to//dir/")
            "/path/to/dir"
        """
        # Replace multiple slashes with single slash
        path = re.sub(r'/+', '/', path)
        # Remove trailing slash
        path = path.rstrip('/')
        return path

