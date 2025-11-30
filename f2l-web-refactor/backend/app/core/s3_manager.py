"""
S3Manager - Complete boto3-based S3 operations manager.
Handles uploads, downloads, listing, and sync operations for Amazon S3 and S3-compatible services.
"""
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime, timezone
import os
import fnmatch
import logging
from pathlib import Path

import boto3
from boto3.s3.transfer import TransferConfig
from botocore.client import Config
from botocore.exceptions import ClientError, BotoCoreError
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


@dataclass
class S3Config:
    """S3 configuration dataclass."""
    bucket: str
    region: str = "us-east-1"
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    endpoint_url: Optional[str] = None  # For S3-compatible services (MinIO, etc.)
    use_ssl: bool = True
    signature_version: str = "s3v4"
    max_pool_connections: int = 50


@dataclass
class S3Object:
    """S3 object metadata."""
    key: str
    size: int
    last_modified: datetime
    etag: str
    storage_class: str = "STANDARD"
    is_directory: bool = False


class S3Manager:
    """
    Production-ready S3 Manager using boto3.

    Features:
    - Multipart uploads/downloads with progress tracking
    - Pagination for large buckets
    - Connection pooling
    - Retry logic with exponential backoff
    - Support for S3-compatible services
    - Async-friendly with ThreadPoolExecutor
    """

    def __init__(self, config: S3Config):
        """
        Initialize S3Manager with configuration.

        Args:
            config: S3Config instance with connection details
        """
        self.config = config
        self.bucket = config.bucket

        # Configure boto3 client
        boto_config = Config(
            signature_version=config.signature_version,
            max_pool_connections=config.max_pool_connections,
            retries={
                'max_attempts': 5,
                'mode': 'adaptive'
            }
        )

        # Create S3 client
        self.client = boto3.client(
            's3',
            region_name=config.region,
            aws_access_key_id=config.access_key,
            aws_secret_access_key=config.secret_key,
            endpoint_url=config.endpoint_url,
            use_ssl=config.use_ssl,
            config=boto_config
        )

        # Transfer configuration for multipart operations
        self.transfer_config = TransferConfig(
            multipart_threshold=8 * 1024 * 1024,  # 8MB
            multipart_chunksize=8 * 1024 * 1024,  # 8MB
            max_concurrency=10,
            use_threads=True
        )

        # Thread pool for async operations
        self.executor = ThreadPoolExecutor(max_workers=10)

        logger.info(f"S3Manager initialized for bucket: {self.bucket}")

    def test_connection(self) -> Dict[str, Any]:
        """
        Test S3 connection and bucket access.

        Returns:
            Dict with connection test results

        Raises:
            ClientError: If connection fails
        """
        try:
            # Check if bucket exists and is accessible
            response = self.client.head_bucket(Bucket=self.bucket)

            return {
                "success": True,
                "message": f"Successfully connected to bucket '{self.bucket}'",
                "bucket": self.bucket,
                "region": self.config.region,
                "status_code": response['ResponseMetadata']['HTTPStatusCode']
            }

        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                message = f"Bucket '{self.bucket}' does not exist"
            elif error_code == '403':
                message = f"Access denied to bucket '{self.bucket}'"
            else:
                message = f"Connection failed: {e.response['Error']['Message']}"

            logger.error(message)
            return {
                "success": False,
                "message": message,
                "error_code": error_code
            }

        except Exception as e:
            logger.exception(f"Unexpected error testing S3 connection: {e}")
            return {
                "success": False,
                "message": f"Unexpected error: {str(e)}"
            }

    def list_objects(
        self,
        prefix: str = "",
        recursive: bool = True,
        max_objects: Optional[int] = None
    ) -> List[S3Object]:
        """
        List objects in S3 bucket with pagination support.

        Args:
            prefix: S3 key prefix to filter objects
            recursive: If True, list all objects recursively. If False, list only top-level
            max_objects: Maximum number of objects to return (None = all)

        Returns:
            List of S3Object instances
        """
        objects = []
        paginator = self.client.get_paginator('list_objects_v2')

        try:
            page_iterator = paginator.paginate(
                Bucket=self.bucket,
                Prefix=prefix,
                Delimiter='' if recursive else '/'
            )

            for page in page_iterator:
                # Handle common prefixes (directories) when not recursive
                if not recursive and 'CommonPrefixes' in page:
                    for prefix_obj in page['CommonPrefixes']:
                        objects.append(S3Object(
                            key=prefix_obj['Prefix'],
                            size=0,
                            last_modified=datetime.now(timezone.utc),
                            etag="",
                            is_directory=True
                        ))

                # Handle objects
                if 'Contents' in page:
                    for obj in page['Contents']:
                        objects.append(S3Object(
                            key=obj['Key'],
                            size=obj['Size'],
                            last_modified=obj['LastModified'],
                            etag=obj['ETag'].strip('"'),
                            storage_class=obj.get('StorageClass', 'STANDARD'),
                            is_directory=obj['Key'].endswith('/')
                        ))

                        # Check max_objects limit
                        if max_objects and len(objects) >= max_objects:
                            return objects[:max_objects]

            logger.info(f"Listed {len(objects)} objects with prefix '{prefix}'")
            return objects

        except ClientError as e:
            logger.error(f"Error listing objects: {e}")
            raise

    def download_file(
        self,
        s3_key: str,
        local_path: str,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> Dict[str, Any]:
        """
        Download file from S3 with progress tracking.

        Args:
            s3_key: S3 object key
            local_path: Local file path to save to
            progress_callback: Optional callback function(bytes_transferred)

        Returns:
            Dict with download results
        """
        try:
            # Ensure local directory exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            # Get object metadata
            head_response = self.client.head_object(Bucket=self.bucket, Key=s3_key)
            file_size = head_response['ContentLength']

            # Progress tracking
            bytes_transferred = [0]

            def progress_hook(chunk):
                bytes_transferred[0] += chunk
                if progress_callback:
                    progress_callback(bytes_transferred[0])

            # Download file
            self.client.download_file(
                Bucket=self.bucket,
                Key=s3_key,
                Filename=local_path,
                Config=self.transfer_config,
                Callback=progress_hook
            )

            logger.info(f"Downloaded {s3_key} to {local_path} ({file_size} bytes)")

            return {
                "success": True,
                "s3_key": s3_key,
                "local_path": local_path,
                "size": file_size,
                "bytes_transferred": bytes_transferred[0]
            }

        except ClientError as e:
            logger.error(f"Error downloading {s3_key}: {e}")
            return {
                "success": False,
                "s3_key": s3_key,
                "local_path": local_path,
                "error": str(e)
            }

    def upload_file(
        self,
        local_path: str,
        s3_key: str,
        metadata: Optional[Dict[str, str]] = None,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> Dict[str, Any]:
        """
        Upload file to S3 with progress tracking.

        Args:
            local_path: Local file path
            s3_key: S3 object key
            metadata: Optional metadata dict
            progress_callback: Optional callback function(bytes_transferred)

        Returns:
            Dict with upload results
        """
        try:
            file_size = os.path.getsize(local_path)

            # Progress tracking
            bytes_transferred = [0]

            def progress_hook(chunk):
                bytes_transferred[0] += chunk
                if progress_callback:
                    progress_callback(bytes_transferred[0])

            # Prepare extra args
            extra_args = {}
            if metadata:
                extra_args['Metadata'] = metadata

            # Upload file
            self.client.upload_file(
                Filename=local_path,
                Bucket=self.bucket,
                Key=s3_key,
                Config=self.transfer_config,
                ExtraArgs=extra_args,
                Callback=progress_hook
            )

            logger.info(f"Uploaded {local_path} to {s3_key} ({file_size} bytes)")

            return {
                "success": True,
                "local_path": local_path,
                "s3_key": s3_key,
                "size": file_size,
                "bytes_transferred": bytes_transferred[0]
            }

        except (ClientError, OSError) as e:
            logger.error(f"Error uploading {local_path}: {e}")
            return {
                "success": False,
                "local_path": local_path,
                "s3_key": s3_key,
                "error": str(e)
            }

    def delete_object(self, s3_key: str) -> Dict[str, Any]:
        """
        Delete object from S3.

        Args:
            s3_key: S3 object key to delete

        Returns:
            Dict with deletion results
        """
        try:
            self.client.delete_object(Bucket=self.bucket, Key=s3_key)
            logger.info(f"Deleted object: {s3_key}")

            return {
                "success": True,
                "s3_key": s3_key
            }

        except ClientError as e:
            logger.error(f"Error deleting {s3_key}: {e}")
            return {
                "success": False,
                "s3_key": s3_key,
                "error": str(e)
            }

    def get_object_metadata(self, s3_key: str) -> Optional[Dict[str, Any]]:
        """
        Get object metadata without downloading.

        Args:
            s3_key: S3 object key

        Returns:
            Dict with object metadata or None if not found
        """
        try:
            response = self.client.head_object(Bucket=self.bucket, Key=s3_key)

            return {
                "key": s3_key,
                "size": response['ContentLength'],
                "last_modified": response['LastModified'],
                "etag": response['ETag'].strip('"'),
                "content_type": response.get('ContentType'),
                "metadata": response.get('Metadata', {}),
                "storage_class": response.get('StorageClass', 'STANDARD')
            }

        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.warning(f"Object not found: {s3_key}")
            else:
                logger.error(f"Error getting metadata for {s3_key}: {e}")
            return None

    def generate_presigned_url(
        self,
        s3_key: str,
        expiration: int = 3600,
        http_method: str = 'GET'
    ) -> Optional[str]:
        """
        Generate presigned URL for temporary access.

        Args:
            s3_key: S3 object key
            expiration: URL expiration time in seconds (default: 1 hour)
            http_method: HTTP method (GET for download, PUT for upload)

        Returns:
            Presigned URL string or None if error
        """
        try:
            client_method = 'get_object' if http_method == 'GET' else 'put_object'

            url = self.client.generate_presigned_url(
                ClientMethod=client_method,
                Params={'Bucket': self.bucket, 'Key': s3_key},
                ExpiresIn=expiration
            )

            logger.info(f"Generated presigned URL for {s3_key} (expires in {expiration}s)")
            return url

        except ClientError as e:
            logger.error(f"Error generating presigned URL for {s3_key}: {e}")
            return None

    def sync_to_local(
        self,
        s3_prefix: str,
        local_dir: str,
        force_overwrite: bool = False,
        folder_filter: Optional[List[str]] = None,
        folder_match_mode: str = "contains",
        file_patterns: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> Dict[str, Any]:
        """
        Sync S3 directory to local directory.

        Args:
            s3_prefix: S3 prefix (directory)
            local_dir: Local directory path
            force_overwrite: If True, overwrite existing files
            folder_filter: List of folder names to filter
            folder_match_mode: 'exact', 'contains', or 'startswith'
            file_patterns: List of file patterns (e.g., ['*.jpg', '*.pdf'])
            progress_callback: Optional callback(file_path, current, total)

        Returns:
            Dict with sync results
        """
        results = {
            "total_files": 0,
            "downloaded": 0,
            "skipped": 0,
            "failed": 0,
            "bytes_transferred": 0
        }

        try:
            # List all objects with prefix
            objects = self.list_objects(prefix=s3_prefix, recursive=True)
            results["total_files"] = len(objects)

            for idx, obj in enumerate(objects, 1):
                # Skip directories
                if obj.is_directory:
                    continue

                # Apply folder filter
                if folder_filter and not self._match_folder_filter(
                    obj.key, folder_filter, folder_match_mode
                ):
                    results["skipped"] += 1
                    continue

                # Apply file pattern filter
                if file_patterns and not self._match_file_patterns(obj.key, file_patterns):
                    results["skipped"] += 1
                    continue

                # Determine local path
                relative_path = obj.key[len(s3_prefix):].lstrip('/')
                local_path = os.path.join(local_dir, relative_path)

                # Check if file exists
                if os.path.exists(local_path) and not force_overwrite:
                    # Compare modification times
                    local_mtime = datetime.fromtimestamp(os.path.getmtime(local_path), tz=timezone.utc)
                    if local_mtime >= obj.last_modified:
                        results["skipped"] += 1
                        if progress_callback:
                            progress_callback(obj.key, idx, results["total_files"])
                        continue

                # Download file
                download_result = self.download_file(obj.key, local_path)

                if download_result["success"]:
                    results["downloaded"] += 1
                    results["bytes_transferred"] += download_result["size"]
                else:
                    results["failed"] += 1

                if progress_callback:
                    progress_callback(obj.key, idx, results["total_files"])

            logger.info(f"Sync completed: {results}")
            return results

        except Exception as e:
            logger.exception(f"Error during sync: {e}")
            results["error"] = str(e)
            return results

    def sync_from_local(
        self,
        local_dir: str,
        s3_prefix: str,
        force_overwrite: bool = False,
        file_patterns: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> Dict[str, Any]:
        """
        Sync local directory to S3.

        Args:
            local_dir: Local directory path
            s3_prefix: S3 prefix (directory)
            force_overwrite: If True, overwrite existing objects
            file_patterns: List of file patterns to include
            progress_callback: Optional callback(file_path, current, total)

        Returns:
            Dict with sync results
        """
        results = {
            "total_files": 0,
            "uploaded": 0,
            "skipped": 0,
            "failed": 0,
            "bytes_transferred": 0
        }

        try:
            # Get all local files
            local_files = []
            for root, dirs, files in os.walk(local_dir):
                for file in files:
                    local_path = os.path.join(root, file)
                    local_files.append(local_path)

            results["total_files"] = len(local_files)

            for idx, local_path in enumerate(local_files, 1):
                # Apply file pattern filter
                if file_patterns and not self._match_file_patterns(local_path, file_patterns):
                    results["skipped"] += 1
                    continue

                # Determine S3 key
                relative_path = os.path.relpath(local_path, local_dir)
                s3_key = os.path.join(s3_prefix, relative_path).replace('\\', '/')

                # Check if object exists in S3
                if not force_overwrite:
                    metadata = self.get_object_metadata(s3_key)
                    if metadata:
                        # Compare sizes and modification times
                        local_size = os.path.getsize(local_path)
                        local_mtime = datetime.fromtimestamp(
                            os.path.getmtime(local_path), tz=timezone.utc
                        )

                        if local_size == metadata["size"] and local_mtime <= metadata["last_modified"]:
                            results["skipped"] += 1
                            if progress_callback:
                                progress_callback(local_path, idx, results["total_files"])
                            continue

                # Upload file
                upload_result = self.upload_file(local_path, s3_key)

                if upload_result["success"]:
                    results["uploaded"] += 1
                    results["bytes_transferred"] += upload_result["size"]
                else:
                    results["failed"] += 1

                if progress_callback:
                    progress_callback(local_path, idx, results["total_files"])

            logger.info(f"Sync completed: {results}")
            return results

        except Exception as e:
            logger.exception(f"Error during sync: {e}")
            results["error"] = str(e)
            return results

    def _match_folder_filter(
        self,
        path: str,
        folder_names: List[str],
        match_mode: str
    ) -> bool:
        """
        Check if path matches folder filter.

        Args:
            path: File path to check
            folder_names: List of folder names to match
            match_mode: 'exact', 'contains', or 'startswith'

        Returns:
            True if matches filter
        """
        path_parts = path.split('/')

        for folder_name in folder_names:
            for part in path_parts[:-1]:  # Exclude filename
                if match_mode == "exact" and part == folder_name:
                    return True
                elif match_mode == "contains" and folder_name in part:
                    return True
                elif match_mode == "startswith" and part.startswith(folder_name):
                    return True

        return False

    def _match_file_patterns(self, path: str, patterns: List[str]) -> bool:
        """
        Check if file matches any of the patterns.

        Args:
            path: File path
            patterns: List of glob patterns

        Returns:
            True if matches any pattern
        """
        filename = os.path.basename(path)

        for pattern in patterns:
            if fnmatch.fnmatch(filename, pattern):
                return True

        return False

    def close(self):
        """Close S3 client and thread pool."""
        self.executor.shutdown(wait=True)
        logger.info("S3Manager closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
