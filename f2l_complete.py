import os
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import sqlite3
from datetime import datetime, timedelta
import threading
import time
from dataclasses import dataclass
from typing import List, Dict, Optional
import queue
import sys
import uuid
import concurrent.futures
import pickle
import hashlib
import json

try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    print("Warning: pystray and PIL not installed. System tray features disabled.")
    pystray = None
    TRAY_AVAILABLE = False

try:
    import schedule
    SCHEDULE_AVAILABLE = True
except ImportError:
    print("Warning: schedule not installed. Scheduling features disabled.")
    schedule = None
    SCHEDULE_AVAILABLE = False

class LogManager:
    """Centralized logging system with real-time display support"""

    LOG_LEVELS = {
        'DEBUG': {'color': 'gray', 'prefix': '⚪'},
        'INFO': {'color': 'blue', 'prefix': '🔵'},
        'SUCCESS': {'color': 'green', 'prefix': '🟢'},
        'WARNING': {'color': 'orange', 'prefix': '🟡'},
        'ERROR': {'color': 'red', 'prefix': '🔴'}
    }

    def __init__(self):
        self.logs = []  # Store all logs
        self.max_logs = 10000  # Maximum logs to keep in memory
        self.callbacks = []  # Callbacks for real-time updates
        self.session_logs = {}  # Separate logs per session
        self.lock = threading.Lock()

    def log(self, message, level='INFO', session_id=None):
        """Add a log entry"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {
            'timestamp': timestamp,
            'level': level,
            'message': message,
            'session_id': session_id
        }

        with self.lock:
            # Add to main logs
            self.logs.append(log_entry)
            if len(self.logs) > self.max_logs:
                self.logs.pop(0)  # Remove oldest log

            # Add to session-specific logs
            if session_id:
                if session_id not in self.session_logs:
                    self.session_logs[session_id] = []
                self.session_logs[session_id].append(log_entry)
                if len(self.session_logs[session_id]) > self.max_logs:
                    self.session_logs[session_id].pop(0)

            # Notify callbacks
            for callback in self.callbacks:
                try:
                    callback(log_entry)
                except Exception as e:
                    print(f"Error in log callback: {e}")

        # Also print to console
        prefix = self.LOG_LEVELS.get(level, {}).get('prefix', '⚪')
        print(f"[{timestamp}] {prefix} [{level}] {message}")

    def debug(self, message, session_id=None):
        self.log(message, 'DEBUG', session_id)

    def info(self, message, session_id=None):
        self.log(message, 'INFO', session_id)

    def success(self, message, session_id=None):
        self.log(message, 'SUCCESS', session_id)

    def warning(self, message, session_id=None):
        self.log(message, 'WARNING', session_id)

    def error(self, message, session_id=None):
        self.log(message, 'ERROR', session_id)

    def register_callback(self, callback):
        """Register a callback for real-time log updates"""
        with self.lock:
            self.callbacks.append(callback)

    def unregister_callback(self, callback):
        """Unregister a callback"""
        with self.lock:
            if callback in self.callbacks:
                self.callbacks.remove(callback)

    def get_logs(self, session_id=None, level=None, limit=None):
        """Get logs with optional filtering"""
        with self.lock:
            if session_id:
                logs = self.session_logs.get(session_id, [])
            else:
                logs = self.logs

            if level:
                logs = [log for log in logs if log['level'] == level]

            if limit:
                logs = logs[-limit:]

            return logs.copy()

    def clear_logs(self, session_id=None):
        """Clear logs"""
        with self.lock:
            if session_id:
                if session_id in self.session_logs:
                    self.session_logs[session_id] = []
            else:
                self.logs = []
                self.session_logs = {}

    def save_to_file(self, filepath, session_id=None):
        """Save logs to a file"""
        logs = self.get_logs(session_id)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                for log in logs:
                    prefix = self.LOG_LEVELS.get(log['level'], {}).get('prefix', '⚪')
                    f.write(f"[{log['timestamp']}] {prefix} [{log['level']}] {log['message']}\n")
            return True
        except Exception as e:
            print(f"Error saving logs: {e}")
            return False

class DirectoryScanCache:
    """Persistent caching system for directory scan results"""

    def __init__(self, cache_file="scan_cache.pkl", max_age_seconds=300):
        self.cache_file = cache_file
        self.max_age_seconds = max_age_seconds  # Cache duration in seconds (default: 5 minutes)
        self.cache = {}
        self.cache_lock = threading.Lock()
        self.load_cache()

    def _get_cache_key(self, directory, folder_filter_key=""):
        """Generate cache key for directory and filter combination"""
        key_string = f"{directory}:{folder_filter_key}"
        return hashlib.md5(key_string.encode()).hexdigest()

    def _get_folder_filter_key(self, folder_names, match_mode, case_sensitive):
        """Generate key for folder filter settings"""
        if not folder_names:
            return ""
        return f"{','.join(sorted(folder_names))}:{match_mode}:{case_sensitive}"

    def load_cache(self):
        """Load cache from disk"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'rb') as f:
                    self.cache = pickle.load(f)
                print(f"Loaded scan cache with {len(self.cache)} entries")
                self.cleanup_expired()
        except Exception as e:
            print(f"Error loading scan cache: {e}")
            self.cache = {}

    def save_cache(self):
        """Save cache to disk"""
        try:
            with self.cache_lock:
                with open(self.cache_file, 'wb') as f:
                    pickle.dump(self.cache, f)
        except Exception as e:
            print(f"Error saving scan cache: {e}")

    def cleanup_expired(self):
        """Remove expired cache entries"""
        current_time = datetime.now()
        expired_keys = []

        with self.cache_lock:
            for key, (data, timestamp, dir_mtime) in self.cache.items():
                age_seconds = (current_time - timestamp).total_seconds()
                if age_seconds > self.max_age_seconds:
                    expired_keys.append(key)

            for key in expired_keys:
                del self.cache[key]

        if expired_keys:
            print(f"Cleaned up {len(expired_keys)} expired cache entries")

    def get_cached_scan(self, directory, folder_names=None, match_mode="exact", case_sensitive=False):
        """Get cached scan results if still valid

        Cache is invalidated if:
        1. Age exceeds max_age_seconds (from settings)
        2. Directory modification time changed (files added/removed/modified)
        """
        if not os.path.exists(directory):
            return None

        folder_filter_key = self._get_folder_filter_key(folder_names or [], match_mode, case_sensitive)
        cache_key = self._get_cache_key(directory, folder_filter_key)

        with self.cache_lock:
            if cache_key in self.cache:
                cached_data, timestamp, cached_dir_mtime = self.cache[cache_key]

                # Check if cache is still valid
                age_seconds = (datetime.now() - timestamp).total_seconds()
                current_dir_mtime = os.path.getmtime(directory)

                # Cache is valid if:
                # 1. Not expired (age < max_age_seconds)
                # 2. Directory not modified (mtime unchanged within 1 second tolerance)
                if age_seconds <= self.max_age_seconds and abs(current_dir_mtime - cached_dir_mtime) < 1:
                    print(f"✓ Cache hit for {directory} (age: {age_seconds:.1f}s / {self.max_age_seconds}s)")
                    return cached_data
                else:
                    # Remove invalid cache entry
                    reason = "expired" if age_seconds > self.max_age_seconds else "directory modified"
                    print(f"✗ Cache invalid for {directory} ({reason})")
                    del self.cache[cache_key]

        return None

    def cache_scan_results(self, directory, results, folder_names=None, match_mode="exact", case_sensitive=False):
        """Cache scan results"""
        if not os.path.exists(directory):
            return

        folder_filter_key = self._get_folder_filter_key(folder_names or [], match_mode, case_sensitive)
        cache_key = self._get_cache_key(directory, folder_filter_key)

        with self.cache_lock:
            self.cache[cache_key] = (
                results,
                datetime.now(),
                os.path.getmtime(directory)
            )

        # Save cache periodically (every 10 entries)
        if len(self.cache) % 10 == 0:
            threading.Thread(target=self.save_cache, daemon=True).start()

@dataclass
class FTPEndpoint:
    id: str
    name: str
    host: str
    port: int
    username: str
    password: str
    remote_path: str
    local_path: str
    is_main_source: bool = True  # FTP is authoritative
    auto_sync_enabled: bool = False
    sync_interval: int = 60  # minutes
    last_sync: Optional[datetime] = None
    connection_status: str = "disconnected"  # disconnected, connected, error
    last_health_check: Optional[datetime] = None

@dataclass
class FTPFileInfo:
    ftp_path: str
    local_path: str
    operation_type: str  # 'download', 'upload', 'update', 'skip', 'conflict'
    file_size: int
    ftp_modified: datetime
    local_modified: Optional[datetime] = None
    endpoint_id: str = ""

class FTPManager:
    def __init__(self, host: str, username: str, password: str, port: int = 21):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.ftp = None
        self.last_activity = None
        self.connection_timeout = 300  # 5 minutes
        
    def connect(self):
        try:
            # Clean up existing connection
            if self.ftp:
                try:
                    self.ftp.quit()
                except:
                    try:
                        self.ftp.close()
                    except:
                        pass

            import ftplib
            self.ftp = ftplib.FTP()

            # Set longer timeout and enable debugging for troubleshooting
            self.ftp.set_debuglevel(0)  # Set to 1 or 2 for debugging

            print(f"Connecting to {self.host}:{self.port}...")
            self.ftp.connect(self.host, self.port, timeout=60)  # Increased timeout

            print(f"Logging in as {self.username}...")
            self.ftp.login(self.username, self.password)

            # Set passive mode (helps with firewalls)
            self.ftp.set_pasv(True)

            # Test the connection
            welcome_msg = self.ftp.getwelcome()
            print(f"Connected successfully. Server: {welcome_msg}")

            self.last_activity = datetime.now()
            return True

        except Exception as e:
            print(f"FTP connection failed to {self.host}:{self.port} - {e}")
            self.ftp = None
            return False
    
    def is_connected(self):
        if not self.ftp:
            return False

        # Check if connection is too old
        if self.last_activity and (datetime.now() - self.last_activity).seconds > self.connection_timeout:
            print(f"Connection timeout exceeded ({self.connection_timeout}s)")
            return False

        try:
            # Send NOOP to test connection
            response = self.ftp.voidcmd("NOOP")
            self.last_activity = datetime.now()
            return True
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False
    
    def ensure_connected(self):
        if not self.is_connected():
            return self.connect()
        return True
    
    def disconnect(self):
        """Properly disconnect from FTP server with comprehensive cleanup"""
        if self.ftp:
            try:
                # Try graceful quit first
                print(f"Disconnecting from {self.host}...")
                self.ftp.quit()
                print("FTP connection closed gracefully")
            except Exception as e:
                print(f"Graceful quit failed, forcing close: {e}")
                try:
                    # Force close if quit fails
                    self.ftp.close()
                    print("FTP connection force closed")
                except Exception as close_error:
                    print(f"Force close also failed: {close_error}")
            finally:
                self.ftp = None
                self.last_activity = None
                print("FTP manager cleaned up")
        else:
            print("No active FTP connection to disconnect")
    
    def health_check(self):
        """Perform comprehensive health check"""
        try:
            if not self.ensure_connected():
                return False, "Connection failed"
            
            # Test basic operations
            try:
                self.ftp.pwd()  # Get current directory
                self.ftp.voidcmd("NOOP")  # Send no-op command
                return True, "Connection healthy"
            except Exception as e:
                return False, f"Health check failed: {str(e)}"
                
        except Exception as e:
            return False, f"Health check error: {str(e)}"
    
    def list_files(self, remote_path: str = "/", max_depth: int = 5, current_depth: int = 0) -> List[Dict]:
        """List all files in remote directory recursively with improved error handling"""
        if not self.ensure_connected():
            return []

        if current_depth >= max_depth:
            print(f"Maximum recursion depth ({max_depth}) reached for {remote_path} - stopping recursion")
            return []

        files = []

        def process_line(line):
            # Parse FTP LIST output with better error handling
            try:
                parts = line.split()
                if len(parts) >= 9:
                    permissions = parts[0]

                    # Handle size field more carefully
                    try:
                        size = int(parts[4]) if parts[4].isdigit() else 0
                    except (ValueError, IndexError):
                        size = 0

                    # Parse date (simplified but more robust)
                    try:
                        month_day = f"{parts[5]} {parts[6]}"
                        year_or_time = parts[7]

                        if ":" in year_or_time:
                            current_year = datetime.now().year
                            date_str = f"{month_day} {current_year} {year_or_time}"
                            try:
                                modified = datetime.strptime(date_str, "%b %d %Y %H:%M")
                            except:
                                modified = datetime.now()
                        else:
                            date_str = f"{month_day} {year_or_time}"
                            try:
                                modified = datetime.strptime(date_str, "%b %d %Y")
                            except:
                                modified = datetime.now()
                    except (IndexError, ValueError):
                        modified = datetime.now()

                    filename = " ".join(parts[8:]) if len(parts) > 8 else ""

                    if filename and not permissions.startswith('d') and filename not in ['.', '..']:
                        full_path = f"{remote_path.rstrip('/')}/{filename}"
                        files.append({
                            'path': full_path,
                            'size': size,
                            'modified': modified,
                            'is_file': True
                        })
            except Exception as e:
                print(f"Error parsing FTP line '{line}': {e}")

        try:
            # Test if directory exists first
            original_dir = self.ftp.pwd()

            try:
                self.ftp.cwd(remote_path)
            except Exception as e:
                print(f"Cannot access directory {remote_path}: {e}")
                return []

            # Get directory listing
            lines = []
            try:
                self.ftp.retrlines('LIST', lines.append)
            except Exception as e:
                print(f"Error getting directory listing for {remote_path}: {e}")
                return []

            # Process files
            for line in lines:
                if line.strip():  # Skip empty lines
                    process_line(line)

            # Get subdirectories and recurse with connection checks
            subdirs = []
            def collect_dirs(line):
                try:
                    parts = line.split()
                    if len(parts) >= 9 and parts[0].startswith('d'):
                        dirname = " ".join(parts[8:]) if len(parts) > 8 else ""
                        if dirname and dirname not in ['.', '..']:
                            subdirs.append(dirname)
                except Exception as e:
                    print(f"Error parsing directory line '{line}': {e}")

            # Re-get listing for directories (some FTP servers need this)
            try:
                self.ftp.cwd(remote_path)  # Ensure we're in the right directory
                dir_lines = []
                self.ftp.retrlines('LIST', dir_lines.append)
                for line in dir_lines:
                    if line.strip():
                        collect_dirs(line)
            except Exception as e:
                print(f"Error getting subdirectory listing for {remote_path}: {e}")

            # Recursively process subdirectories with connection management and path tracking
            for subdir in subdirs:
                if not self.ensure_connected():
                    print(f"Connection lost while processing subdirectories")
                    break

                subdir_path = f"{remote_path.rstrip('/')}/{subdir}"

                # Skip if path is getting too long (potential infinite recursion)
                if len(subdir_path) > 500:
                    print(f"Skipping very long path (potential recursion): {subdir_path}")
                    continue

                # Skip common problematic directories
                if subdir.lower() in ['.', '..', 'system volume information', '$recycle.bin']:
                    continue

                try:
                    print(f"Recursing into: {subdir_path} (depth: {current_depth + 1})")
                    subdir_files = self.list_files(subdir_path, max_depth, current_depth + 1)
                    files.extend(subdir_files)
                except RecursionError:
                    print(f"Recursion error in {subdir_path} - skipping")
                    continue
                except Exception as e:
                    print(f"Error recursing into {subdir_path}: {e}")
                    continue

            # Return to original directory
            try:
                self.ftp.cwd(original_dir)
            except:
                pass  # If we can't return, that's okay

        except Exception as e:
            print(f"Error listing {remote_path}: {e}")

        self.last_activity = datetime.now()
        return files

    def list_files_iterative(self, remote_path: str = "/", max_files: int = 100000) -> List[Dict]:
        """List files using iterative approach to avoid recursion limits

        Args:
            remote_path: Remote directory path to scan
            max_files: Maximum number of files to scan (default: 100,000)
        """
        if not self.ensure_connected():
            return []

        files = []
        directories_to_process = [remote_path]
        processed_dirs = set()
        file_count = 0

        print(f"Starting iterative scan of {remote_path} (max files: {max_files})")

        while directories_to_process and file_count < max_files:
            current_dir = directories_to_process.pop(0)

            # Avoid processing the same directory twice
            if current_dir in processed_dirs:
                continue
            processed_dirs.add(current_dir)

            # Skip very long paths
            if len(current_dir) > 500:
                print(f"Skipping very long path: {current_dir}")
                continue

            try:
                print(f"Processing directory: {current_dir} ({len(processed_dirs)} dirs processed, {file_count} files found)")

                # Get directory listing
                self.ftp.cwd(current_dir)
                lines = []
                self.ftp.retrlines('LIST', lines.append)

                subdirs = []

                for line in lines:
                    if not line.strip():
                        continue

                    try:
                        parts = line.split()
                        if len(parts) >= 9:
                            permissions = parts[0]
                            filename = " ".join(parts[8:]) if len(parts) > 8 else ""

                            if not filename or filename in ['.', '..']:
                                continue

                            full_path = f"{current_dir.rstrip('/')}/{filename}"

                            if permissions.startswith('d'):
                                # It's a directory - add to queue for recursive scanning
                                subdirs.append(full_path)
                            else:
                                # It's a file
                                try:
                                    size = int(parts[4]) if parts[4].isdigit() else 0
                                except (ValueError, IndexError):
                                    size = 0

                                # Parse date
                                try:
                                    month_day = f"{parts[5]} {parts[6]}"
                                    year_or_time = parts[7]

                                    if ":" in year_or_time:
                                        current_year = datetime.now().year
                                        date_str = f"{month_day} {current_year} {year_or_time}"
                                        modified = datetime.strptime(date_str, "%b %d %Y %H:%M")
                                    else:
                                        date_str = f"{month_day} {year_or_time}"
                                        modified = datetime.strptime(date_str, "%b %d %Y")
                                except:
                                    modified = datetime.now()

                                files.append({
                                    'path': full_path,
                                    'size': size,
                                    'modified': modified,
                                    'is_file': True
                                })

                                file_count += 1
                                if file_count >= max_files:
                                    print(f"⚠️ WARNING: Reached maximum file limit ({max_files:,} files)")
                                    print(f"⚠️ Some files may have been skipped. Increase limit in Settings tab if needed.")
                                    break

                    except Exception as e:
                        print(f"Error parsing line '{line}': {e}")
                        continue

                # Add subdirectories to processing queue
                directories_to_process.extend(subdirs)

            except Exception as e:
                print(f"Error processing directory {current_dir}: {e}")
                continue

        print(f"Iterative scan complete: {len(files)} files found, {len(processed_dirs)} directories processed")

        # Warn if there are unprocessed directories (shouldn't happen unless max_files limit hit)
        if directories_to_process:
            print(f"⚠️ WARNING: {len(directories_to_process)} directories were not processed (file limit reached)")

        self.last_activity = datetime.now()
        return files

    def apply_folder_filter(self, files: List[Dict], folder_names: List[str], match_mode: str = "exact", case_sensitive: bool = False) -> List[Dict]:
        """Filter files to only include those in specified folders"""
        if not folder_names:
            return files

        filtered_files = []

        # Normalize folder names for comparison
        if not case_sensitive:
            folder_names = [name.lower().strip() for name in folder_names]
        else:
            folder_names = [name.strip() for name in folder_names]

        print(f"Applying folder filter: {folder_names} (mode: {match_mode}, case_sensitive: {case_sensitive})")

        for file_info in files:
            file_path = file_info['path']
            path_parts = file_path.replace('\\', '/').split('/')

            # Check each part of the path
            should_include = False
            for path_part in path_parts:
                if not path_part:  # Skip empty parts
                    continue

                # Normalize path part for comparison
                compare_part = path_part if case_sensitive else path_part.lower()

                # Check against each folder name
                for folder_name in folder_names:
                    if match_mode == "exact":
                        if compare_part == folder_name:
                            should_include = True
                            break
                    elif match_mode == "contains":
                        if folder_name in compare_part:
                            should_include = True
                            break

                if should_include:
                    break

            if should_include:
                filtered_files.append(file_info)

        print(f"Folder filter result: {len(filtered_files)} files (from {len(files)} total)")
        return filtered_files
    
    def download_file(self, remote_path: str, local_path: str) -> bool:
        """Download file from FTP to local path"""
        try:
            if not self.ensure_connected():
                return False
                
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            with open(local_path, 'wb') as local_file:
                self.ftp.retrbinary(f'RETR {remote_path}', local_file.write)
            
            self.last_activity = datetime.now()
            return True
        except Exception as e:
            print(f"FTP download failed for {remote_path}: {e}")
            return False
    
    def upload_file(self, local_path: str, remote_path: str) -> bool:
        """Upload file from local to FTP"""
        try:
            if not self.ensure_connected():
                return False
            
            # Ensure remote directory exists
            remote_dir = os.path.dirname(remote_path).replace('\\', '/')
            self.ensure_remote_dir(remote_dir)
            
            with open(local_path, 'rb') as local_file:
                self.ftp.storbinary(f'STOR {remote_path}', local_file)
            
            self.last_activity = datetime.now()
            return True
        except Exception as e:
            print(f"FTP upload failed for {local_path}: {e}")
            return False
    
    def ensure_remote_dir(self, remote_dir: str):
        """Create remote directory structure if it doesn't exist"""
        if not remote_dir or remote_dir == '/':
            return
            
        try:
            import ftplib
            self.ftp.cwd('/')
            parts = remote_dir.strip('/').split('/')
            for part in parts:
                if part:
                    try:
                        self.ftp.cwd(part)
                    except ftplib.error_perm:
                        self.ftp.mkd(part)
                        self.ftp.cwd(part)
        except Exception as e:
            print(f"Failed to create remote directory: {e}")

    def get_file_info(self, remote_path: str) -> dict:
        """Get file information from FTP server"""
        try:
            if not self.ensure_connected():
                return None

            # Try to get file size and modification time
            try:
                size = self.ftp.size(remote_path)
            except:
                size = None

            try:
                # Get modification time using MDTM command
                mdtm_response = self.ftp.sendcmd(f'MDTM {remote_path}')
                if mdtm_response.startswith('213'):
                    time_str = mdtm_response[4:].strip()
                    # Parse YYYYMMDDHHMMSS format
                    modified = datetime.strptime(time_str, '%Y%m%d%H%M%S')
                else:
                    modified = None
            except:
                modified = None

            if size is not None or modified is not None:
                return {
                    'size': size,
                    'modified': modified
                }
            else:
                return None

        except Exception as e:
            # File doesn't exist or can't access
            return None

class DatabaseManager:
    def __init__(self, db_path: str = "f2l_sync.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Endpoints table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ftp_endpoints (
                id TEXT PRIMARY KEY,
                name TEXT,
                host TEXT,
                port INTEGER,
                username TEXT,
                password TEXT,
                remote_path TEXT,
                local_path TEXT,
                is_main_source INTEGER,
                auto_sync_enabled INTEGER,
                sync_interval INTEGER,
                last_sync TEXT,
                connection_status TEXT,
                last_health_check TEXT,
                created_date TEXT
            )
        ''')
        
        # Sync operations
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint_id TEXT,
                timestamp TEXT,
                ftp_path TEXT,
                local_path TEXT,
                operation_type TEXT,
                sync_direction TEXT,
                file_size INTEGER,
                success INTEGER,
                error_message TEXT
            )
        ''')

        # Sync sessions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint_id TEXT,
                session_start TEXT,
                session_end TEXT,
                sync_direction TEXT,
                total_files INTEGER,
                successful_files INTEGER,
                failed_files INTEGER,
                bytes_transferred INTEGER
            )
        ''')

        # Local sync configurations (for multi-session support)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS local_sync_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                source_path TEXT,
                dest_path TEXT,
                sync_direction TEXT,
                folder_filter_enabled INTEGER,
                folder_names TEXT,
                match_mode TEXT,
                case_sensitive INTEGER,
                schedule_enabled INTEGER,
                schedule_interval INTEGER,
                schedule_unit TEXT,
                auto_start INTEGER DEFAULT 0,
                parallel_execution INTEGER DEFAULT 1,
                active INTEGER,
                created_date TEXT,
                last_sync TEXT,
                last_status TEXT
            )
        ''')

        # FTP sync configurations (for multi-session support)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ftp_sync_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                endpoint_id INTEGER,
                source_path TEXT,
                dest_path TEXT,
                sync_direction TEXT,
                folder_filter_enabled INTEGER,
                folder_names TEXT,
                match_mode TEXT,
                case_sensitive INTEGER,
                schedule_enabled INTEGER,
                schedule_interval INTEGER,
                schedule_unit TEXT,
                auto_start INTEGER DEFAULT 0,
                parallel_execution INTEGER DEFAULT 1,
                active INTEGER,
                created_date TEXT,
                last_sync TEXT,
                last_status TEXT,
                FOREIGN KEY (endpoint_id) REFERENCES endpoints(id)
            )
        ''')

        # Migration: Add new columns to existing tables if they don't exist
        try:
            # Check and add columns to local_sync_configs
            cursor.execute("PRAGMA table_info(local_sync_configs)")
            local_columns = [col[1] for col in cursor.fetchall()]

            if 'auto_start' not in local_columns:
                cursor.execute("ALTER TABLE local_sync_configs ADD COLUMN auto_start INTEGER DEFAULT 0")
            if 'parallel_execution' not in local_columns:
                cursor.execute("ALTER TABLE local_sync_configs ADD COLUMN parallel_execution INTEGER DEFAULT 1")
            if 'last_status' not in local_columns:
                cursor.execute("ALTER TABLE local_sync_configs ADD COLUMN last_status TEXT")
            if 'force_overwrite' not in local_columns:
                cursor.execute("ALTER TABLE local_sync_configs ADD COLUMN force_overwrite INTEGER DEFAULT 0")

            # Check and add columns to ftp_sync_configs
            cursor.execute("PRAGMA table_info(ftp_sync_configs)")
            ftp_columns = [col[1] for col in cursor.fetchall()]

            if 'source_path' not in ftp_columns:
                cursor.execute("ALTER TABLE ftp_sync_configs ADD COLUMN source_path TEXT")
            if 'dest_path' not in ftp_columns:
                cursor.execute("ALTER TABLE ftp_sync_configs ADD COLUMN dest_path TEXT")
            if 'auto_start' not in ftp_columns:
                cursor.execute("ALTER TABLE ftp_sync_configs ADD COLUMN auto_start INTEGER DEFAULT 0")
            if 'parallel_execution' not in ftp_columns:
                cursor.execute("ALTER TABLE ftp_sync_configs ADD COLUMN parallel_execution INTEGER DEFAULT 1")
            if 'last_status' not in ftp_columns:
                cursor.execute("ALTER TABLE ftp_sync_configs ADD COLUMN last_status TEXT")
            if 'force_overwrite' not in ftp_columns:
                cursor.execute("ALTER TABLE ftp_sync_configs ADD COLUMN force_overwrite INTEGER DEFAULT 0")

            conn.commit()
        except Exception as e:
            print(f"Migration warning: {e}")

        conn.commit()
        conn.close()
    
    def save_endpoint(self, endpoint: FTPEndpoint):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO ftp_endpoints 
            (id, name, host, port, username, password, remote_path, local_path, 
             is_main_source, auto_sync_enabled, sync_interval, last_sync, 
             connection_status, last_health_check, created_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            endpoint.id, endpoint.name, endpoint.host, endpoint.port,
            endpoint.username, endpoint.password, endpoint.remote_path, endpoint.local_path,
            1 if endpoint.is_main_source else 0,
            1 if endpoint.auto_sync_enabled else 0,
            endpoint.sync_interval,
            endpoint.last_sync.isoformat() if endpoint.last_sync else None,
            endpoint.connection_status,
            endpoint.last_health_check.isoformat() if endpoint.last_health_check else None,
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def load_endpoints(self) -> List[FTPEndpoint]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM ftp_endpoints ORDER BY name')
        rows = cursor.fetchall()
        
        endpoints = []
        for row in rows:
            endpoint = FTPEndpoint(
                id=row[0], name=row[1], host=row[2], port=row[3],
                username=row[4], password=row[5], remote_path=row[6], local_path=row[7],
                is_main_source=bool(row[8]), auto_sync_enabled=bool(row[9]),
                sync_interval=row[10],
                last_sync=datetime.fromisoformat(row[11]) if row[11] else None,
                connection_status=row[12],
                last_health_check=datetime.fromisoformat(row[13]) if row[13] else None
            )
            endpoints.append(endpoint)
        
        conn.close()
        return endpoints
    
    def delete_endpoint(self, endpoint_id: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM ftp_endpoints WHERE id = ?', (endpoint_id,))
        cursor.execute('DELETE FROM sync_operations WHERE endpoint_id = ?', (endpoint_id,))
        
        conn.commit()
        conn.close()
    
    def log_operation(self, endpoint_id: str, file_info: FTPFileInfo, sync_direction: str, success: bool, error_msg: str = ""):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO sync_operations 
            (endpoint_id, timestamp, ftp_path, local_path, operation_type, sync_direction, file_size, success, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            endpoint_id, datetime.now().isoformat(),
            file_info.ftp_path, file_info.local_path, file_info.operation_type,
            sync_direction, file_info.file_size,
            1 if success else 0, error_msg
        ))
        
        conn.commit()
        conn.close()

    def start_session(self, endpoint_id: str, sync_direction: str) -> int:
        """Start a new sync session and return session ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO sync_sessions
            (endpoint_id, session_start, sync_direction, total_files, successful_files, failed_files, bytes_transferred)
            VALUES (?, ?, ?, 0, 0, 0, 0)
        ''', (endpoint_id, datetime.now().isoformat(), sync_direction))

        session_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return session_id

    def end_session(self, session_id: int, stats: dict):
        """End a sync session with final statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE sync_sessions
            SET session_end = ?, total_files = ?, successful_files = ?, failed_files = ?, bytes_transferred = ?
            WHERE id = ?
        ''', (
            datetime.now().isoformat(),
            stats.get('total', 0),
            stats.get('successful', 0),
            stats.get('failed', 0),
            stats.get('bytes_transferred', 0),
            session_id
        ))

        conn.commit()
        conn.close()

class FTPSync:
    def __init__(self):
        self.db = DatabaseManager()
        self.ftp_managers = {}  # endpoint_id -> FTPManager
        self.health_check_thread = None
        self.health_check_running = False
    
    def add_endpoint(self, endpoint: FTPEndpoint):
        self.db.save_endpoint(endpoint)
        self.ftp_managers[endpoint.id] = FTPManager(
            endpoint.host, endpoint.username, endpoint.password, endpoint.port
        )
    
    def remove_endpoint(self, endpoint_id: str):
        if endpoint_id in self.ftp_managers:
            self.ftp_managers[endpoint_id].disconnect()
            del self.ftp_managers[endpoint_id]
        self.db.delete_endpoint(endpoint_id)
    
    def get_endpoints(self) -> List[FTPEndpoint]:
        endpoints = self.db.load_endpoints()
        
        # Ensure FTP managers exist
        for endpoint in endpoints:
            if endpoint.id not in self.ftp_managers:
                self.ftp_managers[endpoint.id] = FTPManager(
                    endpoint.host, endpoint.username, endpoint.password, endpoint.port
                )
        
        return endpoints
    
    def test_endpoint_connection(self, endpoint: FTPEndpoint) -> tuple:
        """Test connection and return (success, message, file_count)"""
        if endpoint.id not in self.ftp_managers:
            self.ftp_managers[endpoint.id] = FTPManager(
                endpoint.host, endpoint.username, endpoint.password, endpoint.port
            )

        ftp_manager = self.ftp_managers[endpoint.id]

        try:
            print(f"Testing connection to {endpoint.name} ({endpoint.host}:{endpoint.port})...")

            if ftp_manager.connect():
                print(f"Connected successfully to {endpoint.host}")

                # Test basic operations
                try:
                    current_dir = ftp_manager.ftp.pwd()
                    print(f"Current directory: {current_dir}")

                    # Test if we can access the remote path
                    try:
                        ftp_manager.ftp.cwd(endpoint.remote_path)
                        print(f"Successfully accessed remote path: {endpoint.remote_path}")

                        # OPTIONAL: Quick file count test (disabled for faster connection)
                        # Uncomment the lines below if you want to verify file access during connection
                        # print("Scanning files (limited count for testing)...")
                        # files = ftp_manager.list_files_iterative(endpoint.remote_path, max_files=1000)
                        # file_count = len(files)
                        # print(f"Found {file_count} files")

                        # Update endpoint status
                        endpoint.connection_status = "connected"
                        endpoint.last_health_check = datetime.now()
                        self.db.save_endpoint(endpoint)

                        print(f"✓ Connection successful! (File scanning skipped for faster connection)")

                        return True, f"Connection successful to {endpoint.host}. Remote path accessible.", 0

                    except Exception as path_error:
                        print(f"Cannot access remote path {endpoint.remote_path}: {path_error}")
                        endpoint.connection_status = "error"
                        self.db.save_endpoint(endpoint)
                        return False, f"Connected but cannot access remote path '{endpoint.remote_path}': {str(path_error)}", 0

                except Exception as test_error:
                    print(f"Connection test operations failed: {test_error}")
                    endpoint.connection_status = "error"
                    self.db.save_endpoint(endpoint)
                    return False, f"Connected but basic operations failed: {str(test_error)}", 0

            else:
                print(f"Failed to connect to {endpoint.host}")
                endpoint.connection_status = "error"
                self.db.save_endpoint(endpoint)
                return False, f"Failed to connect to {endpoint.host}. Check host, port, username, and password.", 0

        except Exception as e:
            print(f"Connection test error for {endpoint.host}: {e}")
            endpoint.connection_status = "error"
            self.db.save_endpoint(endpoint)
            return False, f"Connection error: {str(e)}", 0
        finally:
            # Always try to disconnect cleanly
            try:
                ftp_manager.disconnect()
            except:
                pass

    def diagnose_connection_issues(self, endpoint: FTPEndpoint) -> str:
        """Provide diagnostic information for connection issues"""
        diagnostics = []

        diagnostics.append(f"=== FTP Connection Diagnostics for {endpoint.name} ===")
        diagnostics.append(f"Host: {endpoint.host}")
        diagnostics.append(f"Port: {endpoint.port}")
        diagnostics.append(f"Username: {endpoint.username}")
        diagnostics.append(f"Remote Path: {endpoint.remote_path}")
        diagnostics.append(f"Local Path: {endpoint.local_path}")
        diagnostics.append("")

        # Test basic connectivity
        diagnostics.append("Testing basic connectivity...")
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            result = sock.connect_ex((endpoint.host, endpoint.port))
            sock.close()

            if result == 0:
                diagnostics.append("✓ Host and port are reachable")
            else:
                diagnostics.append("✗ Cannot reach host and port")
                diagnostics.append("  - Check if the host is correct")
                diagnostics.append("  - Check if the port is correct (usually 21 for FTP)")
                diagnostics.append("  - Check firewall settings")

        except Exception as e:
            diagnostics.append(f"✗ Network connectivity test failed: {e}")

        diagnostics.append("")

        # Test FTP connection
        diagnostics.append("Testing FTP connection...")
        ftp_manager = FTPManager(endpoint.host, endpoint.username, endpoint.password, endpoint.port)

        try:
            if ftp_manager.connect():
                diagnostics.append("✓ FTP connection successful")

                try:
                    current_dir = ftp_manager.ftp.pwd()
                    diagnostics.append(f"✓ Current directory: {current_dir}")
                except Exception as e:
                    diagnostics.append(f"✗ Cannot get current directory: {e}")

                try:
                    ftp_manager.ftp.cwd(endpoint.remote_path)
                    diagnostics.append(f"✓ Remote path '{endpoint.remote_path}' is accessible")
                except Exception as e:
                    diagnostics.append(f"✗ Cannot access remote path '{endpoint.remote_path}': {e}")
                    diagnostics.append("  - Check if the remote path exists")
                    diagnostics.append("  - Check if you have permissions to access it")

                ftp_manager.disconnect()
            else:
                diagnostics.append("✗ FTP connection failed")
                diagnostics.append("  - Check username and password")
                diagnostics.append("  - Check if FTP service is running on the server")

        except Exception as e:
            diagnostics.append(f"✗ FTP connection error: {e}")

        diagnostics.append("")
        diagnostics.append("=== End Diagnostics ===")

        return "\n".join(diagnostics)

    def disconnect_endpoint(self, endpoint: FTPEndpoint) -> tuple:
        """Disconnect from a specific endpoint and return (success, message)"""
        try:
            print(f"Disconnecting endpoint {endpoint.name} ({endpoint.host}:{endpoint.port})...")

            if endpoint.id in self.ftp_managers:
                ftp_manager = self.ftp_managers[endpoint.id]
                ftp_manager.disconnect()

                # Remove the FTP manager to prevent health monitoring from reconnecting
                del self.ftp_managers[endpoint.id]

                # Update endpoint status
                endpoint.connection_status = "disconnected"
                endpoint.last_health_check = datetime.now()
                self.db.save_endpoint(endpoint)

                print(f"Successfully disconnected from {endpoint.name}")
                return True, f"Successfully disconnected from {endpoint.name}"
            else:
                print(f"No active connection found for {endpoint.name}")
                # Still update status to disconnected
                endpoint.connection_status = "disconnected"
                endpoint.last_health_check = datetime.now()
                self.db.save_endpoint(endpoint)

                return True, f"No active connection found for {endpoint.name} (status updated to disconnected)"

        except Exception as e:
            error_msg = f"Error disconnecting from {endpoint.name}: {str(e)}"
            print(error_msg)

            # Update status to error
            endpoint.connection_status = "error"
            endpoint.last_health_check = datetime.now()
            self.db.save_endpoint(endpoint)

            return False, error_msg

    def disconnect_all_endpoints(self) -> dict:
        """Disconnect from all endpoints and return summary"""
        endpoints = self.get_endpoints()
        results = {
            'total': len(endpoints),
            'successful': 0,
            'failed': 0,
            'errors': []
        }

        print(f"Disconnecting from all {len(endpoints)} endpoints...")

        for endpoint in endpoints:
            success, message = self.disconnect_endpoint(endpoint)
            if success:
                results['successful'] += 1
            else:
                results['failed'] += 1
                results['errors'].append(f"{endpoint.name}: {message}")

        print(f"Disconnect all complete: {results['successful']} successful, {results['failed']} failed")
        return results
    
    def start_health_monitoring(self):
        """Start background health monitoring for all endpoints"""
        if not self.health_check_running:
            self.health_check_running = True
            self.health_check_thread = threading.Thread(target=self._health_monitor_loop, daemon=True)
            self.health_check_thread.start()
    
    def stop_health_monitoring(self):
        self.health_check_running = False
    
    def _health_monitor_loop(self):
        """Background health monitoring loop"""
        while self.health_check_running:
            try:
                endpoints = self.get_endpoints()
                
                for endpoint in endpoints:
                    # Skip health check for manually disconnected endpoints
                    if endpoint.connection_status == "disconnected":
                        continue

                    # Only check endpoints that should be connected
                    if endpoint.id in self.ftp_managers and endpoint.connection_status == "connected":
                        ftp_manager = self.ftp_managers[endpoint.id]

                        # Perform health check
                        is_healthy, message = ftp_manager.health_check()

                        # Update status only if it changed
                        old_status = endpoint.connection_status
                        new_status = "connected" if is_healthy else "error"

                        if old_status != new_status:
                            endpoint.connection_status = new_status
                            endpoint.last_health_check = datetime.now()
                            self.db.save_endpoint(endpoint)
                            print(f"Health check: {endpoint.name} status changed from {old_status} to {new_status}")
                        else:
                            # Just update the last check time
                            endpoint.last_health_check = datetime.now()
                
                # Wait 30 seconds before next check
                time.sleep(30)
                
            except Exception as e:
                print(f"Health monitor error: {e}")
                time.sleep(30)
    
    def scan_endpoint(self, endpoint: FTPEndpoint, sync_direction: str = "ftp_to_local", force_overwrite: bool = False) -> List[FTPFileInfo]:
        """Scan endpoint and create list of operations

        Args:
            force_overwrite: If True, force copy/download all files regardless of modification dates
        """

        # Check if endpoint is connected
        if endpoint.connection_status != "connected":
            raise Exception(f"Endpoint '{endpoint.name}' is not connected (status: {endpoint.connection_status}). Please connect first.")

        # Check if FTP manager exists
        if endpoint.id not in self.ftp_managers:
            raise Exception(f"No active FTP connection for endpoint '{endpoint.name}'. Please connect first.")

        ftp_manager = self.ftp_managers[endpoint.id]

        # Verify the connection is still active
        if not ftp_manager.ensure_connected():
            # Connection failed, update status and remove manager
            endpoint.connection_status = "error"
            self.db.save_endpoint(endpoint)
            if endpoint.id in self.ftp_managers:
                del self.ftp_managers[endpoint.id]
            raise Exception(f"Lost connection to endpoint '{endpoint.name}'. Please reconnect.")
        
        operations = []
        
        if sync_direction in ["ftp_to_local", "bidirectional"]:
            # Scan FTP to Local operations using safer iterative method
            print(f"Scanning {endpoint.remote_path} for sync operations...")
            # Use configurable max_files limit from settings
            max_files_limit = getattr(self, 'scan_config', {}).get('ftp_max_files', 500000) if hasattr(self, 'scan_config') else 500000
            print(f"FTP scan limit: {max_files_limit} files")
            ftp_files = ftp_manager.list_files_iterative(endpoint.remote_path, max_files=max_files_limit)

            # Apply folder filtering if enabled (will be set by GUI)
            if hasattr(endpoint, 'folder_filter_enabled') and endpoint.folder_filter_enabled:
                folder_names = getattr(endpoint, 'folder_names', [])
                match_mode = getattr(endpoint, 'folder_match_mode', 'exact')
                case_sensitive = getattr(endpoint, 'folder_case_sensitive', False)
                ftp_files = ftp_manager.apply_folder_filter(ftp_files, folder_names, match_mode, case_sensitive)
            
            for ftp_file in ftp_files:
                ftp_path = ftp_file['path']
                
                # Calculate local path
                rel_path = os.path.relpath(ftp_path, endpoint.remote_path)
                if rel_path.startswith('..'):
                    rel_path = ftp_path.lstrip('/')
                
                local_path = os.path.join(endpoint.local_path, rel_path.replace('/', os.sep))
                
                # Determine operation
                operation_type = self._should_sync_file(
                    ftp_path, local_path, ftp_file['modified'], ftp_file['size'],
                    sync_direction, endpoint.is_main_source, force_overwrite
                )
                
                local_mtime = None
                if os.path.exists(local_path):
                    local_stat = os.stat(local_path)
                    local_mtime = datetime.fromtimestamp(local_stat.st_mtime)
                
                operations.append(FTPFileInfo(
                    ftp_path=ftp_path,
                    local_path=local_path,
                    operation_type=operation_type,
                    file_size=ftp_file['size'],
                    ftp_modified=ftp_file['modified'],
                    local_modified=local_mtime,
                    endpoint_id=endpoint.id
                ))

        # For bidirectional sync, also scan Local to FTP operations
        if sync_direction in ["local_to_ftp", "bidirectional"]:
            print(f"Scanning {endpoint.local_path} for upload operations...")

            # Scan local directory
            local_files = []
            for root, dirs, files in os.walk(endpoint.local_path):
                for file in files:
                    local_file_path = os.path.join(root, file)
                    try:
                        stat_info = os.stat(local_file_path)
                        local_files.append({
                            'path': local_file_path,
                            'size': stat_info.st_size,
                            'modified': datetime.fromtimestamp(stat_info.st_mtime)
                        })
                    except (OSError, IOError):
                        continue  # Skip files we can't access

            # Apply folder filtering if enabled
            if hasattr(endpoint, 'folder_filter_enabled') and endpoint.folder_filter_enabled:
                folder_names = getattr(endpoint, 'folder_names', [])
                match_mode = getattr(endpoint, 'folder_match_mode', 'exact')
                case_sensitive = getattr(endpoint, 'folder_case_sensitive', False)

                filtered_files = []
                for local_file in local_files:
                    rel_path = os.path.relpath(local_file['path'], endpoint.local_path)
                    folder_path = os.path.dirname(rel_path)

                    should_include = False
                    if not folder_names:  # No filter specified
                        should_include = True
                    else:
                        for folder_name in folder_names:
                            if match_mode == 'exact':
                                if case_sensitive:
                                    should_include = folder_path == folder_name
                                else:
                                    should_include = folder_path.lower() == folder_name.lower()
                            elif match_mode == 'contains':
                                if case_sensitive:
                                    should_include = folder_name in folder_path
                                else:
                                    should_include = folder_name.lower() in folder_path.lower()
                            elif match_mode == 'startswith':
                                if case_sensitive:
                                    should_include = folder_path.startswith(folder_name)
                                else:
                                    should_include = folder_path.lower().startswith(folder_name.lower())

                            if should_include:
                                break

                    if should_include:
                        filtered_files.append(local_file)

                local_files = filtered_files

            # Process local files for upload operations
            for local_file in local_files:
                local_path = local_file['path']

                # Calculate FTP path
                rel_path = os.path.relpath(local_path, endpoint.local_path)
                ftp_path = endpoint.remote_path.rstrip('/') + '/' + rel_path.replace(os.sep, '/')

                # Skip if we already have this file from FTP scan (avoid duplicates in bidirectional)
                if sync_direction == "bidirectional":
                    existing = any(op.ftp_path == ftp_path for op in operations)
                    if existing:
                        continue

                # Get FTP file info if it exists
                ftp_modified = None
                ftp_size = None
                try:
                    ftp_info = ftp_manager.get_file_info(ftp_path)
                    if ftp_info:
                        ftp_modified = ftp_info.get('modified')
                        ftp_size = ftp_info.get('size')
                except:
                    pass  # FTP file doesn't exist or can't access

                # Determine operation (reverse the logic for local→ftp)
                operation_type = self._should_sync_file_reverse(
                    local_path, ftp_path, local_file['modified'], local_file['size'],
                    ftp_modified, ftp_size, sync_direction, endpoint.is_main_source, force_overwrite
                )

                if operation_type != "skip":
                    operations.append(FTPFileInfo(
                        ftp_path=ftp_path,
                        local_path=local_path,
                        operation_type=operation_type,
                        file_size=local_file['size'],
                        ftp_modified=ftp_modified,
                        local_modified=local_file['modified'],
                        endpoint_id=endpoint.id
                    ))

        return operations
    
    def _should_sync_file(self, ftp_path: str, local_path: str, ftp_modified: datetime,
                         ftp_size: int, sync_direction: str, ftp_is_main: bool, force_overwrite: bool = False) -> str:
        """Determine if file should be synced and how

        Args:
            force_overwrite: If True, always download/upload regardless of modification dates
        """

        # Force overwrite mode: always sync based on direction
        if force_overwrite:
            if sync_direction == "ftp_to_local":
                return "download"
            elif sync_direction == "local_to_ftp":
                return "upload"
            elif sync_direction == "bidirectional":
                # In bidirectional mode with force, prefer FTP if it's main source
                return "download" if ftp_is_main else "upload"

        if not os.path.exists(local_path):
            return "download"

        local_stat = os.stat(local_path)
        local_mtime = datetime.fromtimestamp(local_stat.st_mtime)

        # Compare modifications
        if ftp_modified > local_mtime:
            if ftp_is_main or sync_direction == "ftp_to_local":
                return "download"
            else:
                return "conflict"
        elif local_mtime > ftp_modified:
            if not ftp_is_main and sync_direction in ["local_to_ftp", "bidirectional"]:
                return "upload"
            elif ftp_is_main:
                return "skip"
            else:
                return "conflict"

        # Same modification time, check size
        if ftp_size != local_stat.st_size:
            if ftp_is_main:
                return "download"
            else:
                return "conflict"

        return "skip"

    def _should_sync_file_reverse(self, local_path: str, ftp_path: str, local_modified: datetime,
                                 local_size: int, ftp_modified: datetime, ftp_size: int,
                                 sync_direction: str, ftp_is_main: bool, force_overwrite: bool = False) -> str:
        """Determine if local file should be uploaded to FTP (reverse of _should_sync_file)

        Args:
            force_overwrite: If True, always upload regardless of modification dates
        """

        # Force overwrite mode: always sync based on direction
        if force_overwrite:
            if sync_direction == "local_to_ftp":
                return "upload"
            elif sync_direction == "bidirectional":
                # In bidirectional mode with force, prefer local if FTP is not main source
                return "upload" if not ftp_is_main else "download"

        # If FTP file doesn't exist, upload
        if ftp_modified is None:
            return "upload"

        # Compare modifications
        if local_modified > ftp_modified:
            if not ftp_is_main and sync_direction in ["local_to_ftp", "bidirectional"]:
                return "upload"
            elif ftp_is_main:
                return "skip"
            else:
                return "conflict"
        elif ftp_modified > local_modified:
            if ftp_is_main or sync_direction == "ftp_to_local":
                return "skip"  # Don't upload older file
            else:
                return "conflict"

        # Same modification time, check size
        if ftp_size is not None and local_size != ftp_size:
            if not ftp_is_main:
                return "upload"
            else:
                return "skip"

        return "skip"

    def sync_file(self, endpoint: FTPEndpoint, file_info: FTPFileInfo, sync_direction: str) -> tuple:
        """Sync a single file"""
        try:
            ftp_manager = self.ftp_managers[endpoint.id]
            
            if file_info.operation_type == "download":
                success = ftp_manager.download_file(file_info.ftp_path, file_info.local_path)
                
                if success:
                    # Set modification time to match FTP
                    timestamp = file_info.ftp_modified.timestamp()
                    os.utime(file_info.local_path, (timestamp, timestamp))
                
            elif file_info.operation_type == "upload":
                success = ftp_manager.upload_file(file_info.local_path, file_info.ftp_path)
            
            else:
                success = True  # Skip operations
            
            if success:
                self.db.log_operation(endpoint.id, file_info, sync_direction, True)
            else:
                self.db.log_operation(endpoint.id, file_info, sync_direction, False, "Sync failed")
            
            return success, "" if success else "Sync operation failed"
            
        except Exception as e:
            error_msg = str(e)
            self.db.log_operation(endpoint.id, file_info, sync_direction, False, error_msg)
            return False, error_msg

def create_tray_icon():
    """Create system tray icon"""
    if not pystray:
        return None
    image = Image.new('RGB', (64, 64), color='blue')
    draw = ImageDraw.Draw(image)
    draw.rectangle([8, 8, 56, 56], fill='white')
    draw.text((15, 20), "F2L", fill='blue')
    return image

class F2LGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("F2L - FTP to Local Multi-Endpoint Sync")
        self.root.geometry("1200x800")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.ftp_sync = FTPSync()
        self.operations = []
        self.is_syncing = False
        self.sync_thread = None
        self.progress_queue = queue.Queue()

        # Current selected endpoint
        self.current_endpoint = None
        self.endpoints = []

        # System tray
        self.tray_icon = None
        self.is_hidden = False

        # Initialize local sync scheduling (must be before UI setup)
        self.local_schedule_active = False
        self.local_schedule_thread = None
        self.local_next_sync_time = None

        # Scan performance settings
        # Scan configuration with defaults
        self.scan_config = {
            # Local scan settings
            "local_max_workers": 8,           # Thread pool size for local scanning (1-16)
            "local_parallel_enabled": True,   # Enable parallel local scanning
            "cache_enabled": True,            # Enable result caching
            "cache_duration": 300,            # Cache duration in seconds (5 minutes default)
            "progress_updates": True,         # Real-time progress
            "early_filtering": False,         # Filter during scan (DISABLED - causes issues)
            "max_depth": 50,                  # Prevent infinite recursion
            "chunk_size": 500,                # Files per progress update

            # FTP scan settings
            "ftp_max_files": 500000,          # Maximum files to scan from FTP (100k to 1M)
            "ftp_smart_filter": True,         # Use smart folder-first scanning when filter enabled
            "ftp_show_warnings": True,        # Show warning when limits reached

            # Memory optimization
            "memory_efficient": True,         # Use streaming/chunked processing
            "max_memory_mb": 512,            # Maximum memory usage in MB
        }

        # Load saved settings from database
        self.load_scan_settings()

        # Initialize directory scan cache with configured duration
        self.scan_cache = DirectoryScanCache(max_age_seconds=self.scan_config["cache_duration"])

        # Multi-session manager variables
        self.session_configs = {}  # Store session configurations
        self.active_sessions = {}  # Store active session threads
        self.session_schedulers = {}  # Store session schedulers

        # Initialize log manager
        self.log_manager = LogManager()
        self.log_window = None  # Will hold the log viewer window

        print("Setting up UI...")
        self.setup_ui()
        print("UI setup complete!")
        if pystray:
            self.setup_tray()
        self.load_endpoints()
        self.ftp_sync.start_health_monitoring()
        self.check_progress_queue()

        # Auto-start sessions after UI is ready
        self.root.after(2000, self.auto_start_sessions)  # Delay 2 seconds for UI to stabilize
    
    def setup_tray(self):
        """Setup system tray icon"""
        if not pystray:
            return
            
        icon_image = create_tray_icon()
        
        menu = pystray.Menu(
            pystray.MenuItem("Show F2L", self.show_window, default=True),
            pystray.MenuItem("Hide F2L", self.hide_window),
            pystray.MenuItem("Health Check All", self.tray_health_check_all),
            pystray.MenuItem("Quit F2L", self.quit_app)
        )
        
        self.tray_icon = pystray.Icon("F2L", icon_image, "F2L Multi-Endpoint Sync", menu)
        
        # Start tray icon in separate thread
        tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
        tray_thread.start()

    def show_window(self, icon=None, item=None):
        """Show main window"""
        self.root.deiconify()
        self.root.lift()
        self.is_hidden = False
    
    def hide_window(self, icon=None, item=None):
        """Hide window to system tray"""
        self.root.withdraw()
        self.is_hidden = True
    
    def on_closing(self):
        """Handle window close event"""
        if pystray:
            self.hide_window()
        else:
            self.quit_app()
    
    def quit_app(self, icon=None, item=None):
        """Quit application completely with proper cleanup"""
        print("Shutting down F2L application...")

        # Remove lock file
        lock_file = "f2l_app.lock"
        if os.path.exists(lock_file):
            try:
                os.remove(lock_file)
                print("Lock file removed.")
            except Exception as e:
                print(f"Error removing lock file: {e}")

        # Stop health monitoring
        self.ftp_sync.stop_health_monitoring()

        # Stop local scheduled sync
        if hasattr(self, 'local_schedule_active') and self.local_schedule_active:
            self.local_schedule_active = False
            print("Stopped local scheduled sync")

        # Save scan cache
        if hasattr(self, 'scan_cache'):
            self.scan_cache.save_cache()
            print("Saved directory scan cache")

        # Disconnect from all endpoints
        try:
            print("Disconnecting from all FTP endpoints...")
            results = self.ftp_sync.disconnect_all_endpoints()
            print(f"Cleanup complete: {results['successful']}/{results['total']} endpoints disconnected")
        except Exception as e:
            print(f"Error during FTP cleanup: {e}")

        # Stop tray icon
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except:
                pass

        print("F2L application shutdown complete")
        self.root.quit()
        sys.exit()
    
    def tray_health_check_all(self, icon=None, item=None):
        """Perform health check on all endpoints from tray"""
        threading.Thread(target=self._perform_all_health_checks, daemon=True).start()
    
    def _perform_all_health_checks(self):
        """Background health check for all endpoints"""
        healthy_count = 0
        total_count = len(self.endpoints)
        
        for endpoint in self.endpoints:
            success, message, file_count = self.ftp_sync.test_endpoint_connection(endpoint)
            if success:
                healthy_count += 1
        
        # Show tray notification
        if self.tray_icon:
            try:
                self.tray_icon.notify(
                    f"Health Check: {healthy_count}/{total_count} endpoints healthy",
                    "F2L Health Check"
                )
            except:
                pass
    
    def setup_ui(self):
        print("  - Creating notebook...")
        # Create notebook for tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        print("  - Setting up Endpoints tab...")
        # Endpoints management tab
        self.setup_endpoints_tab(notebook)

        print("  - Setting up Sync operations tab...")
        # Sync operations tab
        self.setup_sync_tab(notebook)

        print("  - Setting up Local sync tab...")
        # Local sync tab
        self.setup_local_sync_tab(notebook)

        print("  - Setting up Multi-session manager tab...")
        # Multi-session manager tab (Local)
        self.setup_multi_session_tab(notebook)

        print("  - Setting up FTP Multi-session manager tab...")
        # FTP Multi-session manager tab
        self.setup_ftp_multi_session_tab(notebook)

        print("  - Setting up Reports tab...")
        # Reports tab
        self.setup_reports_tab(notebook)

        print("  - Setting up Settings tab...")
        # Settings tab
        self.setup_settings_tab(notebook)
    
    def setup_endpoints_tab(self, notebook):
        endpoints_frame = ttk.Frame(notebook)
        notebook.add(endpoints_frame, text="FTP Endpoints")
        
        # Toolbar
        toolbar_frame = ttk.Frame(endpoints_frame)
        toolbar_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(toolbar_frame, text="Add Endpoint", command=self.add_endpoint_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar_frame, text="Edit Endpoint", command=self.edit_endpoint_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar_frame, text="Delete Endpoint", command=self.delete_endpoint).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar_frame, text="Connect", command=self.connect_selected_endpoint).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar_frame, text="Test Connection", command=self.test_selected_endpoint).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar_frame, text="Disconnect", command=self.disconnect_selected_endpoint).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar_frame, text="Diagnose Issues", command=self.diagnose_selected_endpoint).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar_frame, text="Health Check All", command=self.health_check_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar_frame, text="Disconnect All", command=self.disconnect_all_endpoints_gui).pack(side=tk.LEFT, padx=5)

        # Health monitoring control
        self.health_monitor_button = ttk.Button(toolbar_frame, text="Pause Health Monitor", command=self.toggle_health_monitoring)
        self.health_monitor_button.pack(side=tk.RIGHT, padx=5)
        
        if pystray:
            ttk.Button(toolbar_frame, text="Hide to Tray", command=self.hide_window).pack(side=tk.RIGHT, padx=5)
        
        # Endpoints list
        list_frame = ttk.LabelFrame(endpoints_frame, text="FTP Endpoints", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Treeview for endpoints
        columns = ('Name', 'Host', 'Remote Path', 'Local Path', 'Status', 'Last Check', 'Main Source', 'Auto Sync')
        self.endpoints_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=8)
        
        # Configure columns
        for col in columns:
            self.endpoints_tree.heading(col, text=col)
        
        self.endpoints_tree.column('Name', width=120)
        self.endpoints_tree.column('Host', width=120)
        self.endpoints_tree.column('Remote Path', width=100)
        self.endpoints_tree.column('Local Path', width=100)
        self.endpoints_tree.column('Status', width=80)
        self.endpoints_tree.column('Last Check', width=120)
        self.endpoints_tree.column('Main Source', width=80)
        self.endpoints_tree.column('Auto Sync', width=80)
        
        # Scrollbars
        endpoints_scrollbar_v = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.endpoints_tree.yview)
        endpoints_scrollbar_h = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL, command=self.endpoints_tree.xview)
        self.endpoints_tree.configure(yscrollcommand=endpoints_scrollbar_v.set, xscrollcommand=endpoints_scrollbar_h.set)
        
        self.endpoints_tree.grid(row=0, column=0, sticky='nsew')
        endpoints_scrollbar_v.grid(row=0, column=1, sticky='ns')
        endpoints_scrollbar_h.grid(row=1, column=0, sticky='ew')
        
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(0, weight=1)
        
        # Bind selection and context menu
        self.endpoints_tree.bind('<<TreeviewSelect>>', self.on_endpoint_select)
        self.endpoints_tree.bind('<Button-3>', self.show_endpoint_context_menu)  # Right-click
        
        # Connection status frame
        status_frame = ttk.LabelFrame(endpoints_frame, text="Connection Status", padding=10)
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.status_var = tk.StringVar(value="No endpoint selected")
        ttk.Label(status_frame, textvariable=self.status_var).pack(side=tk.LEFT)
    
    def setup_sync_tab(self, notebook):
        sync_frame = ttk.Frame(notebook)
        notebook.add(sync_frame, text="Sync Operations")
        
        # Endpoint selector
        selector_frame = ttk.LabelFrame(sync_frame, text="Select Endpoint & Direction", padding=10)
        selector_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Endpoint selection
        ttk.Label(selector_frame, text="Endpoint:").grid(row=0, column=0, sticky='w', padx=5)

        self.sync_endpoint_var = tk.StringVar()
        self.sync_endpoint_combo = ttk.Combobox(selector_frame, textvariable=self.sync_endpoint_var, state='readonly')
        self.sync_endpoint_combo.grid(row=0, column=1, sticky='ew', padx=5)

        # Sync direction
        ttk.Label(selector_frame, text="Direction:").grid(row=0, column=2, sticky='w', padx=5)

        self.sync_direction_var = tk.StringVar(value="ftp_to_local")
        direction_frame = ttk.Frame(selector_frame)
        direction_frame.grid(row=0, column=3, sticky='w', padx=5)

        ttk.Radiobutton(direction_frame, text="FTP → Local", variable=self.sync_direction_var,
                       value="ftp_to_local").pack(side=tk.LEFT)
        ttk.Radiobutton(direction_frame, text="Local → FTP", variable=self.sync_direction_var,
                       value="local_to_ftp").pack(side=tk.LEFT)
        ttk.Radiobutton(direction_frame, text="Bidirectional", variable=self.sync_direction_var,
                       value="bidirectional").pack(side=tk.LEFT)

        # Dry run option
        self.dry_run_var = tk.BooleanVar()
        ttk.Checkbutton(selector_frame, text="Dry Run", variable=self.dry_run_var).grid(row=0, column=4, padx=5)

        # Force overwrite option
        self.force_overwrite_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(selector_frame, text="Force Overwrite", variable=self.force_overwrite_var).grid(row=0, column=5, padx=5)

        selector_frame.grid_columnconfigure(1, weight=1)

        # Folder filtering section
        filter_frame = ttk.LabelFrame(sync_frame, text="Folder Filtering", padding=10)
        filter_frame.pack(fill=tk.X, padx=10, pady=5)

        # Enable folder filtering checkbox
        self.enable_folder_filter_var = tk.BooleanVar(value=False)
        filter_enable_frame = ttk.Frame(filter_frame)
        filter_enable_frame.pack(fill="x", pady=2)

        ttk.Checkbutton(filter_enable_frame, text="Enable specific folder sync",
                       variable=self.enable_folder_filter_var,
                       command=self.toggle_folder_filter).pack(side="left")

        # Help button
        ttk.Button(filter_enable_frame, text="?", width=3,
                  command=self.show_folder_filter_help).pack(side="right")

        # Folder names input
        folder_input_frame = ttk.Frame(filter_frame)
        folder_input_frame.pack(fill="x", pady=5)

        ttk.Label(folder_input_frame, text="Folder names (comma-separated):").pack(anchor="w")
        self.folder_names_var = tk.StringVar(value="hero, model, texture, anim")
        self.folder_names_entry = ttk.Entry(folder_input_frame, textvariable=self.folder_names_var)
        self.folder_names_entry.pack(fill="x", pady=2)

        # Add trace to clear cache when folder names change
        self.folder_names_var.trace('w', self.on_ftp_filter_change)

        # Match mode and options
        options_frame = ttk.Frame(filter_frame)
        options_frame.pack(fill="x", pady=2)

        # Match mode
        ttk.Label(options_frame, text="Match mode:").pack(side="left")
        self.folder_match_mode_var = tk.StringVar(value="exact")
        self.folder_exact_radio = ttk.Radiobutton(options_frame, text="Exact match", variable=self.folder_match_mode_var, value="exact",
                                                 command=self.on_ftp_filter_change)
        self.folder_exact_radio.pack(side="left", padx=10)
        self.folder_contains_radio = ttk.Radiobutton(options_frame, text="Contains", variable=self.folder_match_mode_var, value="contains",
                                                    command=self.on_ftp_filter_change)
        self.folder_contains_radio.pack(side="left", padx=10)

        # Case sensitivity
        self.case_sensitive_var = tk.BooleanVar(value=False)
        self.case_sensitive_check = ttk.Checkbutton(options_frame, text="Case sensitive", variable=self.case_sensitive_var,
                                                   command=self.on_ftp_filter_change)
        self.case_sensitive_check.pack(side="right", padx=10)

        # Initially disable folder filter controls
        self.toggle_folder_filter()

        # Control buttons
        control_frame = ttk.Frame(sync_frame)
        control_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(control_frame, text="Scan Operations", command=self.scan_operations).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Sync All", command=self.start_sync).pack(side=tk.LEFT, padx=5)
        self.sync_selected_btn = ttk.Button(control_frame, text="Sync Selected (0)",
                                           command=self.start_sync_selected, state='disabled')
        self.sync_selected_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Stop Sync", command=self.stop_sync).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="📋 View Logs", command=lambda: self.show_log_viewer()).pack(side=tk.LEFT, padx=5)

        # Progress
        progress_frame = ttk.LabelFrame(sync_frame, text="Progress", padding=10)
        progress_frame.pack(fill=tk.X, padx=10, pady=5)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=5)

        self.progress_status_var = tk.StringVar(value="Ready")
        ttk.Label(progress_frame, textvariable=self.progress_status_var).pack()

        # Operations list
        operations_frame = ttk.LabelFrame(sync_frame, text="Operations", padding=10)
        operations_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Search and Filter controls
        search_filter_frame = ttk.Frame(operations_frame)
        search_filter_frame.pack(fill=tk.X, pady=(0, 5))

        # Search box
        search_frame = ttk.Frame(search_filter_frame)
        search_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(search_frame, text="🔍 Search:").pack(side=tk.LEFT, padx=(0, 5))
        self.operations_search_var = tk.StringVar()
        self.operations_search_entry = ttk.Entry(search_frame, textvariable=self.operations_search_var, width=30)
        self.operations_search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.operations_search_var.trace('w', lambda *args: self.filter_operations())

        ttk.Button(search_frame, text="Clear", width=8,
                  command=lambda: self.operations_search_var.set("")).pack(side=tk.LEFT)

        # Filter controls
        filter_controls_frame = ttk.Frame(search_filter_frame)
        filter_controls_frame.pack(side=tk.LEFT, padx=(10, 0))

        ttk.Label(filter_controls_frame, text="Filter:").pack(side=tk.LEFT, padx=(0, 5))

        # Operation type filter
        self.operations_filter_type_var = tk.StringVar(value="All")
        operations_type_combo = ttk.Combobox(filter_controls_frame,
                                            textvariable=self.operations_filter_type_var,
                                            values=["All", "Download", "Upload", "Skip", "Conflict"],
                                            state='readonly', width=12)
        operations_type_combo.pack(side=tk.LEFT, padx=(0, 5))
        operations_type_combo.bind('<<ComboboxSelected>>', lambda e: self.filter_operations())

        # Size filter
        self.operations_filter_size_var = tk.StringVar(value="All Sizes")
        operations_size_combo = ttk.Combobox(filter_controls_frame,
                                            textvariable=self.operations_filter_size_var,
                                            values=["All Sizes", "<1 MB", "1-10 MB", "10-100 MB", ">100 MB"],
                                            state='readonly', width=12)
        operations_size_combo.pack(side=tk.LEFT, padx=(0, 5))
        operations_size_combo.bind('<<ComboboxSelected>>', lambda e: self.filter_operations())

        # Quick filter: Show only changes
        self.operations_show_changes_only_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(filter_controls_frame, text="Changes only",
                       variable=self.operations_show_changes_only_var,
                       command=self.filter_operations).pack(side=tk.LEFT, padx=(5, 0))

        # Operations count label
        self.operations_count_var = tk.StringVar(value="Operations: 0")
        ttk.Label(operations_frame, textvariable=self.operations_count_var,
                 font=('TkDefaultFont', 9)).pack(anchor='w', pady=(5, 5))

        # Selection controls
        selection_frame = ttk.Frame(operations_frame)
        selection_frame.pack(fill=tk.X, pady=(5, 5))

        ttk.Button(selection_frame, text="☑ Select All", width=12,
                  command=self.select_all_operations).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(selection_frame, text="☐ Select None", width=12,
                  command=self.select_none_operations).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(selection_frame, text="☑ Select Filtered", width=14,
                  command=self.select_filtered_operations).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(selection_frame, text="☑ Select Changes", width=14,
                  command=self.select_changes_operations).pack(side=tk.LEFT, padx=(0, 5))

        # Selection summary
        self.operations_selection_var = tk.StringVar(value="Selected: 0 files (0 B)")
        ttk.Label(selection_frame, textvariable=self.operations_selection_var,
                 font=('TkDefaultFont', 9, 'bold')).pack(side=tk.RIGHT)

        # Create a container frame for tree and scrollbars (using grid)
        tree_container = ttk.Frame(operations_frame)
        tree_container.pack(fill=tk.BOTH, expand=True)

        # Operations treeview with checkbox column (parent is tree_container)
        op_columns = ('☑', 'Operation', 'FTP Path', 'Local Path', 'Size', 'FTP Modified', 'Local Modified')
        self.operations_tree = ttk.Treeview(tree_container, columns=op_columns, show='headings', height=10)

        for col in op_columns:
            self.operations_tree.heading(col, text=col)

        self.operations_tree.column('☑', width=30, anchor='center')
        self.operations_tree.column('Operation', width=80)
        self.operations_tree.column('FTP Path', width=200)
        self.operations_tree.column('Local Path', width=200)
        self.operations_tree.column('Size', width=80)
        self.operations_tree.column('FTP Modified', width=120)
        self.operations_tree.column('Local Modified', width=120)

        # Bind click event for checkbox toggle
        self.operations_tree.bind('<Button-1>', self.on_operations_tree_click)

        # Scrollbars for operations
        op_scrollbar_v = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.operations_tree.yview)
        op_scrollbar_h = ttk.Scrollbar(tree_container, orient=tk.HORIZONTAL, command=self.operations_tree.xview)
        self.operations_tree.configure(yscrollcommand=op_scrollbar_v.set, xscrollcommand=op_scrollbar_h.set)

        # Use grid inside the container
        self.operations_tree.grid(row=0, column=0, sticky='nsew')
        op_scrollbar_v.grid(row=0, column=1, sticky='ns')
        op_scrollbar_h.grid(row=1, column=0, sticky='ew')

        tree_container.grid_columnconfigure(0, weight=1)
        tree_container.grid_rowconfigure(0, weight=1)

    def setup_reports_tab(self, notebook):
        """Setup reports and monitoring tab"""
        reports_frame = ttk.Frame(notebook)
        notebook.add(reports_frame, text="Reports & Monitoring")

        # Report controls
        control_frame = ttk.Frame(reports_frame)
        control_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(control_frame, text="Sync Report", command=self.generate_sync_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Health Report", command=self.generate_health_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Export Report", command=self.export_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Clear Logs", command=self.clear_logs).pack(side=tk.RIGHT, padx=5)

        # Report display
        report_frame = ttk.LabelFrame(reports_frame, text="Reports", padding=10)
        report_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.report_text = scrolledtext.ScrolledText(report_frame, height=15, font=('Courier', 9))
        self.report_text.pack(fill=tk.BOTH, expand=True)

        # Health monitoring log
        health_frame = ttk.LabelFrame(reports_frame, text="Health Monitor", padding=10)
        health_frame.pack(fill=tk.X, padx=10, pady=5)

        self.health_log = scrolledtext.ScrolledText(health_frame, height=8, font=('Courier', 9))
        self.health_log.pack(fill=tk.BOTH, expand=True)
        self.health_log.insert(tk.END, f"F2L Health Monitor Started - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    def setup_settings_tab(self, notebook):
        """Setup performance and scan settings tab"""
        # Create main frame for the tab
        settings_tab = ttk.Frame(notebook)
        notebook.add(settings_tab, text="⚙️ Settings")

        # Create canvas and scrollbar for scrollable content
        canvas = tk.Canvas(settings_tab, highlightthickness=0)
        scrollbar = ttk.Scrollbar(settings_tab, orient="vertical", command=canvas.yview)
        settings_frame = ttk.Frame(canvas)

        # Configure canvas scrolling
        settings_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=settings_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Enable mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Title
        title_frame = ttk.Frame(settings_frame)
        title_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(title_frame, text="Performance & Scan Settings",
                 font=('TkDefaultFont', 12, 'bold')).pack(anchor='w')
        ttk.Label(title_frame, text="Configure scanning performance, caching, and memory usage",
                 foreground='gray').pack(anchor='w')

        # ===== LOCAL SCAN SETTINGS =====
        local_frame = ttk.LabelFrame(settings_frame, text="Local Directory Scanning", padding=10)
        local_frame.pack(fill=tk.X, padx=10, pady=5)

        # Parallel scanning
        parallel_frame = ttk.Frame(local_frame)
        parallel_frame.pack(fill=tk.X, pady=5)

        self.settings_local_parallel_var = tk.BooleanVar(value=self.scan_config["local_parallel_enabled"])
        ttk.Checkbutton(parallel_frame, text="Enable Parallel Scanning",
                       variable=self.settings_local_parallel_var).pack(side=tk.LEFT)
        ttk.Label(parallel_frame, text="(Faster for large directories)",
                 foreground='gray', font=('TkDefaultFont', 8)).pack(side=tk.LEFT, padx=5)

        # Thread count
        workers_frame = ttk.Frame(local_frame)
        workers_frame.pack(fill=tk.X, pady=5)

        ttk.Label(workers_frame, text="Parallel Threads:").pack(side=tk.LEFT)
        self.settings_local_workers_var = tk.IntVar(value=self.scan_config["local_max_workers"])
        workers_spin = ttk.Spinbox(workers_frame, from_=1, to=16, width=10,
                                   textvariable=self.settings_local_workers_var)
        workers_spin.pack(side=tk.LEFT, padx=5)
        ttk.Label(workers_frame, text="(1-16 threads, recommended: 4-8)",
                 foreground='gray', font=('TkDefaultFont', 8)).pack(side=tk.LEFT)

        # ===== FTP SCAN SETTINGS =====
        ftp_frame = ttk.LabelFrame(settings_frame, text="FTP Scanning", padding=10)
        ftp_frame.pack(fill=tk.X, padx=10, pady=5)

        # Max files
        max_files_frame = ttk.Frame(ftp_frame)
        max_files_frame.pack(fill=tk.X, pady=5)

        ttk.Label(max_files_frame, text="Maximum Files to Scan:").pack(side=tk.LEFT)
        self.settings_ftp_max_files_var = tk.IntVar(value=self.scan_config["ftp_max_files"])
        max_files_spin = ttk.Spinbox(max_files_frame, from_=10000, to=2000000, increment=50000,
                                     width=15, textvariable=self.settings_ftp_max_files_var)
        max_files_spin.pack(side=tk.LEFT, padx=5)
        ttk.Label(max_files_frame, text="(10k - 2M files)",
                 foreground='gray', font=('TkDefaultFont', 8)).pack(side=tk.LEFT)

        # Smart filter
        smart_filter_frame = ttk.Frame(ftp_frame)
        smart_filter_frame.pack(fill=tk.X, pady=5)

        self.settings_ftp_smart_filter_var = tk.BooleanVar(value=self.scan_config["ftp_smart_filter"])
        ttk.Checkbutton(smart_filter_frame, text="Smart Folder-First Scanning",
                       variable=self.settings_ftp_smart_filter_var).pack(side=tk.LEFT)
        ttk.Label(smart_filter_frame, text="(Only scan filtered folders when filter enabled - much faster)",
                 foreground='gray', font=('TkDefaultFont', 8)).pack(side=tk.LEFT, padx=5)

        # Show warnings
        warnings_frame = ttk.Frame(ftp_frame)
        warnings_frame.pack(fill=tk.X, pady=5)

        self.settings_ftp_warnings_var = tk.BooleanVar(value=self.scan_config["ftp_show_warnings"])
        ttk.Checkbutton(warnings_frame, text="Show Warnings When Limits Reached",
                       variable=self.settings_ftp_warnings_var).pack(side=tk.LEFT)
        ttk.Label(warnings_frame, text="(Alert when file limit is hit)",
                 foreground='gray', font=('TkDefaultFont', 8)).pack(side=tk.LEFT, padx=5)

        # ===== CACHE SETTINGS =====
        cache_frame = ttk.LabelFrame(settings_frame, text="Scan Caching", padding=10)
        cache_frame.pack(fill=tk.X, padx=10, pady=5)

        # Enable cache
        cache_enable_frame = ttk.Frame(cache_frame)
        cache_enable_frame.pack(fill=tk.X, pady=5)

        self.settings_cache_enabled_var = tk.BooleanVar(value=self.scan_config["cache_enabled"])
        ttk.Checkbutton(cache_enable_frame, text="Enable Scan Result Caching",
                       variable=self.settings_cache_enabled_var).pack(side=tk.LEFT)
        ttk.Label(cache_enable_frame, text="(Reuse recent scan results for faster subsequent scans)",
                 foreground='gray', font=('TkDefaultFont', 8)).pack(side=tk.LEFT, padx=5)

        # Cache duration
        cache_duration_frame = ttk.Frame(cache_frame)
        cache_duration_frame.pack(fill=tk.X, pady=5)

        ttk.Label(cache_duration_frame, text="Cache Duration:").pack(side=tk.LEFT)
        self.settings_cache_duration_var = tk.IntVar(value=self.scan_config["cache_duration"])
        cache_duration_spin = ttk.Spinbox(cache_duration_frame, from_=60, to=3600, increment=60,
                                          width=10, textvariable=self.settings_cache_duration_var)
        cache_duration_spin.pack(side=tk.LEFT, padx=5)
        ttk.Label(cache_duration_frame, text="seconds (1-60 minutes)",
                 foreground='gray', font=('TkDefaultFont', 8)).pack(side=tk.LEFT)

        # Cache info
        cache_info_frame = ttk.Frame(cache_frame)
        cache_info_frame.pack(fill=tk.X, pady=5)
        ttk.Label(cache_info_frame, text="ℹ️ Cached scans are reused if directory hasn't changed",
                 foreground='blue', font=('TkDefaultFont', 8)).pack(anchor='w')

        # ===== MEMORY SETTINGS =====
        memory_frame = ttk.LabelFrame(settings_frame, text="Memory Optimization", padding=10)
        memory_frame.pack(fill=tk.X, padx=10, pady=5)

        # Memory efficient mode
        memory_efficient_frame = ttk.Frame(memory_frame)
        memory_efficient_frame.pack(fill=tk.X, pady=5)

        self.settings_memory_efficient_var = tk.BooleanVar(value=self.scan_config["memory_efficient"])
        ttk.Checkbutton(memory_efficient_frame, text="Memory-Efficient Mode",
                       variable=self.settings_memory_efficient_var).pack(side=tk.LEFT)
        ttk.Label(memory_efficient_frame, text="(Use streaming/chunked processing for large datasets)",
                 foreground='gray', font=('TkDefaultFont', 8)).pack(side=tk.LEFT, padx=5)

        # Max memory
        max_memory_frame = ttk.Frame(memory_frame)
        max_memory_frame.pack(fill=tk.X, pady=5)

        ttk.Label(max_memory_frame, text="Maximum Memory Usage:").pack(side=tk.LEFT)
        self.settings_max_memory_var = tk.IntVar(value=self.scan_config["max_memory_mb"])
        max_memory_spin = ttk.Spinbox(max_memory_frame, from_=128, to=4096, increment=128,
                                      width=10, textvariable=self.settings_max_memory_var)
        max_memory_spin.pack(side=tk.LEFT, padx=5)
        ttk.Label(max_memory_frame, text="MB (128 MB - 4 GB)",
                 foreground='gray', font=('TkDefaultFont', 8)).pack(side=tk.LEFT)

        # ===== ADVANCED SETTINGS =====
        advanced_frame = ttk.LabelFrame(settings_frame, text="Advanced Settings", padding=10)
        advanced_frame.pack(fill=tk.X, padx=10, pady=5)

        # Max depth
        max_depth_frame = ttk.Frame(advanced_frame)
        max_depth_frame.pack(fill=tk.X, pady=5)

        ttk.Label(max_depth_frame, text="Maximum Directory Depth:").pack(side=tk.LEFT)
        self.settings_max_depth_var = tk.IntVar(value=self.scan_config["max_depth"])
        max_depth_spin = ttk.Spinbox(max_depth_frame, from_=10, to=200, increment=10,
                                     width=10, textvariable=self.settings_max_depth_var)
        max_depth_spin.pack(side=tk.LEFT, padx=5)
        ttk.Label(max_depth_frame, text="(Prevent infinite recursion)",
                 foreground='gray', font=('TkDefaultFont', 8)).pack(side=tk.LEFT)

        # Chunk size
        chunk_size_frame = ttk.Frame(advanced_frame)
        chunk_size_frame.pack(fill=tk.X, pady=5)

        ttk.Label(chunk_size_frame, text="Progress Update Chunk Size:").pack(side=tk.LEFT)
        self.settings_chunk_size_var = tk.IntVar(value=self.scan_config["chunk_size"])
        chunk_size_spin = ttk.Spinbox(chunk_size_frame, from_=100, to=2000, increment=100,
                                      width=10, textvariable=self.settings_chunk_size_var)
        chunk_size_spin.pack(side=tk.LEFT, padx=5)
        ttk.Label(chunk_size_frame, text="files (100-2000)",
                 foreground='gray', font=('TkDefaultFont', 8)).pack(side=tk.LEFT)

        # ===== ACTION BUTTONS =====
        action_frame = ttk.Frame(settings_frame)
        action_frame.pack(fill=tk.X, padx=10, pady=20)

        ttk.Button(action_frame, text="💾 Save Settings",
                  command=self.apply_settings_from_ui).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="🔄 Reset to Defaults",
                  command=self.reset_scan_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="🗑️ Clear Cache",
                  command=self.clear_scan_cache).pack(side=tk.LEFT, padx=5)

        # ===== PERFORMANCE TIPS =====
        tips_frame = ttk.LabelFrame(settings_frame, text="💡 Performance Tips", padding=10)
        tips_frame.pack(fill=tk.X, padx=10, pady=5)

        tips_text = """• For filtered scans: Enable "Smart Folder-First Scanning" for 10-100x speed improvement
• For large directories: Increase parallel threads (4-8 recommended)
• For frequent scans: Enable caching with 5-10 minute duration
• For memory-constrained systems: Enable "Memory-Efficient Mode" and reduce max memory
• For very large FTP servers: Increase "Maximum Files to Scan" limit
• Cache is automatically cleared when directory structure changes"""

        ttk.Label(tips_frame, text=tips_text.strip(), justify=tk.LEFT,
                 foreground='#006400', font=('TkDefaultFont', 8)).pack(anchor='w')

        # ===== CURRENT STATUS =====
        status_frame = ttk.LabelFrame(settings_frame, text="Current Status", padding=10)
        status_frame.pack(fill=tk.X, padx=10, pady=5)

        self.settings_status_var = tk.StringVar(value="Settings loaded from database")
        ttk.Label(status_frame, textvariable=self.settings_status_var,
                 font=('TkDefaultFont', 9)).pack(anchor='w')

    def setup_ftp_multi_session_tab(self, notebook):
        """Setup FTP multi-session manager tab"""
        # Create main frame for the tab
        ftp_multi_tab = ttk.Frame(notebook)
        notebook.add(ftp_multi_tab, text="FTP Multi-Session")

        # Create canvas and scrollbar for scrollable content
        canvas = tk.Canvas(ftp_multi_tab, highlightthickness=0)
        scrollbar = ttk.Scrollbar(ftp_multi_tab, orient="vertical", command=canvas.yview)
        ftp_multi_frame = ttk.Frame(canvas)

        # Configure canvas scrolling
        ftp_multi_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=ftp_multi_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Enable mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Title and description
        title_frame = ttk.Frame(ftp_multi_frame)
        title_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(title_frame, text="FTP Multi-Session Manager",
                 font=('TkDefaultFont', 12, 'bold')).pack(anchor='w')
        ttk.Label(title_frame, text="Manage multiple FTP sync sessions with independent endpoints and folder filters",
                 foreground='gray').pack(anchor='w')

        # Control buttons
        control_frame = ttk.Frame(ftp_multi_frame)
        control_frame.pack(fill=tk.X, padx=10, pady=5)

        # Session management buttons
        ttk.Button(control_frame, text="➕ Add Session",
                  command=self.add_ftp_session).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="✏️ Edit Session",
                  command=self.edit_ftp_session).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="🗑️ Delete Session",
                  command=self.delete_ftp_session).pack(side=tk.LEFT, padx=5)

        ttk.Separator(control_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        # Individual session controls
        ttk.Button(control_frame, text="▶️ Start",
                  command=self.start_ftp_session).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="⏹️ Stop",
                  command=self.stop_ftp_session).pack(side=tk.LEFT, padx=5)

        ttk.Separator(control_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        # Batch controls
        ttk.Button(control_frame, text="▶️ Start All",
                  command=self.start_all_ftp_sessions).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="⏹️ Stop All",
                  command=self.stop_all_ftp_sessions).pack(side=tk.LEFT, padx=5)

        ttk.Separator(control_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        # Log viewer
        ttk.Button(control_frame, text="📋 Session Logs",
                  command=self.view_ftp_session_logs).pack(side=tk.LEFT, padx=5)

        # Sessions list
        sessions_frame = ttk.LabelFrame(ftp_multi_frame, text="FTP Sync Sessions", padding=10)
        sessions_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Create treeview for sessions
        columns = ("Name", "Endpoint", "Direction", "Filter", "Schedule", "Status", "Last Sync")
        self.ftp_sessions_tree = ttk.Treeview(sessions_frame, columns=columns, show="headings", height=10)

        # Configure columns
        self.ftp_sessions_tree.heading("Name", text="Session Name")
        self.ftp_sessions_tree.heading("Endpoint", text="FTP Endpoint")
        self.ftp_sessions_tree.heading("Direction", text="Direction")
        self.ftp_sessions_tree.heading("Filter", text="Folder Filter")
        self.ftp_sessions_tree.heading("Schedule", text="Schedule")
        self.ftp_sessions_tree.heading("Status", text="Status")
        self.ftp_sessions_tree.heading("Last Sync", text="Last Sync")

        self.ftp_sessions_tree.column("Name", width=150)
        self.ftp_sessions_tree.column("Endpoint", width=150)
        self.ftp_sessions_tree.column("Direction", width=100)
        self.ftp_sessions_tree.column("Filter", width=150)
        self.ftp_sessions_tree.column("Schedule", width=100)
        self.ftp_sessions_tree.column("Status", width=100)
        self.ftp_sessions_tree.column("Last Sync", width=150)

        # Add scrollbars (vertical and horizontal)
        ftp_sessions_scrollbar_v = ttk.Scrollbar(sessions_frame, orient="vertical",
                                                 command=self.ftp_sessions_tree.yview)
        ftp_sessions_scrollbar_h = ttk.Scrollbar(sessions_frame, orient="horizontal",
                                                 command=self.ftp_sessions_tree.xview)
        self.ftp_sessions_tree.configure(yscrollcommand=ftp_sessions_scrollbar_v.set,
                                         xscrollcommand=ftp_sessions_scrollbar_h.set)

        self.ftp_sessions_tree.grid(row=0, column=0, sticky='nsew')
        ftp_sessions_scrollbar_v.grid(row=0, column=1, sticky='ns')
        ftp_sessions_scrollbar_h.grid(row=1, column=0, sticky='ew')

        sessions_frame.grid_columnconfigure(0, weight=1)
        sessions_frame.grid_rowconfigure(0, weight=1)

        # Status bar
        status_frame = ttk.Frame(ftp_multi_frame)
        status_frame.pack(fill=tk.X, padx=10, pady=5)

        self.ftp_multi_status_var = tk.StringVar(value="Ready")
        ttk.Label(status_frame, textvariable=self.ftp_multi_status_var).pack(side=tk.LEFT)

        # Initialize FTP sessions storage
        self.ftp_sessions = {}
        self.ftp_session_threads = {}

        # Load existing sessions from database
        self.load_ftp_sessions()

    def scan_operations(self):
        """Scan for sync operations"""
        endpoint_name = self.sync_endpoint_var.get()
        if not endpoint_name:
            messagebox.showwarning("Warning", "Please select an endpoint first.")
            return

        # Find selected endpoint
        selected_endpoint = None
        for endpoint in self.endpoints:
            if f"{endpoint.name} ({endpoint.host})" == endpoint_name:
                selected_endpoint = endpoint
                break

        if not selected_endpoint:
            messagebox.showerror("Error", "Selected endpoint not found.")
            return

        # Check if endpoint is connected
        if selected_endpoint.connection_status != "connected":
            messagebox.showerror("Connection Required",
                               f"Endpoint '{selected_endpoint.name}' is not connected.\n\n"
                               f"Current status: {selected_endpoint.connection_status.title()}\n\n"
                               f"Please connect to the endpoint first before scanning operations.")
            return

        # Set folder filter settings on endpoint
        selected_endpoint.folder_filter_enabled = self.enable_folder_filter_var.get()
        if selected_endpoint.folder_filter_enabled:
            folder_names_text = self.folder_names_var.get()
            selected_endpoint.folder_names = [name.strip() for name in folder_names_text.split(',') if name.strip()]
            selected_endpoint.folder_match_mode = self.folder_match_mode_var.get()
            selected_endpoint.folder_case_sensitive = self.case_sensitive_var.get()

            print(f"Folder filtering enabled: {selected_endpoint.folder_names} (mode: {selected_endpoint.folder_match_mode})")
        else:
            print("Folder filtering disabled - scanning all folders")

        self.progress_status_var.set("Scanning operations...")
        self.progress_var.set(0)

        # Start scan in background thread
        scan_thread = threading.Thread(target=self.perform_scan, args=(selected_endpoint,), daemon=True)
        scan_thread.start()

    def perform_scan(self, endpoint):
        """Perform scan operation in background"""
        try:
            sync_direction = self.sync_direction_var.get()
            force_overwrite = self.force_overwrite_var.get()
            operations = self.ftp_sync.scan_endpoint(endpoint, sync_direction, force_overwrite)

            # Update UI in main thread
            self.root.after(0, self.show_scan_results, operations)

        except Exception as e:
            self.root.after(0, self.show_scan_error, str(e))

    def show_scan_results(self, operations):
        """Show scan results in operations tree"""
        self.operations = operations

        # Reset filters
        self.operations_search_var.set("")
        self.operations_filter_type_var.set("All")
        self.operations_filter_size_var.set("All Sizes")
        self.operations_show_changes_only_var.set(False)

        # Use filter method to display (handles all display logic)
        self.filter_operations()

        return  # filter_operations handles everything

        # Clear existing items
        for item in self.operations_tree.get_children():
            self.operations_tree.delete(item)

        # Add operations to tree
        download_count = upload_count = skip_count = conflict_count = 0

        for op in operations:
            local_modified_str = op.local_modified.strftime('%Y-%m-%d %H:%M:%S') if op.local_modified else "N/A"
            ftp_modified_str = op.ftp_modified.strftime('%Y-%m-%d %H:%M:%S')

            # Color code by operation type
            tags = []
            if op.operation_type == "download":
                tags = ["download"]
                download_count += 1
            elif op.operation_type == "upload":
                tags = ["upload"]
                upload_count += 1
            elif op.operation_type == "skip":
                tags = ["skip"]
                skip_count += 1
            elif op.operation_type == "conflict":
                tags = ["conflict"]
                conflict_count += 1

            self.operations_tree.insert('', 'end', values=(
                op.operation_type.title(),
                op.ftp_path,
                op.local_path,
                self.format_file_size(op.file_size),
                ftp_modified_str,
                local_modified_str
            ), tags=tags)

        # Configure tags for color coding
        self.operations_tree.tag_configure("download", background="#e8f5e8")
        self.operations_tree.tag_configure("upload", background="#e8e8f5")
        self.operations_tree.tag_configure("skip", background="#f5f5f5")
        self.operations_tree.tag_configure("conflict", background="#f5e8e8")

        # Update summary
        summary = f"Scan complete: {len(operations)} operations found"
        if download_count > 0:
            summary += f", {download_count} downloads"
        if upload_count > 0:
            summary += f", {upload_count} uploads"
        if skip_count > 0:
            summary += f", {skip_count} skipped"
        if conflict_count > 0:
            summary += f", {conflict_count} conflicts"

        self.progress_status_var.set(summary)
        self.progress_var.set(100)

    def show_scan_error(self, error_msg):
        """Show scan error"""
        self.progress_status_var.set("Scan failed")
        messagebox.showerror("Scan Error", f"Failed to scan operations: {error_msg}")

    def filter_operations(self):
        """Filter operations based on search and filter criteria"""
        if not hasattr(self, 'operations') or not self.operations:
            return

        # Get filter criteria
        search_text = self.operations_search_var.get().lower()
        filter_type = self.operations_filter_type_var.get()
        filter_size = self.operations_filter_size_var.get()
        changes_only = self.operations_show_changes_only_var.get()

        # Clear tree
        for item in self.operations_tree.get_children():
            self.operations_tree.delete(item)

        # Filter and display operations
        filtered_count = 0
        download_count = upload_count = skip_count = conflict_count = 0

        for op in self.operations:
            # Apply filters
            # Search filter
            if search_text:
                if (search_text not in op.ftp_path.lower() and
                    search_text not in op.local_path.lower() and
                    search_text not in os.path.basename(op.ftp_path).lower()):
                    continue

            # Type filter
            if filter_type != "All":
                if op.operation_type.lower() != filter_type.lower():
                    continue

            # Size filter
            if filter_size != "All Sizes":
                size_mb = op.file_size / (1024 * 1024)
                if filter_size == "<1 MB" and size_mb >= 1:
                    continue
                elif filter_size == "1-10 MB" and (size_mb < 1 or size_mb >= 10):
                    continue
                elif filter_size == "10-100 MB" and (size_mb < 10 or size_mb >= 100):
                    continue
                elif filter_size == ">100 MB" and size_mb < 100:
                    continue

            # Changes only filter
            if changes_only and op.operation_type == "skip":
                continue

            # Add to tree
            local_modified_str = op.local_modified.strftime('%Y-%m-%d %H:%M:%S') if op.local_modified else "N/A"
            ftp_modified_str = op.ftp_modified.strftime('%Y-%m-%d %H:%M:%S')

            tags = []
            if op.operation_type == "download":
                tags = ["download"]
                download_count += 1
            elif op.operation_type == "upload":
                tags = ["upload"]
                upload_count += 1
            elif op.operation_type == "skip":
                tags = ["skip"]
                skip_count += 1
            elif op.operation_type == "conflict":
                tags = ["conflict"]
                conflict_count += 1

            self.operations_tree.insert('', 'end', values=(
                '☐',  # Checkbox - unchecked by default
                op.operation_type.title(),
                op.ftp_path,
                op.local_path,
                self.format_file_size(op.file_size),
                ftp_modified_str,
                local_modified_str
            ), tags=tags)

            filtered_count += 1

        # Update count label
        total_count = len(self.operations)
        if filtered_count == total_count:
            self.operations_count_var.set(f"Operations: {total_count}")
        else:
            self.operations_count_var.set(f"Showing {filtered_count} of {total_count} operations")

        # Update status
        summary = f"Filtered: {filtered_count} operations"
        if download_count > 0:
            summary += f", {download_count} downloads"
        if upload_count > 0:
            summary += f", {upload_count} uploads"
        if skip_count > 0:
            summary += f", {skip_count} skipped"
        if conflict_count > 0:
            summary += f", {conflict_count} conflicts"

        self.progress_status_var.set(summary)

    def on_operations_tree_click(self, event):
        """Handle click on operations tree (for checkbox toggle)"""
        region = self.operations_tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self.operations_tree.identify_column(event.x)
            if column == '#1':  # Checkbox column
                item = self.operations_tree.identify_row(event.y)
                if item:
                    # Toggle selection
                    current_values = list(self.operations_tree.item(item, 'values'))
                    if current_values[0] == '☐':
                        current_values[0] = '☑'
                    else:
                        current_values[0] = '☐'
                    self.operations_tree.item(item, values=current_values)
                    self.update_selection_summary()

    def select_all_operations(self):
        """Select all operations in tree"""
        for item in self.operations_tree.get_children():
            values = list(self.operations_tree.item(item, 'values'))
            values[0] = '☑'
            self.operations_tree.item(item, values=values)
        self.update_selection_summary()

    def select_none_operations(self):
        """Deselect all operations"""
        for item in self.operations_tree.get_children():
            values = list(self.operations_tree.item(item, 'values'))
            values[0] = '☐'
            self.operations_tree.item(item, values=values)
        self.update_selection_summary()

    def select_filtered_operations(self):
        """Select all currently visible (filtered) operations"""
        for item in self.operations_tree.get_children():
            values = list(self.operations_tree.item(item, 'values'))
            values[0] = '☑'
            self.operations_tree.item(item, values=values)
        self.update_selection_summary()

    def select_changes_operations(self):
        """Select only operations that involve changes (not skip)"""
        for item in self.operations_tree.get_children():
            values = list(self.operations_tree.item(item, 'values'))
            operation_type = values[1].lower()  # Operation column
            if operation_type != 'skip':
                values[0] = '☑'
            else:
                values[0] = '☐'
            self.operations_tree.item(item, values=values)
        self.update_selection_summary()

    def update_selection_summary(self):
        """Update selection summary label"""
        selected_count = 0
        selected_size = 0

        for item in self.operations_tree.get_children():
            values = self.operations_tree.item(item, 'values')
            if values[0] == '☑':
                selected_count += 1
                # Parse size from string (e.g., "5.2 MB" -> bytes)
                size_str = values[4]  # Size column
                try:
                    if 'KB' in size_str:
                        selected_size += float(size_str.split()[0]) * 1024
                    elif 'MB' in size_str:
                        selected_size += float(size_str.split()[0]) * 1024 * 1024
                    elif 'GB' in size_str:
                        selected_size += float(size_str.split()[0]) * 1024 * 1024 * 1024
                    elif 'B' in size_str and 'KB' not in size_str and 'MB' not in size_str:
                        selected_size += float(size_str.split()[0])
                except:
                    pass

        # Update summary label
        size_formatted = self.format_file_size(int(selected_size))
        self.operations_selection_var.set(f"Selected: {selected_count} files ({size_formatted})")

        # Update "Sync Selected" button
        if selected_count > 0:
            self.sync_selected_btn.config(text=f"Sync Selected ({selected_count})", state='normal')
        else:
            self.sync_selected_btn.config(text="Sync Selected (0)", state='disabled')

    def get_selected_operations(self):
        """Get list of selected operations"""
        selected = []
        tree_items = self.operations_tree.get_children()

        for i, item in enumerate(tree_items):
            values = self.operations_tree.item(item, 'values')
            if values[0] == '☑' and i < len(self.operations):
                selected.append(self.operations[i])

        return selected

    def start_sync_selected(self):
        """Start sync with only selected operations"""
        selected_ops = self.get_selected_operations()

        if not selected_ops:
            messagebox.showwarning("Warning", "No operations selected.")
            return

        # Get selected endpoint
        endpoint_name = self.sync_endpoint_var.get()
        selected_endpoint = None
        for endpoint in self.endpoints:
            if f"{endpoint.name} ({endpoint.host})" == endpoint_name:
                selected_endpoint = endpoint
                break

        if not selected_endpoint:
            messagebox.showerror("Error", "Please select an endpoint.")
            return

        # Confirm sync
        response = messagebox.askyesno(
            "Confirm Sync",
            f"Sync {len(selected_ops)} selected operations?\n\n"
            f"Endpoint: {selected_endpoint.name}\n"
            f"Direction: {self.sync_direction_var.get()}"
        )

        if not response:
            return

        # Start sync with selected operations only
        self.is_syncing = True
        self.sync_thread = threading.Thread(
            target=self.perform_sync,
            args=(selected_endpoint, selected_ops),
            daemon=True
        )
        self.sync_thread.start()

    def start_sync(self):
        """Start sync operation"""
        if not self.operations:
            messagebox.showwarning("Warning", "Please scan operations first.")
            return
        
        # Get selected endpoint
        endpoint_name = self.sync_endpoint_var.get()
        selected_endpoint = None
        for endpoint in self.endpoints:
            if f"{endpoint.name} ({endpoint.host})" == endpoint_name:
                selected_endpoint = endpoint
                break
        
        if not selected_endpoint:
            messagebox.showerror("Error", "Selected endpoint not found.")
            return

        # Check if endpoint is still connected
        if selected_endpoint.connection_status != "connected":
            messagebox.showerror("Connection Required",
                               f"Endpoint '{selected_endpoint.name}' is not connected.\n\n"
                               f"Current status: {selected_endpoint.connection_status.title()}\n\n"
                               f"Please connect to the endpoint first before starting sync operations.")
            return

        # Filter operations to sync
        operations_to_sync = [op for op in self.operations if op.operation_type not in ["skip"]]
        
        if self.dry_run_var.get():
            messagebox.showinfo("Dry Run", 
                f"Dry run completed. {len(operations_to_sync)} operations would be performed.")
            return
        
        if not operations_to_sync:
            messagebox.showinfo("Sync", "No operations to perform - all files are up to date!")
            return
        
        self.is_syncing = True
        self.progress_status_var.set("Starting sync...")
        
        # Start sync thread
        self.sync_thread = threading.Thread(target=self.perform_sync, 
                                           args=(selected_endpoint, operations_to_sync), daemon=True)
        self.sync_thread.start()
    
    def perform_sync(self, endpoint, operations):
        """Perform sync operations"""
        session_id = self.ftp_sync.db.start_session(endpoint.id, self.sync_direction_var.get())
        
        stats = {
            'total': len(operations),
            'successful': 0,
            'failed': 0,
            'downloaded': 0,
            'uploaded': 0,
            'bytes_transferred': 0
        }
        
        try:
            for i, operation in enumerate(operations):
                if not self.is_syncing:  # Check if cancelled
                    break
                
                progress = ((i + 1) / len(operations)) * 100
                self.progress_queue.put(('progress', progress, f"Processing: {os.path.basename(operation.ftp_path)}"))
                
                # Perform sync operation
                success, error = self.ftp_sync.sync_file(endpoint, operation, self.sync_direction_var.get())
                
                if success:
                    stats['successful'] += 1
                    stats['bytes_transferred'] += operation.file_size
                    if operation.operation_type == "download":
                        stats['downloaded'] += 1
                    elif operation.operation_type == "upload":
                        stats['uploaded'] += 1
                else:
                    stats['failed'] += 1
                    print(f"Sync failed for {operation.ftp_path}: {error}")
        
        except Exception as e:
            self.progress_queue.put(('error', str(e)))
        finally:
            self.ftp_sync.db.end_session(session_id, stats)
            self.progress_queue.put(('complete', stats))
    
    def stop_sync(self):
        """Stop sync operation"""
        self.is_syncing = False
        self.progress_status_var.set("Stopping sync...")
    
    def check_progress_queue(self):
        """Check for progress updates from sync thread"""
        try:
            while True:
                msg_type, *args = self.progress_queue.get_nowait()
                
                if msg_type == 'progress':
                    progress, status = args
                    self.progress_var.set(progress)
                    self.progress_status_var.set(status)
                
                elif msg_type == 'error':
                    error_msg = args[0]
                    messagebox.showerror("Sync Error", error_msg)
                    self.is_syncing = False
                
                elif msg_type == 'complete':
                    stats = args[0]
                    self.progress_var.set(100)
                    self.progress_status_var.set(f"Sync complete! Success: {stats['successful']}, Failed: {stats['failed']}")
                    self.is_syncing = False
                    
                    # Log to health monitor
                    self.health_log.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} Sync completed: {stats['successful']} successful, {stats['failed']} failed\n")
                    self.health_log.see(tk.END)
                    
                    # Show tray notification if hidden
                    if self.is_hidden and TRAY_AVAILABLE:
                        try:
                            self.tray_icon.notify(f"Sync completed: {stats['successful']} files", "F2L Sync Complete")
                        except:
                            pass
                    
                    if not self.is_hidden:
                        messagebox.showinfo("Sync Complete", 
                                          f"Sync completed!\n\n"
                                          f"Total operations: {stats['total']}\n"
                                          f"Successful: {stats['successful']}\n"
                                          f"Failed: {stats['failed']}\n"
                                          f"Downloaded: {stats['downloaded']}\n"
                                          f"Uploaded: {stats['uploaded']}\n"
                                          f"Data transferred: {self.format_file_size(stats['bytes_transferred'])}")
        
        except queue.Empty:
            pass
        
        # Schedule next check
        self.root.after(100, self.check_progress_queue)
    
    # Utility methods
    def format_file_size(self, size_bytes):
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0 B"
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    # Endpoint management methods
    def load_endpoints(self):
        """Load endpoints from database"""
        self.endpoints = self.ftp_sync.get_endpoints()
        self.refresh_endpoints_tree()
        self.refresh_sync_endpoint_combo()

    def refresh_endpoints_tree(self):
        """Refresh the endpoints tree view with visual status indicators"""
        # Clear existing items
        for item in self.endpoints_tree.get_children():
            self.endpoints_tree.delete(item)

        # Add endpoints with status-based formatting
        for endpoint in self.endpoints:
            last_check = endpoint.last_health_check.strftime('%Y-%m-%d %H:%M:%S') if endpoint.last_health_check else "Never"

            # Add status icon to the status text
            status_text = endpoint.connection_status.title()
            if endpoint.connection_status == "connected":
                status_text = "🟢 Connected"
            elif endpoint.connection_status == "disconnected":
                status_text = "🔴 Disconnected"
            elif endpoint.connection_status == "connecting":
                status_text = "🟡 Connecting..."
            elif endpoint.connection_status == "disconnecting":
                status_text = "🟡 Disconnecting..."
            elif endpoint.connection_status == "error":
                status_text = "⚠️ Error"
            else:
                status_text = "⚪ Unknown"

            # Determine tags for color coding
            tags = []
            if endpoint.connection_status == "connected":
                tags = ["connected"]
            elif endpoint.connection_status == "disconnected":
                tags = ["disconnected"]
            elif endpoint.connection_status == "error":
                tags = ["error"]

            item_id = self.endpoints_tree.insert('', 'end', values=(
                endpoint.name,
                endpoint.host,
                endpoint.remote_path,
                endpoint.local_path,
                status_text,
                last_check,
                "Yes" if endpoint.is_main_source else "No",
                "Yes" if endpoint.auto_sync_enabled else "No"
            ), tags=tags)

        # Configure tags for visual feedback
        self.endpoints_tree.tag_configure("connected", background="#e8f5e8")  # Light green
        self.endpoints_tree.tag_configure("disconnected", background="#f5f5f5")  # Light gray
        self.endpoints_tree.tag_configure("error", background="#f5e8e8")  # Light red

    def refresh_sync_endpoint_combo(self):
        """Refresh sync endpoint combo box"""
        endpoint_names = [f"{ep.name} ({ep.host})" for ep in self.endpoints]
        self.sync_endpoint_combo['values'] = endpoint_names
        if endpoint_names and not self.sync_endpoint_var.get():
            self.sync_endpoint_var.set(endpoint_names[0])

    def on_endpoint_select(self, event):
        """Handle endpoint selection"""
        selection = self.endpoints_tree.selection()
        if selection:
            item = self.endpoints_tree.item(selection[0])
            endpoint_name = item['values'][0]

            # Find the endpoint
            for endpoint in self.endpoints:
                if endpoint.name == endpoint_name:
                    self.current_endpoint = endpoint
                    self.status_var.set(f"Selected: {endpoint.name} ({endpoint.host}:{endpoint.port}) - Status: {endpoint.connection_status}")
                    break
        else:
            self.current_endpoint = None
            self.status_var.set("No endpoint selected")

    def show_endpoint_context_menu(self, event):
        """Show context menu for endpoint operations"""
        # Select the item under cursor
        item = self.endpoints_tree.identify_row(event.y)
        if item:
            self.endpoints_tree.selection_set(item)
            self.on_endpoint_select(None)  # Update current_endpoint

            if self.current_endpoint:
                # Create context menu
                context_menu = tk.Menu(self.root, tearoff=0)

                # Add menu items based on connection status
                if self.current_endpoint.connection_status == "connected":
                    context_menu.add_command(label="🔌 Disconnect", command=self.disconnect_selected_endpoint)
                    context_menu.add_separator()
                elif self.current_endpoint.connection_status in ["disconnected", "error"]:
                    context_menu.add_command(label="🔗 Connect", command=self.connect_selected_endpoint)
                    context_menu.add_separator()

                context_menu.add_command(label="🔍 Test Connection", command=self.test_selected_endpoint)
                context_menu.add_command(label="🩺 Diagnose Issues", command=self.diagnose_selected_endpoint)
                context_menu.add_separator()
                context_menu.add_command(label="✏️ Edit Endpoint", command=self.edit_endpoint_dialog)
                context_menu.add_command(label="🗑️ Delete Endpoint", command=self.delete_endpoint)

                # Show context menu
                try:
                    context_menu.tk_popup(event.x_root, event.y_root)
                finally:
                    context_menu.grab_release()

    def add_endpoint_dialog(self):
        """Show add endpoint dialog"""
        self.endpoint_dialog(None)

    def edit_endpoint_dialog(self):
        """Show edit endpoint dialog"""
        if not self.current_endpoint:
            messagebox.showwarning("Warning", "Please select an endpoint to edit.")
            return
        self.endpoint_dialog(self.current_endpoint)

    def endpoint_dialog(self, endpoint=None):
        """Show endpoint configuration dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Endpoint" if endpoint is None else "Edit Endpoint")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

        # Form fields
        fields = {}

        # Name
        ttk.Label(dialog, text="Name:").grid(row=0, column=0, sticky='w', padx=10, pady=5)
        fields['name'] = tk.StringVar(value=endpoint.name if endpoint else "")
        ttk.Entry(dialog, textvariable=fields['name'], width=40).grid(row=0, column=1, padx=10, pady=5)

        # Host
        ttk.Label(dialog, text="Host:").grid(row=1, column=0, sticky='w', padx=10, pady=5)
        fields['host'] = tk.StringVar(value=endpoint.host if endpoint else "")
        ttk.Entry(dialog, textvariable=fields['host'], width=40).grid(row=1, column=1, padx=10, pady=5)

        # Port
        ttk.Label(dialog, text="Port:").grid(row=2, column=0, sticky='w', padx=10, pady=5)
        fields['port'] = tk.StringVar(value=str(endpoint.port) if endpoint else "21")
        ttk.Entry(dialog, textvariable=fields['port'], width=40).grid(row=2, column=1, padx=10, pady=5)

        # Username
        ttk.Label(dialog, text="Username:").grid(row=3, column=0, sticky='w', padx=10, pady=5)
        fields['username'] = tk.StringVar(value=endpoint.username if endpoint else "")
        ttk.Entry(dialog, textvariable=fields['username'], width=40).grid(row=3, column=1, padx=10, pady=5)

        # Password
        ttk.Label(dialog, text="Password:").grid(row=4, column=0, sticky='w', padx=10, pady=5)
        fields['password'] = tk.StringVar(value=endpoint.password if endpoint else "")
        ttk.Entry(dialog, textvariable=fields['password'], width=40, show="*").grid(row=4, column=1, padx=10, pady=5)

        # Remote path
        ttk.Label(dialog, text="Remote Path:").grid(row=5, column=0, sticky='w', padx=10, pady=5)
        fields['remote_path'] = tk.StringVar(value=endpoint.remote_path if endpoint else "/")
        ttk.Entry(dialog, textvariable=fields['remote_path'], width=40).grid(row=5, column=1, padx=10, pady=5)

        # Local path
        ttk.Label(dialog, text="Local Path:").grid(row=6, column=0, sticky='w', padx=10, pady=5)
        local_frame = ttk.Frame(dialog)
        local_frame.grid(row=6, column=1, padx=10, pady=5, sticky='ew')

        fields['local_path'] = tk.StringVar(value=endpoint.local_path if endpoint else "")
        ttk.Entry(local_frame, textvariable=fields['local_path'], width=30).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(local_frame, text="Browse", command=lambda: self.browse_local_path(fields['local_path'])).pack(side=tk.RIGHT, padx=(5, 0))

        # Options
        options_frame = ttk.LabelFrame(dialog, text="Options", padding=10)
        options_frame.grid(row=7, column=0, columnspan=2, padx=10, pady=10, sticky='ew')

        fields['is_main_source'] = tk.BooleanVar(value=endpoint.is_main_source if endpoint else True)
        ttk.Checkbutton(options_frame, text="Main Source (FTP is authoritative)", variable=fields['is_main_source']).pack(anchor='w')

        fields['auto_sync_enabled'] = tk.BooleanVar(value=endpoint.auto_sync_enabled if endpoint else False)
        ttk.Checkbutton(options_frame, text="Enable Auto Sync", variable=fields['auto_sync_enabled']).pack(anchor='w')

        sync_frame = ttk.Frame(options_frame)
        sync_frame.pack(fill='x', pady=5)
        ttk.Label(sync_frame, text="Sync Interval (minutes):").pack(side=tk.LEFT)
        fields['sync_interval'] = tk.StringVar(value=str(endpoint.sync_interval) if endpoint else "60")
        ttk.Entry(sync_frame, textvariable=fields['sync_interval'], width=10).pack(side=tk.RIGHT)

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=8, column=0, columnspan=2, pady=20)

        def save_endpoint():
            try:
                # Validate fields
                name = fields['name'].get().strip()
                host = fields['host'].get().strip()
                port = int(fields['port'].get())
                username = fields['username'].get().strip()
                password = fields['password'].get()
                remote_path = fields['remote_path'].get().strip()
                local_path = fields['local_path'].get().strip()
                sync_interval = int(fields['sync_interval'].get())

                if not all([name, host, username, remote_path, local_path]):
                    messagebox.showerror("Error", "Please fill in all required fields.")
                    return

                # Create or update endpoint
                if endpoint is None:
                    new_endpoint = FTPEndpoint(
                        id=str(uuid.uuid4()),
                        name=name,
                        host=host,
                        port=port,
                        username=username,
                        password=password,
                        remote_path=remote_path,
                        local_path=local_path,
                        is_main_source=fields['is_main_source'].get(),
                        auto_sync_enabled=fields['auto_sync_enabled'].get(),
                        sync_interval=sync_interval
                    )
                    self.ftp_sync.add_endpoint(new_endpoint)
                else:
                    endpoint.name = name
                    endpoint.host = host
                    endpoint.port = port
                    endpoint.username = username
                    endpoint.password = password
                    endpoint.remote_path = remote_path
                    endpoint.local_path = local_path
                    endpoint.is_main_source = fields['is_main_source'].get()
                    endpoint.auto_sync_enabled = fields['auto_sync_enabled'].get()
                    endpoint.sync_interval = sync_interval
                    self.ftp_sync.db.save_endpoint(endpoint)

                self.load_endpoints()
                dialog.destroy()
                messagebox.showinfo("Success", "Endpoint saved successfully!")

            except ValueError as e:
                messagebox.showerror("Error", "Please enter valid numeric values for port and sync interval.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save endpoint: {str(e)}")

        ttk.Button(button_frame, text="Save", command=save_endpoint).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        # Configure grid weights
        dialog.grid_columnconfigure(1, weight=1)
        local_frame.grid_columnconfigure(0, weight=1)

    def browse_local_path(self, path_var):
        """Browse for local path"""
        path = filedialog.askdirectory(title="Select Local Directory")
        if path:
            path_var.set(path)

    def delete_endpoint(self):
        """Delete selected endpoint"""
        if not self.current_endpoint:
            messagebox.showwarning("Warning", "Please select an endpoint to delete.")
            return

        if messagebox.askyesno("Confirm Delete", f"Delete endpoint '{self.current_endpoint.name}'?\n\nThis will also delete all associated sync history."):
            self.ftp_sync.remove_endpoint(self.current_endpoint.id)
            self.load_endpoints()
            self.current_endpoint = None
            self.status_var.set("No endpoint selected")
            messagebox.showinfo("Success", "Endpoint deleted successfully!")

    def test_selected_endpoint(self):
        """Test connection to selected endpoint"""
        if not self.current_endpoint:
            messagebox.showwarning("Warning", "Please select an endpoint to test.")
            return

        self.status_var.set("Testing connection...")

        # Test in background thread
        test_thread = threading.Thread(target=self.perform_connection_test, args=(self.current_endpoint,), daemon=True)
        test_thread.start()

    def perform_connection_test(self, endpoint):
        """Perform connection test in background"""
        success, message, file_count = self.ftp_sync.test_endpoint_connection(endpoint)

        # Update UI in main thread
        self.root.after(0, self.show_connection_test_result, endpoint, success, message, file_count)

    def show_connection_test_result(self, endpoint, success, message, file_count):
        """Show connection test result"""
        self.load_endpoints()  # Refresh to show updated status

        if success:
            messagebox.showinfo("Connection Test", f"{message}\n\nFiles found: {file_count}")
            self.status_var.set(f"Connection test successful - {file_count} files found")
        else:
            messagebox.showerror("Connection Test", message)
            self.status_var.set("Connection test failed")

    def health_check_all(self):
        """Perform health check on all endpoints"""
        if not self.endpoints:
            messagebox.showinfo("Health Check", "No endpoints configured.")
            return

        self.status_var.set("Performing health checks...")

        # Start health check in background
        health_thread = threading.Thread(target=self.perform_all_health_checks, daemon=True)
        health_thread.start()

    def perform_all_health_checks(self):
        """Perform health checks on all endpoints"""
        healthy_count = 0
        total_count = len(self.endpoints)

        for endpoint in self.endpoints:
            success, message, file_count = self.ftp_sync.test_endpoint_connection(endpoint)
            if success:
                healthy_count += 1

        # Update UI in main thread
        self.root.after(0, self.show_health_check_results, healthy_count, total_count)

    def show_health_check_results(self, healthy_count, total_count):
        """Show health check results"""
        self.load_endpoints()  # Refresh to show updated statuses

        message = f"Health Check Complete\n\n{healthy_count}/{total_count} endpoints are healthy"
        messagebox.showinfo("Health Check", message)
        self.status_var.set(f"Health check complete: {healthy_count}/{total_count} healthy")

        # Log to health monitor
        self.health_log.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} Health check: {healthy_count}/{total_count} endpoints healthy\n")
        self.health_log.see(tk.END)

    def diagnose_selected_endpoint(self):
        """Run diagnostics on selected endpoint"""
        if not self.current_endpoint:
            messagebox.showwarning("Warning", "Please select an endpoint to diagnose.")
            return

        self.status_var.set("Running diagnostics...")

        # Run diagnostics in background thread
        diag_thread = threading.Thread(target=self.perform_diagnostics, args=(self.current_endpoint,), daemon=True)
        diag_thread.start()

    def perform_diagnostics(self, endpoint):
        """Perform diagnostics in background"""
        try:
            diagnostics = self.ftp_sync.diagnose_connection_issues(endpoint)
            # Update UI in main thread
            self.root.after(0, self.show_diagnostics_result, diagnostics)
        except Exception as e:
            self.root.after(0, self.show_diagnostics_error, str(e))

    def show_diagnostics_result(self, diagnostics):
        """Show diagnostics result in a dialog"""
        self.status_var.set("Diagnostics complete")

        # Create diagnostics window
        diag_window = tk.Toplevel(self.root)
        diag_window.title("FTP Connection Diagnostics")
        diag_window.geometry("800x600")
        diag_window.transient(self.root)

        # Center the window
        diag_window.update_idletasks()
        x = (diag_window.winfo_screenwidth() // 2) - (diag_window.winfo_width() // 2)
        y = (diag_window.winfo_screenheight() // 2) - (diag_window.winfo_height() // 2)
        diag_window.geometry(f"+{x}+{y}")

        # Text widget with scrollbar
        text_frame = ttk.Frame(diag_window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        text_widget = scrolledtext.ScrolledText(text_frame, font=('Courier', 10))
        text_widget.pack(fill=tk.BOTH, expand=True)
        text_widget.insert(tk.END, diagnostics)
        text_widget.config(state=tk.DISABLED)

        # Buttons
        button_frame = ttk.Frame(diag_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        def copy_to_clipboard():
            diag_window.clipboard_clear()
            diag_window.clipboard_append(diagnostics)
            messagebox.showinfo("Copied", "Diagnostics copied to clipboard!")

        ttk.Button(button_frame, text="Copy to Clipboard", command=copy_to_clipboard).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=diag_window.destroy).pack(side=tk.RIGHT, padx=5)

    def show_diagnostics_error(self, error_msg):
        """Show diagnostics error"""
        self.status_var.set("Diagnostics failed")
        messagebox.showerror("Diagnostics Error", f"Failed to run diagnostics: {error_msg}")

    def disconnect_selected_endpoint(self):
        """Disconnect from selected endpoint"""
        if not self.current_endpoint:
            messagebox.showwarning("Warning", "Please select an endpoint to disconnect.")
            return

        # Check if endpoint is actually connected
        if self.current_endpoint.connection_status != "connected":
            messagebox.showinfo("Info", f"Endpoint '{self.current_endpoint.name}' is not currently connected.")
            return

        # Confirm disconnection
        if not messagebox.askyesno("Confirm Disconnect",
                                  f"Disconnect from '{self.current_endpoint.name}'?\n\n"
                                  f"Host: {self.current_endpoint.host}:{self.current_endpoint.port}"):
            return

        self.status_var.set("Disconnecting...")

        # Disconnect in background thread
        disconnect_thread = threading.Thread(target=self.perform_disconnect,
                                           args=(self.current_endpoint,), daemon=True)
        disconnect_thread.start()

    def perform_disconnect(self, endpoint):
        """Perform disconnect operation in background"""
        try:
            # Update status to show disconnecting in progress
            endpoint.connection_status = "disconnecting"
            self.root.after(0, self.load_endpoints)  # Refresh UI to show disconnecting status

            success, message = self.ftp_sync.disconnect_endpoint(endpoint)
            # Update UI in main thread
            self.root.after(0, self.show_disconnect_result, endpoint, success, message)
        except Exception as e:
            self.root.after(0, self.show_disconnect_error, endpoint, str(e))

    def show_disconnect_result(self, endpoint, success, message):
        """Show disconnect result"""
        self.load_endpoints()  # Refresh to show updated status

        if success:
            messagebox.showinfo("Disconnect Successful", message)
            self.status_var.set(f"Disconnected from {endpoint.name}")

            # Log to health monitor
            self.health_log.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} Disconnected from {endpoint.name}\n")
            self.health_log.see(tk.END)
        else:
            messagebox.showerror("Disconnect Failed", message)
            self.status_var.set("Disconnect failed")

    def show_disconnect_error(self, endpoint, error_msg):
        """Show disconnect error"""
        self.load_endpoints()  # Refresh to show updated status
        self.status_var.set("Disconnect error")
        messagebox.showerror("Disconnect Error", f"Error disconnecting from {endpoint.name}: {error_msg}")

    def disconnect_all_endpoints_gui(self):
        """Disconnect from all endpoints (GUI method)"""
        if not self.endpoints:
            messagebox.showinfo("Info", "No endpoints configured.")
            return

        # Count connected endpoints
        connected_endpoints = [ep for ep in self.endpoints if ep.connection_status == "connected"]

        if not connected_endpoints:
            messagebox.showinfo("Info", "No endpoints are currently connected.")
            return

        # Confirm disconnection
        if not messagebox.askyesno("Confirm Disconnect All",
                                  f"Disconnect from all {len(connected_endpoints)} connected endpoints?\n\n"
                                  f"This will close all active FTP connections."):
            return

        self.status_var.set("Disconnecting from all endpoints...")

        # Disconnect in background thread
        disconnect_all_thread = threading.Thread(target=self.perform_disconnect_all, daemon=True)
        disconnect_all_thread.start()

    def perform_disconnect_all(self):
        """Perform disconnect all operation in background"""
        try:
            results = self.ftp_sync.disconnect_all_endpoints()
            # Update UI in main thread
            self.root.after(0, self.show_disconnect_all_result, results)
        except Exception as e:
            self.root.after(0, self.show_disconnect_all_error, str(e))

    def show_disconnect_all_result(self, results):
        """Show disconnect all results"""
        self.load_endpoints()  # Refresh to show updated statuses

        message = f"Disconnect All Complete\n\n"
        message += f"Total endpoints: {results['total']}\n"
        message += f"Successfully disconnected: {results['successful']}\n"
        message += f"Failed: {results['failed']}\n"

        if results['errors']:
            message += f"\nErrors:\n"
            for error in results['errors']:
                message += f"• {error}\n"

        if results['failed'] > 0:
            messagebox.showwarning("Disconnect All Complete", message)
        else:
            messagebox.showinfo("Disconnect All Complete", message)

        self.status_var.set(f"Disconnected from {results['successful']}/{results['total']} endpoints")

        # Log to health monitor
        self.health_log.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} Disconnected from {results['successful']}/{results['total']} endpoints\n")
        self.health_log.see(tk.END)

    def show_disconnect_all_error(self, error_msg):
        """Show disconnect all error"""
        self.load_endpoints()  # Refresh to show updated statuses
        self.status_var.set("Disconnect all failed")
        messagebox.showerror("Disconnect All Error", f"Error during disconnect all: {error_msg}")

    def connect_selected_endpoint(self):
        """Manually connect to selected endpoint and maintain connection"""
        if not self.current_endpoint:
            messagebox.showwarning("Warning", "Please select an endpoint to connect.")
            return

        # Check if already connected
        if self.current_endpoint.connection_status == "connected":
            messagebox.showinfo("Info", f"Endpoint '{self.current_endpoint.name}' is already connected.")
            return

        self.status_var.set("Connecting...")

        # Connect in background thread
        connect_thread = threading.Thread(target=self.perform_connect,
                                         args=(self.current_endpoint,), daemon=True)
        connect_thread.start()

    def perform_connect(self, endpoint):
        """Perform connect operation in background and maintain connection"""
        try:
            # Update status to show connecting in progress
            endpoint.connection_status = "connecting"
            self.root.after(0, self.load_endpoints)  # Refresh UI to show connecting status

            # Get or create FTP manager
            if endpoint.id not in self.ftp_sync.ftp_managers:
                self.ftp_sync.ftp_managers[endpoint.id] = FTPManager(
                    endpoint.host, endpoint.username, endpoint.password, endpoint.port
                )

            ftp_manager = self.ftp_sync.ftp_managers[endpoint.id]

            # Attempt connection
            if ftp_manager.connect():
                # Test basic operations to ensure connection is working
                try:
                    current_dir = ftp_manager.ftp.pwd()
                    print(f"Connected to {endpoint.name}, current directory: {current_dir}")

                    # Test access to remote path
                    ftp_manager.ftp.cwd(endpoint.remote_path)
                    print(f"Successfully accessed remote path: {endpoint.remote_path}")

                    # OPTIONAL: File count test (disabled for faster health checks)
                    # Uncomment if you want to verify file access during health checks
                    # files = ftp_manager.list_files_iterative(endpoint.remote_path, max_files=1000)
                    # file_count = len(files)
                    # print(f"Health check: Found {file_count} files")

                    # Update endpoint status to connected
                    endpoint.connection_status = "connected"
                    endpoint.last_health_check = datetime.now()
                    self.ftp_sync.db.save_endpoint(endpoint)

                    print(f"✓ Health check passed for {endpoint.name}")

                    # Update UI in main thread
                    self.root.after(0, self.show_connect_result, endpoint, True,
                                  f"Successfully connected to {endpoint.host}", 0)

                except Exception as path_error:
                    # Connection succeeded but path access failed
                    ftp_manager.disconnect()
                    endpoint.connection_status = "error"
                    self.ftp_sync.db.save_endpoint(endpoint)

                    self.root.after(0, self.show_connect_result, endpoint, False,
                                  f"Connected but cannot access remote path '{endpoint.remote_path}': {str(path_error)}", 0)
            else:
                # Connection failed
                endpoint.connection_status = "error"
                self.ftp_sync.db.save_endpoint(endpoint)

                self.root.after(0, self.show_connect_result, endpoint, False,
                              f"Failed to connect to {endpoint.host}. Check credentials and network.", 0)

        except Exception as e:
            # Update status to error
            endpoint.connection_status = "error"
            self.ftp_sync.db.save_endpoint(endpoint)

            self.root.after(0, self.show_connect_error, endpoint, str(e))

    def show_connect_result(self, endpoint, success, message, file_count):
        """Show connect result"""
        self.load_endpoints()  # Refresh to show updated status

        if success:
            messagebox.showinfo("Connection Successful", f"{message}\n\nFiles found: {file_count}\n\nConnection is now active and will be maintained.")
            self.status_var.set(f"Connected to {endpoint.name} - {file_count} files found")

            # Log to health monitor
            self.health_log.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} Connected to {endpoint.name} ({file_count} files)\n")
            self.health_log.see(tk.END)
        else:
            messagebox.showerror("Connection Failed", message)
            self.status_var.set("Connection failed")

    def show_connect_error(self, endpoint, error_msg):
        """Show connect error"""
        self.load_endpoints()  # Refresh to show updated status
        self.status_var.set("Connection error")
        messagebox.showerror("Connection Error", f"Error connecting to {endpoint.name}: {error_msg}")

    def _show_startup_connection_results(self, connected_count, failed_count):
        """Show startup connection results"""
        self.load_endpoints()  # Refresh to show updated statuses

        total_count = connected_count + failed_count

        if connected_count > 0:
            self.status_var.set(f"Auto-connect complete: {connected_count}/{total_count} endpoints connected")

            # Log to health monitor
            self.health_log.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} Auto-connect: {connected_count}/{total_count} endpoints connected\n")
            self.health_log.see(tk.END)

            # Show notification if some failed
            if failed_count > 0:
                messagebox.showwarning("Auto-Connect Complete",
                                     f"Auto-connect completed with mixed results:\n\n"
                                     f"✅ Connected: {connected_count}\n"
                                     f"❌ Failed: {failed_count}\n\n"
                                     f"Check the endpoints list for details.")
            else:
                # Show success notification only if not hidden to tray
                if not self.is_hidden:
                    messagebox.showinfo("Auto-Connect Complete",
                                      f"Successfully connected to all {connected_count} endpoints!")
        else:
            self.status_var.set(f"Auto-connect failed: 0/{total_count} endpoints connected")
            messagebox.showerror("Auto-Connect Failed",
                               f"Failed to connect to any endpoints.\n\n"
                               f"Please check your endpoint configurations and network connectivity.")

    def connect_selected_endpoint(self):
        """Manually connect to selected endpoint"""
        if not self.current_endpoint:
            messagebox.showwarning("Warning", "Please select an endpoint to connect.")
            return

        # Check if already connected
        if self.current_endpoint.connection_status == "connected":
            messagebox.showinfo("Info", f"Endpoint '{self.current_endpoint.name}' is already connected.")
            return

        self.status_var.set("Connecting...")

        # Connect in background thread
        connect_thread = threading.Thread(target=self.perform_connect,
                                         args=(self.current_endpoint,), daemon=True)
        connect_thread.start()

    def perform_connect(self, endpoint):
        """Perform connect operation in background"""
        try:
            # Update status to show connecting in progress
            endpoint.connection_status = "connecting"
            self.root.after(0, self.load_endpoints)  # Refresh UI to show connecting status

            success, message, file_count = self.ftp_sync.test_endpoint_connection(endpoint)
            # Update UI in main thread
            self.root.after(0, self.show_connect_result, endpoint, success, message, file_count)
        except Exception as e:
            self.root.after(0, self.show_connect_error, endpoint, str(e))

    def show_connect_result(self, endpoint, success, message, file_count):
        """Show connect result"""
        self.load_endpoints()  # Refresh to show updated status

        if success:
            messagebox.showinfo("Connection Successful", f"{message}\n\nFiles found: {file_count}")
            self.status_var.set(f"Connected to {endpoint.name} - {file_count} files found")

            # Log to health monitor
            self.health_log.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} Connected to {endpoint.name} ({file_count} files)\n")
            self.health_log.see(tk.END)
        else:
            messagebox.showerror("Connection Failed", message)
            self.status_var.set("Connection failed")

    def show_connect_error(self, endpoint, error_msg):
        """Show connect error"""
        self.load_endpoints()  # Refresh to show updated status
        self.status_var.set("Connection error")
        messagebox.showerror("Connection Error", f"Error connecting to {endpoint.name}: {error_msg}")

    def toggle_health_monitoring(self):
        """Toggle health monitoring on/off"""
        if self.ftp_sync.health_check_running:
            # Stop health monitoring
            self.ftp_sync.stop_health_monitoring()
            self.health_monitor_button.config(text="Resume Health Monitor")
            self.status_var.set("Health monitoring paused")

            # Log to health monitor
            self.health_log.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} Health monitoring paused by user\n")
            self.health_log.see(tk.END)

            messagebox.showinfo("Health Monitor", "Health monitoring has been paused.\n\nEndpoints will not be automatically checked for connectivity.")
        else:
            # Start health monitoring
            self.ftp_sync.start_health_monitoring()
            self.health_monitor_button.config(text="Pause Health Monitor")
            self.status_var.set("Health monitoring resumed")

            # Log to health monitor
            self.health_log.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} Health monitoring resumed by user\n")
            self.health_log.see(tk.END)

            messagebox.showinfo("Health Monitor", "Health monitoring has been resumed.\n\nConnected endpoints will be automatically checked every 30 seconds.")

    def toggle_folder_filter(self):
        """Toggle folder filter controls"""
        enabled = self.enable_folder_filter_var.get()

        # Enable/disable folder filter controls
        state = "normal" if enabled else "disabled"

        try:
            # Enable/disable the folder names entry
            if hasattr(self, 'folder_names_entry'):
                self.folder_names_entry.config(state=state)

            # Enable/disable match mode radiobuttons
            if hasattr(self, 'folder_exact_radio'):
                self.folder_exact_radio.config(state=state)
            if hasattr(self, 'folder_contains_radio'):
                self.folder_contains_radio.config(state=state)

            # Enable/disable case sensitive checkbox
            if hasattr(self, 'case_sensitive_check'):
                self.case_sensitive_check.config(state=state)

            # IMPORTANT: Clear cache when filter settings change
            # This ensures fresh scan results when toggling filters
            if hasattr(self, 'scan_cache'):
                print("Clearing scan cache due to FTP filter toggle")
                self.scan_cache.cache = {}  # Clear all cached results

            # Clear current operations to force rescan
            if hasattr(self, 'operations'):
                self.operations = []
            if hasattr(self, 'operations_tree'):
                self.operations_tree.delete(*self.operations_tree.get_children())

        except Exception as e:
            print(f"Error toggling folder filter controls: {e}")

    def show_folder_filter_help(self):
        """Show help dialog for folder filtering"""
        help_text = """FOLDER FILTERING HELP

This feature allows you to sync only specific folders by name, making sync operations faster and more targeted.

HOW IT WORKS:
• Enter folder names separated by commas (e.g., "hero, model, texture")
• The application will search for folders with these names in the entire directory tree
• Only matching folders and their contents will be synchronized

MATCH MODES:
• Exact match: Folder name must match exactly (case-sensitive if enabled)
• Contains: Folder name must contain the specified text

EXAMPLES:
Source: /SWA/all/asset/Character/Main/AjayMechsuit/hero/mesh/high.fbx
Filter: "hero"
Result: Syncs to {local_path}\\SWA\\all\\asset\\Character\\Main\\AjayMechsuit\\hero\\mesh\\high.fbx

BENEFITS:
• Faster sync (only specific folders)
• Reduced network traffic
• Targeted synchronization
• Avoid syncing unwanted folders

TIPS:
• Use common folder names like "hero", "model", "texture", "anim"
• Case sensitivity matters for exact matches
• Use "Contains" mode for partial matches"""

        messagebox.showinfo("Folder Filtering Help", help_text)

    def setup_local_sync_tab(self, notebook):
        """Setup local-to-local directory synchronization tab"""
        # Create main frame for the tab
        local_sync_tab = ttk.Frame(notebook)
        notebook.add(local_sync_tab, text="Local Sync")

        # Create canvas and scrollbar for scrollable content
        canvas = tk.Canvas(local_sync_tab, highlightthickness=0)
        scrollbar = ttk.Scrollbar(local_sync_tab, orient="vertical", command=canvas.yview)
        local_sync_frame = ttk.Frame(canvas)

        # Configure canvas scrolling
        local_sync_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=local_sync_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Enable mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Directory selector
        dir_selector_frame = ttk.LabelFrame(local_sync_frame, text="Directory Selection", padding=10)
        dir_selector_frame.pack(fill=tk.X, padx=10, pady=5)

        # Source directory
        source_frame = ttk.Frame(dir_selector_frame)
        source_frame.pack(fill="x", pady=2)

        ttk.Label(source_frame, text="Source Directory:").pack(anchor="w")
        source_input_frame = ttk.Frame(source_frame)
        source_input_frame.pack(fill="x", pady=2)

        self.local_source_var = tk.StringVar()
        self.local_source_entry = ttk.Entry(source_input_frame, textvariable=self.local_source_var)
        self.local_source_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ttk.Button(source_input_frame, text="Browse", command=self.browse_source_directory).pack(side="right")

        # Destination directory
        dest_frame = ttk.Frame(dir_selector_frame)
        dest_frame.pack(fill="x", pady=2)

        ttk.Label(dest_frame, text="Destination Directory:").pack(anchor="w")
        dest_input_frame = ttk.Frame(dest_frame)
        dest_input_frame.pack(fill="x", pady=2)

        self.local_dest_var = tk.StringVar()
        self.local_dest_entry = ttk.Entry(dest_input_frame, textvariable=self.local_dest_var)
        self.local_dest_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ttk.Button(dest_input_frame, text="Browse", command=self.browse_dest_directory).pack(side="right")

        # Sync direction and options
        options_frame = ttk.LabelFrame(local_sync_frame, text="Sync Options", padding=10)
        options_frame.pack(fill=tk.X, padx=10, pady=5)

        # Sync direction
        direction_frame = ttk.Frame(options_frame)
        direction_frame.pack(fill="x", pady=2)

        ttk.Label(direction_frame, text="Direction:").pack(side="left")
        self.local_sync_direction_var = tk.StringVar(value="source_to_dest")
        ttk.Radiobutton(direction_frame, text="Source → Destination",
                       variable=self.local_sync_direction_var, value="source_to_dest").pack(side="left", padx=10)
        ttk.Radiobutton(direction_frame, text="Destination → Source",
                       variable=self.local_sync_direction_var, value="dest_to_source").pack(side="left", padx=10)
        ttk.Radiobutton(direction_frame, text="Bidirectional",
                       variable=self.local_sync_direction_var, value="bidirectional").pack(side="left", padx=10)

        # Dry run option
        self.local_dry_run_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Dry Run (preview only)",
                       variable=self.local_dry_run_var).pack(anchor="w", pady=2)

        # Force overwrite option
        self.local_force_overwrite_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Force Overwrite (copy all files)",
                       variable=self.local_force_overwrite_var).pack(anchor="w", pady=2)

        # Scheduled sync section
        schedule_frame = ttk.LabelFrame(local_sync_frame, text="Scheduled Sync", padding=10)
        schedule_frame.pack(fill=tk.X, padx=10, pady=5)

        # Enable scheduled sync
        self.local_enable_schedule_var = tk.BooleanVar(value=False)
        schedule_enable_frame = ttk.Frame(schedule_frame)
        schedule_enable_frame.pack(fill="x", pady=2)

        ttk.Checkbutton(schedule_enable_frame, text="Enable automatic sync",
                       variable=self.local_enable_schedule_var,
                       command=self.toggle_local_schedule).pack(side="left")

        # Schedule status
        self.local_schedule_status_var = tk.StringVar(value="Scheduled sync disabled")
        ttk.Label(schedule_enable_frame, textvariable=self.local_schedule_status_var,
                 foreground="gray").pack(side="right")

        # Interval settings
        interval_frame = ttk.Frame(schedule_frame)
        interval_frame.pack(fill="x", pady=5)

        ttk.Label(interval_frame, text="Sync every:").pack(side="left")

        self.local_interval_value_var = tk.StringVar(value="30")
        interval_spinbox = ttk.Spinbox(interval_frame, from_=1, to=999, width=5,
                                      textvariable=self.local_interval_value_var)
        interval_spinbox.pack(side="left", padx=5)

        self.local_interval_unit_var = tk.StringVar(value="minutes")
        interval_combo = ttk.Combobox(interval_frame, textvariable=self.local_interval_unit_var,
                                     values=["seconds", "minutes", "hours", "days"],
                                     state="readonly", width=10)
        interval_combo.pack(side="left", padx=5)

        # Enhanced Schedule Status Display (Phase 4)
        schedule_status_display = ttk.LabelFrame(schedule_frame, text="Schedule Status", padding=5)
        schedule_status_display.pack(fill="x", pady=5)

        # Status row
        status_row = ttk.Frame(schedule_status_display)
        status_row.pack(fill="x", pady=2)
        ttk.Label(status_row, text="Status:", font=('TkDefaultFont', 9, 'bold')).pack(side="left")
        self.local_schedule_state_icon_var = tk.StringVar(value="⏹️ Disabled")
        ttk.Label(status_row, textvariable=self.local_schedule_state_icon_var,
                 font=('TkDefaultFont', 9)).pack(side="left", padx=5)

        # Last run row
        last_run_row = ttk.Frame(schedule_status_display)
        last_run_row.pack(fill="x", pady=2)
        ttk.Label(last_run_row, text="Last run:", font=('TkDefaultFont', 9, 'bold')).pack(side="left")
        self.local_last_run_display_var = tk.StringVar(value="Never")
        ttk.Label(last_run_row, textvariable=self.local_last_run_display_var,
                 font=('TkDefaultFont', 9)).pack(side="left", padx=5)

        # Stats row
        stats_row = ttk.Frame(schedule_status_display)
        stats_row.pack(fill="x", pady=2)
        ttk.Label(stats_row, text="Today:", font=('TkDefaultFont', 9, 'bold')).pack(side="left")
        self.local_schedule_stats_var = tk.StringVar(value="0 runs | 0 files")
        ttk.Label(stats_row, textvariable=self.local_schedule_stats_var,
                 font=('TkDefaultFont', 9)).pack(side="left", padx=5)

        # Schedule controls
        schedule_controls_frame = ttk.Frame(schedule_frame)
        schedule_controls_frame.pack(fill="x", pady=5)

        self.local_start_schedule_btn = ttk.Button(schedule_controls_frame, text="▶️ Start Schedule",
                                                  command=self.start_local_schedule)
        self.local_start_schedule_btn.pack(side="left", padx=5)

        self.local_stop_schedule_btn = ttk.Button(schedule_controls_frame, text="⏹️ Stop Schedule",
                                                 command=self.stop_local_schedule)
        self.local_stop_schedule_btn.pack(side="left", padx=5)

        self.local_pause_schedule_btn = ttk.Button(schedule_controls_frame, text="⏸️ Pause",
                                                   command=self.pause_local_schedule, state='disabled')
        self.local_pause_schedule_btn.pack(side="left", padx=5)

        ttk.Button(schedule_controls_frame, text="▶️ Run Now",
                  command=self.run_local_schedule_now).pack(side="left", padx=5)

        # Next sync info (countdown timer)
        self.local_next_sync_var = tk.StringVar(value="")
        ttk.Label(schedule_controls_frame, textvariable=self.local_next_sync_var,
                 foreground="blue", font=('TkDefaultFont', 9, 'bold')).pack(side="right")

        # Schedule options
        schedule_options_frame = ttk.Frame(schedule_frame)
        schedule_options_frame.pack(fill="x", pady=2)

        self.local_auto_scan_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(schedule_options_frame, text="Auto-scan before sync",
                       variable=self.local_auto_scan_var).pack(side="left")

        self.local_skip_if_no_changes_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(schedule_options_frame, text="Skip if no changes",
                       variable=self.local_skip_if_no_changes_var).pack(side="left", padx=20)

        # Initially disable schedule controls
        self.toggle_local_schedule()

        # Folder filtering (reuse same logic as FTP sync)
        local_filter_frame = ttk.LabelFrame(local_sync_frame, text="Folder Filtering", padding=10)
        local_filter_frame.pack(fill=tk.X, padx=10, pady=5)

        # Enable folder filtering checkbox
        self.local_enable_folder_filter_var = tk.BooleanVar(value=False)
        local_filter_enable_frame = ttk.Frame(local_filter_frame)
        local_filter_enable_frame.pack(fill="x", pady=2)

        ttk.Checkbutton(local_filter_enable_frame, text="Enable specific folder sync",
                       variable=self.local_enable_folder_filter_var,
                       command=self.toggle_local_folder_filter).pack(side="left")

        # Help button
        ttk.Button(local_filter_enable_frame, text="?", width=3,
                  command=self.show_folder_filter_help).pack(side="right")

        # Folder names input
        local_folder_input_frame = ttk.Frame(local_filter_frame)
        local_folder_input_frame.pack(fill="x", pady=5)

        ttk.Label(local_folder_input_frame, text="Folder names (comma-separated):").pack(anchor="w")
        self.local_folder_names_var = tk.StringVar(value="hero, model, texture, anim")
        self.local_folder_names_entry = ttk.Entry(local_folder_input_frame, textvariable=self.local_folder_names_var)
        self.local_folder_names_entry.pack(fill="x", pady=2)

        # Add trace to clear cache when folder names change
        self.local_folder_names_var.trace('w', self.on_local_filter_change)

        # Match mode and options
        local_options_frame = ttk.Frame(local_filter_frame)
        local_options_frame.pack(fill="x", pady=2)

        # Match mode
        ttk.Label(local_options_frame, text="Match mode:").pack(side="left")
        self.local_folder_match_mode_var = tk.StringVar(value="exact")
        self.local_folder_exact_radio = ttk.Radiobutton(local_options_frame, text="Exact match",
                                                       variable=self.local_folder_match_mode_var, value="exact",
                                                       command=self.on_local_filter_change)
        self.local_folder_exact_radio.pack(side="left", padx=10)
        self.local_folder_contains_radio = ttk.Radiobutton(local_options_frame, text="Contains",
                                                          variable=self.local_folder_match_mode_var, value="contains",
                                                          command=self.on_local_filter_change)
        self.local_folder_contains_radio.pack(side="left", padx=10)

        # Case sensitivity
        self.local_case_sensitive_var = tk.BooleanVar(value=False)
        self.local_case_sensitive_check = ttk.Checkbutton(local_options_frame, text="Case sensitive",
                                                         variable=self.local_case_sensitive_var,
                                                         command=self.on_local_filter_change)
        self.local_case_sensitive_check.pack(side="right", padx=10)

        # Initially disable folder filter controls
        self.toggle_local_folder_filter()

        # Control buttons
        local_control_frame = ttk.Frame(local_sync_frame)
        local_control_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(local_control_frame, text="Scan Operations", command=self.scan_local_operations).pack(side=tk.LEFT, padx=5)
        ttk.Button(local_control_frame, text="Sync All", command=self.start_local_sync).pack(side=tk.LEFT, padx=5)
        self.local_sync_selected_btn = ttk.Button(local_control_frame, text="Sync Selected (0)",
                                                  command=self.start_local_sync_selected, state='disabled')
        self.local_sync_selected_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(local_control_frame, text="Stop Sync", command=self.stop_local_sync).pack(side=tk.LEFT, padx=5)
        ttk.Button(local_control_frame, text="📋 View Logs", command=lambda: self.show_log_viewer()).pack(side=tk.LEFT, padx=5)

        # Progress
        local_progress_frame = ttk.LabelFrame(local_sync_frame, text="Scan Progress", padding=10)
        local_progress_frame.pack(fill=tk.X, padx=10, pady=5)

        # Progress bar with percentage
        progress_bar_frame = ttk.Frame(local_progress_frame)
        progress_bar_frame.pack(fill=tk.X, pady=2)

        self.local_progress_var = tk.DoubleVar()
        self.local_progress_bar = ttk.Progressbar(progress_bar_frame, variable=self.local_progress_var, maximum=100)
        self.local_progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Percentage label
        self.local_progress_percent_var = tk.StringVar(value="0%")
        ttk.Label(progress_bar_frame, textvariable=self.local_progress_percent_var, width=6).pack(side=tk.RIGHT, padx=(5, 0))

        # Main status
        self.local_progress_status_var = tk.StringVar(value="Ready to scan")
        ttk.Label(local_progress_frame, textvariable=self.local_progress_status_var, font=('TkDefaultFont', 9, 'bold')).pack(anchor="w")

        # Detailed scan status for performance monitoring
        self.local_scan_status_var = tk.StringVar()
        ttk.Label(local_progress_frame, textvariable=self.local_scan_status_var, font=('TkDefaultFont', 8), foreground='gray').pack(anchor="w")

        # Scan statistics
        self.local_scan_stats_var = tk.StringVar()
        ttk.Label(local_progress_frame, textvariable=self.local_scan_stats_var, font=('TkDefaultFont', 8), foreground='blue').pack(anchor="w")

        # Operations tree
        local_operations_frame = ttk.LabelFrame(local_sync_frame, text="Operations", padding=10)
        local_operations_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Search and Filter controls for local operations
        local_search_filter_frame = ttk.Frame(local_operations_frame)
        local_search_filter_frame.pack(fill=tk.X, pady=(0, 5))

        # Search box
        local_search_frame = ttk.Frame(local_search_filter_frame)
        local_search_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(local_search_frame, text="🔍 Search:").pack(side=tk.LEFT, padx=(0, 5))
        self.local_operations_search_var = tk.StringVar()
        local_search_entry = ttk.Entry(local_search_frame, textvariable=self.local_operations_search_var, width=30)
        local_search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.local_operations_search_var.trace('w', lambda *args: self.filter_local_operations())

        ttk.Button(local_search_frame, text="Clear", width=8,
                  command=lambda: self.local_operations_search_var.set("")).pack(side=tk.LEFT)

        # Filter controls
        local_filter_controls_frame = ttk.Frame(local_search_filter_frame)
        local_filter_controls_frame.pack(side=tk.LEFT, padx=(10, 0))

        ttk.Label(local_filter_controls_frame, text="Filter:").pack(side=tk.LEFT, padx=(0, 5))

        # Operation type filter
        self.local_operations_filter_type_var = tk.StringVar(value="All")
        local_type_combo = ttk.Combobox(local_filter_controls_frame,
                                       textvariable=self.local_operations_filter_type_var,
                                       values=["All", "Copy", "Skip"],
                                       state='readonly', width=10)
        local_type_combo.pack(side=tk.LEFT, padx=(0, 5))
        local_type_combo.bind('<<ComboboxSelected>>', lambda e: self.filter_local_operations())

        # Size filter
        self.local_operations_filter_size_var = tk.StringVar(value="All Sizes")
        local_size_combo = ttk.Combobox(local_filter_controls_frame,
                                       textvariable=self.local_operations_filter_size_var,
                                       values=["All Sizes", "<1 MB", "1-10 MB", "10-100 MB", ">100 MB"],
                                       state='readonly', width=12)
        local_size_combo.pack(side=tk.LEFT, padx=(0, 5))
        local_size_combo.bind('<<ComboboxSelected>>', lambda e: self.filter_local_operations())

        # Quick filter: Show only changes
        self.local_operations_show_changes_only_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(local_filter_controls_frame, text="Changes only",
                       variable=self.local_operations_show_changes_only_var,
                       command=self.filter_local_operations).pack(side=tk.LEFT, padx=(5, 0))

        # Operations count label
        self.local_operations_count_var = tk.StringVar(value="Operations: 0")
        ttk.Label(local_operations_frame, textvariable=self.local_operations_count_var,
                 font=('TkDefaultFont', 9)).pack(anchor='w', pady=(5, 5))

        # Selection controls for local operations
        local_selection_frame = ttk.Frame(local_operations_frame)
        local_selection_frame.pack(fill=tk.X, pady=(5, 5))

        ttk.Button(local_selection_frame, text="☑ Select All", width=12,
                  command=self.select_all_local_operations).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(local_selection_frame, text="☐ Select None", width=12,
                  command=self.select_none_local_operations).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(local_selection_frame, text="☑ Select Filtered", width=14,
                  command=self.select_filtered_local_operations).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(local_selection_frame, text="☑ Select Changes", width=14,
                  command=self.select_changes_local_operations).pack(side=tk.LEFT, padx=(0, 5))

        # Selection summary for local operations
        self.local_operations_selection_var = tk.StringVar(value="Selected: 0 files (0 B)")
        ttk.Label(local_selection_frame, textvariable=self.local_operations_selection_var,
                 font=('TkDefaultFont', 9, 'bold')).pack(side=tk.RIGHT)

        # Create container frame for tree and scrollbars (to avoid geometry manager conflict)
        local_tree_container = ttk.Frame(local_operations_frame)
        local_tree_container.pack(fill=tk.BOTH, expand=True)

        # Create treeview for operations with checkbox column
        columns = ("☑", "Operation", "Source", "Destination", "Size", "Modified")
        self.local_operations_tree = ttk.Treeview(local_tree_container, columns=columns, show="headings", height=10)

        # Configure columns
        self.local_operations_tree.heading("☑", text="☑")
        self.local_operations_tree.heading("Operation", text="Operation")
        self.local_operations_tree.heading("Source", text="Source")
        self.local_operations_tree.heading("Destination", text="Destination")
        self.local_operations_tree.heading("Size", text="Size")
        self.local_operations_tree.heading("Modified", text="Modified")

        self.local_operations_tree.column("☑", width=30, anchor='center')
        self.local_operations_tree.column("Operation", width=100)
        self.local_operations_tree.column("Source", width=200)
        self.local_operations_tree.column("Destination", width=200)
        self.local_operations_tree.column("Size", width=80)
        self.local_operations_tree.column("Modified", width=120)

        # Bind click event for checkbox toggle
        self.local_operations_tree.bind('<Button-1>', self.on_local_operations_tree_click)

        # Add scrollbars (vertical and horizontal)
        local_tree_scrollbar_v = ttk.Scrollbar(local_tree_container, orient="vertical",
                                               command=self.local_operations_tree.yview)
        local_tree_scrollbar_h = ttk.Scrollbar(local_tree_container, orient="horizontal",
                                               command=self.local_operations_tree.xview)
        self.local_operations_tree.configure(yscrollcommand=local_tree_scrollbar_v.set,
                                            xscrollcommand=local_tree_scrollbar_h.set)

        # Use grid inside the container
        self.local_operations_tree.grid(row=0, column=0, sticky='nsew')
        local_tree_scrollbar_v.grid(row=0, column=1, sticky='ns')
        local_tree_scrollbar_h.grid(row=1, column=0, sticky='ew')

        local_tree_container.grid_columnconfigure(0, weight=1)
        local_tree_container.grid_rowconfigure(0, weight=1)

        # Initialize local operations list
        self.local_operations = []
        self.local_is_syncing = False
        self.local_sync_thread = None

    def browse_source_directory(self):
        """Browse for source directory"""
        directory = filedialog.askdirectory(title="Select Source Directory")
        if directory:
            self.local_source_var.set(directory)

    def browse_dest_directory(self):
        """Browse for destination directory"""
        directory = filedialog.askdirectory(title="Select Destination Directory")
        if directory:
            self.local_dest_var.set(directory)

    def toggle_local_folder_filter(self):
        """Toggle local folder filter controls"""
        enabled = self.local_enable_folder_filter_var.get()

        # Enable/disable folder filter controls
        state = "normal" if enabled else "disabled"

        try:
            # Enable/disable the folder names entry
            if hasattr(self, 'local_folder_names_entry'):
                self.local_folder_names_entry.config(state=state)

            # Enable/disable match mode radiobuttons
            if hasattr(self, 'local_folder_exact_radio'):
                self.local_folder_exact_radio.config(state=state)
            if hasattr(self, 'local_folder_contains_radio'):
                self.local_folder_contains_radio.config(state=state)

            # Enable/disable case sensitive checkbox
            if hasattr(self, 'local_case_sensitive_check'):
                self.local_case_sensitive_check.config(state=state)

            # IMPORTANT: Clear cache when filter settings change
            # This ensures fresh scan results when toggling filters
            if hasattr(self, 'scan_cache'):
                print("Clearing scan cache due to filter toggle")
                self.scan_cache.cache = {}  # Clear all cached results

            # Clear current operations to force rescan
            if hasattr(self, 'local_operations'):
                self.local_operations = []
            if hasattr(self, 'local_operations_tree'):
                self.local_operations_tree.delete(*self.local_operations_tree.get_children())

        except Exception as e:
            print(f"Error toggling local folder filter controls: {e}")

    def on_local_filter_change(self, *args):
        """Called when any local filter setting changes"""
        try:
            # Clear cache when filter settings change
            if hasattr(self, 'scan_cache'):
                print("Clearing scan cache due to filter change")
                self.scan_cache.cache = {}  # Clear all cached results

            # Clear current operations to force rescan
            if hasattr(self, 'local_operations'):
                self.local_operations = []
            if hasattr(self, 'local_operations_tree'):
                self.local_operations_tree.delete(*self.local_operations_tree.get_children())

            # Update status to indicate cache cleared
            if hasattr(self, 'local_progress_status_var'):
                self.local_progress_status_var.set("Filter changed - cache cleared")

        except Exception as e:
            print(f"Error handling filter change: {e}")

    def on_ftp_filter_change(self, *args):
        """Called when any FTP filter setting changes"""
        try:
            # Clear cache when filter settings change
            if hasattr(self, 'scan_cache'):
                print("Clearing scan cache due to FTP filter change")
                self.scan_cache.cache = {}  # Clear all cached results

            # Clear current operations to force rescan
            if hasattr(self, 'operations'):
                self.operations = []
            if hasattr(self, 'operations_tree'):
                self.operations_tree.delete(*self.operations_tree.get_children())

        except Exception as e:
            print(f"Error handling FTP filter change: {e}")

    def scan_local_operations(self):
        """Scan for local sync operations"""
        source_dir = self.local_source_var.get().strip()
        dest_dir = self.local_dest_var.get().strip()

        print(f"DEBUG: Starting scan with source='{source_dir}', dest='{dest_dir}'")

        if not source_dir or not dest_dir:
            messagebox.showwarning("Warning", "Please select both source and destination directories.")
            return

        if not os.path.exists(source_dir):
            print(f"DEBUG: Source directory does not exist: {source_dir}")
            messagebox.showerror("Error", f"Source directory does not exist: {source_dir}")
            return
        else:
            print(f"DEBUG: Source directory exists: {source_dir}")
            # Test if we can list files in source directory
            try:
                test_files = list(os.listdir(source_dir))
                print(f"DEBUG: Source directory contains {len(test_files)} items: {test_files[:5]}...")
            except Exception as e:
                print(f"DEBUG: Error listing source directory: {e}")

        if not os.path.exists(dest_dir):
            # Ask if user wants to create destination directory
            if messagebox.askyesno("Create Directory", f"Destination directory does not exist: {dest_dir}\n\nWould you like to create it?"):
                try:
                    os.makedirs(dest_dir, exist_ok=True)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to create destination directory: {e}")
                    return
            else:
                return

        self.local_progress_status_var.set("Scanning local directories...")
        self.local_progress_var.set(0)

        # Start scan in background thread
        scan_thread = threading.Thread(target=self.perform_local_scan, args=(source_dir, dest_dir), daemon=True)
        scan_thread.start()

    def perform_local_scan(self, source_dir, dest_dir):
        """Perform local directory scan in background"""
        try:
            # DEBUG: Print the directories being scanned
            print(f"=== DEBUG SCAN START ===")
            print(f"Source Directory: '{source_dir}'")
            print(f"Destination Directory: '{dest_dir}'")
            print(f"Source exists: {os.path.exists(source_dir)}")
            print(f"Dest exists: {os.path.exists(dest_dir)}")

            # Test basic directory access
            if os.path.exists(source_dir):
                try:
                    source_contents = os.listdir(source_dir)
                    print(f"Source directory contents ({len(source_contents)} items): {source_contents[:10]}")  # Show first 10 items
                except Exception as e:
                    print(f"Error reading source directory: {e}")
            else:
                print(f"ERROR: Source directory does not exist!")

            if os.path.exists(dest_dir):
                try:
                    dest_contents = os.listdir(dest_dir)
                    print(f"Dest directory contents ({len(dest_contents)} items): {dest_contents[:10]}")  # Show first 10 items
                except Exception as e:
                    print(f"Error reading dest directory: {e}")
            else:
                print(f"ERROR: Destination directory does not exist!")

            # Initialize progress
            self.root.after(0, lambda: self.local_progress_var.set(0))
            self.root.after(0, lambda: self.local_progress_percent_var.set("0%"))
            self.root.after(0, lambda: self.local_progress_status_var.set("Initializing scan..."))
            self.root.after(0, lambda: self.local_scan_status_var.set("Preparing directory scan"))
            self.root.after(0, lambda: self.local_scan_stats_var.set(""))

            sync_direction = self.local_sync_direction_var.get()
            operations = []

            # Get folder filter settings
            folder_filter_enabled = self.local_enable_folder_filter_var.get()
            folder_names = []
            match_mode = "exact"
            case_sensitive = False

            if folder_filter_enabled:
                folder_names_text = self.local_folder_names_var.get()
                folder_names = [name.strip() for name in folder_names_text.split(',') if name.strip()]
                match_mode = self.local_folder_match_mode_var.get()
                case_sensitive = self.local_case_sensitive_var.get()
                print(f"Local folder filtering enabled: {folder_names} (mode: {match_mode})")
                self.root.after(0, lambda: self.local_scan_stats_var.set(f"Filter: {', '.join(folder_names)} ({match_mode})"))
            else:
                print("Local folder filtering disabled - scanning all folders")
                self.root.after(0, lambda: self.local_scan_stats_var.set("No folder filtering - scanning all directories"))

            # Progress callback for real-time updates
            def update_progress(progress, status, stats=""):
                self.root.after(0, lambda: self.local_progress_var.set(progress))
                self.root.after(0, lambda: self.local_progress_percent_var.set(f"{int(progress)}%"))
                self.root.after(0, lambda: self.local_scan_status_var.set(status))
                if stats:
                    self.root.after(0, lambda: self.local_scan_stats_var.set(stats))
                # Force UI update and add small delay to make progress visible
                self.root.after(0, lambda: self.root.update_idletasks())
                time.sleep(0.01)  # Small delay to make progress visible

            # Get force overwrite setting
            force_overwrite = self.local_force_overwrite_var.get() if hasattr(self, 'local_force_overwrite_var') else False

            if sync_direction in ["source_to_dest", "bidirectional"]:
                # Scan source to destination with optimized method
                source_files = self.scan_local_directory(
                    source_dir,
                    folder_names if folder_filter_enabled else None,
                    match_mode,
                    case_sensitive,
                    lambda p, s, stats="": update_progress(p * 0.4, s, stats)  # 0-40% progress
                )

                # Process source files and determine operations
                update_progress(50, "Processing source files...", f"Found {len(source_files)} source files")

                for i, file_info in enumerate(source_files):
                    rel_path = os.path.relpath(file_info['path'], source_dir)
                    dest_path = os.path.join(dest_dir, rel_path)

                    operation_type = self.determine_local_operation(file_info['path'], dest_path, file_info, force_overwrite)
                    # Add ALL operations (including skip) - let the "Changes only" filter handle display
                    operations.append({
                        'operation': operation_type,
                        'source': file_info['path'],
                        'destination': dest_path,
                        'size': file_info['size'],
                        'modified': file_info['modified']
                    })

                    # Update progress every 100 files
                    if i % 100 == 0 and i > 0:
                        progress = 50 + ((i / len(source_files)) * 20)  # 50-70% progress
                        update_progress(progress, f"Processing files: {i}/{len(source_files)}",
                                      f"Operations found: {len(operations)}")

            if sync_direction in ["dest_to_source", "bidirectional"]:
                # Scan destination to source with optimized method
                base_progress = 70 if sync_direction == "bidirectional" else 0
                dest_files = self.scan_local_directory(
                    dest_dir,
                    folder_names if folder_filter_enabled else None,
                    match_mode,
                    case_sensitive,
                    lambda p, s, stats="": update_progress(base_progress + (p * 0.25), s, stats)  # 70-95% or 0-25% progress
                )

                for file_info in dest_files:
                    rel_path = os.path.relpath(file_info['path'], dest_dir)
                    source_path = os.path.join(source_dir, rel_path)

                    # Skip if we already have this operation from source_to_dest scan
                    if sync_direction == "bidirectional":
                        existing = any(op['source'] == source_path and op['destination'] == file_info['path'] for op in operations)
                        if existing:
                            continue

                    operation_type = self.determine_local_operation(file_info['path'], source_path, file_info, force_overwrite)
                    if operation_type != "skip":
                        operations.append({
                            'operation': operation_type,
                            'source': file_info['path'],
                            'destination': source_path,
                            'size': file_info['size'],
                            'modified': file_info['modified']
                        })

            # Final progress update
            update_progress(95, "Finalizing scan results...", f"Total operations: {len(operations)}")

            # Update UI in main thread
            self.root.after(0, self.show_local_scan_results, operations)

        except Exception as e:
            self.root.after(0, self.show_local_scan_error, str(e))

    def show_local_scan_results(self, operations):
        """Show scan results in UI"""
        try:
            # Store operations
            self.local_operations = operations

            # Clear and populate tree
            self.local_operations_tree.delete(*self.local_operations_tree.get_children())

            for op in operations:
                # Determine base directory for relative path calculation
                if op['operation'] in ['copy', 'update']:
                    base_dir = os.path.dirname(op['source'])
                else:
                    base_dir = os.path.dirname(op['source'])

                try:
                    rel_source = os.path.relpath(op['source'], base_dir)
                except ValueError:
                    rel_source = op['source']  # Use full path if relative fails

                size_str = f"{op['size']:,} bytes" if op['size'] > 0 else ""
                modified_str = op['modified'].strftime('%Y-%m-%d %H:%M:%S') if op['modified'] else ""

                self.local_operations_tree.insert("", "end", values=(
                    op['operation'].title(),
                    rel_source,
                    os.path.basename(op['destination']),
                    size_str,
                    modified_str
                ))

            # Update progress
            self.local_progress_var.set(100)
            self.local_progress_status_var.set(f"Scan complete: {len(operations)} operations found")
            self.local_scan_status_var.set("")

            # Show completion message with performance info
            cache_info = "Used cached results" if "cache" in str(self.local_scan_status_var.get()) else "Fresh scan completed"
            threading_info = f"Multi-threading: {'enabled' if self.scan_config['max_workers'] > 1 else 'disabled'}"

            messagebox.showinfo("Scan Complete",
                              f"Found {len(operations)} operations to perform.\n\n"
                              f"{cache_info}\n"
                              f"{threading_info}\n"
                              f"Cache enabled: {self.scan_config['cache_enabled']}")

        except Exception as e:
            print(f"Error showing scan results: {e}")
            messagebox.showerror("Display Error", f"Error displaying results: {str(e)}")

    def show_local_scan_error(self, error_message):
        """Show scan error in UI"""
        self.local_progress_var.set(0)
        self.local_progress_status_var.set("Scan failed")
        self.local_scan_status_var.set("")
        messagebox.showerror("Scan Error", f"Error during scan: {error_message}")

    def scan_local_directory(self, directory, folder_names=None, match_mode="exact", case_sensitive=False, progress_callback=None):
        """Optimized scan of local directory with caching, filtering, and multi-threading"""

        # Check cache first
        if self.scan_config["cache_enabled"]:
            print(f"DEBUG: Checking cache for directory: {directory}")
            cached_results = self.scan_cache.get_cached_scan(directory, folder_names, match_mode, case_sensitive)
            if cached_results is not None:
                print(f"DEBUG: CACHE HIT - returning {len(cached_results)} cached files")
                if progress_callback:
                    progress_callback(100, f"Loaded from cache: {len(cached_results)} files", "Cache hit - no scanning needed")
                return cached_results
            else:
                print(f"DEBUG: CACHE MISS - proceeding with fresh scan")

        print(f"=== SCAN_LOCAL_DIRECTORY DEBUG ===")
        print(f"Scanning directory: '{directory}'")
        print(f"Directory exists: {os.path.exists(directory)}")
        print(f"Directory is accessible: {os.access(directory, os.R_OK) if os.path.exists(directory) else 'N/A'}")

        # Test basic directory listing
        if os.path.exists(directory):
            try:
                test_contents = os.listdir(directory)
                print(f"Directory contents ({len(test_contents)} items): {test_contents[:10]}")  # Show first 10

                # If filtering, check if filter directory exists
                if folder_names:
                    for fname in folder_names:
                        test_path = os.path.join(directory, fname)
                        if os.path.exists(test_path):
                            print(f"  ✓ Filter directory '{fname}' exists at: {test_path}")
                            if os.path.isdir(test_path):
                                try:
                                    filter_contents = os.listdir(test_path)
                                    print(f"    Contains {len(filter_contents)} items")
                                except Exception as e:
                                    print(f"    Error listing: {e}")
                        else:
                            print(f"  ✗ Filter directory '{fname}' NOT FOUND at: {test_path}")
            except Exception as e:
                print(f"Error listing directory: {e}")

        if folder_names:
            print(f"Folder filter: {folder_names} (mode: {match_mode}, case_sensitive: {case_sensitive})")
        else:
            print("No folder filtering - scanning all directories")



        # Use optimized scanning method


        # Use optimized scanning method (check if parallel is enabled)
        if self.scan_config.get("local_parallel_enabled", True) and self.scan_config.get("local_max_workers", 8) > 1:
            files = self._scan_directory_multithreaded(directory, folder_names, match_mode, case_sensitive, progress_callback)
        else:
            files = self._scan_directory_single_threaded(directory, folder_names, match_mode, case_sensitive, progress_callback)

        print(f"DEBUG: Raw scan found {len(files)} files before filtering")
        if files:
            print(f"DEBUG: Sample files (first 5):")
            for i, f in enumerate(files[:5]):
                print(f"  {i+1}. {f['path']}")

            # Debug: Show which folders were scanned
            if folder_names:
                print(f"DEBUG: Checking if filter folders were scanned...")
                for folder_name in folder_names:
                    matching_files = [f for f in files if folder_name.lower() in f['path'].lower()]
                    print(f"  Files containing '{folder_name}' in path: {len(matching_files)}")
                    if matching_files:
                        print(f"    Sample: {matching_files[0]['path']}")

        # Apply folder filtering if enabled (at file level, not directory level)
        if folder_names:
            print(f"DEBUG: Applying folder filter: {folder_names} (mode: {match_mode})")
            files = self.apply_local_folder_filter(files, directory, folder_names, match_mode, case_sensitive)
            print(f"DEBUG: After filtering: {len(files)} files remain")

        # Cache results
        if self.scan_config["cache_enabled"]:
            self.scan_cache.cache_scan_results(directory, files, folder_names, match_mode, case_sensitive)

        print(f"Scan complete: {len(files)} files found")
        return files

    def _scan_directory_single_threaded(self, directory, folder_names, match_mode, case_sensitive, progress_callback):
        """Single-threaded directory scan with early filtering"""
        files = []
        processed_files = 0

        # Estimate total files for progress (quick estimate)
        total_estimate = sum(len(filenames) for _, _, filenames in os.walk(directory))

        for root, dirs, filenames in os.walk(directory):

            # Early directory filtering disabled to prevent over-exclusion
            # Filtering is now done at file level after complete scan

            # Directory-level filtering disabled - filtering done at file level

            # Process files in current directory
            for filename in filenames:
                file_path = os.path.join(root, filename)
                try:
                    # Use os.scandir for better performance when available
                    stat = os.stat(file_path)
                    files.append({
                        'path': file_path,
                        'size': stat.st_size,
                        'modified': datetime.fromtimestamp(stat.st_mtime),
                        'is_file': True
                    })
                except (OSError, IOError) as e:
                    print(f"Error accessing file {file_path}: {e}")
                    continue

                processed_files += 1

                # Update progress periodically
                if progress_callback and processed_files % self.scan_config["chunk_size"] == 0:
                    progress = min((processed_files / total_estimate) * 100, 99)
                    current_dir = os.path.basename(root)
                    stats = f"Files found: {len(files)} | Processed: {processed_files}/{total_estimate}"
                    progress_callback(progress, f"Scanning: {current_dir}", stats)



        if progress_callback:
            stats = f"Total files found: {len(files)} | Scan method: Single-threaded"
            progress_callback(100, f"Scan complete: {len(files)} files", stats)

        return files

    def _scan_directory_multithreaded(self, directory, folder_names, match_mode, case_sensitive, progress_callback):
        """Multi-threaded directory scan for better performance"""
        files = []
        files_lock = threading.Lock()
        processed_dirs = 0
        total_dirs = 0

        # Count total directories for progress
        for _, dirs, _ in os.walk(directory):
            total_dirs += len(dirs) + 1  # +1 for current directory

        def scan_subdirectory(subdir_path, depth=0):
            """Scan a single subdirectory recursively"""
            local_files = []
            dir_count = 0

            if depth > self.scan_config["max_depth"]:
                return local_files

            try:
                # os.walk already handles recursion, so we don't need to break
                for root, dirs, filenames in os.walk(subdir_path):
                    dir_count += 1

                    # Early filtering (only if enabled)
                    if self.scan_config["early_filtering"] and folder_names:
                        if not self._path_matches_filter(root, directory, folder_names, match_mode, case_sensitive):
                            continue

                    # Process files in this directory
                    for filename in filenames:
                        file_path = os.path.join(root, filename)
                        try:
                            stat = os.stat(file_path)
                            local_files.append({
                                'path': file_path,
                                'size': stat.st_size,
                                'modified': datetime.fromtimestamp(stat.st_mtime),
                                'is_file': True
                            })
                        except (OSError, IOError):
                            continue

                    # os.walk will continue to subdirectories automatically
                    # No break needed - let it scan recursively

                print(f"DEBUG: Thread scanned {subdir_path}: {dir_count} directories, {len(local_files)} files")

            except Exception as e:
                print(f"Error scanning {subdir_path}: {e}")

            return local_files

        # Use ThreadPoolExecutor for parallel scanning
        max_workers = min(self.scan_config.get("local_max_workers", 8), 16)  # Cap at 16 threads

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []

            # Submit top-level directories to thread pool
            try:
                for root, dirs, filenames in os.walk(directory):
                    # Process files in root directory first
                    root_files = []
                    for filename in filenames:
                        file_path = os.path.join(root, filename)
                        try:
                            stat = os.stat(file_path)
                            root_files.append({
                                'path': file_path,
                                'size': stat.st_size,
                                'modified': datetime.fromtimestamp(stat.st_mtime),
                                'is_file': True
                            })
                        except (OSError, IOError):
                            continue

                    with files_lock:
                        files.extend(root_files)

                    # Submit subdirectories to thread pool
                    print(f"DEBUG: Submitting {len(dirs)} subdirectories to thread pool: {dirs}")
                    for subdir in dirs:
                        subdir_path = os.path.join(root, subdir)
                        if self.scan_config["early_filtering"] and folder_names:
                            should_include = self._should_include_directory(subdir, folder_names, match_mode, case_sensitive)
                            print(f"DEBUG: Early filter check - subdir '{subdir}' should_include={should_include} (filter={folder_names}, mode={match_mode})")
                            if not should_include:
                                print(f"DEBUG: Skipping subdirectory '{subdir}' due to early filter")
                                continue

                        print(f"DEBUG: Submitting thread for: {subdir_path}")
                        future = executor.submit(scan_subdirectory, subdir_path, 1)
                        futures.append(future)

                    # Only process top level in this loop
                    break

                # Collect results from threads
                for i, future in enumerate(concurrent.futures.as_completed(futures)):
                    try:
                        thread_files = future.result()
                        with files_lock:
                            files.extend(thread_files)

                        # Update progress
                        processed_dirs += 1
                        if progress_callback:
                            progress = min((processed_dirs / max(total_dirs, 1)) * 100, 99)
                            stats = f"Threads: {max_workers} | Directories: {processed_dirs}/{total_dirs} | Files: {len(files)}"
                            progress_callback(progress, f"Multi-threaded scan in progress", stats)

                    except Exception as e:
                        print(f"Thread error: {e}")

            except Exception as e:
                print(f"Multi-threaded scan error: {e}")
                # Fallback to single-threaded
                return self._scan_directory_single_threaded(directory, folder_names, match_mode, case_sensitive, progress_callback)

        if progress_callback:
            stats = f"Total files found: {len(files)} | Scan method: Multi-threaded ({max_workers} threads)"
            progress_callback(100, f"Multi-threaded scan complete", stats)

        return files

    def _should_include_directory(self, dir_name, folder_names, match_mode, case_sensitive):
        """Check if directory should be included based on folder filter"""
        if not folder_names:
            return True

        compare_dir = dir_name if case_sensitive else dir_name.lower()

        for folder_name in folder_names:
            compare_folder = folder_name.strip() if case_sensitive else folder_name.strip().lower()

            if match_mode == "exact":
                # FIXED: Exact match should be truly exact - no partial matches
                if compare_dir == compare_folder:
                    return True
            elif match_mode == "contains":
                if compare_folder in compare_dir:
                    return True

        return False

    def _path_matches_filter(self, path, base_path, folder_names, match_mode, case_sensitive):
        """Check if path matches folder filter"""
        if not folder_names:
            return True

        # Get relative path and split into parts
        try:
            rel_path = os.path.relpath(path, base_path)
            path_parts = rel_path.replace('\\', '/').split('/')
        except ValueError:
            return True  # If can't get relative path, include it

        # Check each part of the path
        for part in path_parts:
            if self._should_include_directory(part, folder_names, match_mode, case_sensitive):
                return True

        return False

    def apply_local_folder_filter(self, files, base_path, folder_names, match_mode="exact", case_sensitive=False):
        """Apply folder filtering to local files"""
        if not folder_names:
            return files

        filtered_files = []

        # Normalize folder names for comparison
        if not case_sensitive:
            folder_names = [name.lower().strip() for name in folder_names]
        else:
            folder_names = [name.strip() for name in folder_names]

        print(f"Applying local folder filter: {folder_names} (mode: {match_mode}, case_sensitive: {case_sensitive})")
        print(f"Base path: {base_path}")
        print(f"Total files to filter: {len(files)}")

        for i, file_info in enumerate(files):
            file_path = file_info['path']
            # Get relative path from base directory
            try:
                rel_path = os.path.relpath(file_path, base_path)
                path_parts = rel_path.replace('\\', '/').split('/')
            except ValueError:
                # Handle case where file_path is not under base_path
                path_parts = file_path.replace('\\', '/').split('/')

            if i < 5:  # Debug first 5 files
                print(f"  File {i+1}: {file_path}")
                print(f"    Rel path: {rel_path}")
                print(f"    Path parts: {path_parts}")

            # Check each part of the path
            should_include = False
            for path_part in path_parts:
                if not path_part:  # Skip empty parts
                    continue

                # Normalize path part for comparison
                compare_part = path_part if case_sensitive else path_part.lower()

                # Check against each folder name
                for folder_name in folder_names:
                    if match_mode == "exact":
                        # FIXED: Exact match should be truly exact
                        if compare_part == folder_name:
                            should_include = True
                            if i < 5:  # Debug first 5 files
                                print(f"    MATCH: '{compare_part}' == '{folder_name}' (exact)")
                            break
                    elif match_mode == "contains":
                        if folder_name in compare_part:
                            should_include = True
                            if i < 5:  # Debug first 5 files
                                print(f"    MATCH: '{folder_name}' in '{compare_part}' (contains)")
                            break

                if should_include:
                    break

            if should_include:
                filtered_files.append(file_info)

        print(f"Local folder filter result: {len(filtered_files)} files (from {len(files)} total)")
        return filtered_files

    def determine_local_operation(self, source_path, dest_path, source_info, force_overwrite=False):
        """Determine what operation should be performed for local sync

        Args:
            force_overwrite: If True, always copy regardless of modification dates
        """
        # Force overwrite mode: always copy
        if force_overwrite:
            return "copy"

        if not os.path.exists(dest_path):
            return "copy"

        try:
            dest_stat = os.stat(dest_path)
            dest_modified = datetime.fromtimestamp(dest_stat.st_mtime)
            dest_size = dest_stat.st_size

            # Compare modification times and sizes
            if source_info['modified'] > dest_modified:
                return "copy"  # Source is newer
            elif source_info['modified'] < dest_modified:
                return "skip"  # Destination is newer
            elif source_info['size'] != dest_size:
                return "copy"  # Different sizes
            else:
                return "skip"  # Files are the same

        except (OSError, IOError):
            return "copy"  # If we can't stat destination, copy anyway

    def show_local_scan_results(self, operations):
        """Show local scan results in the tree view"""
        self.local_operations = operations

        # Reset filters
        self.local_operations_search_var.set("")
        self.local_operations_filter_type_var.set("All")
        self.local_operations_filter_size_var.set("All Sizes")
        self.local_operations_show_changes_only_var.set(False)

        # Use filter method to display
        self.filter_local_operations()

        return  # filter_local_operations handles everything

        # Clear existing items
        for item in self.local_operations_tree.get_children():
            self.local_operations_tree.delete(item)

        self.local_operations = operations

        # Count operations by type
        copy_count = sum(1 for op in operations if op['operation'] == 'copy')
        skip_count = sum(1 for op in operations if op['operation'] == 'skip')

        # Add operations to tree
        for operation in operations:
            # Format size
            size_str = self.format_file_size(operation['size'])

            # Format modified time
            modified_str = operation['modified'].strftime('%Y-%m-%d %H:%M:%S')

            # Determine tags for color coding
            tags = []
            if operation['operation'] == 'copy':
                tags = ["copy"]
            elif operation['operation'] == 'skip':
                tags = ["skip"]

            self.local_operations_tree.insert('', 'end', values=(
                operation['operation'].title(),
                operation['source'],
                operation['destination'],
                size_str,
                modified_str
            ), tags=tags)

        # Configure tags for color coding
        self.local_operations_tree.tag_configure("copy", background="#e8f5e8")
        self.local_operations_tree.tag_configure("skip", background="#f5f5f5")

        # Update summary
        summary = f"Local scan complete: {len(operations)} operations found"
        if copy_count > 0:
            summary += f", {copy_count} copies"
        if skip_count > 0:
            summary += f", {skip_count} skipped"

        self.local_progress_status_var.set(summary)
        self.local_progress_var.set(100)

    def show_local_scan_error(self, error_msg):
        """Show local scan error"""
        self.local_progress_status_var.set("Local scan failed")
        messagebox.showerror("Local Scan Error", f"Failed to scan local directories: {error_msg}")

    def filter_local_operations(self):
        """Filter local operations based on search and filter criteria"""
        if not hasattr(self, 'local_operations') or not self.local_operations:
            return

        # Get filter criteria
        search_text = self.local_operations_search_var.get().lower()
        filter_type = self.local_operations_filter_type_var.get()
        filter_size = self.local_operations_filter_size_var.get()
        changes_only = self.local_operations_show_changes_only_var.get()

        # Clear tree
        for item in self.local_operations_tree.get_children():
            self.local_operations_tree.delete(item)

        # Filter and display operations
        filtered_count = 0
        copy_count = skip_count = 0

        for op in self.local_operations:
            # Apply filters
            # Search filter
            if search_text:
                if (search_text not in op['source'].lower() and
                    search_text not in op['destination'].lower() and
                    search_text not in os.path.basename(op['source']).lower()):
                    continue

            # Type filter
            if filter_type != "All":
                if op['operation'].lower() != filter_type.lower():
                    continue

            # Size filter
            if filter_size != "All Sizes":
                size_mb = op['size'] / (1024 * 1024)
                if filter_size == "<1 MB" and size_mb >= 1:
                    continue
                elif filter_size == "1-10 MB" and (size_mb < 1 or size_mb >= 10):
                    continue
                elif filter_size == "10-100 MB" and (size_mb < 10 or size_mb >= 100):
                    continue
                elif filter_size == ">100 MB" and size_mb < 100:
                    continue

            # Changes only filter
            if changes_only and op['operation'] == "skip":
                continue

            # Add to tree
            size_str = self.format_file_size(op['size'])
            modified_str = op['modified'].strftime('%Y-%m-%d %H:%M:%S')

            tags = []
            if op['operation'] == 'copy':
                tags = ["copy"]
                copy_count += 1
            elif op['operation'] == 'skip':
                tags = ["skip"]
                skip_count += 1

            self.local_operations_tree.insert('', 'end', values=(
                '☐',  # Checkbox - unchecked by default
                op['operation'].title(),
                op['source'],
                op['destination'],
                size_str,
                modified_str
            ), tags=tags)

            filtered_count += 1

        # Update count label
        total_count = len(self.local_operations)
        if filtered_count == total_count:
            self.local_operations_count_var.set(f"Operations: {total_count}")
        else:
            self.local_operations_count_var.set(f"Showing {filtered_count} of {total_count} operations")

        # Update status
        summary = f"Filtered: {filtered_count} operations"
        if copy_count > 0:
            summary += f", {copy_count} copies"
        if skip_count > 0:
            summary += f", {skip_count} skipped"

        self.local_progress_status_var.set(summary)

    def on_local_operations_tree_click(self, event):
        """Handle click on local operations tree (for checkbox toggle)"""
        region = self.local_operations_tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self.local_operations_tree.identify_column(event.x)
            if column == '#1':  # Checkbox column
                item = self.local_operations_tree.identify_row(event.y)
                if item:
                    # Toggle selection
                    current_values = list(self.local_operations_tree.item(item, 'values'))
                    if current_values[0] == '☐':
                        current_values[0] = '☑'
                    else:
                        current_values[0] = '☐'
                    self.local_operations_tree.item(item, values=current_values)
                    self.update_local_selection_summary()

    def select_all_local_operations(self):
        """Select all local operations in tree"""
        for item in self.local_operations_tree.get_children():
            values = list(self.local_operations_tree.item(item, 'values'))
            values[0] = '☑'
            self.local_operations_tree.item(item, values=values)
        self.update_local_selection_summary()

    def select_none_local_operations(self):
        """Deselect all local operations"""
        for item in self.local_operations_tree.get_children():
            values = list(self.local_operations_tree.item(item, 'values'))
            values[0] = '☐'
            self.local_operations_tree.item(item, values=values)
        self.update_local_selection_summary()

    def select_filtered_local_operations(self):
        """Select all currently visible (filtered) local operations"""
        for item in self.local_operations_tree.get_children():
            values = list(self.local_operations_tree.item(item, 'values'))
            values[0] = '☑'
            self.local_operations_tree.item(item, values=values)
        self.update_local_selection_summary()

    def select_changes_local_operations(self):
        """Select only local operations that involve changes (not skip)"""
        for item in self.local_operations_tree.get_children():
            values = list(self.local_operations_tree.item(item, 'values'))
            operation_type = values[1].lower()  # Operation column
            if operation_type != 'skip':
                values[0] = '☑'
            else:
                values[0] = '☐'
            self.local_operations_tree.item(item, values=values)
        self.update_local_selection_summary()

    def update_local_selection_summary(self):
        """Update local selection summary label"""
        selected_count = 0
        selected_size = 0

        for item in self.local_operations_tree.get_children():
            values = self.local_operations_tree.item(item, 'values')
            if values[0] == '☑':
                selected_count += 1
                # Parse size from string
                size_str = values[4]  # Size column
                try:
                    if 'KB' in size_str:
                        selected_size += float(size_str.split()[0]) * 1024
                    elif 'MB' in size_str:
                        selected_size += float(size_str.split()[0]) * 1024 * 1024
                    elif 'GB' in size_str:
                        selected_size += float(size_str.split()[0]) * 1024 * 1024 * 1024
                    elif 'B' in size_str and 'KB' not in size_str and 'MB' not in size_str:
                        selected_size += float(size_str.split()[0])
                except:
                    pass

        # Update summary label
        size_formatted = self.format_file_size(int(selected_size))
        self.local_operations_selection_var.set(f"Selected: {selected_count} files ({size_formatted})")

        # Update "Sync Selected" button
        if selected_count > 0:
            self.local_sync_selected_btn.config(text=f"Sync Selected ({selected_count})", state='normal')
        else:
            self.local_sync_selected_btn.config(text="Sync Selected (0)", state='disabled')

    def get_selected_local_operations(self):
        """Get list of selected local operations"""
        selected = []
        tree_items = self.local_operations_tree.get_children()

        for i, item in enumerate(tree_items):
            values = self.local_operations_tree.item(item, 'values')
            if values[0] == '☑' and i < len(self.local_operations):
                selected.append(self.local_operations[i])

        return selected

    def start_local_sync_selected(self):
        """Start local sync with only selected operations"""
        selected_ops = self.get_selected_local_operations()

        if not selected_ops:
            messagebox.showwarning("Warning", "No operations selected.")
            return

        # Confirm sync
        response = messagebox.askyesno(
            "Confirm Sync",
            f"Sync {len(selected_ops)} selected operations?\n\n"
            f"Source: {self.local_source_var.get()}\n"
            f"Destination: {self.local_dest_var.get()}"
        )

        if not response:
            return

        # Start sync with selected operations only
        self.local_is_syncing = True
        self.local_sync_thread = threading.Thread(
            target=self.perform_local_sync,
            args=(selected_ops,),
            daemon=True
        )
        self.local_sync_thread.start()

    def format_file_size(self, size_bytes):
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0 B"

        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1

        return f"{size_bytes:.1f} {size_names[i]}"

    # FTP Multi-Session Manager Methods
    def load_ftp_sessions(self):
        """Load FTP sessions from database"""
        try:
            conn = sqlite3.connect(self.ftp_sync.db.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, name, endpoint_id, source_path, dest_path, sync_direction,
                       folder_filter_enabled, folder_names, match_mode, case_sensitive,
                       schedule_enabled, schedule_interval, schedule_unit, auto_start,
                       parallel_execution, active, last_sync, last_status, force_overwrite
                FROM ftp_sync_configs
            ''')

            sessions = cursor.fetchall()
            conn.close()

            # Clear tree
            for item in self.ftp_sessions_tree.get_children():
                self.ftp_sessions_tree.delete(item)

            # Store sessions data for later use
            self.ftp_sessions = {}

            # Add sessions to tree
            for session in sessions:
                session_id, name, endpoint_id, source_path, dest_path, direction, filter_enabled, \
                folder_names, match_mode, case_sensitive, schedule_enabled, interval, unit, \
                auto_start, parallel_exec, active, last_sync, last_status, force_overwrite = session

                # Store session data
                self.ftp_sessions[session_id] = {
                    'id': session_id,
                    'name': name,
                    'endpoint_id': endpoint_id,
                    'source_path': source_path,
                    'dest_path': dest_path,
                    'direction': direction,
                    'filter_enabled': filter_enabled,
                    'folder_names': folder_names,
                    'match_mode': match_mode,
                    'case_sensitive': case_sensitive,
                    'schedule_enabled': schedule_enabled,
                    'interval': interval,
                    'unit': unit,
                    'auto_start': auto_start,
                    'parallel_execution': parallel_exec,
                    'active': active,
                    'last_sync': last_sync,
                    'last_status': last_status,
                    'force_overwrite': force_overwrite
                }

                # Get endpoint name
                endpoint_name = "Unknown"
                for endpoint in self.endpoints:
                    if endpoint.id == endpoint_id:
                        endpoint_name = endpoint.name
                        break

                # Format filter info
                filter_info = folder_names if filter_enabled else "All files"

                # Format schedule info
                if schedule_enabled:
                    auto_str = " (Auto)" if auto_start else ""
                    schedule_info = f"{interval} {unit}{auto_str}"
                else:
                    schedule_info = "Manual"

                # Status - check if currently running
                if session_id in self.ftp_session_threads and self.ftp_session_threads[session_id].is_alive():
                    status = "🔄 Running"
                elif last_status:
                    status = last_status
                elif active:
                    status = "⏹️ Ready"
                else:
                    status = "⏸️ Inactive"

                # Last sync
                last_sync_str = last_sync if last_sync else "Never"

                self.ftp_sessions_tree.insert('', 'end', values=(
                    name, endpoint_name, direction, filter_info, schedule_info, status, last_sync_str
                ), tags=(str(session_id),))

            self.ftp_multi_status_var.set(f"Loaded {len(sessions)} FTP sync sessions")

        except Exception as e:
            print(f"Error loading FTP sessions: {e}")
            self.ftp_multi_status_var.set("Error loading sessions")

    def add_ftp_session(self):
        """Add new FTP sync session"""
        self.show_ftp_session_dialog()

    def edit_ftp_session(self):
        """Edit selected FTP sync session"""
        selection = self.ftp_sessions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a session to edit.")
            return

        # Get session ID from tags
        item = selection[0]
        session_id = int(self.ftp_sessions_tree.item(item, 'tags')[0])

        # Get session data
        if session_id in self.ftp_sessions:
            self.show_ftp_session_dialog(self.ftp_sessions[session_id])
        else:
            messagebox.showerror("Error", "Session data not found.")

    def show_ftp_session_dialog(self, session_data=None):
        """Show dialog to add or edit FTP sync session"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add FTP Session" if not session_data else "Edit FTP Session")
        dialog.geometry("700x800")
        dialog.transient(self.root)
        dialog.grab_set()

        # Main frame with scrollbar
        main_canvas = tk.Canvas(dialog)
        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=main_canvas.yview)
        scrollable_frame = ttk.Frame(main_canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )

        main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)

        main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Session Name
        name_frame = ttk.LabelFrame(scrollable_frame, text="Session Configuration", padding=10)
        name_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(name_frame, text="Session Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        name_var = tk.StringVar(value=session_data['name'] if session_data else "")
        ttk.Entry(name_frame, textvariable=name_var, width=40).grid(row=0, column=1, sticky=tk.W+tk.E, padx=5, pady=5)
        name_frame.columnconfigure(1, weight=1)

        # Endpoint Selection
        endpoint_frame = ttk.LabelFrame(scrollable_frame, text="FTP Endpoint", padding=10)
        endpoint_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(endpoint_frame, text="Endpoint:").grid(row=0, column=0, sticky=tk.W, pady=5)
        endpoint_var = tk.StringVar()
        endpoint_combo = ttk.Combobox(endpoint_frame, textvariable=endpoint_var, state='readonly', width=37)
        endpoint_combo['values'] = [ep.name for ep in self.endpoints]
        if session_data and session_data['endpoint_id']:
            for ep in self.endpoints:
                if ep.id == session_data['endpoint_id']:
                    endpoint_var.set(ep.name)
                    break
        elif self.endpoints:
            endpoint_var.set(self.endpoints[0].name)
        endpoint_combo.grid(row=0, column=1, sticky=tk.W+tk.E, padx=5, pady=5)
        endpoint_frame.columnconfigure(1, weight=1)

        # Paths
        paths_frame = ttk.LabelFrame(scrollable_frame, text="Sync Paths", padding=10)
        paths_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(paths_frame, text="Source Path (FTP):").grid(row=0, column=0, sticky=tk.W, pady=5)
        source_var = tk.StringVar(value=session_data['source_path'] if session_data and session_data['source_path'] else "")
        source_entry = ttk.Entry(paths_frame, textvariable=source_var, width=40)
        source_entry.grid(row=0, column=1, sticky=tk.W+tk.E, padx=5, pady=5)
        ttk.Button(paths_frame, text="Browse FTP",
                  command=lambda: self.browse_ftp_directory(endpoint_var, source_var)).grid(row=0, column=2, padx=5, pady=5)
        ttk.Label(paths_frame, text="(Relative to endpoint path or absolute)", foreground='gray', font=('TkDefaultFont', 8)).grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(paths_frame, text="Destination Path (Local):").grid(row=2, column=0, sticky=tk.W, pady=5)
        dest_var = tk.StringVar(value=session_data['dest_path'] if session_data and session_data['dest_path'] else "")
        dest_entry = ttk.Entry(paths_frame, textvariable=dest_var, width=40)
        dest_entry.grid(row=2, column=1, sticky=tk.W+tk.E, padx=5, pady=5)
        ttk.Button(paths_frame, text="Browse", command=lambda: self.browse_directory(dest_var)).grid(row=2, column=2, padx=5, pady=5)
        paths_frame.columnconfigure(1, weight=1)

        # Sync Direction
        direction_frame = ttk.LabelFrame(scrollable_frame, text="Sync Direction", padding=10)
        direction_frame.pack(fill=tk.X, padx=10, pady=5)

        direction_var = tk.StringVar(value=session_data['direction'] if session_data else "ftp_to_local")
        ttk.Radiobutton(direction_frame, text="FTP → Local (Download)", variable=direction_var, value="ftp_to_local").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(direction_frame, text="Local → FTP (Upload)", variable=direction_var, value="local_to_ftp").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(direction_frame, text="Bidirectional (Sync both ways)", variable=direction_var, value="bidirectional").pack(anchor=tk.W, pady=2)

        # Folder Filtering
        filter_frame = ttk.LabelFrame(scrollable_frame, text="Folder Filtering", padding=10)
        filter_frame.pack(fill=tk.X, padx=10, pady=5)

        filter_enabled_var = tk.BooleanVar(value=session_data['filter_enabled'] if session_data else False)
        ttk.Checkbutton(filter_frame, text="Enable folder filtering", variable=filter_enabled_var).pack(anchor=tk.W, pady=5)

        ttk.Label(filter_frame, text="Folder names (comma-separated):").pack(anchor=tk.W, pady=2)
        folder_names_var = tk.StringVar(value=session_data['folder_names'] if session_data and session_data['folder_names'] else "")
        ttk.Entry(filter_frame, textvariable=folder_names_var, width=60).pack(fill=tk.X, pady=2)

        ttk.Label(filter_frame, text="Match mode:").pack(anchor=tk.W, pady=5)
        match_mode_var = tk.StringVar(value=session_data['match_mode'] if session_data and session_data['match_mode'] else "contains")
        match_frame = ttk.Frame(filter_frame)
        match_frame.pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(match_frame, text="Contains", variable=match_mode_var, value="contains").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(match_frame, text="Exact", variable=match_mode_var, value="exact").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(match_frame, text="Starts with", variable=match_mode_var, value="startswith").pack(side=tk.LEFT, padx=5)

        case_sensitive_var = tk.BooleanVar(value=session_data['case_sensitive'] if session_data else False)
        ttk.Checkbutton(filter_frame, text="Case sensitive", variable=case_sensitive_var).pack(anchor=tk.W, pady=5)

        # Scheduling
        schedule_frame = ttk.LabelFrame(scrollable_frame, text="Scheduling", padding=10)
        schedule_frame.pack(fill=tk.X, padx=10, pady=5)

        schedule_enabled_var = tk.BooleanVar(value=session_data['schedule_enabled'] if session_data else False)
        ttk.Checkbutton(schedule_frame, text="Enable automatic sync", variable=schedule_enabled_var).pack(anchor=tk.W, pady=5)

        interval_frame = ttk.Frame(schedule_frame)
        interval_frame.pack(anchor=tk.W, pady=5)
        ttk.Label(interval_frame, text="Sync every:").pack(side=tk.LEFT, padx=5)
        interval_var = tk.IntVar(value=session_data['interval'] if session_data and session_data['interval'] else 30)
        ttk.Spinbox(interval_frame, from_=1, to=999, textvariable=interval_var, width=10).pack(side=tk.LEFT, padx=5)
        unit_var = tk.StringVar(value=session_data['unit'] if session_data and session_data['unit'] else "minutes")
        ttk.Combobox(interval_frame, textvariable=unit_var, values=["minutes", "hours", "days"], state='readonly', width=10).pack(side=tk.LEFT, padx=5)

        auto_start_var = tk.BooleanVar(value=session_data['auto_start'] if session_data else False)
        ttk.Checkbutton(schedule_frame, text="Auto-start when application launches", variable=auto_start_var).pack(anchor=tk.W, pady=5)

        # Execution Settings
        exec_frame = ttk.LabelFrame(scrollable_frame, text="Execution Settings", padding=10)
        exec_frame.pack(fill=tk.X, padx=10, pady=5)

        parallel_var = tk.BooleanVar(value=session_data['parallel_execution'] if session_data else True)
        ttk.Checkbutton(exec_frame, text="Allow parallel execution with other sessions", variable=parallel_var).pack(anchor=tk.W, pady=5)
        ttk.Label(exec_frame, text="(If disabled, this session will wait for others to complete)", foreground='gray', font=('TkDefaultFont', 8)).pack(anchor=tk.W, padx=20)

        force_overwrite_var = tk.BooleanVar(value=session_data.get('force_overwrite', False) if session_data else False)
        ttk.Checkbutton(exec_frame, text="Force Overwrite (copy/download all files, ignore modification dates)", variable=force_overwrite_var).pack(anchor=tk.W, pady=5)
        ttk.Label(exec_frame, text="(Overwrites existing files even if they're newer)", foreground='gray', font=('TkDefaultFont', 8)).pack(anchor=tk.W, padx=20)

        # Active Status
        active_var = tk.BooleanVar(value=session_data['active'] if session_data else True)
        ttk.Checkbutton(scrollable_frame, text="Session is active", variable=active_var).pack(anchor=tk.W, padx=10, pady=10)

        # Buttons
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        def save_session():
            # Validation
            name = name_var.get().strip()
            if not name:
                messagebox.showerror("Error", "Please enter a session name.")
                return

            endpoint_name = endpoint_var.get()
            if not endpoint_name:
                messagebox.showerror("Error", "Please select an endpoint.")
                return

            # Get endpoint ID
            endpoint_id = None
            for ep in self.endpoints:
                if ep.name == endpoint_name:
                    endpoint_id = ep.id
                    break

            if not endpoint_id:
                messagebox.showerror("Error", "Invalid endpoint selected.")
                return

            dest_path = dest_var.get().strip()
            if not dest_path:
                messagebox.showerror("Error", "Please enter a destination path.")
                return

            # Save to database
            try:
                conn = sqlite3.connect(self.ftp_sync.db.db_path)
                cursor = conn.cursor()

                if session_data:  # Edit existing
                    cursor.execute('''
                        UPDATE ftp_sync_configs
                        SET name=?, endpoint_id=?, source_path=?, dest_path=?, sync_direction=?,
                            folder_filter_enabled=?, folder_names=?, match_mode=?, case_sensitive=?,
                            schedule_enabled=?, schedule_interval=?, schedule_unit=?, auto_start=?,
                            parallel_execution=?, active=?, force_overwrite=?
                        WHERE id=?
                    ''', (name, endpoint_id, source_var.get().strip(), dest_path, direction_var.get(),
                          1 if filter_enabled_var.get() else 0, folder_names_var.get().strip(),
                          match_mode_var.get(), 1 if case_sensitive_var.get() else 0,
                          1 if schedule_enabled_var.get() else 0, interval_var.get(), unit_var.get(),
                          1 if auto_start_var.get() else 0, 1 if parallel_var.get() else 0,
                          1 if active_var.get() else 0, 1 if force_overwrite_var.get() else 0, session_data['id']))
                else:  # Add new
                    cursor.execute('''
                        INSERT INTO ftp_sync_configs
                        (name, endpoint_id, source_path, dest_path, sync_direction, folder_filter_enabled,
                         folder_names, match_mode, case_sensitive, schedule_enabled, schedule_interval,
                         schedule_unit, auto_start, parallel_execution, active, force_overwrite, created_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (name, endpoint_id, source_var.get().strip(), dest_path, direction_var.get(),
                          1 if filter_enabled_var.get() else 0, folder_names_var.get().strip(),
                          match_mode_var.get(), 1 if case_sensitive_var.get() else 0,
                          1 if schedule_enabled_var.get() else 0, interval_var.get(), unit_var.get(),
                          1 if auto_start_var.get() else 0, 1 if parallel_var.get() else 0,
                          1 if active_var.get() else 0, 1 if force_overwrite_var.get() else 0, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                conn.commit()
                conn.close()

                # Reload sessions
                self.load_ftp_sessions()

                dialog.destroy()
                messagebox.showinfo("Success", f"Session '{name}' saved successfully.")

            except sqlite3.IntegrityError:
                messagebox.showerror("Error", f"A session with the name '{name}' already exists.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save session: {e}")

        ttk.Button(button_frame, text="Save", command=save_session).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def delete_ftp_session(self):
        """Delete selected FTP sync session"""
        selection = self.ftp_sessions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a session to delete.")
            return

        item = selection[0]
        values = self.ftp_sessions_tree.item(item, 'values')
        session_name = values[0]

        response = messagebox.askyesno("Confirm Delete",
                                      f"Delete FTP sync session '{session_name}'?")
        if not response:
            return

        try:
            # Get session ID from tags
            tags = self.ftp_sessions_tree.item(item, 'tags')
            if tags:
                session_id = int(tags[0])

                # Delete from database
                conn = sqlite3.connect(self.ftp_sync.db.db_path)
                cursor = conn.cursor()
                cursor.execute('DELETE FROM ftp_sync_configs WHERE id = ?', (session_id,))
                conn.commit()
                conn.close()

                # Remove from tree
                self.ftp_sessions_tree.delete(item)

                messagebox.showinfo("Success", f"Session '{session_name}' deleted.")
                self.ftp_multi_status_var.set(f"Deleted session: {session_name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete session: {e}")

    def update_ftp_session_status(self, session_id, status):
        """Update the status of a specific session in the tree"""
        try:
            # Find the tree item with this session_id
            for item in self.ftp_sessions_tree.get_children():
                tags = self.ftp_sessions_tree.item(item, 'tags')
                if tags and int(tags[0]) == session_id:
                    # Get current values
                    values = list(self.ftp_sessions_tree.item(item, 'values'))
                    # Update status column (index 6)
                    values[6] = status
                    self.ftp_sessions_tree.item(item, values=values)
                    break
        except Exception as e:
            print(f"Error updating session status: {e}")

    def start_ftp_session(self):
        """Start selected FTP sync session"""
        selection = self.ftp_sessions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a session to start.")
            return

        # Get session ID from tags
        item = selection[0]
        session_id = int(self.ftp_sessions_tree.item(item, 'tags')[0])

        # Check if already running
        if session_id in self.ftp_session_threads and self.ftp_session_threads[session_id].is_alive():
            messagebox.showwarning("Warning", "This session is already running.")
            return

        # Get session data
        if session_id not in self.ftp_sessions:
            messagebox.showerror("Error", "Session data not found.")
            return

        session = self.ftp_sessions[session_id]

        # Update status in tree
        self.ftp_sessions_tree.item(item, values=(
            session['name'],
            self.ftp_sessions_tree.item(item, 'values')[1],  # Endpoint
            self.ftp_sessions_tree.item(item, 'values')[2],  # Direction
            self.ftp_sessions_tree.item(item, 'values')[3],  # Filter
            self.ftp_sessions_tree.item(item, 'values')[4],  # Schedule
            "🔄 Running",
            self.ftp_sessions_tree.item(item, 'values')[6]   # Last Sync
        ))

        # Start session in background thread
        thread = threading.Thread(target=self.run_ftp_session, args=(session_id, session), daemon=True)
        self.ftp_session_threads[session_id] = thread
        thread.start()

        self.ftp_multi_status_var.set(f"Started session: {session['name']}")

    def stop_ftp_session(self):
        """Stop selected FTP sync session"""
        selection = self.ftp_sessions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a session to stop.")
            return

        # Get session ID from tags
        item = selection[0]
        session_id = int(self.ftp_sessions_tree.item(item, 'tags')[0])

        # Check if running
        if session_id not in self.ftp_session_threads or not self.ftp_session_threads[session_id].is_alive():
            messagebox.showwarning("Warning", "This session is not running.")
            return

        # Set stop flag (we'll need to add this to the session data)
        if session_id in self.ftp_sessions:
            self.ftp_sessions[session_id]['stop_requested'] = True

        self.ftp_multi_status_var.set(f"Stopping session...")
        messagebox.showinfo("Stop Requested", "Session will stop after current operation completes.")

    def run_ftp_session(self, session_id, session):
        """Run FTP sync session in background"""
        try:
            # Initialize stop flag
            session['stop_requested'] = False

            # Get endpoint
            endpoint = None
            for ep in self.endpoints:
                if ep.id == session['endpoint_id']:
                    endpoint = ep
                    break

            if not endpoint:
                raise Exception("Endpoint not found")

            # Build paths
            if session['source_path']:
                remote_path = f"{endpoint.remote_path.rstrip('/')}/{session['source_path'].strip('/')}"
            else:
                remote_path = endpoint.remote_path

            local_path = session['dest_path']

            # Log start
            log_msg = f"[{datetime.now().strftime('%H:%M:%S')}] Starting FTP session: {session['name']}\n"
            log_msg += f"  Endpoint: {endpoint.name}\n"
            log_msg += f"  Remote: {remote_path}\n"
            log_msg += f"  Local: {local_path}\n"
            log_msg += f"  Direction: {session['direction']}\n"
            print(log_msg)

            # Update status to show scanning
            def update_status(msg):
                self.root.after(0, lambda: self.ftp_multi_status_var.set(msg))
                # Also update the tree item status
                self.root.after(0, lambda: self.update_ftp_session_status(session_id, msg))

            update_status(f"🔍 Scanning: {session['name']}...")

            # Get or create FTP manager
            if endpoint.id not in self.ftp_sync.ftp_managers:
                self.ftp_sync.ftp_managers[endpoint.id] = FTPManager(
                    endpoint.host, endpoint.username, endpoint.password, endpoint.port
                )

            ftp_manager = self.ftp_sync.ftp_managers[endpoint.id]

            # Ensure connected
            if not ftp_manager.ensure_connected():
                raise Exception("Failed to connect to FTP server")

            # Apply folder filtering if enabled
            filter_enabled = session.get('filter_enabled', False)
            folder_names = []

            if filter_enabled:
                folder_names = [f.strip() for f in session.get('folder_names', '').split(',') if f.strip()]

            # Scan for files
            print(f"Scanning {remote_path}...")
            update_status(f"Scanning files: {session['name']}...")

            # Use the existing scan_endpoint method
            temp_endpoint = FTPEndpoint(
                id=endpoint.id,
                name=endpoint.name,
                host=endpoint.host,
                port=endpoint.port,
                username=endpoint.username,
                password=endpoint.password,
                remote_path=remote_path,
                local_path=local_path,
                is_main_source=True,
                connection_status="connected"
            )

            # Copy folder filter settings
            if filter_enabled:
                temp_endpoint.folder_filter_enabled = True
                temp_endpoint.folder_names = folder_names
                temp_endpoint.folder_match_mode = session.get('match_mode', 'exact')
                temp_endpoint.folder_case_sensitive = session.get('case_sensitive', False)
            else:
                temp_endpoint.folder_filter_enabled = False

            # Get force_overwrite setting
            force_overwrite = session.get('force_overwrite', False)

            operations = self.ftp_sync.scan_endpoint(temp_endpoint, session['direction'], force_overwrite)

            print(f"Found {len(operations)} operations")
            update_status(f"Found {len(operations)} files to sync: {session['name']}")

            # Check for stop request
            if session.get('stop_requested'):
                raise Exception("Stopped by user")

            # Perform sync
            successful = 0
            failed = 0
            skipped = 0

            for i, file_info in enumerate(operations):
                # Check for stop request
                if session.get('stop_requested'):
                    raise Exception("Stopped by user")

                # Update progress
                progress = f"Syncing {i+1}/{len(operations)}: {session['name']}"
                update_status(progress)

                if file_info.operation_type == 'skip':
                    skipped += 1
                    continue

                # Sync the file
                success, error = self.ftp_sync.sync_file(temp_endpoint, file_info, session['direction'])

                if success:
                    successful += 1
                    print(f"✓ {file_info.operation_type}: {file_info.ftp_path}")
                else:
                    failed += 1
                    print(f"✗ {file_info.operation_type}: {file_info.ftp_path} - {error}")

            # Summary
            summary = f"✅ {successful} synced, {skipped} skipped, {failed} failed"
            print(f"\nSession '{session['name']}' completed: {summary}")

            # Update database
            conn = sqlite3.connect(self.ftp_sync.db.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE ftp_sync_configs
                SET last_sync=?, last_status=?
                WHERE id=?
            ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), summary, session_id))
            conn.commit()
            conn.close()

            # Update UI
            self.root.after(0, self.load_ftp_sessions)
            self.root.after(0, lambda: self.ftp_multi_status_var.set(f"Completed: {session['name']} - {summary}"))

        except Exception as e:
            # Capture error message immediately
            error_msg = str(e)
            session_name = session['name']
            print(f"Error in FTP session {session_name}: {error_msg}")

            # Update database with error
            try:
                conn = sqlite3.connect(self.ftp_sync.db.db_path)
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE ftp_sync_configs
                    SET last_sync=?, last_status=?
                    WHERE id=?
                ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), f'❌ Error: {error_msg[:50]}', session_id))
                conn.commit()
                conn.close()
            except:
                pass

            # Update UI
            self.root.after(0, self.load_ftp_sessions)
            self.root.after(0, lambda: self.ftp_multi_status_var.set(f"Session '{session_name}' failed: {error_msg}"))

    def start_all_ftp_sessions(self):
        """Start all active FTP sync sessions"""
        if not self.ftp_sessions:
            messagebox.showinfo("Info", "No FTP sessions configured.")
            return

        # Get active sessions
        active_sessions = [(sid, s) for sid, s in self.ftp_sessions.items() if s['active']]

        if not active_sessions:
            messagebox.showinfo("Info", "No active sessions to start.")
            return

        # Separate parallel and sequential sessions
        parallel_sessions = [(sid, s) for sid, s in active_sessions if s['parallel_execution']]
        sequential_sessions = [(sid, s) for sid, s in active_sessions if not s['parallel_execution']]

        started_count = 0

        # Start parallel sessions
        for session_id, session in parallel_sessions:
            # Check if already running
            if session_id in self.ftp_session_threads and self.ftp_session_threads[session_id].is_alive():
                continue

            # Start in background thread
            thread = threading.Thread(target=self.run_ftp_session, args=(session_id, session), daemon=True)
            self.ftp_session_threads[session_id] = thread
            thread.start()
            started_count += 1

        # Start sequential sessions (one after another)
        if sequential_sessions:
            def run_sequential():
                for session_id, session in sequential_sessions:
                    if session_id in self.ftp_session_threads and self.ftp_session_threads[session_id].is_alive():
                        continue
                    self.run_ftp_session(session_id, session)

            thread = threading.Thread(target=run_sequential, daemon=True)
            thread.start()
            started_count += len(sequential_sessions)

        self.ftp_multi_status_var.set(f"Started {started_count} sessions")
        self.load_ftp_sessions()  # Refresh display
        messagebox.showinfo("Sessions Started", f"Started {started_count} FTP sync sessions.")

    def stop_all_ftp_sessions(self):
        """Stop all running FTP sync sessions"""
        stopped_count = 0

        for session_id, thread in list(self.ftp_session_threads.items()):
            if thread.is_alive():
                # Set stop flag
                if session_id in self.ftp_sessions:
                    self.ftp_sessions[session_id]['stop_requested'] = True
                stopped_count += 1

        if stopped_count > 0:
            self.ftp_multi_status_var.set(f"Stopping {stopped_count} sessions...")
            messagebox.showinfo("Stop Requested", f"Requested stop for {stopped_count} running sessions.")
        else:
            messagebox.showinfo("Info", "No sessions are currently running.")

    def view_ftp_session_logs(self):
        """View logs for selected FTP session"""
        selection = self.ftp_sessions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a session to view logs.")
            return

        # Get session ID and name
        item = selection[0]
        session_id = int(self.ftp_sessions_tree.item(item, 'tags')[0])
        session_name = self.ftp_sessions_tree.item(item, 'values')[0]

        # Create log viewer dialog
        log_dialog = tk.Toplevel(self.root)
        log_dialog.title(f"Session Logs - {session_name}")
        log_dialog.geometry("800x600")
        log_dialog.transient(self.root)

        # Log text area
        log_text = scrolledtext.ScrolledText(log_dialog, wrap=tk.WORD, font=('Courier', 9))
        log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Load logs (placeholder - in real implementation, logs would be stored)
        log_text.insert(tk.END, f"=== Session Logs: {session_name} ===\n\n")
        log_text.insert(tk.END, "Log functionality will store and display:\n")
        log_text.insert(tk.END, "• Sync start/end times\n")
        log_text.insert(tk.END, "• Files transferred\n")
        log_text.insert(tk.END, "• Errors and warnings\n")
        log_text.insert(tk.END, "• Performance metrics\n\n")
        log_text.insert(tk.END, "Logs will be implemented in the next update.\n")
        log_text.config(state=tk.DISABLED)

        # Close button
        ttk.Button(log_dialog, text="Close", command=log_dialog.destroy).pack(pady=10)

    def auto_start_sessions(self):
        """Auto-start FTP and Local sessions that have auto_start enabled"""
        try:
            # Auto-start FTP sessions
            ftp_auto_started = 0
            for session_id, session in self.ftp_sessions.items():
                if session.get('auto_start') and session.get('active') and session.get('schedule_enabled'):
                    # Check if not already running
                    if session_id not in self.ftp_session_threads or not self.ftp_session_threads[session_id].is_alive():
                        thread = threading.Thread(target=self.run_ftp_session, args=(session_id, session), daemon=True)
                        self.ftp_session_threads[session_id] = thread
                        thread.start()
                        ftp_auto_started += 1
                        print(f"Auto-started FTP session: {session['name']}")

            # Auto-start Local sessions
            local_auto_started = 0
            if hasattr(self, 'session_configs'):
                for session_id, config in self.session_configs.items():
                    if config.get('auto_start') and config.get('active') and config.get('schedule_enabled'):
                        # Check if not already running
                        if session_id not in self.session_threads or not self.session_threads[session_id].is_alive():
                            thread = threading.Thread(target=self.run_session_sync, args=(session_id,), daemon=True)
                            self.session_threads[session_id] = thread
                            thread.start()
                            local_auto_started += 1
                            print(f"Auto-started Local session: {config['name']}")

            # Update status
            total_started = ftp_auto_started + local_auto_started
            if total_started > 0:
                if ftp_auto_started > 0:
                    self.ftp_multi_status_var.set(f"Auto-started {ftp_auto_started} FTP sessions")
                    self.load_ftp_sessions()  # Refresh display
                if local_auto_started > 0 and hasattr(self, 'multi_session_status_var'):
                    self.multi_session_status_var.set(f"Auto-started {local_auto_started} Local sessions")
                    self.refresh_sessions_display()  # Refresh display
                print(f"Auto-started {ftp_auto_started} FTP and {local_auto_started} Local sessions on application launch")

        except Exception as e:
            print(f"Error in auto-start: {e}")

    def start_local_sync(self):
        """Start local sync operation"""
        if not self.local_operations:
            messagebox.showwarning("Warning", "Please scan operations first.")
            return

        # Filter operations to sync (exclude skipped)
        operations_to_sync = [op for op in self.local_operations if op['operation'] != "skip"]

        if self.local_dry_run_var.get():
            messagebox.showinfo("Dry Run",
                f"Local dry run completed. {len(operations_to_sync)} operations would be performed.")
            return

        if not operations_to_sync:
            messagebox.showinfo("Local Sync", "No operations to perform - all files are up to date!")
            return

        self.local_is_syncing = True
        self.local_progress_status_var.set("Starting local sync...")

        # Start sync thread
        self.local_sync_thread = threading.Thread(target=self.perform_local_sync,
                                                 args=(operations_to_sync,), daemon=True)
        self.local_sync_thread.start()

    def perform_local_sync(self, operations):
        """Perform local sync operations"""
        total_operations = len(operations)
        completed = 0
        errors = []

        for i, operation in enumerate(operations):
            try:
                # Update progress
                progress = (i / total_operations) * 100
                self.root.after(0, lambda p=progress: self.local_progress_var.set(p))

                status = f"Copying {os.path.basename(operation['source'])} ({i+1}/{total_operations})"
                self.root.after(0, lambda s=status: self.local_progress_status_var.set(s))

                if operation['operation'] == 'copy':
                    # Ensure destination directory exists
                    dest_dir = os.path.dirname(operation['destination'])
                    os.makedirs(dest_dir, exist_ok=True)

                    # Copy file
                    shutil.copy2(operation['source'], operation['destination'])
                    completed += 1
                    print(f"Copied: {operation['source']} -> {operation['destination']}")

            except Exception as e:
                error_msg = f"Failed to copy {operation['source']}: {str(e)}"
                errors.append(error_msg)
                print(f"Error: {error_msg}")
                continue

        # Update UI with results
        self.root.after(0, self.show_local_sync_results, completed, total_operations, errors)

    def show_local_sync_results(self, completed, total, errors):
        """Show local sync results"""
        self.local_is_syncing = False
        self.local_progress_var.set(100)

        if errors:
            error_summary = f"Local sync completed with errors:\n\n"
            error_summary += f"✅ Successful: {completed}/{total}\n"
            error_summary += f"❌ Failed: {len(errors)}\n\n"
            error_summary += "Errors:\n" + "\n".join(errors[:5])  # Show first 5 errors
            if len(errors) > 5:
                error_summary += f"\n... and {len(errors) - 5} more errors"

            self.local_progress_status_var.set(f"Sync completed with {len(errors)} errors")
            messagebox.showwarning("Local Sync Completed with Errors", error_summary)
        else:
            self.local_progress_status_var.set(f"Local sync completed successfully - {completed} files copied")
            messagebox.showinfo("Local Sync Complete", f"Successfully copied {completed} files!")

    def stop_local_sync(self):
        """Stop local sync operation"""
        if self.local_is_syncing:
            self.local_is_syncing = False
            self.local_progress_status_var.set("Local sync stopped by user")
            messagebox.showinfo("Local Sync Stopped", "Local sync operation has been stopped.")
        else:
            messagebox.showinfo("Local Sync", "No local sync operation is currently running.")

    def toggle_local_schedule(self):
        """Toggle local schedule controls"""
        enabled = self.local_enable_schedule_var.get()

        # Enable/disable schedule controls
        state = "normal" if enabled else "disabled"

        # Find and update schedule controls (only if they exist)
        try:
            if hasattr(self, 'local_start_schedule_btn'):
                self.local_start_schedule_btn.config(state=state)
            if hasattr(self, 'local_stop_schedule_btn'):
                stop_state = "disabled" if not enabled else ("disabled" if not self.local_schedule_active else "normal")
                self.local_stop_schedule_btn.config(state=stop_state)

            # Update status display (Phase 4)
            if hasattr(self, 'local_schedule_state_icon_var'):
                if enabled:
                    self.local_schedule_state_icon_var.set("⏹️ Ready")
                else:
                    self.local_schedule_state_icon_var.set("⏹️ Disabled")
        except:
            pass  # Controls might not be created yet

        if not enabled and self.local_schedule_active:
            self.stop_local_schedule()

    def start_local_schedule(self):
        """Start scheduled local sync"""
        source_dir = self.local_source_var.get().strip()
        dest_dir = self.local_dest_var.get().strip()

        if not source_dir or not dest_dir:
            messagebox.showwarning("Warning", "Please select both source and destination directories before starting scheduled sync.")
            return

        if not os.path.exists(source_dir):
            messagebox.showerror("Error", f"Source directory does not exist: {source_dir}")
            return

        # Get interval settings
        try:
            interval_value = int(self.local_interval_value_var.get())
            interval_unit = self.local_interval_unit_var.get()
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid interval value.")
            return

        if interval_value <= 0:
            messagebox.showerror("Error", "Interval value must be greater than 0.")
            return

        # Convert to seconds
        unit_multipliers = {
            "seconds": 1,
            "minutes": 60,
            "hours": 3600,
            "days": 86400
        }

        interval_seconds = interval_value * unit_multipliers[interval_unit]

        # Start scheduling
        self.local_schedule_active = True
        self.local_next_sync_time = datetime.now() + timedelta(seconds=interval_seconds)

        # Update UI
        self.local_start_schedule_btn.config(state="disabled")
        self.local_stop_schedule_btn.config(state="normal")
        if hasattr(self, 'local_pause_schedule_btn'):
            self.local_pause_schedule_btn.config(state="normal")
        self.local_schedule_status_var.set(f"Scheduled sync active - every {interval_value} {interval_unit}")
        self.update_local_next_sync_display()

        # Update Phase 4 status displays
        if hasattr(self, 'local_schedule_state_icon_var'):
            self.local_schedule_state_icon_var.set("⏰ Active")
        if hasattr(self, 'local_schedule_paused'):
            self.local_schedule_paused = False

        # Start schedule thread
        self.local_schedule_thread = threading.Thread(target=self.local_schedule_loop,
                                                     args=(interval_seconds,), daemon=True)
        self.local_schedule_thread.start()

        messagebox.showinfo("Schedule Started", f"Local sync scheduled every {interval_value} {interval_unit}")

    def stop_local_schedule(self):
        """Stop scheduled local sync"""
        self.local_schedule_active = False
        self.local_next_sync_time = None

        # Update UI
        self.local_start_schedule_btn.config(state="normal")
        self.local_stop_schedule_btn.config(state="disabled")
        self.local_schedule_status_var.set("Scheduled sync disabled")
        self.local_next_sync_var.set("")

        messagebox.showinfo("Schedule Stopped", "Local sync schedule has been stopped.")

    def pause_local_schedule(self):
        """Pause local schedule temporarily"""
        if not self.local_schedule_active:
            messagebox.showwarning("Warning", "No schedule is currently running.")
            return

        # Toggle pause state
        if not hasattr(self, 'local_schedule_paused'):
            self.local_schedule_paused = False

        self.local_schedule_paused = not self.local_schedule_paused

        if self.local_schedule_paused:
            self.local_pause_schedule_btn.config(text="▶️ Resume")
            self.local_schedule_state_icon_var.set("⏸️ Paused")
            messagebox.showinfo("Schedule Paused", "Local sync schedule has been paused.")
        else:
            self.local_pause_schedule_btn.config(text="⏸️ Pause")
            self.local_schedule_state_icon_var.set("⏰ Active")
            messagebox.showinfo("Schedule Resumed", "Local sync schedule has been resumed.")

    def run_local_schedule_now(self):
        """Run scheduled sync immediately"""
        source_dir = self.local_source_var.get().strip()
        dest_dir = self.local_dest_var.get().strip()

        if not source_dir or not dest_dir:
            messagebox.showwarning("Warning", "Please select both source and destination directories.")
            return

        if not os.path.exists(source_dir):
            messagebox.showerror("Error", f"Source directory does not exist: {source_dir}")
            return

        # Run sync in background
        response = messagebox.askyesno("Run Now",
                                      "Run local sync now?\n\n"
                                      f"Source: {source_dir}\n"
                                      f"Destination: {dest_dir}")
        if response:
            threading.Thread(target=self.scan_local_operations, daemon=True).start()
            messagebox.showinfo("Sync Started", "Local sync started. Check the operations tab for progress.")

    def view_local_schedule_history(self):
        """View schedule run history"""
        messagebox.showinfo("Schedule History",
                          "Schedule history feature will show:\n\n"
                          "• Past sync runs\n"
                          "• Success/failure status\n"
                          "• Files synced\n"
                          "• Duration\n"
                          "• Error messages\n\n"
                          "This feature will be fully implemented in the next update.")

    def local_schedule_loop(self, interval_seconds):
        """Background loop for scheduled local sync"""
        while self.local_schedule_active:
            try:
                # Wait for the interval
                time.sleep(min(interval_seconds, 60))  # Check every minute or interval, whichever is shorter

                if not self.local_schedule_active:
                    break

                # Update next sync time display
                if self.local_next_sync_time and datetime.now() < self.local_next_sync_time:
                    self.root.after(0, self.update_local_next_sync_display)
                    continue

                # Time for sync
                print(f"Scheduled local sync starting at {datetime.now()}")

                # Update next sync time
                self.local_next_sync_time = datetime.now() + timedelta(seconds=interval_seconds)
                self.root.after(0, self.update_local_next_sync_display)

                # Perform scheduled sync
                self.root.after(0, self.perform_scheduled_local_sync)

            except Exception as e:
                print(f"Error in local schedule loop: {e}")
                time.sleep(60)  # Wait a minute before retrying

    def update_local_next_sync_display(self):
        """Update the next sync time display"""
        if self.local_next_sync_time:
            time_until = self.local_next_sync_time - datetime.now()
            if time_until.total_seconds() > 0:
                hours, remainder = divmod(int(time_until.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)

                if hours > 0:
                    time_str = f"Next sync in: {hours}h {minutes}m"
                elif minutes > 0:
                    time_str = f"Next sync in: {minutes}m {seconds}s"
                else:
                    time_str = f"Next sync in: {seconds}s"

                self.local_next_sync_var.set(time_str)
            else:
                self.local_next_sync_var.set("Sync starting...")
        else:
            self.local_next_sync_var.set("")

    def perform_scheduled_local_sync(self):
        """Perform a scheduled local sync"""
        if self.local_is_syncing:
            print("Local sync already in progress, skipping scheduled sync")
            return

        source_dir = self.local_source_var.get().strip()
        dest_dir = self.local_dest_var.get().strip()

        if not source_dir or not dest_dir:
            print("Source or destination directory not set, skipping scheduled sync")
            return

        print(f"Starting scheduled local sync: {source_dir} -> {dest_dir}")

        # Auto-scan if enabled
        if self.local_auto_scan_var.get():
            # Perform scan in background
            scan_thread = threading.Thread(target=self.perform_scheduled_scan_and_sync,
                                          args=(source_dir, dest_dir), daemon=True)
            scan_thread.start()
        else:
            # Use existing operations if available
            if self.local_operations:
                operations_to_sync = [op for op in self.local_operations if op['operation'] != "skip"]
                if operations_to_sync or not self.local_skip_if_no_changes_var.get():
                    sync_thread = threading.Thread(target=self.perform_local_sync,
                                                  args=(operations_to_sync,), daemon=True)
                    sync_thread.start()
                else:
                    print("No changes detected, skipping scheduled sync")
            else:
                print("No operations available, skipping scheduled sync")

    def perform_scheduled_scan_and_sync(self, source_dir, dest_dir):
        """Perform scan and sync for scheduled operation"""
        try:
            # Perform scan
            sync_direction = self.local_sync_direction_var.get()
            operations = []

            # Get folder filter settings
            folder_filter_enabled = self.local_enable_folder_filter_var.get()
            folder_names = []
            match_mode = "exact"
            case_sensitive = False

            if folder_filter_enabled:
                folder_names_text = self.local_folder_names_var.get()
                folder_names = [name.strip() for name in folder_names_text.split(',') if name.strip()]
                match_mode = self.local_folder_match_mode_var.get()
                case_sensitive = self.local_case_sensitive_var.get()

            # Scan operations (similar to perform_local_scan but simplified)
            if sync_direction in ["source_to_dest", "bidirectional"]:
                source_files = self.scan_local_directory(source_dir)

                if folder_filter_enabled and folder_names:
                    source_files = self.apply_local_folder_filter(source_files, source_dir, folder_names, match_mode, case_sensitive)

                for file_info in source_files:
                    rel_path = os.path.relpath(file_info['path'], source_dir)
                    dest_path = os.path.join(dest_dir, rel_path)

                    operation_type = self.determine_local_operation(file_info['path'], dest_path, file_info)
                    if operation_type != "skip":
                        operations.append({
                            'operation': operation_type,
                            'source': file_info['path'],
                            'destination': dest_path,
                            'size': file_info['size'],
                            'modified': file_info['modified']
                        })

            # Filter operations to sync
            operations_to_sync = [op for op in operations if op['operation'] != "skip"]

            if operations_to_sync:
                print(f"Scheduled sync: {len(operations_to_sync)} operations found")
                # Update operations list in UI thread
                self.root.after(0, lambda: setattr(self, 'local_operations', operations))

                # Perform sync
                self.perform_local_sync(operations_to_sync)
            elif self.local_skip_if_no_changes_var.get():
                print("Scheduled sync: No changes detected, skipping")
            else:
                print("Scheduled sync: No operations needed")

        except Exception as e:
            print(f"Error in scheduled scan and sync: {e}")

    # Report methods
    def generate_sync_report(self):
        """Generate sync operations report"""
        try:
            conn = sqlite3.connect(self.ftp_sync.db.db_path)
            cursor = conn.cursor()
            
            # Get recent sync operations
            cursor.execute('''
                SELECT so.*, fe.name as endpoint_name 
                FROM sync_operations so
                LEFT JOIN ftp_endpoints fe ON so.endpoint_id = fe.id
                ORDER BY so.timestamp DESC 
                LIMIT 100
            ''')
            operations = cursor.fetchall()
            
            # Get sync sessions
            cursor.execute('''
                SELECT ss.*, fe.name as endpoint_name 
                FROM sync_sessions ss
                LEFT JOIN ftp_endpoints fe ON ss.endpoint_id = fe.id
                ORDER BY ss.session_start DESC 
                LIMIT 20
            ''')
            sessions = cursor.fetchall()
            
            conn.close()
            
            # Generate report
            report = "F2L SYNC OPERATIONS REPORT\n"
            report += "=" * 80 + "\n\n"
            
            # Endpoint summary
            report += "CONFIGURED ENDPOINTS\n"
            report += "-" * 40 + "\n"
            for endpoint in self.endpoints:
                status_icon = "✓" if endpoint.connection_status == "connected" else "✗"
                main_icon = "★" if endpoint.is_main_source else "○"
                auto_icon = "⚡" if endpoint.auto_sync_enabled else "○"
                
                report += f"{status_icon} {endpoint.name} ({endpoint.host}:{endpoint.port})\n"
                report += f"   Remote: {endpoint.remote_path} → Local: {endpoint.local_path}\n"
                report += f"   Main Source: {main_icon} | Auto Sync: {auto_icon} ({endpoint.sync_interval}min)\n"
                report += f"   Status: {endpoint.connection_status.title()}\n\n"
            
            # Recent sessions
            if sessions:
                report += "RECENT SYNC SESSIONS\n"
                report += "-" * 40 + "\n"
                for session in sessions[:10]:
                    endpoint_name = session[9] or "Unknown"
                    start_time = session[1][:16] if session[1] else "Unknown"
                    end_time = session[2][:16] if session[2] else "In Progress"
                    
                    report += f"Session: {endpoint_name} | {start_time} - {end_time}\n"
                    report += f"Direction: {session[3]} | Files: {session[4]} total\n"
                    report += f"Success: {session[5]} | Failed: {session[6]}\n"
                    report += f"Data: {self.format_file_size(session[7] or 0)}\n\n"
            
            # Recent operations
            if operations:
                report += "RECENT OPERATIONS\n"
                report += "-" * 40 + "\n"
                for op in operations[:30]:
                    endpoint_name = op[10] or "Unknown"
                    status = "✓" if op[7] else "✗"
                    direction = "↓" if op[5] == "ftp_to_local" else "↑" if op[5] == "local_to_ftp" else "↔"
                    timestamp = op[1][:16] if op[1] else "Unknown"
                    
                    report += f"{status} {direction} {endpoint_name} | {op[4]} | "
                    report += f"{os.path.basename(op[3])} | {timestamp}\n"
                    if op[8]:  # Error message
                        report += f"    Error: {op[8]}\n"
            
            self.report_text.delete(1.0, tk.END)
            self.report_text.insert(1.0, report)
            
        except Exception as e:
            messagebox.showerror("Report Error", f"Failed to generate sync report: {str(e)}")
    
    def generate_health_report(self):
        """Generate health monitoring report"""
        report = "F2L HEALTH MONITORING REPORT\n"
        report += "=" * 80 + "\n\n"
        
        report += f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        if not self.endpoints:
            report += "No endpoints configured.\n"
        else:
            total_endpoints = len(self.endpoints)
            connected_endpoints = len([ep for ep in self.endpoints if ep.connection_status == "connected"])
            
            report += f"ENDPOINT HEALTH SUMMARY\n"
            report += "-" * 40 + "\n"
            report += f"Total Endpoints: {total_endpoints}\n"
            report += f"Connected: {connected_endpoints}\n"
            report += f"Disconnected: {total_endpoints - connected_endpoints}\n"
            report += f"Health Monitoring: {'Active' if self.ftp_sync.health_check_running else 'Inactive'}\n\n"
            
            report += "INDIVIDUAL ENDPOINT STATUS\n"
            report += "-" * 40 + "\n"
            
            for endpoint in self.endpoints:
                status_icon = "✓" if endpoint.connection_status == "connected" else "✗"
                last_check = endpoint.last_health_check.strftime('%Y-%m-%d %H:%M:%S') if endpoint.last_health_check else "Never"
                
                report += f"{status_icon} {endpoint.name}\n"
                report += f"    Host: {endpoint.host}:{endpoint.port}\n"
                report += f"    Status: {endpoint.connection_status.upper()}\n"
                report += f"    Last Health Check: {last_check}\n"
                report += f"    Auto Sync: {'Enabled' if endpoint.auto_sync_enabled else 'Disabled'}\n\n"
        
        # Add system information
        report += "SYSTEM INFORMATION\n"
        report += "-" * 40 + "\n"
        report += f"System Tray: {'Available' if TRAY_AVAILABLE else 'Not Available'}\n"
        report += f"Scheduling: {'Available' if SCHEDULE_AVAILABLE else 'Not Available'}\n"
        report += f"Database: f2l_sync.db\n"
        report += f"Application: F2L v1.0\n"
        
        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(1.0, report)
    
    def export_report(self):
        """Export current report to file"""
        filename = filedialog.asksaveasfilename(
            title="Export Report",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfilename=f"f2l_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.report_text.get(1.0, tk.END))
                messagebox.showinfo("Export Complete", f"Report exported to:\n{filename}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export report: {str(e)}")
    
    def clear_logs(self):
        """Clear all logs"""
        if messagebox.askyesno("Confirm", "Clear all sync logs and history?\n\nThis will permanently delete all operation logs and session history."):
            try:
                conn = sqlite3.connect(self.ftp_sync.db.db_path)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM sync_operations")
                cursor.execute("DELETE FROM sync_sessions")
                conn.commit()
                conn.close()
                
                self.report_text.delete(1.0, tk.END)
                self.health_log.delete(1.0, tk.END)
                self.health_log.insert(tk.END, f"F2L Health Monitor Restarted - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                self.health_log.insert(tk.END, "All logs have been cleared.\n\n")
                
                messagebox.showinfo("Success", "All logs cleared successfully.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to clear logs: {str(e)}")
    
    def run(self):
        """Main application loop with proper cleanup"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            print("\nApplication interrupted by user")
        finally:
            # Comprehensive cleanup
            print("Performing final cleanup...")

            # Stop health monitoring
            try:
                self.ftp_sync.stop_health_monitoring()
            except Exception as e:
                print(f"Error stopping health monitoring: {e}")

            # Disconnect all FTP connections
            try:
                results = self.ftp_sync.disconnect_all_endpoints()
                print(f"Final FTP cleanup: {results['successful']}/{results['total']} endpoints disconnected")
            except Exception as e:
                print(f"Error during final FTP cleanup: {e}")

            # Stop tray icon
            if self.tray_icon:
                try:
                    self.tray_icon.stop()
                except Exception as e:
                    print(f"Error stopping tray icon: {e}")

            print("Final cleanup complete")

def check_single_instance():
    """Check if another instance is already running"""
    lock_file = "f2l_app.lock"

    # Check if lock file exists
    if os.path.exists(lock_file):
        try:
            # Try to read the PID from lock file
            with open(lock_file, 'r') as f:
                pid = int(f.read().strip())

            # Check if process with this PID is still running
            try:
                # On Windows, we can check if process exists
                if sys.platform == 'win32':
                    import ctypes
                    kernel32 = ctypes.windll.kernel32
                    PROCESS_QUERY_INFORMATION = 0x0400
                    handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, 0, pid)
                    if handle:
                        kernel32.CloseHandle(handle)
                        # Process is running
                        return False, lock_file
                    else:
                        # Process not found, stale lock file
                        os.remove(lock_file)
                else:
                    # On Unix-like systems
                    os.kill(pid, 0)
                    # If no exception, process is running
                    return False, lock_file
            except (OSError, ProcessLookupError):
                # Process not running, remove stale lock file
                os.remove(lock_file)
        except (ValueError, IOError):
            # Invalid lock file, remove it
            try:
                os.remove(lock_file)
            except:
                pass

    # Create lock file with current PID
    try:
        with open(lock_file, 'w') as f:
            f.write(str(os.getpid()))
        return True, lock_file
    except IOError:
        return False, None

def main():
    """Main entry point"""
    print("=" * 60)
    print("F2L - FTP to Local Multi-Endpoint Sync Application")
    print("=" * 60)
    print()

    # Check for single instance
    can_run, lock_file = check_single_instance()
    if not can_run:
        print("=" * 60)
        print("ERROR: Another instance of F2L is already running!")
        print("=" * 60)
        print()
        print("Only one instance of F2L can run at a time.")
        print("Please close the other instance before starting a new one.")
        print()
        input("Press Enter to exit...")
        sys.exit(1)

    # Check requirements
    print("Checking requirements...")

    required_modules = ['tkinter', 'sqlite3', 'ftplib', 'threading']
    missing_modules = []

    for module in required_modules:
        try:
            __import__(module)
            print(f"✓ {module} - Available")
        except ImportError:
            missing_modules.append(module)
            print(f"✗ {module} - Missing")
    
    if missing_modules:
        print(f"\nError: Missing required modules: {', '.join(missing_modules)}")
        print("Please install the missing modules and try again.")
        return
    
    # Check optional modules
    optional_status = []
    if TRAY_AVAILABLE:
        optional_status.append("✓ System Tray Support")
    else:
        optional_status.append("✗ System Tray Support (install: pip install pystray pillow)")
    
    if SCHEDULE_AVAILABLE:
        optional_status.append("✓ Scheduling Support")
    else:
        optional_status.append("✗ Scheduling Support (install: pip install schedule)")
    
    print("\nOptional features:")
    for status in optional_status:
        print(f"  {status}")
    
    print(f"\nStarting F2L Application...")
    print(f"Database: f2l_sync.db")
    print(f"Working Directory: {os.getcwd()}")
    print()
    
    try:
        app = F2LGUI()
        app.run()
    except KeyboardInterrupt:
        print("\nApplication interrupted by user.")
    except Exception as e:
        print(f"\nApplication error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Remove lock file
        if lock_file and os.path.exists(lock_file):
            try:
                os.remove(lock_file)
                print("Lock file removed.")
            except:
                pass
        print("\nF2L Application closed.")

# Add multi-session methods to F2LGUI class
def add_multi_session_methods():
    """Add multi-session manager methods to F2LGUI class"""

    def setup_multi_session_tab(self, notebook):
        """Setup multi-session manager tab"""
        # Create main frame for the tab
        multi_session_tab = ttk.Frame(notebook)
        notebook.add(multi_session_tab, text="Multi-Session Manager")

        # Create canvas and scrollbar for scrollable content
        canvas = tk.Canvas(multi_session_tab, highlightthickness=0)
        scrollbar = ttk.Scrollbar(multi_session_tab, orient="vertical", command=canvas.yview)
        main_container = ttk.Frame(canvas)

        # Configure canvas scrolling
        main_container.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=main_container, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y")

        # Enable mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Title and description
        title_frame = ttk.Frame(main_container)
        title_frame.pack(fill=tk.X, pady=(0, 10))

        title_label = ttk.Label(title_frame, text="Multi-Session Sync Manager", font=("Arial", 14, "bold"))
        title_label.pack(side=tk.LEFT)

        desc_label = ttk.Label(title_frame, text="Create and manage multiple sync sessions with independent scheduling",
                              font=("Arial", 9), foreground="gray")
        desc_label.pack(side=tk.LEFT, padx=(20, 0))

        # Control buttons frame
        control_frame = ttk.Frame(main_container)
        control_frame.pack(fill=tk.X, pady=(0, 10))

        # Add new session button
        add_session_btn = ttk.Button(control_frame, text="➕ Add New Session",
                                   command=self.add_new_session)
        add_session_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Load sessions button
        load_sessions_btn = ttk.Button(control_frame, text="📂 Load Saved Sessions",
                                     command=self.load_saved_sessions)
        load_sessions_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Start all button
        start_all_btn = ttk.Button(control_frame, text="▶️ Start All Active",
                                 command=self.start_all_sessions)
        start_all_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Stop all button
        stop_all_btn = ttk.Button(control_frame, text="⏹️ Stop All Sessions",
                                command=self.stop_all_sessions)
        stop_all_btn.pack(side=tk.LEFT)

        # Sessions list frame with scrollbar
        sessions_container = ttk.Frame(main_container)
        sessions_container.pack(fill=tk.BOTH, expand=True)

        # Create treeview for sessions
        columns = ("Name", "Source", "Destination", "Filter", "Schedule", "Status", "Last Sync", "Actions")
        self.sessions_tree = ttk.Treeview(sessions_container, columns=columns, show="headings", height=15)

        # Configure columns
        self.sessions_tree.heading("Name", text="Session Name")
        self.sessions_tree.heading("Source", text="Source Path")
        self.sessions_tree.heading("Destination", text="Destination Path")
        self.sessions_tree.heading("Filter", text="Folder Filter")
        self.sessions_tree.heading("Schedule", text="Schedule")
        self.sessions_tree.heading("Status", text="Status")
        self.sessions_tree.heading("Last Sync", text="Last Sync")
        self.sessions_tree.heading("Actions", text="Actions")

        # Configure column widths
        self.sessions_tree.column("Name", width=120, minwidth=100)
        self.sessions_tree.column("Source", width=150, minwidth=120)
        self.sessions_tree.column("Destination", width=150, minwidth=120)
        self.sessions_tree.column("Filter", width=100, minwidth=80)
        self.sessions_tree.column("Schedule", width=100, minwidth=80)
        self.sessions_tree.column("Status", width=80, minwidth=60)
        self.sessions_tree.column("Last Sync", width=120, minwidth=100)
        self.sessions_tree.column("Actions", width=100, minwidth=80)

        # Add scrollbars (vertical and horizontal)
        sessions_scrollbar_v = ttk.Scrollbar(sessions_container, orient=tk.VERTICAL,
                                            command=self.sessions_tree.yview)
        sessions_scrollbar_h = ttk.Scrollbar(sessions_container, orient=tk.HORIZONTAL,
                                            command=self.sessions_tree.xview)
        self.sessions_tree.configure(yscrollcommand=sessions_scrollbar_v.set,
                                    xscrollcommand=sessions_scrollbar_h.set)

        # Use grid for proper scrollbar layout
        self.sessions_tree.grid(row=0, column=0, sticky='nsew')
        sessions_scrollbar_v.grid(row=0, column=1, sticky='ns')
        sessions_scrollbar_h.grid(row=1, column=0, sticky='ew')

        sessions_container.grid_columnconfigure(0, weight=1)
        sessions_container.grid_rowconfigure(0, weight=1)

        # Bind double-click to edit session
        self.sessions_tree.bind("<Double-1>", self.edit_session)

        # Context menu for sessions
        self.sessions_context_menu = tk.Menu(self.root, tearoff=0)
        self.sessions_context_menu.add_command(label="▶️ Start Session", command=self.start_selected_session)
        self.sessions_context_menu.add_command(label="⏸️ Pause Session", command=self.pause_selected_session)
        self.sessions_context_menu.add_command(label="⏹️ Stop Session", command=self.stop_selected_session)
        self.sessions_context_menu.add_separator()
        self.sessions_context_menu.add_command(label="✏️ Edit Session", command=self.edit_selected_session)
        self.sessions_context_menu.add_command(label="📋 Duplicate Session", command=self.duplicate_selected_session)
        self.sessions_context_menu.add_separator()
        self.sessions_context_menu.add_command(label="🗑️ Delete Session", command=self.delete_selected_session)

        # Bind right-click to show context menu
        self.sessions_tree.bind("<Button-3>", self.show_sessions_context_menu)

        # Status bar for multi-session
        status_frame = ttk.Frame(main_container)
        status_frame.pack(fill=tk.X, pady=(10, 0))

        self.multi_session_status_var = tk.StringVar(value="Ready - No active sessions")
        status_label = ttk.Label(status_frame, textvariable=self.multi_session_status_var,
                               font=("Arial", 9), foreground="blue")
        status_label.pack(side=tk.LEFT)

        # Load existing sessions on startup
        self.root.after(100, self.load_saved_sessions)

    def add_new_session(self):
        """Open dialog to create a new sync session"""
        self.show_session_dialog()

    def show_session_dialog(self, session_id=None):
        """Show dialog for creating/editing a sync session"""
        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Add New Sync Session" if session_id is None else "Edit Sync Session")
        dialog.geometry("600x700")
        dialog.transient(self.root)
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (600 // 2)
        y = (dialog.winfo_screenheight() // 2) - (700 // 2)
        dialog.geometry(f"600x700+{x}+{y}")

        # Main frame with scrollbar
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Session name
        name_frame = ttk.LabelFrame(main_frame, text="Session Configuration", padding=10)
        name_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(name_frame, text="Session Name:").grid(row=0, column=0, sticky=tk.W, pady=2)
        session_name_var = tk.StringVar()
        session_name_entry = ttk.Entry(name_frame, textvariable=session_name_var, width=40)
        session_name_entry.grid(row=0, column=1, sticky=tk.W+tk.E, padx=(10, 0), pady=2)
        name_frame.columnconfigure(1, weight=1)

        # Directory paths
        paths_frame = ttk.LabelFrame(main_frame, text="Directory Paths", padding=10)
        paths_frame.pack(fill=tk.X, pady=(0, 10))

        # Source directory
        ttk.Label(paths_frame, text="Source Directory:").grid(row=0, column=0, sticky=tk.W, pady=2)
        source_var = tk.StringVar()
        source_entry = ttk.Entry(paths_frame, textvariable=source_var, width=40)
        source_entry.grid(row=0, column=1, sticky=tk.W+tk.E, padx=(10, 0), pady=2)
        source_browse_btn = ttk.Button(paths_frame, text="Browse",
                                     command=lambda: self.browse_directory(source_var))
        source_browse_btn.grid(row=0, column=2, padx=(5, 0), pady=2)

        # Destination directory
        ttk.Label(paths_frame, text="Destination Directory:").grid(row=1, column=0, sticky=tk.W, pady=2)
        dest_var = tk.StringVar()
        dest_entry = ttk.Entry(paths_frame, textvariable=dest_var, width=40)
        dest_entry.grid(row=1, column=1, sticky=tk.W+tk.E, padx=(10, 0), pady=2)
        dest_browse_btn = ttk.Button(paths_frame, text="Browse",
                                   command=lambda: self.browse_directory(dest_var))
        dest_browse_btn.grid(row=1, column=2, padx=(5, 0), pady=2)

        paths_frame.columnconfigure(1, weight=1)

        # Sync direction
        direction_frame = ttk.LabelFrame(main_frame, text="Sync Direction", padding=10)
        direction_frame.pack(fill=tk.X, pady=(0, 10))

        direction_var = tk.StringVar(value="source_to_dest")
        ttk.Radiobutton(direction_frame, text="Source → Destination",
                       variable=direction_var, value="source_to_dest").pack(anchor=tk.W)
        ttk.Radiobutton(direction_frame, text="Destination → Source",
                       variable=direction_var, value="dest_to_source").pack(anchor=tk.W)
        ttk.Radiobutton(direction_frame, text="Bidirectional (Both ways)",
                       variable=direction_var, value="bidirectional").pack(anchor=tk.W)

        # Folder filtering
        filter_frame = ttk.LabelFrame(main_frame, text="Folder Filtering", padding=10)
        filter_frame.pack(fill=tk.X, pady=(0, 10))

        filter_enabled_var = tk.BooleanVar()
        filter_checkbox = ttk.Checkbutton(filter_frame, text="Enable specific folder sync",
                                        variable=filter_enabled_var,
                                        command=lambda: self.toggle_session_filter_controls(filter_settings_frame, filter_enabled_var.get()))
        filter_checkbox.pack(anchor=tk.W, pady=(0, 5))

        # Filter settings frame
        filter_settings_frame = ttk.Frame(filter_frame)
        filter_settings_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Label(filter_settings_frame, text="Folder names (comma-separated):").pack(anchor=tk.W)
        folder_names_var = tk.StringVar()
        folder_names_entry = ttk.Entry(filter_settings_frame, textvariable=folder_names_var, width=50)
        folder_names_entry.pack(fill=tk.X, pady=(2, 5))

        # Match mode
        match_frame = ttk.Frame(filter_settings_frame)
        match_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(match_frame, text="Match mode:").pack(side=tk.LEFT)
        match_mode_var = tk.StringVar(value="exact")
        ttk.Radiobutton(match_frame, text="Exact", variable=match_mode_var, value="exact").pack(side=tk.LEFT, padx=(10, 5))
        ttk.Radiobutton(match_frame, text="Contains", variable=match_mode_var, value="contains").pack(side=tk.LEFT)

        case_sensitive_var = tk.BooleanVar()
        ttk.Checkbutton(filter_settings_frame, text="Case sensitive",
                       variable=case_sensitive_var).pack(anchor=tk.W)

        # Initialize filter controls state (disabled by default)
        self.toggle_session_filter_controls(filter_settings_frame, False)

        # Store dialog variables for access in save function
        dialog.session_name_var = session_name_var
        dialog.source_var = source_var
        dialog.dest_var = dest_var
        dialog.direction_var = direction_var
        dialog.filter_enabled_var = filter_enabled_var
        dialog.folder_names_var = folder_names_var
        dialog.match_mode_var = match_mode_var
        dialog.case_sensitive_var = case_sensitive_var

        # Scheduling section
        schedule_frame = ttk.LabelFrame(main_frame, text="Scheduling", padding=10)
        schedule_frame.pack(fill=tk.X, pady=(0, 10))

        schedule_enabled_var = tk.BooleanVar()
        schedule_checkbox = ttk.Checkbutton(schedule_frame, text="Enable automatic scheduling",
                                          variable=schedule_enabled_var)
        schedule_checkbox.pack(anchor=tk.W, pady=(0, 5))

        # Schedule settings frame
        schedule_settings_frame = ttk.Frame(schedule_frame)
        schedule_settings_frame.pack(fill=tk.X, pady=(5, 0))

        # Interval settings
        interval_frame = ttk.Frame(schedule_settings_frame)
        interval_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(interval_frame, text="Run every:").pack(side=tk.LEFT)
        interval_var = tk.IntVar(value=30)
        interval_spinbox = ttk.Spinbox(interval_frame, from_=1, to=999, textvariable=interval_var, width=10)
        interval_spinbox.pack(side=tk.LEFT, padx=(5, 5))

        unit_var = tk.StringVar(value="minutes")
        unit_combo = ttk.Combobox(interval_frame, textvariable=unit_var, values=["minutes", "hours", "days"],
                                width=10, state="readonly")
        unit_combo.pack(side=tk.LEFT)

        # Store scheduling variables
        dialog.schedule_enabled_var = schedule_enabled_var
        dialog.interval_var = interval_var
        dialog.unit_var = unit_var

        # Auto-start option
        auto_start_var = tk.BooleanVar()
        auto_start_checkbox = ttk.Checkbutton(schedule_settings_frame, text="Auto-start when application launches",
                                             variable=auto_start_var)
        auto_start_checkbox.pack(anchor=tk.W, pady=(5, 0))
        dialog.auto_start_var = auto_start_var

        # Execution Settings
        exec_frame = ttk.LabelFrame(main_frame, text="Execution Settings", padding=10)
        exec_frame.pack(fill=tk.X, pady=(0, 10))

        parallel_var = tk.BooleanVar(value=True)
        parallel_checkbox = ttk.Checkbutton(exec_frame, text="Allow parallel execution with other sessions",
                                           variable=parallel_var)
        parallel_checkbox.pack(anchor=tk.W, pady=(0, 5))
        ttk.Label(exec_frame, text="(If disabled, this session will wait for others to complete)",
                 foreground='gray', font=('TkDefaultFont', 8)).pack(anchor=tk.W, padx=20)
        dialog.parallel_var = parallel_var

        force_overwrite_var = tk.BooleanVar(value=False)
        force_overwrite_checkbox = ttk.Checkbutton(exec_frame, text="Force Overwrite (copy all files, ignore modification dates)",
                                                   variable=force_overwrite_var)
        force_overwrite_checkbox.pack(anchor=tk.W, pady=(5, 5))
        ttk.Label(exec_frame, text="(Overwrites existing files even if they're newer)",
                 foreground='gray', font=('TkDefaultFont', 8)).pack(anchor=tk.W, padx=20)
        dialog.force_overwrite_var = force_overwrite_var

        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=(20, 0))

        # Save button
        save_btn = ttk.Button(buttons_frame, text="💾 Save Session",
                            command=lambda: self.save_session_config(dialog, session_id))
        save_btn.pack(side=tk.RIGHT, padx=(5, 0))

        # Cancel button
        cancel_btn = ttk.Button(buttons_frame, text="❌ Cancel", command=dialog.destroy)
        cancel_btn.pack(side=tk.RIGHT)

        # Test sync button
        test_btn = ttk.Button(buttons_frame, text="🧪 Test Sync",
                            command=lambda: self.test_session_config(dialog))
        test_btn.pack(side=tk.LEFT, padx=(0, 5))

        # Dry run button
        dry_run_btn = ttk.Button(buttons_frame, text="👁️ Dry Run",
                               command=lambda: self.dry_run_session_config(dialog))
        dry_run_btn.pack(side=tk.LEFT)

        # If editing existing session, populate fields
        if session_id and session_id in self.session_configs:
            config = self.session_configs[session_id]
            session_name_var.set(config.get('name', ''))
            source_var.set(config.get('source_path', ''))
            dest_var.set(config.get('dest_path', ''))
            direction_var.set(config.get('sync_direction', 'source_to_dest'))
            filter_enabled_var.set(config.get('folder_filter_enabled', False))
            folder_names_var.set(','.join(config.get('folder_names', [])))
            match_mode_var.set(config.get('match_mode', 'exact'))
            case_sensitive_var.set(config.get('case_sensitive', False))
            schedule_enabled_var.set(config.get('schedule_enabled', False))
            interval_var.set(config.get('schedule_interval', 30))
            unit_var.set(config.get('schedule_unit', 'minutes'))
            auto_start_var.set(config.get('auto_start', False))
            parallel_var.set(config.get('parallel_execution', True))
            force_overwrite_var.set(config.get('force_overwrite', False))

    def save_session_config(self, dialog, session_id=None):
        """Save session configuration to database and memory"""
        try:
            # Get values from dialog
            name = dialog.session_name_var.get().strip()
            source_path = dialog.source_var.get().strip()
            dest_path = dialog.dest_var.get().strip()

            # Validation
            if not name:
                messagebox.showerror("Error", "Please enter a session name.")
                return
            if not source_path or not dest_path:
                messagebox.showerror("Error", "Please select both source and destination directories.")
                return
            if not os.path.exists(source_path):
                messagebox.showerror("Error", f"Source directory does not exist: {source_path}")
                return

            # Create destination directory if it doesn't exist
            if not os.path.exists(dest_path):
                try:
                    os.makedirs(dest_path, exist_ok=True)
                except Exception as e:
                    messagebox.showerror("Error", f"Cannot create destination directory: {e}")
                    return

            # Prepare configuration
            config = {
                'name': name,
                'source_path': source_path,
                'dest_path': dest_path,
                'sync_direction': dialog.direction_var.get(),
                'folder_filter_enabled': dialog.filter_enabled_var.get(),
                'folder_names': [f.strip() for f in dialog.folder_names_var.get().split(',') if f.strip()],
                'match_mode': dialog.match_mode_var.get(),
                'case_sensitive': dialog.case_sensitive_var.get(),
                'schedule_enabled': dialog.schedule_enabled_var.get(),
                'schedule_interval': dialog.interval_var.get(),
                'schedule_unit': dialog.unit_var.get(),
                'auto_start': dialog.auto_start_var.get(),
                'parallel_execution': dialog.parallel_var.get(),
                'force_overwrite': dialog.force_overwrite_var.get(),
                'active': True,
                'created_date': datetime.now().isoformat(),
                'last_sync': None,
                'last_status': None
            }

            # Save to database
            self.save_session_to_db(config, session_id)

            # Update memory
            if session_id is None:
                session_id = name  # Use name as ID for new sessions
            self.session_configs[session_id] = config

            # Refresh sessions display
            self.refresh_sessions_display()

            # Close dialog
            dialog.destroy()

            messagebox.showinfo("Success", f"Session '{name}' saved successfully!")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save session: {e}")

    def save_session_to_db(self, config, session_id=None):
        """Save session configuration to database"""
        conn = sqlite3.connect("f2l_sync.db")
        cursor = conn.cursor()

        try:
            if session_id is None:
                # Insert new session
                cursor.execute('''
                    INSERT INTO local_sync_configs
                    (name, source_path, dest_path, sync_direction, folder_filter_enabled,
                     folder_names, match_mode, case_sensitive, schedule_enabled,
                     schedule_interval, schedule_unit, auto_start, parallel_execution,
                     force_overwrite, active, created_date, last_sync, last_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    config['name'], config['source_path'], config['dest_path'],
                    config['sync_direction'], config['folder_filter_enabled'],
                    ','.join(config['folder_names']), config['match_mode'],
                    config['case_sensitive'], config['schedule_enabled'],
                    config['schedule_interval'], config['schedule_unit'],
                    config.get('auto_start', False), config.get('parallel_execution', True),
                    config.get('force_overwrite', False),
                    config['active'], config['created_date'], config['last_sync'],
                    config.get('last_status')
                ))
            else:
                # Update existing session
                cursor.execute('''
                    UPDATE local_sync_configs SET
                    name=?, source_path=?, dest_path=?, sync_direction=?, folder_filter_enabled=?,
                    folder_names=?, match_mode=?, case_sensitive=?, schedule_enabled=?,
                    schedule_interval=?, schedule_unit=?, auto_start=?, parallel_execution=?, force_overwrite=?, active=?
                    WHERE name=?
                ''', (
                    config['name'], config['source_path'], config['dest_path'],
                    config['sync_direction'], config['folder_filter_enabled'],
                    ','.join(config['folder_names']), config['match_mode'],
                    config['case_sensitive'], config['schedule_enabled'],
                    config['schedule_interval'], config['schedule_unit'],
                    config.get('auto_start', False), config.get('parallel_execution', True),
                    config.get('force_overwrite', False),
                    config['active'], session_id
                ))

            conn.commit()
        finally:
            conn.close()

    def load_saved_sessions(self):
        """Load saved sessions from database"""
        conn = sqlite3.connect("f2l_sync.db")
        cursor = conn.cursor()

        try:
            cursor.execute('SELECT * FROM local_sync_configs')
            rows = cursor.fetchall()

            # Get column names
            columns = [description[0] for description in cursor.description]

            # Clear existing sessions
            self.session_configs.clear()

            # Load sessions
            for row in rows:
                session_data = dict(zip(columns, row))
                session_id = session_data['name']

                # Convert folder_names back to list
                folder_names = session_data['folder_names'].split(',') if session_data['folder_names'] else []
                session_data['folder_names'] = [f.strip() for f in folder_names if f.strip()]

                # Convert boolean fields
                session_data['folder_filter_enabled'] = bool(session_data['folder_filter_enabled'])
                session_data['case_sensitive'] = bool(session_data['case_sensitive'])
                session_data['schedule_enabled'] = bool(session_data['schedule_enabled'])
                session_data['active'] = bool(session_data['active'])

                self.session_configs[session_id] = session_data

            # Refresh display
            self.refresh_sessions_display()

        except sqlite3.Error as e:
            print(f"Database error loading sessions: {e}")
        finally:
            conn.close()

    def refresh_sessions_display(self):
        """Refresh the sessions tree view"""
        # Clear existing items
        for item in self.sessions_tree.get_children():
            self.sessions_tree.delete(item)

        # Add sessions to tree
        for session_id, config in self.session_configs.items():
            # Format filter info
            if config['folder_filter_enabled'] and config['folder_names']:
                filter_text = f"{','.join(config['folder_names'][:2])} ({config['match_mode']})"
                if len(config['folder_names']) > 2:
                    filter_text += f" +{len(config['folder_names'])-2} more"
            else:
                filter_text = "All files"

            # Format schedule info
            if config['schedule_enabled']:
                schedule_text = f"Every {config['schedule_interval']} {config['schedule_unit']}"
            else:
                schedule_text = "Manual"

            # Get status
            if session_id in self.active_sessions:
                status = "Running"
            elif config['active']:
                status = "Ready"
            else:
                status = "Paused"

            # Format last sync
            last_sync = config.get('last_sync', 'Never')
            if last_sync and last_sync != 'Never':
                try:
                    last_sync_dt = datetime.fromisoformat(last_sync)
                    last_sync = last_sync_dt.strftime("%Y-%m-%d %H:%M")
                except:
                    pass

            # Insert into tree
            self.sessions_tree.insert("", tk.END, iid=session_id, values=(
                config['name'],
                config['source_path'][:30] + "..." if len(config['source_path']) > 30 else config['source_path'],
                config['dest_path'][:30] + "..." if len(config['dest_path']) > 30 else config['dest_path'],
                filter_text,
                schedule_text,
                status,
                last_sync,
                "⚙️"
            ))

        # Update status
        active_count = len(self.active_sessions)
        total_count = len(self.session_configs)
        self.multi_session_status_var.set(f"Sessions: {active_count} active, {total_count} total")

    def start_selected_session(self):
        """Start the selected session"""
        selection = self.sessions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a session to start.")
            return

        session_id = selection[0]
        self.start_session(session_id)

    def start_session(self, session_id):
        """Start a specific session"""
        if session_id not in self.session_configs:
            messagebox.showerror("Error", f"Session '{session_id}' not found.")
            return

        if session_id in self.active_sessions:
            messagebox.showinfo("Info", f"Session '{session_id}' is already running.")
            return

        config = self.session_configs[session_id]

        # Create session thread
        session_thread = threading.Thread(
            target=self.run_session,
            args=(session_id, config),
            daemon=True
        )

        # Store active session
        self.active_sessions[session_id] = {
            'thread': session_thread,
            'config': config,
            'status': 'starting',
            'last_run': None
        }

        # Start thread
        session_thread.start()

        # Start scheduler if enabled
        if config['schedule_enabled']:
            self.start_session_scheduler(session_id, config)

        # Refresh display
        self.refresh_sessions_display()

        print(f"Started session: {session_id}")

    def run_session(self, session_id, config):
        """Run a sync session (runs in separate thread)"""
        try:
            self.active_sessions[session_id]['status'] = 'running'

            # Perform sync operation
            source_dir = config['source_path']
            dest_dir = config['dest_path']
            sync_direction = config['sync_direction']

            # Get folder filter settings
            folder_names = config['folder_names'] if config['folder_filter_enabled'] else []
            match_mode = config['match_mode']
            case_sensitive = config['case_sensitive']

            # Get force_overwrite setting
            force_overwrite = config.get('force_overwrite', False)

            # Scan source directory
            print(f"Session {session_id}: Scanning {source_dir}...")
            source_files = self.scan_local_directory(
                source_dir, folder_names, match_mode, case_sensitive,
                progress_callback=lambda p, s, d: print(f"Session {session_id}: {s}")
            )

            # Determine operations
            operations = []
            for file_info in source_files:
                rel_path = os.path.relpath(file_info['path'], source_dir)
                dest_path = os.path.join(dest_dir, rel_path)

                operation_type = self.determine_local_operation(file_info['path'], dest_path, file_info, force_overwrite)
                if operation_type != "skip":
                    operations.append({
                        'operation': operation_type,
                        'source': file_info['path'],
                        'destination': dest_path,
                        'size': file_info['size']
                    })

            # Execute operations
            successful_ops = 0
            for i, operation in enumerate(operations):
                if session_id not in self.active_sessions:  # Check if session was stopped
                    break

                try:
                    if operation['operation'] == 'copy':
                        # Create destination directory if needed
                        dest_dir_path = os.path.dirname(operation['destination'])
                        os.makedirs(dest_dir_path, exist_ok=True)

                        # Copy file
                        shutil.copy2(operation['source'], operation['destination'])
                        successful_ops += 1

                        print(f"Session {session_id}: Copied {os.path.basename(operation['source'])}")

                except Exception as e:
                    print(f"Session {session_id}: Error copying {operation['source']}: {e}")

            # Update last sync time
            self.session_configs[session_id]['last_sync'] = datetime.now().isoformat()
            self.update_session_last_sync(session_id)

            print(f"Session {session_id}: Completed - {successful_ops}/{len(operations)} files synced")

        except Exception as e:
            print(f"Session {session_id}: Error - {e}")
        finally:
            # Clean up active session if it's a one-time run
            if not config['schedule_enabled'] and session_id in self.active_sessions:
                del self.active_sessions[session_id]
                self.root.after(0, self.refresh_sessions_display)

    def stop_selected_session(self):
        """Stop the selected session"""
        selection = self.sessions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a session to stop.")
            return

        session_id = selection[0]
        self.stop_session(session_id)

    def stop_session(self, session_id):
        """Stop a specific session"""
        if session_id in self.active_sessions:
            # Stop scheduler if running
            if session_id in self.session_schedulers:
                self.session_schedulers[session_id].cancel()
                del self.session_schedulers[session_id]

            # Remove from active sessions
            del self.active_sessions[session_id]

            # Refresh display
            self.refresh_sessions_display()

            print(f"Stopped session: {session_id}")
        else:
            messagebox.showinfo("Info", f"Session '{session_id}' is not running.")

    def start_all_sessions(self):
        """Start all active sessions"""
        started_count = 0
        for session_id, config in self.session_configs.items():
            if config['active'] and session_id not in self.active_sessions:
                self.start_session(session_id)
                started_count += 1

        if started_count > 0:
            messagebox.showinfo("Info", f"Started {started_count} sessions.")
        else:
            messagebox.showinfo("Info", "No sessions to start.")

    def stop_all_sessions(self):
        """Stop all active sessions"""
        session_ids = list(self.active_sessions.keys())
        for session_id in session_ids:
            self.stop_session(session_id)

        if session_ids:
            messagebox.showinfo("Info", f"Stopped {len(session_ids)} sessions.")
        else:
            messagebox.showinfo("Info", "No active sessions to stop.")

    def start_session_scheduler(self, session_id, config):
        """Start scheduler for a session"""
        if not config['schedule_enabled']:
            return

        # Calculate interval in seconds
        interval = config['schedule_interval']
        unit = config['schedule_unit']

        if unit == 'minutes':
            interval_seconds = interval * 60
        elif unit == 'hours':
            interval_seconds = interval * 3600
        elif unit == 'days':
            interval_seconds = interval * 86400
        else:
            interval_seconds = interval * 60  # Default to minutes

        # Create timer
        def run_scheduled_sync():
            if session_id in self.active_sessions:
                # Run sync in separate thread
                sync_thread = threading.Thread(
                    target=self.run_session,
                    args=(session_id, config),
                    daemon=True
                )
                sync_thread.start()

                # Schedule next run
                timer = threading.Timer(interval_seconds, run_scheduled_sync)
                timer.daemon = True
                timer.start()
                self.session_schedulers[session_id] = timer

        # Start first scheduled run
        timer = threading.Timer(interval_seconds, run_scheduled_sync)
        timer.daemon = True
        timer.start()
        self.session_schedulers[session_id] = timer

    def update_session_last_sync(self, session_id):
        """Update last sync time in database"""
        conn = sqlite3.connect("f2l_sync.db")
        cursor = conn.cursor()

        try:
            cursor.execute('''
                UPDATE local_sync_configs
                SET last_sync = ?
                WHERE name = ?
            ''', (datetime.now().isoformat(), session_id))
            conn.commit()
        finally:
            conn.close()

    # Context menu and utility methods
    def show_sessions_context_menu(self, event):
        """Show context menu for sessions tree"""
        item = self.sessions_tree.identify_row(event.y)
        if item:
            self.sessions_tree.selection_set(item)
            self.sessions_context_menu.post(event.x_root, event.y_root)

    def edit_session(self, event):
        """Edit session on double-click"""
        selection = self.sessions_tree.selection()
        if selection:
            self.edit_selected_session()

    def edit_selected_session(self):
        """Edit the selected session"""
        selection = self.sessions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a session to edit.")
            return

        session_id = selection[0]
        self.show_session_dialog(session_id)

    def pause_selected_session(self):
        """Pause the selected session"""
        selection = self.sessions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a session to pause.")
            return

        session_id = selection[0]
        if session_id in self.session_configs:
            self.session_configs[session_id]['active'] = False
            self.save_session_to_db(self.session_configs[session_id], session_id)
            self.refresh_sessions_display()
            messagebox.showinfo("Info", f"Session '{session_id}' paused.")

    def duplicate_selected_session(self):
        """Duplicate the selected session"""
        selection = self.sessions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a session to duplicate.")
            return

        session_id = selection[0]
        if session_id in self.session_configs:
            config = self.session_configs[session_id].copy()
            config['name'] = f"{config['name']} (Copy)"
            config['created_date'] = datetime.now().isoformat()
            config['last_sync'] = None

            # Save duplicate
            self.save_session_to_db(config)
            self.session_configs[config['name']] = config
            self.refresh_sessions_display()
            messagebox.showinfo("Info", f"Session duplicated as '{config['name']}'.")

    def delete_selected_session(self):
        """Delete the selected session"""
        selection = self.sessions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a session to delete.")
            return

        session_id = selection[0]
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete session '{session_id}'?"):
            # Stop session if running
            if session_id in self.active_sessions:
                self.stop_session(session_id)

            # Delete from database
            conn = sqlite3.connect("f2l_sync.db")
            cursor = conn.cursor()
            try:
                cursor.execute('DELETE FROM local_sync_configs WHERE name = ?', (session_id,))
                conn.commit()
            finally:
                conn.close()

            # Remove from memory
            if session_id in self.session_configs:
                del self.session_configs[session_id]

            self.refresh_sessions_display()
            messagebox.showinfo("Info", f"Session '{session_id}' deleted.")

    def browse_directory(self, var):
        """Browse and select a directory"""
        from tkinter import filedialog

        directory = filedialog.askdirectory(
            title="Select Directory",
            initialdir=var.get() if var.get() else os.getcwd()
        )

        if directory:
            var.set(directory)

    def browse_ftp_directory(self, endpoint_var, path_var):
        """Browse FTP directory structure and select a path"""
        endpoint_name = endpoint_var.get()
        if not endpoint_name:
            messagebox.showwarning("Warning", "Please select an FTP endpoint first.")
            return

        # Find the endpoint
        endpoint = None
        for ep in self.endpoints:
            if ep.name == endpoint_name:
                endpoint = ep
                break

        if not endpoint:
            messagebox.showerror("Error", "Selected endpoint not found.")
            return

        # Create FTP browser dialog
        browser_dialog = tk.Toplevel(self.root)
        browser_dialog.title(f"Browse FTP - {endpoint.name}")
        browser_dialog.geometry("600x500")
        browser_dialog.transient(self.root)
        browser_dialog.grab_set()

        # Current path display
        path_frame = ttk.Frame(browser_dialog)
        path_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(path_frame, text="Current Path:").pack(side=tk.LEFT, padx=(0, 5))
        current_path_var = tk.StringVar(value=endpoint.remote_path)
        current_path_label = ttk.Label(path_frame, textvariable=current_path_var,
                                       font=('TkDefaultFont', 9, 'bold'), foreground='blue')
        current_path_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Navigation buttons
        nav_frame = ttk.Frame(browser_dialog)
        nav_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(nav_frame, text="⬆️ Parent Directory",
                  command=lambda: go_to_parent()).pack(side=tk.LEFT, padx=5)
        ttk.Button(nav_frame, text="🏠 Endpoint Root",
                  command=lambda: go_to_root()).pack(side=tk.LEFT, padx=5)
        ttk.Button(nav_frame, text="🔄 Refresh",
                  command=lambda: load_directory(current_path_var.get())).pack(side=tk.LEFT, padx=5)

        # Directory tree
        tree_frame = ttk.Frame(browser_dialog)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        columns = ("Name", "Type", "Size", "Modified")
        dir_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)

        dir_tree.heading("Name", text="Name")
        dir_tree.heading("Type", text="Type")
        dir_tree.heading("Size", text="Size")
        dir_tree.heading("Modified", text="Modified")

        dir_tree.column("Name", width=250)
        dir_tree.column("Type", width=80)
        dir_tree.column("Size", width=100)
        dir_tree.column("Modified", width=150)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=dir_tree.yview)
        dir_tree.configure(yscrollcommand=scrollbar.set)

        dir_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Status label
        status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(browser_dialog, textvariable=status_var, foreground='gray')
        status_label.pack(fill=tk.X, padx=10, pady=(0, 10))

        # Buttons
        button_frame = ttk.Frame(browser_dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        def select_current_path():
            current = current_path_var.get()
            # Make it relative to endpoint path
            if current.startswith(endpoint.remote_path):
                relative = current[len(endpoint.remote_path):].lstrip('/')
                path_var.set(relative if relative else "")
            else:
                path_var.set(current)
            browser_dialog.destroy()

        def select_highlighted():
            selection = dir_tree.selection()
            if selection:
                item = selection[0]
                values = dir_tree.item(item, 'values')
                if values[1] == "📁 Directory":
                    # Navigate into directory
                    dir_name = values[0]
                    new_path = f"{current_path_var.get().rstrip('/')}/{dir_name}"
                    load_directory(new_path)

        def go_to_parent():
            current = current_path_var.get()
            if current != endpoint.remote_path and current != '/':
                parent = '/'.join(current.rstrip('/').split('/')[:-1])
                if not parent:
                    parent = '/'
                load_directory(parent)

        def go_to_root():
            load_directory(endpoint.remote_path)

        def load_directory(path):
            status_var.set("Loading...")
            dir_tree.delete(*dir_tree.get_children())

            def load_in_background():
                try:
                    # Get or create FTP manager
                    if endpoint.id not in self.ftp_sync.ftp_managers:
                        self.ftp_sync.ftp_managers[endpoint.id] = FTPManager(
                            endpoint.host, endpoint.username, endpoint.password, endpoint.port
                        )

                    ftp_manager = self.ftp_sync.ftp_managers[endpoint.id]

                    # Ensure connected
                    if not ftp_manager.ensure_connected():
                        raise Exception("Failed to connect to FTP server")

                    # List directory
                    items = []
                    ftp_manager.ftp.cwd(path)

                    # Get directory listing
                    lines = []
                    ftp_manager.ftp.retrlines('LIST', lines.append)

                    for line in lines:
                        parts = line.split(None, 8)
                        if len(parts) >= 9:
                            permissions = parts[0]
                            size = parts[4] if len(parts) > 4 else "0"
                            name = parts[8]

                            # Skip . and ..
                            if name in ['.', '..']:
                                continue

                            is_dir = permissions.startswith('d')
                            item_type = "📁 Directory" if is_dir else "📄 File"

                            items.append((name, item_type, size if not is_dir else "", ""))

                    # Update UI in main thread
                    def update_ui():
                        current_path_var.set(path)

                        # Sort: directories first, then files
                        items.sort(key=lambda x: (0 if x[1] == "📁 Directory" else 1, x[0].lower()))

                        for item in items:
                            dir_tree.insert('', 'end', values=item)

                        status_var.set(f"Loaded {len(items)} items")

                    self.root.after(0, update_ui)

                except Exception as e:
                    # Capture error message immediately
                    error_msg = str(e)
                    def show_error():
                        status_var.set(f"Error: {error_msg}")
                        messagebox.showerror("FTP Error", f"Failed to load directory:\n{error_msg}")
                    self.root.after(0, show_error)

            threading.Thread(target=load_in_background, daemon=True).start()

        ttk.Button(button_frame, text="✅ Select Current Path",
                  command=select_current_path).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="❌ Cancel",
                  command=browser_dialog.destroy).pack(side=tk.RIGHT, padx=5)

        # Bind double-click to navigate
        dir_tree.bind('<Double-1>', lambda e: select_highlighted())

        # Load initial directory
        load_directory(endpoint.remote_path)

    def toggle_session_filter_controls(self, filter_frame, enabled):
        """Toggle folder filter controls on/off"""
        state = tk.NORMAL if enabled else tk.DISABLED

        # Enable/disable all child widgets
        for child in filter_frame.winfo_children():
            if isinstance(child, (ttk.Entry, ttk.Combobox, ttk.Radiobutton, ttk.Checkbutton)):
                child.configure(state=state)
            elif isinstance(child, ttk.Frame):
                # Recursively handle nested frames
                for subchild in child.winfo_children():
                    if isinstance(subchild, (ttk.Entry, ttk.Combobox, ttk.Radiobutton, ttk.Checkbutton)):
                        subchild.configure(state=state)

    def test_session_config(self, dialog):
        """Test the session configuration"""
        try:
            source_path = dialog.source_var.get().strip()
            dest_path = dialog.dest_var.get().strip()

            if not source_path or not dest_path:
                messagebox.showwarning("Warning", "Please select both source and destination directories.")
                return

            if not os.path.exists(source_path):
                messagebox.showerror("Error", f"Source directory does not exist: {source_path}")
                return

            # Test scan with proper progress callback
            folder_names = [f.strip() for f in dialog.folder_names_var.get().split(',') if f.strip()] if dialog.filter_enabled_var.get() else []
            match_mode = dialog.match_mode_var.get()
            case_sensitive = dialog.case_sensitive_var.get()

            print(f"\n=== TEST SYNC DEBUG ===")
            print(f"Source: {source_path}")
            print(f"Destination: {dest_path}")
            print(f"Filter enabled: {dialog.filter_enabled_var.get()}")
            print(f"Folder names: {folder_names}")
            print(f"Match mode: {match_mode}")
            print(f"Case sensitive: {case_sensitive}")

            # Check if source directory exists and list contents
            if os.path.exists(source_path):
                try:
                    contents = os.listdir(source_path)
                    print(f"Source directory contents: {contents}")

                    # Check if filter directory exists
                    if folder_names:
                        for folder_name in folder_names:
                            test_path = os.path.join(source_path, folder_name)
                            exists = os.path.exists(test_path)
                            is_dir = os.path.isdir(test_path) if exists else False
                            print(f"  Filter '{folder_name}': path={test_path}, exists={exists}, is_dir={is_dir}")
                            if exists and is_dir:
                                try:
                                    filter_contents = os.listdir(test_path)
                                    print(f"    Contents of '{folder_name}': {len(filter_contents)} items")
                                except Exception as e:
                                    print(f"    Error listing '{folder_name}': {e}")
                except Exception as e:
                    print(f"Error listing source directory: {e}")
            print(f"======================\n")

            # Quick scan test
            files = self.scan_local_directory(source_path, folder_names, match_mode, case_sensitive,
                                            progress_callback=lambda p, s, d: print(f"Test scan: {s}"))

            messagebox.showinfo("Test Results",
                              f"✅ Test successful!\n\n"
                              f"Source directory: Accessible\n"
                              f"Files found: {len(files)}\n"
                              f"Filter applied: {'Yes' if folder_names else 'No'}\n"
                              f"Filter criteria: {', '.join(folder_names) if folder_names else 'None'}\n"
                              f"Match mode: {match_mode}\n"
                              f"Ready for sync!")

        except Exception as e:
            print(f"Test error: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Test Failed", f"❌ Test failed:\n\n{str(e)}")

    def dry_run_session_config(self, dialog):
        """Perform a dry run of the session configuration"""
        try:
            source_path = dialog.source_var.get().strip()
            dest_path = dialog.dest_var.get().strip()

            if not source_path or not dest_path:
                messagebox.showwarning("Warning", "Please select both source and destination directories.")
                return

            if not os.path.exists(source_path):
                messagebox.showerror("Error", f"Source directory does not exist: {source_path}")
                return

            # Get configuration
            folder_names = [f.strip() for f in dialog.folder_names_var.get().split(',') if f.strip()] if dialog.filter_enabled_var.get() else []
            match_mode = dialog.match_mode_var.get()
            case_sensitive = dialog.case_sensitive_var.get()
            sync_direction = dialog.direction_var.get()

            print(f"DEBUG: Dry run - source: {source_path}")
            print(f"DEBUG: Dry run - dest: {dest_path}")
            print(f"DEBUG: Dry run - filter enabled: {dialog.filter_enabled_var.get()}")
            print(f"DEBUG: Dry run - folder names: {folder_names}")

            # Scan source directory
            source_files = self.scan_local_directory(source_path, folder_names, match_mode, case_sensitive,
                                                   progress_callback=lambda p, s, d: print(f"Dry run scan: {s}"))

            if not source_files:
                messagebox.showwarning("Dry Run Results",
                                     f"⚠️ No files found!\n\n"
                                     f"Source: {source_path}\n"
                                     f"Filter: {', '.join(folder_names) if folder_names else 'None'}\n"
                                     f"Match mode: {match_mode}\n\n"
                                     f"Check your filter settings or source directory.")
                return

            # Determine operations
            operations = []
            for file_info in source_files:
                rel_path = os.path.relpath(file_info['path'], source_path)
                dest_file_path = os.path.join(dest_path, rel_path)

                operation_type = self.determine_local_operation(file_info['path'], dest_file_path, file_info)
                operations.append({
                    'operation': operation_type,
                    'source': file_info['path'],
                    'destination': dest_file_path,
                    'size': file_info['size'],
                    'relative_path': rel_path
                })

            # Count operations
            copy_ops = [op for op in operations if op['operation'] == 'copy']
            skip_ops = [op for op in operations if op['operation'] == 'skip']

            # Calculate total size
            total_size = sum(op['size'] for op in copy_ops)
            size_mb = total_size / (1024 * 1024)

            # Show detailed results
            result_text = f"🔍 Dry Run Results:\n\n"
            result_text += f"📁 Source: {source_path}\n"
            result_text += f"📁 Destination: {dest_path}\n"
            result_text += f"🔄 Direction: {sync_direction}\n"
            result_text += f"🗂️ Filter: {', '.join(folder_names) if folder_names else 'All files'}\n"
            result_text += f"🎯 Match mode: {match_mode}\n\n"
            result_text += f"📊 Operations Summary:\n"
            result_text += f"  • Files to copy: {len(copy_ops)}\n"
            result_text += f"  • Files to skip: {len(skip_ops)}\n"
            result_text += f"  • Total size to copy: {size_mb:.1f} MB\n\n"

            if copy_ops:
                result_text += f"📋 Files to be copied (first 10):\n"
                for i, op in enumerate(copy_ops[:10]):
                    size_kb = op['size'] / 1024
                    result_text += f"  • {op['relative_path']} ({size_kb:.1f} KB)\n"

                if len(copy_ops) > 10:
                    result_text += f"  ... and {len(copy_ops) - 10} more files\n"

            messagebox.showinfo("Dry Run Results", result_text)

        except Exception as e:
            print(f"Dry run error: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Dry Run Failed", f"❌ Dry run failed:\n\n{str(e)}")

    def show_log_viewer(self, session_id=None):
        """Show real-time log viewer window"""
        # If window already exists, bring it to front
        if self.log_window and tk.Toplevel.winfo_exists(self.log_window):
            self.log_window.lift()
            self.log_window.focus()
            return

        # Create log viewer window
        self.log_window = tk.Toplevel(self.root)
        title = f"F2L - Real-Time Logs" if not session_id else f"F2L - Session Logs: {session_id}"
        self.log_window.title(title)
        self.log_window.geometry("1000x700")

        # Store session_id for filtering
        self.log_window.session_id = session_id
        self.log_window.auto_scroll = tk.BooleanVar(value=True)
        self.log_window.filter_level = tk.StringVar(value="ALL")

        # Main container
        main_frame = ttk.Frame(self.log_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Toolbar
        toolbar = ttk.Frame(main_frame)
        toolbar.pack(fill=tk.X, pady=(0, 10))

        # Filter buttons
        filter_frame = ttk.LabelFrame(toolbar, text="Filter by Level", padding=5)
        filter_frame.pack(side=tk.LEFT, padx=(0, 10))

        filter_buttons = [
            ("🔘 All", "ALL"),
            ("🔵 Info", "INFO"),
            ("🟢 Success", "SUCCESS"),
            ("🟡 Warning", "WARNING"),
            ("🔴 Error", "ERROR"),
            ("⚪ Debug", "DEBUG")
        ]

        for text, level in filter_buttons:
            btn = ttk.Radiobutton(filter_frame, text=text, value=level,
                                variable=self.log_window.filter_level,
                                command=lambda: self.refresh_log_display())
            btn.pack(side=tk.LEFT, padx=2)

        # Control buttons
        control_frame = ttk.Frame(toolbar)
        control_frame.pack(side=tk.LEFT, padx=(0, 10))

        pause_btn = ttk.Checkbutton(control_frame, text="⏸️ Pause Auto-scroll",
                                   variable=self.log_window.auto_scroll)
        pause_btn.pack(side=tk.LEFT, padx=2)

        clear_btn = ttk.Button(control_frame, text="🗑️ Clear",
                             command=lambda: self.clear_log_display(session_id))
        clear_btn.pack(side=tk.LEFT, padx=2)

        save_btn = ttk.Button(control_frame, text="💾 Save",
                            command=lambda: self.save_logs_to_file(session_id))
        save_btn.pack(side=tk.LEFT, padx=2)

        # Search frame
        search_frame = ttk.Frame(toolbar)
        search_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(search_frame, text="🔍 Search:").pack(side=tk.LEFT, padx=(0, 5))
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        search_entry.bind('<KeyRelease>', lambda e: self.search_logs(search_var.get()))
        self.log_window.search_var = search_var

        # Log display area
        log_frame = ttk.Frame(main_frame)
        log_frame.pack(fill=tk.BOTH, expand=True)

        # Create scrolled text widget
        self.log_window.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            font=("Consolas", 9),
            bg="#1E1E1E",
            fg="#FFFFFF",
            insertbackground="white"
        )
        self.log_window.log_text.pack(fill=tk.BOTH, expand=True)

        # Configure color tags
        self.log_window.log_text.tag_config("DEBUG", foreground="#808080")
        self.log_window.log_text.tag_config("INFO", foreground="#4FC3F7")
        self.log_window.log_text.tag_config("SUCCESS", foreground="#66BB6A")
        self.log_window.log_text.tag_config("WARNING", foreground="#FFA726")
        self.log_window.log_text.tag_config("ERROR", foreground="#EF5350")
        self.log_window.log_text.tag_config("TIMESTAMP", foreground="#9E9E9E")

        # Status bar
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(10, 0))

        self.log_window.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(status_frame, textvariable=self.log_window.status_var,
                               font=("Arial", 9))
        status_label.pack(side=tk.LEFT)

        # Register callback for real-time updates
        def log_callback(log_entry):
            if self.log_window and tk.Toplevel.winfo_exists(self.log_window):
                # Filter by session if needed
                if session_id and log_entry.get('session_id') != session_id:
                    return

                # Add log to display
                self.root.after(0, lambda: self.append_log_to_display(log_entry))

        self.log_manager.register_callback(log_callback)
        self.log_window.log_callback = log_callback

        # Load existing logs
        self.refresh_log_display()

        # Handle window close
        def on_close():
            self.log_manager.unregister_callback(log_callback)
            self.log_window.destroy()
            self.log_window = None

        self.log_window.protocol("WM_DELETE_WINDOW", on_close)

    def append_log_to_display(self, log_entry):
        """Append a log entry to the display"""
        if not self.log_window or not tk.Toplevel.winfo_exists(self.log_window):
            return

        # Check filter
        filter_level = self.log_window.filter_level.get()
        if filter_level != "ALL" and log_entry['level'] != filter_level:
            return

        # Check search
        search_text = self.log_window.search_var.get().lower()
        if search_text and search_text not in log_entry['message'].lower():
            return

        # Format log entry
        timestamp = log_entry['timestamp']
        level = log_entry['level']
        message = log_entry['message']
        prefix = LogManager.LOG_LEVELS.get(level, {}).get('prefix', '⚪')

        # Insert into text widget
        text_widget = self.log_window.log_text
        text_widget.config(state=tk.NORMAL)

        # Add timestamp
        text_widget.insert(tk.END, f"[{timestamp}] ", "TIMESTAMP")

        # Add level with color
        text_widget.insert(tk.END, f"{prefix} [{level}] ", level)

        # Add message
        text_widget.insert(tk.END, f"{message}\n")

        text_widget.config(state=tk.DISABLED)

        # Auto-scroll if enabled
        if self.log_window.auto_scroll.get():
            text_widget.see(tk.END)

        # Update status
        total_logs = len(self.log_manager.get_logs(self.log_window.session_id))
        self.log_window.status_var.set(f"Total logs: {total_logs} | Auto-scroll: {'ON' if self.log_window.auto_scroll.get() else 'OFF'}")

    def refresh_log_display(self):
        """Refresh the entire log display"""
        if not self.log_window or not tk.Toplevel.winfo_exists(self.log_window):
            return

        # Clear display
        text_widget = self.log_window.log_text
        text_widget.config(state=tk.NORMAL)
        text_widget.delete(1.0, tk.END)

        # Get logs
        session_id = self.log_window.session_id
        filter_level = self.log_window.filter_level.get()
        search_text = self.log_window.search_var.get().lower()

        logs = self.log_manager.get_logs(session_id)

        # Filter logs
        if filter_level != "ALL":
            logs = [log for log in logs if log['level'] == filter_level]

        if search_text:
            logs = [log for log in logs if search_text in log['message'].lower()]

        # Display logs
        for log_entry in logs:
            timestamp = log_entry['timestamp']
            level = log_entry['level']
            message = log_entry['message']
            prefix = LogManager.LOG_LEVELS.get(level, {}).get('prefix', '⚪')

            text_widget.insert(tk.END, f"[{timestamp}] ", "TIMESTAMP")
            text_widget.insert(tk.END, f"{prefix} [{level}] ", level)
            text_widget.insert(tk.END, f"{message}\n")

        text_widget.config(state=tk.DISABLED)

        # Scroll to end
        if self.log_window.auto_scroll.get():
            text_widget.see(tk.END)

        # Update status
        self.log_window.status_var.set(f"Showing {len(logs)} logs | Auto-scroll: {'ON' if self.log_window.auto_scroll.get() else 'OFF'}")

    def clear_log_display(self, session_id=None):
        """Clear logs"""
        if messagebox.askyesno("Clear Logs", "Are you sure you want to clear all logs?"):
            self.log_manager.clear_logs(session_id)
            self.refresh_log_display()

    def save_logs_to_file(self, session_id=None):
        """Save logs to a file"""
        from tkinter import filedialog

        filename = filedialog.asksaveasfilename(
            title="Save Logs",
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")]
        )

        if filename:
            if self.log_manager.save_to_file(filename, session_id):
                messagebox.showinfo("Success", f"Logs saved to:\n{filename}")
            else:
                messagebox.showerror("Error", "Failed to save logs to file.")

    def search_logs(self, search_text):
        """Search logs"""
        self.refresh_log_display()

    # Add all methods to F2LGUI class
    F2LGUI.setup_multi_session_tab = setup_multi_session_tab
    F2LGUI.show_log_viewer = show_log_viewer
    F2LGUI.append_log_to_display = append_log_to_display
    F2LGUI.refresh_log_display = refresh_log_display
    F2LGUI.clear_log_display = clear_log_display
    F2LGUI.save_logs_to_file = save_logs_to_file
    F2LGUI.search_logs = search_logs
    F2LGUI.add_new_session = add_new_session
    F2LGUI.show_session_dialog = show_session_dialog
    F2LGUI.save_session_config = save_session_config
    F2LGUI.save_session_to_db = save_session_to_db
    F2LGUI.load_saved_sessions = load_saved_sessions
    F2LGUI.refresh_sessions_display = refresh_sessions_display
    F2LGUI.start_selected_session = start_selected_session
    F2LGUI.start_session = start_session
    F2LGUI.run_session = run_session
    F2LGUI.stop_selected_session = stop_selected_session
    F2LGUI.stop_session = stop_session
    F2LGUI.start_all_sessions = start_all_sessions
    F2LGUI.stop_all_sessions = stop_all_sessions
    F2LGUI.start_session_scheduler = start_session_scheduler
    F2LGUI.update_session_last_sync = update_session_last_sync
    F2LGUI.show_sessions_context_menu = show_sessions_context_menu
    F2LGUI.edit_session = edit_session
    F2LGUI.edit_selected_session = edit_selected_session
    F2LGUI.pause_selected_session = pause_selected_session
    F2LGUI.duplicate_selected_session = duplicate_selected_session
    F2LGUI.delete_selected_session = delete_selected_session
    F2LGUI.browse_directory = browse_directory
    F2LGUI.browse_ftp_directory = browse_ftp_directory
    F2LGUI.toggle_session_filter_controls = toggle_session_filter_controls
    F2LGUI.test_session_config = test_session_config
    F2LGUI.dry_run_session_config = dry_run_session_config

# Apply the multi-session methods
add_multi_session_methods()

# Settings methods
def add_settings_methods():
    """Add settings management methods to F2LGUI class"""

    def load_scan_settings(self):
        """Load scan settings from database"""
        try:
            conn = sqlite3.connect(self.ftp_sync.db.db_path)
            cursor = conn.cursor()

            # Create settings table if not exists
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_date TEXT
                )
            ''')

            # Load each setting
            cursor.execute('SELECT key, value FROM app_settings')
            rows = cursor.fetchall()

            for key, value in rows:
                if key in self.scan_config:
                    # Convert to appropriate type
                    if isinstance(self.scan_config[key], bool):
                        self.scan_config[key] = value.lower() == 'true'
                    elif isinstance(self.scan_config[key], int):
                        self.scan_config[key] = int(value)
                    elif isinstance(self.scan_config[key], float):
                        self.scan_config[key] = float(value)
                    else:
                        self.scan_config[key] = value

            conn.close()
            print("✓ Scan settings loaded from database")

        except Exception as e:
            print(f"Note: Could not load scan settings (using defaults): {e}")

    def save_scan_settings(self):
        """Save scan settings to database"""
        try:
            conn = sqlite3.connect(self.ftp_sync.db.db_path)
            cursor = conn.cursor()

            # Create settings table if not exists
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_date TEXT
                )
            ''')

            # Save each setting
            for key, value in self.scan_config.items():
                cursor.execute('''
                    INSERT OR REPLACE INTO app_settings (key, value, updated_date)
                    VALUES (?, ?, ?)
                ''', (key, str(value), datetime.now().isoformat()))

            conn.commit()
            conn.close()
            print("✓ Scan settings saved to database")
            messagebox.showinfo("Success", "Settings saved successfully!")
            return True

        except Exception as e:
            print(f"Error saving scan settings: {e}")
            messagebox.showerror("Error", f"Failed to save settings:\n{e}")
            return False

    def reset_scan_settings(self):
        """Reset scan settings to defaults"""
        if messagebox.askyesno("Reset Settings", "Reset all settings to default values?"):
            # Reset to defaults
            self.scan_config = {
                "local_max_workers": 8,
                "local_parallel_enabled": True,
                "cache_enabled": True,
                "cache_duration": 300,
                "progress_updates": True,
                "early_filtering": False,
                "max_depth": 50,
                "chunk_size": 500,
                "ftp_max_files": 500000,
                "ftp_smart_filter": True,
                "ftp_show_warnings": True,
                "memory_efficient": True,
                "max_memory_mb": 512,
            }

            # Update UI
            self.update_settings_ui()

            # Save to database
            self.save_scan_settings()

            messagebox.showinfo("Success", "Settings reset to defaults!")

    def update_settings_ui(self):
        """Update settings UI with current values"""
        # Local scan settings
        self.settings_local_workers_var.set(self.scan_config["local_max_workers"])
        self.settings_local_parallel_var.set(self.scan_config["local_parallel_enabled"])

        # Cache settings
        self.settings_cache_enabled_var.set(self.scan_config["cache_enabled"])
        self.settings_cache_duration_var.set(self.scan_config["cache_duration"])

        # FTP scan settings
        self.settings_ftp_max_files_var.set(self.scan_config["ftp_max_files"])
        self.settings_ftp_smart_filter_var.set(self.scan_config["ftp_smart_filter"])
        self.settings_ftp_warnings_var.set(self.scan_config["ftp_show_warnings"])

        # Memory settings
        self.settings_memory_efficient_var.set(self.scan_config["memory_efficient"])
        self.settings_max_memory_var.set(self.scan_config["max_memory_mb"])

        # Advanced settings
        self.settings_max_depth_var.set(self.scan_config["max_depth"])
        self.settings_chunk_size_var.set(self.scan_config["chunk_size"])

    def apply_settings_from_ui(self):
        """Apply settings from UI to scan_config"""
        try:
            # Local scan settings
            self.scan_config["local_max_workers"] = int(self.settings_local_workers_var.get())
            self.scan_config["local_parallel_enabled"] = self.settings_local_parallel_var.get()

            # Cache settings
            self.scan_config["cache_enabled"] = self.settings_cache_enabled_var.get()
            self.scan_config["cache_duration"] = int(self.settings_cache_duration_var.get())

            # Update cache duration in the cache object
            if hasattr(self, 'scan_cache'):
                self.scan_cache.max_age_seconds = self.scan_config["cache_duration"]
                print(f"Updated cache duration to {self.scan_config['cache_duration']} seconds")

            # FTP scan settings
            self.scan_config["ftp_max_files"] = int(self.settings_ftp_max_files_var.get())
            self.scan_config["ftp_smart_filter"] = self.settings_ftp_smart_filter_var.get()
            self.scan_config["ftp_show_warnings"] = self.settings_ftp_warnings_var.get()

            # Memory settings
            self.scan_config["memory_efficient"] = self.settings_memory_efficient_var.get()
            self.scan_config["max_memory_mb"] = int(self.settings_max_memory_var.get())

            # Advanced settings
            self.scan_config["max_depth"] = int(self.settings_max_depth_var.get())
            self.scan_config["chunk_size"] = int(self.settings_chunk_size_var.get())

            # Save to database
            return self.save_scan_settings()

        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Please enter valid numbers:\n{e}")
            return False

    def clear_scan_cache(self):
        """Clear scan cache"""
        if messagebox.askyesno("Clear Cache", "Clear all cached scan results?"):
            try:
                self.scan_cache.clear_all()
                messagebox.showinfo("Success", "Scan cache cleared successfully!")
                self.settings_status_var.set("Cache cleared - next scans will be fresh")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to clear cache:\n{e}")

    # Attach methods to class
    F2LGUI.load_scan_settings = load_scan_settings
    F2LGUI.save_scan_settings = save_scan_settings
    F2LGUI.reset_scan_settings = reset_scan_settings
    F2LGUI.update_settings_ui = update_settings_ui
    F2LGUI.apply_settings_from_ui = apply_settings_from_ui
    F2LGUI.clear_scan_cache = clear_scan_cache

# Apply settings methods
add_settings_methods()

if __name__ == "__main__":
    main()
