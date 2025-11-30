"""
FTP Service - Handle FTP/SFTP connections and operations.
"""
import ftplib
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, List
from datetime import datetime


class FTPService:
    """Service for FTP operations."""
    
    def __init__(self):
        """Initialize FTP service with thread pool for blocking operations."""
        self.executor = ThreadPoolExecutor(max_workers=5)
    
    def _test_connection_sync(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        timeout: int = 10
    ) -> Dict[str, any]:
        """
        Synchronous FTP connection test (runs in thread pool).
        
        Args:
            host: FTP server hostname
            port: FTP server port
            username: FTP username
            password: FTP password
            timeout: Connection timeout in seconds
            
        Returns:
            Dictionary with success, message, and error keys
        """
        ftp = None
        try:
            # Create FTP connection
            ftp = ftplib.FTP()
            ftp.set_debuglevel(0)
            
            # Connect to server
            ftp.connect(host, port, timeout=timeout)
            
            # Login
            ftp.login(username, password)
            
            # Set passive mode
            ftp.set_pasv(True)
            
            # Get welcome message
            welcome_msg = ftp.getwelcome()
            
            # Test basic operation
            current_dir = ftp.pwd()
            
            # Close connection
            ftp.quit()
            
            return {
                'success': True,
                'message': f'Connected successfully to {host}:{port}. Current directory: {current_dir}',
                'error': None,
                'details': {
                    'welcome': welcome_msg,
                    'current_directory': current_dir
                }
            }
            
        except ftplib.error_perm as e:
            # Permission/authentication error
            error_msg = str(e)
            return {
                'success': False,
                'message': f'Authentication failed: {error_msg}',
                'error': error_msg,
                'details': None
            }
            
        except ftplib.error_temp as e:
            # Temporary error
            error_msg = str(e)
            return {
                'success': False,
                'message': f'Temporary FTP error: {error_msg}',
                'error': error_msg,
                'details': None
            }
            
        except TimeoutError as e:
            error_msg = f'Connection timeout after {timeout} seconds'
            return {
                'success': False,
                'message': error_msg,
                'error': str(e),
                'details': None
            }
            
        except Exception as e:
            # General error
            error_msg = str(e)
            return {
                'success': False,
                'message': f'Connection failed: {error_msg}',
                'error': error_msg,
                'details': None
            }
            
        finally:
            # Cleanup
            if ftp:
                try:
                    ftp.quit()
                except:
                    try:
                        ftp.close()
                    except:
                        pass
    
    async def test_connection(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        timeout: int = 10
    ) -> Dict[str, any]:
        """
        Test FTP connection asynchronously.
        
        Args:
            host: FTP server hostname
            port: FTP server port
            username: FTP username
            password: FTP password
            timeout: Connection timeout in seconds
            
        Returns:
            Dictionary with success, message, and error keys
        """
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self.executor,
            self._test_connection_sync,
            host,
            port,
            username,
            password,
            timeout
        )
        return result
    
    def _list_directory_sync(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        remote_path: str,
        timeout: int = 10
    ) -> Dict[str, any]:
        """
        Synchronous FTP directory listing (runs in thread pool).
        
        Args:
            host: FTP server hostname
            port: FTP server port
            username: FTP username
            password: FTP password
            remote_path: Remote directory path
            timeout: Connection timeout in seconds
            
        Returns:
            Dictionary with success, files list, and error keys
        """
        ftp = None
        try:
            # Create FTP connection
            ftp = ftplib.FTP()
            ftp.set_debuglevel(0)
            
            # Connect and login
            ftp.connect(host, port, timeout=timeout)
            ftp.login(username, password)
            ftp.set_pasv(True)
            
            # Change to directory
            ftp.cwd(remote_path)
            
            # List directory contents
            files = []
            
            # Try MLSD first (more detailed)
            try:
                for name, facts in ftp.mlsd():
                    if name in ['.', '..']:
                        continue
                    
                    is_dir = facts.get('type', '') == 'dir'
                    size = int(facts.get('size', 0))
                    
                    # Parse modify time
                    modify_str = facts.get('modify', '')
                    modified_time = None
                    if modify_str:
                        try:
                            modified_time = datetime.strptime(modify_str, '%Y%m%d%H%M%S').isoformat()
                        except:
                            pass
                    
                    files.append({
                        'name': name,
                        'size': size,
                        'modified_time': modified_time,
                        'is_directory': is_dir,
                        'path': f"{remote_path.rstrip('/')}/{name}"
                    })
            
            except ftplib.error_perm:
                # MLSD not supported, fall back to NLST + SIZE
                names = ftp.nlst()
                for name in names:
                    if name in ['.', '..']:
                        continue
                    
                    # Try to determine if it's a directory
                    is_dir = False
                    size = 0
                    try:
                        # Try to CWD into it
                        ftp.cwd(f"{remote_path.rstrip('/')}/{name}")
                        is_dir = True
                        ftp.cwd(remote_path)  # Go back
                    except:
                        # Not a directory, try to get size
                        try:
                            size = ftp.size(name) or 0
                        except:
                            size = 0
                    
                    files.append({
                        'name': name,
                        'size': size,
                        'modified_time': None,
                        'is_directory': is_dir,
                        'path': f"{remote_path.rstrip('/')}/{name}"
                    })
            
            # Close connection
            ftp.quit()
            
            return {
                'success': True,
                'files': files,
                'error': None
            }
            
        except Exception as e:
            error_msg = str(e)
            return {
                'success': False,
                'files': [],
                'error': error_msg
            }
            
        finally:
            if ftp:
                try:
                    ftp.quit()
                except:
                    try:
                        ftp.close()
                    except:
                        pass
    
    async def list_directory(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        remote_path: str,
        timeout: int = 10
    ) -> Dict[str, any]:
        """
        List FTP directory contents asynchronously.
        
        Args:
            host: FTP server hostname
            port: FTP server port
            username: FTP username
            password: FTP password
            remote_path: Remote directory path
            timeout: Connection timeout in seconds
            
        Returns:
            Dictionary with success, files list, and error keys
        """
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self.executor,
            self._list_directory_sync,
            host,
            port,
            username,
            password,
            remote_path,
            timeout
        )
        return result


# Global FTP service instance
ftp_service = FTPService()

