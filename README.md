# F2L - FTP to Local Multi-Endpoint Sync Application

## Overview

F2L is an advanced file synchronization tool designed to sync files between multiple FTP endpoints and local storage. It features intelligent conflict resolution, health monitoring, multi-directional sync capabilities, local-to-local sync, multi-session management, and advanced folder filtering.

## Features

### Core Features
- **Multi-Endpoint Management**: Manage multiple FTP connections from a single interface
- **Bidirectional Sync**: Support for FTP→Local, Local→FTP, and Bidirectional synchronization
- **Local-to-Local Sync**: Sync between local directories without FTP
- **Intelligent Conflict Resolution**: Handle file conflicts with customizable strategies
- **Health Monitoring**: Real-time connection monitoring with automatic health checks
- **Smart File Detection**: Only syncs changed/new files based on modification time and size
- **Folder Filtering**: Target specific folders with exact match or contains mode (case-sensitive/insensitive)

### Multi-Session Management
- **FTP Multi-Session**: Manage multiple independent FTP sync sessions
- **Local Multi-Session**: Manage multiple local directory sync sessions
- **Session Scheduling**: Auto-run sessions at specified intervals (minutes/hours/days)
- **Parallel/Sequential Execution**: Control whether sessions run simultaneously or one-at-a-time
- **Auto-Start**: Sessions can start automatically when application launches
- **Session Logs**: Individual log viewer for each session with real-time updates
- **Session Status Tracking**: Monitor running/stopped/completed status for each session

### Advanced Features
- **System Tray Integration**: Run in background with system tray support
- **Comprehensive Logging**: Complete audit trail of all operations with color-coded levels
- **Progress Tracking**: Real-time progress monitoring with detailed status and statistics
- **Dry Run Mode**: Preview operations before execution
- **Multi-threaded Operations**: Efficient file transfers with configurable thread count (up to 8 threads)
- **Database Tracking**: SQLite database for persistent operation history
- **Scan Caching**: Intelligent directory scan caching for improved performance
- **Single Instance Lock**: Prevents multiple app instances from running simultaneously
- **FTP Directory Browser**: Visual FTP directory browser for easy path selection

### Search & Filter Operations
- **Search**: Real-time search across file paths and names
- **Type Filter**: Filter by operation type (Download/Upload/Skip/Conflict)
- **Size Filter**: Filter by file size ranges (<1MB, 1-10MB, 10-100MB, >100MB)
- **Changes Only**: Quick filter to show only files that need syncing
- **Select Operations**: Bulk select all, none, filtered, or changes only
- **Per-File Selection**: Checkbox for each file to sync individually

### User Interface
- **Tabbed Interface**: 6 tabs - FTP Endpoints, Sync Operations, Local Sync, Multi-Session Manager, FTP Multi-Session, Reports
- **Scrollable Tabs**: All tabs support vertical scrolling for large content
- **Visual Status Indicators**: Real-time connection status with color-coded indicators
- **Detailed Reports**: Comprehensive sync and health reports with export functionality
- **Easy Configuration**: User-friendly dialogs for endpoint and session setup
- **Horizontal & Vertical Scrollbars**: Navigate large file lists and wide columns easily

## Installation

### Requirements
- Python 3.7 or higher
- Windows Operating System

### Core Dependencies (Included with Python)
- tkinter
- sqlite3
- ftplib
- threading
- datetime
- os, shutil, pathlib

### Optional Dependencies (For Enhanced Features)
```bash
# For system tray support
pip install pystray pillow

# For scheduling support  
pip install schedule
```

### Quick Start
1. Download the `f2l_complete.py` file
2. Run the application:
   ```bash
   python f2l_complete.py
   ```

## Usage Guide

### 1. Adding FTP Endpoints
1. Click "Add Endpoint" in the FTP Endpoints tab
2. Fill in the connection details:
   - Endpoint Name (for identification)
   - FTP Host and Port
   - Username and Password
   - Remote Path (FTP directory)
   - Local Path (destination directory)
3. Configure options:
   - **FTP is main source**: FTP wins file conflicts
   - **Auto sync**: Enable automatic synchronization
   - **Sync interval**: Time between automatic syncs
4. Test the connection before saving

### 2. Performing FTP Sync Operations
1. Go to the "Sync Operations" tab
2. Select an endpoint from the dropdown
3. Choose sync direction:
   - **FTP → Local**: Download from FTP to local
   - **Local → FTP**: Upload from local to FTP
   - **Bidirectional**: Sync both directions
4. Enable folder filtering (optional):
   - Enter folder names (comma-separated)
   - Choose match mode (Exact or Contains)
   - Toggle case sensitivity
5. Click "Scan Operations" to preview
6. Use search and filters to refine operations
7. Select specific files or use "Select All"
8. Click "Start Sync" to begin

### 3. Local-to-Local Sync
1. Go to the "Local Sync" tab
2. Select source and destination directories
3. Choose sync direction:
   - **Source → Dest**: Copy from source to destination
   - **Dest → Source**: Copy from destination to source
   - **Bidirectional**: Sync both ways
4. Enable folder filtering (optional)
5. Enable scheduling (optional):
   - Set interval (minutes/hours/days)
   - Start/stop/pause schedule
   - Run now for immediate sync
6. Click "Scan" to preview operations
7. Click "Start Sync" to begin

### 4. FTP Multi-Session Manager
1. Go to the "FTP Multi-Session" tab
2. Click "➕ Add Session" to create a new session
3. Configure session:
   - Session name
   - Select FTP endpoint
   - Set source path (within endpoint path)
   - Set destination path (local)
   - Choose sync direction
   - Enable folder filtering (optional)
   - Enable scheduling (optional)
   - Set auto-start (optional)
   - Allow parallel execution (optional)
4. Click "Save"
5. Use controls:
   - **▶️ Start**: Start selected session
   - **⏹️ Stop**: Stop selected session
   - **▶️ Start All**: Start all active sessions
   - **⏹️ Stop All**: Stop all running sessions
   - **📋 Session Logs**: View session-specific logs

### 5. Local Multi-Session Manager
1. Go to the "Multi-Session Manager" tab
2. Click "➕ Add Session" to create a new session
3. Configure similar to FTP Multi-Session
4. Manage multiple local sync sessions independently

### 6. Health Monitoring
- View real-time connection status in the "Health Monitor" tab
- Auto health monitoring runs every 30 seconds by default
- Check detailed logs for connection issues
- Manually test all endpoints with "Test All Connections"

### 7. Reports and Logs
- Generate comprehensive sync reports
- View health monitoring reports
- Export reports to text files
- Clear logs when needed
- View session-specific logs with color-coded levels

## Configuration Options

### Endpoint Settings
- **Name**: Friendly name for identification
- **Host/Port**: FTP server connection details
- **Credentials**: Username and password
- **Paths**: Remote FTP path and local destination
- **Main Source**: Designate authoritative data source
- **Auto Sync**: Enable background synchronization
- **Interval**: Minutes between automatic syncs

### Sync Settings
- **Direction**: FTP→Local, Local→FTP, or Bidirectional
- **Conflict Resolution**: FTP wins, Local wins, Newer wins, or Ask user
- **Folder Filtering**: Target specific folders by name
- **Match Mode**: Exact match or Contains
- **Case Sensitivity**: Toggle case-sensitive matching

### Session Settings
- **Session Name**: Unique identifier for the session
- **Source/Destination Paths**: Independent paths for each session
- **Scheduling**: Auto-run at intervals (minutes/hours/days)
- **Auto-Start**: Start when application launches
- **Parallel Execution**: Allow simultaneous execution with other sessions
- **Active Status**: Enable/disable session without deleting

### Scan Performance Settings
- **Max Workers**: Thread pool size (1-8 threads)
- **Cache Enabled**: Enable directory scan caching
- **Max Depth**: Maximum recursion depth (default: 50)
- **Chunk Size**: Files per progress update (default: 500)

## File Structure

```
D:\ppr\dev\
├── f2l_complete.py     # Main application file
├── f2l_sync.db         # SQLite database (created automatically)
├── README.md           # This documentation
└── requirements.txt    # Optional dependencies
```

## Database Schema

The application uses SQLite to store:
- **ftp_endpoints**: FTP endpoint configurations
- **sync_operations**: Individual file operations log
- **sync_sessions**: Sync session summaries
- **ftp_sync_configs**: FTP multi-session configurations
- **local_sync_configs**: Local multi-session configurations
- **scan_cache**: Directory scan cache for performance

## Advanced Usage

### System Tray Operation
With pystray installed:
1. Click "Hide to Tray" to minimize to system tray
2. Right-click tray icon for quick actions
3. App continues running in background
4. Health monitoring and auto-sync continue

### Command Line Usage
```bash
# Basic run
python f2l_complete.py

# With full features (install optional deps first)
pip install pystray pillow schedule
python f2l_complete.py
```

## Troubleshooting

### Common Issues

**Connection Failed**
- Check FTP credentials
- Verify network connectivity
- Ensure FTP server allows connections
- Check firewall settings

**Permission Denied**
- Verify FTP user has read/write permissions
- Check local directory write permissions
- Ensure paths exist and are accessible

**Sync Not Working**
- Verify endpoint is marked as "Connected"
- Check file modification times
- Review conflict resolution settings
- Check available disk space

**Folder Filter Not Finding Files**
- Ensure folder names are spelled correctly
- Check case sensitivity setting
- Use "Contains" mode for partial matches
- Verify folders exist in the directory structure
- Check debug output for scan statistics

**Operations Widget Shows Wrong Count**
- Uncheck "Changes only" to see all operations (Copy + Skip)
- Check "Changes only" to see only files needing sync
- Verify folder filter is not too restrictive
- Review scan debug output for file counts

**Multiple App Instances Error**
- Only one instance can run at a time
- Close existing instance or check Task Manager
- Delete `f2l_sync.lock` file if app crashed

**Session Not Starting**
- Check session is marked as "Active"
- Verify paths exist and are accessible
- Check session logs for error messages
- Ensure FTP endpoint is connected (for FTP sessions)

### Logs and Debugging
- Check Health Monitor tab for connection logs
- Review sync operation reports
- Enable health monitoring for automatic status updates
- Export reports for detailed analysis
- View session-specific logs for multi-session issues
- Check console output for debug messages

## Architecture

### Components
- **FTPManager**: Handles FTP connections and operations
- **DatabaseManager**: Manages SQLite database operations
- **FTPSync**: Core synchronization logic
- **F2LGUI**: User interface and main application

### Threading
- Health monitoring runs in background thread
- Sync operations use separate thread pool
- UI remains responsive during operations
- Progress updates via thread-safe queue

## Security Considerations

- FTP passwords stored in local SQLite database
- No encryption for stored credentials
- Consider using secure FTP (SFTP) if available
- Run application with appropriate user permissions

## Limitations

- FTP only (no SFTP support in current version)
- Windows-focused (but should work on other platforms)
- No real-time file watching (planned feature)
- Limited to text-based progress reporting

## Version History

**v2.0** - Major Feature Update
- Local-to-local directory sync
- FTP Multi-Session manager
- Local Multi-Session manager
- Advanced folder filtering (exact/contains, case-sensitive)
- Search & filter operations (type, size, changes only)
- Per-file selection with checkboxes
- Session scheduling (minutes/hours/days)
- Auto-start sessions
- Parallel/sequential session execution
- Real-time session logs with color coding
- FTP directory browser
- Scan caching for performance
- Multi-threaded directory scanning (up to 8 threads)
- Single instance lock
- Scrollable tab content
- Horizontal scrollbars for wide content
- Enhanced progress tracking with statistics

**v1.0** - Initial Release
- Multi-endpoint FTP sync
- Health monitoring
- System tray support
- Comprehensive reporting
- Bidirectional sync
- Conflict resolution

## Support

For issues or questions:
1. Check the Health Monitor logs
2. Review the troubleshooting section
3. Export reports for detailed analysis
4. Check FTP server logs if available

## License

This software is provided as-is for educational and development purposes.
