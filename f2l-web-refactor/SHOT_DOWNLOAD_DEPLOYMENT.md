# Shot Download Feature - Deployment Documentation

## Overview

The Shot Download feature allows users to download animation and lighting shots from FTP to local storage with version control and file conflict management.

## Current Status

### ✅ Completed Features (Phase 1-4)

1. **Backend Foundation**
   - Database models for tasks and items
   - Shot comparison service
   - Shot download service
   - FTP structure scanning

2. **Backend API**
   - GET /shots/structure/{endpoint_id} - Get cached structure
   - POST /shots/structure/{endpoint_id}/scan - Trigger scan
   - POST /shots/compare - Compare shots
   - POST /shots/tasks - Create download task
   - GET /shots/tasks - List tasks
   - GET /shots/tasks/{task_id} - Get task details
   - POST /shots/tasks/{task_id}/execute - Execute task
   - POST /shots/tasks/{task_id}/cancel - Cancel task
   - DELETE /shots/tasks/{task_id} - Delete task

3. **Frontend UI**
   - Shot Download page with task list
   - Create Task Dialog with filters
   - Automatic structure scanning
   - Task execution and monitoring
   - Real-time progress updates

4. **Deployment & Testing**
   - Git-based deployment workflow
   - Docker container setup
   - Database migrations
   - Bug fixes and optimizations

### 🚧 Pending Features (Phase 5-6)

## Phase 5: Version Selection & File Conflict Handling

### Feature 1: Version Selection (Hybrid Approach)

**User Story:**
As a user, I want to control which version of shots to download, so I can get the exact versions I need for my work.

**Implementation Plan:**

#### 5.1. Database Schema Changes

**Add to `shot_download_tasks` table:**
```sql
ALTER TABLE shot_download_tasks ADD COLUMN version_strategy VARCHAR(20) DEFAULT 'latest';
-- Options: 'latest', 'specific', 'all', 'custom'

ALTER TABLE shot_download_tasks ADD COLUMN specific_version VARCHAR(20);
-- Used when version_strategy = 'specific'
```

**Add to `shot_download_items` table:**
```sql
ALTER TABLE shot_download_items ADD COLUMN selected_version VARCHAR(20);
-- Used when version_strategy = 'custom'

ALTER TABLE shot_download_items ADD COLUMN available_versions JSONB;
-- List of available versions from FTP: ["v001", "v002", "v003"]

ALTER TABLE shot_download_items ADD COLUMN latest_version VARCHAR(20);
-- Latest available version
```

#### 5.2. Backend Changes

**File: `backend/app/database/models.py`**
```python
class ShotDownloadTask(Base):
    # ... existing fields ...

    # Version Control
    version_strategy: Mapped[str] = mapped_column(String(20), default='latest')
    specific_version: Mapped[Optional[str]] = mapped_column(String(20))

class ShotDownloadItem(Base):
    # ... existing fields ...

    # Version Control
    selected_version: Mapped[Optional[str]] = mapped_column(String(20))
    available_versions: Mapped[Optional[List[str]]] = mapped_column(JSONB)
    latest_version: Mapped[Optional[str]] = mapped_column(String(20))
```

**File: `backend/app/services/shot_comparison_service.py`**
```python
# Add method to list available versions
async def _list_anim_versions(
    self,
    ftp_manager: FTPManager,
    paths: ShotPaths
) -> List[str]:
    """List all available animation versions."""
    publish_path = f"{paths.anim_path}/publish"

    try:
        items = ftp_manager.list_directory(publish_path, recursive=False)
        versions = [
            item.path.split('/')[-1]
            for item in items
            if not item.is_file and item.path.split('/')[-1].startswith('v')
        ]
        return sorted(versions)
    except Exception as e:
        logger.error(f"Failed to list anim versions: {e}")
        return []

async def _list_lighting_versions(
    self,
    ftp_manager: FTPManager,
    paths: ShotPaths
) -> List[str]:
    """List all available lighting versions."""
    version_path = f"{paths.lighting_path}/version"

    try:
        items = ftp_manager.list_directory(version_path, recursive=False)
        # Extract unique version numbers from filenames
        versions = set()
        for item in items:
            if item.is_file:
                filename = item.path.split('/')[-1]
                # Extract version like v001, v002 from filename
                import re
                match = re.search(r'_v(\d+)\.', filename)
                if match:
                    versions.add(f"v{match.group(1)}")
        return sorted(list(versions))
    except Exception as e:
        logger.error(f"Failed to list lighting versions: {e}")
        return []

# Update compare_shot to include version info
async def compare_shot(...) -> ShotComparisonResult:
    # ... existing code ...

    # List available versions
    if department == 'anim':
        available_versions = await self._list_anim_versions(ftp_manager, paths)
    else:
        available_versions = await self._list_lighting_versions(ftp_manager, paths)

    latest_version = available_versions[-1] if available_versions else None

    return ShotComparisonResult(
        # ... existing fields ...
        available_versions=available_versions,
        latest_version=latest_version
    )
```

**File: `backend/app/services/shot_download_service.py`**
```python
async def create_download_task(..., version_strategy: str = 'latest', specific_version: Optional[str] = None):
    """Create download task with version strategy."""

    task = ShotDownloadTask(
        # ... existing fields ...
        version_strategy=version_strategy,
        specific_version=specific_version
    )

    # ... rest of existing code ...

async def _download_item(self, endpoint, item):
    """Download item with version selection logic."""

    # Determine which version to download
    if item.task.version_strategy == 'latest':
        version = item.latest_version or item.ftp_version

    elif item.task.version_strategy == 'specific':
        version = item.task.specific_version
        # Check if version exists
        if version not in (item.available_versions or []):
            logger.warning(
                f"Version {version} not available for {item.shot}/{item.department}, "
                f"available: {item.available_versions}, skipping"
            )
            item.status = ShotDownloadItemStatus.SKIPPED
            item.error_message = f"Version {version} not available"
            await self.db.commit()
            return

    elif item.task.version_strategy == 'custom':
        version = item.selected_version or item.latest_version

    elif item.task.version_strategy == 'all':
        # Download all versions
        for version in (item.available_versions or []):
            await self._download_version(ftp_manager, local_manager, item, version)
        return

    # Download the selected version
    await self._download_version(ftp_manager, local_manager, item, version)
```

#### 5.3. Frontend Changes

**File: `frontend/src/pages/ShotDownload/CreateTaskDialog.tsx`**
```typescript
// Add state for version strategy
const [versionStrategy, setVersionStrategy] = useState<'latest' | 'specific' | 'all' | 'custom'>('latest');
const [specificVersion, setSpecificVersion] = useState('');
const [customVersions, setCustomVersions] = useState<Record<string, string>>({});

// Add UI for version selection
<FormControl mt={4}>
  <FormLabel>Version Strategy</FormLabel>
  <RadioGroup value={versionStrategy} onChange={(v) => setVersionStrategy(v as any)}>
    <Stack spacing={2}>
      <Radio value="latest">
        <Box>
          <Text fontWeight="medium">Latest Version</Text>
          <Text fontSize="sm" color="gray.600">
            Download the newest version of each shot (recommended)
          </Text>
        </Box>
      </Radio>

      <Radio value="specific">
        <HStack>
          <Text fontWeight="medium">Specific Version:</Text>
          <Input
            placeholder="v005"
            width="100px"
            value={specificVersion}
            onChange={(e) => setSpecificVersion(e.target.value)}
            isDisabled={versionStrategy !== 'specific'}
          />
        </HStack>
        <Text fontSize="sm" color="gray.600" ml={6}>
          Download the same version for all shots (skips if not available)
        </Text>
      </Radio>

      <Radio value="all">
        <Box>
          <Text fontWeight="medium">All Versions</Text>
          <Text fontSize="sm" color="gray.600">
            Download all available versions for each shot
          </Text>
        </Box>
      </Radio>

      <Radio value="custom">
        <Box>
          <Text fontWeight="medium">Custom (Advanced)</Text>
          <Text fontSize="sm" color="gray.600">
            Select specific version for each shot individually
          </Text>
        </Box>
      </Radio>
    </Stack>
  </RadioGroup>
</FormControl>

// Show custom version matrix if selected
{versionStrategy === 'custom' && comparisonResults.length > 0 && (
  <Box mt={4} maxH="400px" overflowY="auto">
    <HStack mb={2} spacing={2}>
      <Button size="sm" onClick={() => setAllVersionsToLatest()}>
        Set All to Latest
      </Button>
      <HStack>
        <Text fontSize="sm">Set All to:</Text>
        <Input
          size="sm"
          placeholder="v___"
          width="80px"
          onKeyPress={(e) => {
            if (e.key === 'Enter') {
              setAllVersionsToSpecific(e.currentTarget.value);
            }
          }}
        />
      </HStack>
    </HStack>

    <Table size="sm" variant="simple">
      <Thead position="sticky" top={0} bg="white" zIndex={1}>
        <Tr>
          <Th>Shot</Th>
          <Th>Dept</Th>
          <Th>Available</Th>
          <Th>Local</Th>
          <Th>Download</Th>
        </Tr>
      </Thead>
      <Tbody>
        {comparisonResults.map((result) => {
          const key = `${result.shot}-${result.department}`;
          return (
            <Tr key={key}>
              <Td>{result.shot}</Td>
              <Td>
                <Badge colorScheme={result.department === 'anim' ? 'blue' : 'orange'}>
                  {result.department}
                </Badge>
              </Td>
              <Td fontSize="xs">
                {result.available_versions?.join(', ') || 'N/A'}
              </Td>
              <Td fontSize="xs">{result.local_version || 'None'}</Td>
              <Td>
                <Select
                  size="sm"
                  value={customVersions[key] || result.latest_version}
                  onChange={(e) => setCustomVersions({
                    ...customVersions,
                    [key]: e.target.value
                  })}
                >
                  <option value={result.latest_version}>
                    Latest ({result.latest_version})
                  </option>
                  {result.available_versions?.map((v) => (
                    <option key={v} value={v}>{v}</option>
                  ))}
                </Select>
              </Td>
            </Tr>
          ))}
      </Tbody>
    </Table>
  </Box>
)}
```

### Feature 2: File Conflict Handling

**User Story:**
As a user, I want to control how existing files are handled during download, so I can avoid overwriting important files or skip unnecessary downloads.

#### 5.4. Database Schema Changes

**Add to `shot_download_tasks` table:**
```sql
ALTER TABLE shot_download_tasks ADD COLUMN conflict_strategy VARCHAR(20) DEFAULT 'skip';
-- Options: 'skip', 'overwrite', 'compare', 'keep_both'
```

**Add to `shot_download_items` table:**
```sql
ALTER TABLE shot_download_items ADD COLUMN files_skipped INTEGER DEFAULT 0;
ALTER TABLE shot_download_items ADD COLUMN files_overwritten INTEGER DEFAULT 0;
ALTER TABLE shot_download_items ADD COLUMN files_kept_both INTEGER DEFAULT 0;
```

#### 5.5. Backend Changes

**File: `backend/app/database/models.py`**
```python
class ShotDownloadTask(Base):
    # ... existing fields ...

    # File Conflict Handling
    conflict_strategy: Mapped[str] = mapped_column(String(20), default='skip')

class ShotDownloadItem(Base):
    # ... existing fields ...

    # File Statistics
    files_skipped: Mapped[int] = mapped_column(Integer, default=0)
    files_overwritten: Mapped[int] = mapped_column(Integer, default=0)
    files_kept_both: Mapped[int] = mapped_column(Integer, default=0)
```

**File: `backend/app/core/ftp_manager.py`**
```python
def download_file_with_conflict_handling(
    self,
    remote_path: str,
    local_path: str,
    conflict_strategy: str = 'skip'
) -> dict:
    """
    Download file with conflict handling.

    Returns:
        dict with keys: 'action' ('downloaded', 'skipped', 'overwritten', 'kept_both'),
                       'local_path', 'size'
    """
    import os
    from datetime import datetime

    # Check if file exists
    if os.path.exists(local_path):
        if conflict_strategy == 'skip':
            logger.info(f"Skipping existing file: {local_path}")
            return {
                'action': 'skipped',
                'local_path': local_path,
                'size': os.path.getsize(local_path)
            }

        elif conflict_strategy == 'compare':
            # Get remote file info
            remote_size = self.get_file_size(remote_path)
            remote_mtime = self.get_file_mtime(remote_path)

            # Get local file info
            local_size = os.path.getsize(local_path)
            local_mtime = datetime.fromtimestamp(os.path.getmtime(local_path))

            # Skip if same size and remote is not newer
            if local_size == remote_size and remote_mtime <= local_mtime:
                logger.info(f"Skipping unchanged file: {local_path}")
                return {
                    'action': 'skipped',
                    'local_path': local_path,
                    'size': local_size
                }

            # Otherwise, overwrite
            logger.info(f"Overwriting outdated file: {local_path}")
            self.download_file(remote_path, local_path)
            return {
                'action': 'overwritten',
                'local_path': local_path,
                'size': os.path.getsize(local_path)
            }

        elif conflict_strategy == 'keep_both':
            # Rename existing file with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            base, ext = os.path.splitext(local_path)
            backup_path = f"{base}_backup_{timestamp}{ext}"
            os.rename(local_path, backup_path)
            logger.info(f"Renamed existing file to: {backup_path}")

            # Download new file
            self.download_file(remote_path, local_path)
            return {
                'action': 'kept_both',
                'local_path': local_path,
                'backup_path': backup_path,
                'size': os.path.getsize(local_path)
            }

        elif conflict_strategy == 'overwrite':
            # Overwrite without checking
            logger.info(f"Overwriting file: {local_path}")
            self.download_file(remote_path, local_path)
            return {
                'action': 'overwritten',
                'local_path': local_path,
                'size': os.path.getsize(local_path)
            }
    else:
        # File doesn't exist, download normally
        self.download_file(remote_path, local_path)
        return {
            'action': 'downloaded',
            'local_path': local_path,
            'size': os.path.getsize(local_path)
        }
```

**File: `backend/app/services/shot_download_service.py`**
```python
async def _download_anim_version(self, ftp_manager, local_manager, item):
    """Download animation version with conflict handling."""
    # ... existing code ...

    conflict_strategy = item.task.conflict_strategy

    for file_info in file_infos:
        if file_info.is_file:
            remote_file = file_info.path
            relative_path = remote_file.replace(version_path + '/', '')
            local_file = os.path.join(local_version_path, relative_path)

            # Create subdirectories
            local_dir = os.path.dirname(local_file)
            os.makedirs(local_dir, exist_ok=True)

            # Download with conflict handling
            result = await loop.run_in_executor(
                None,
                ftp_manager.download_file_with_conflict_handling,
                remote_file,
                local_file,
                conflict_strategy
            )

            # Update statistics
            if result['action'] == 'skipped':
                item.files_skipped += 1
            elif result['action'] == 'overwritten':
                item.files_overwritten += 1
            elif result['action'] == 'kept_both':
                item.files_kept_both += 1

            item.downloaded_size += result['size']
            await self.db.commit()
```

#### 5.6. Frontend Changes

**File: `frontend/src/pages/ShotDownload/CreateTaskDialog.tsx`**
```typescript
// Add state for conflict strategy
const [conflictStrategy, setConflictStrategy] = useState<'skip' | 'overwrite' | 'compare' | 'keep_both'>('skip');

// Add UI for conflict strategy
<FormControl mt={4}>
  <FormLabel>File Conflict Strategy</FormLabel>
  <RadioGroup value={conflictStrategy} onChange={(v) => setConflictStrategy(v as any)}>
    <Stack spacing={2}>
      <Radio value="skip">
        <Box>
          <HStack>
            <Text fontWeight="medium">Skip Existing</Text>
            <Badge colorScheme="green">Recommended</Badge>
          </HStack>
          <Text fontSize="sm" color="gray.600">
            Don't download if file already exists locally (fastest, saves bandwidth)
          </Text>
        </Box>
      </Radio>

      <Radio value="compare">
        <Box>
          <Text fontWeight="medium">Compare & Update</Text>
          <Text fontSize="sm" color="gray.600">
            Only download if FTP file is newer or different size (smart, efficient)
          </Text>
        </Box>
      </Radio>

      <Radio value="overwrite">
        <Box>
          <Text fontWeight="medium">Overwrite All</Text>
          <Text fontSize="sm" color="gray.600">
            Always download and replace existing files (ensures fresh copies)
          </Text>
        </Box>
      </Radio>

      <Radio value="keep_both">
        <Box>
          <Text fontWeight="medium">Keep Both</Text>
          <Text fontSize="sm" color="gray.600">
            Rename existing file with timestamp, download new one (safest, uses more storage)
          </Text>
        </Box>
      </Radio>
    </Stack>
  </RadioGroup>
</FormControl>
```

**File: `frontend/src/pages/ShotDownload/TaskDetailsDialog.tsx`**
```typescript
// Show file statistics
<Stat>
  <StatLabel>Files Downloaded</StatLabel>
  <StatNumber>{item.file_count - item.files_skipped}</StatNumber>
</Stat>

<Stat>
  <StatLabel>Files Skipped</StatLabel>
  <StatNumber>{item.files_skipped}</StatNumber>
  <StatHelpText>Already existed</StatHelpText>
</Stat>

<Stat>
  <StatLabel>Files Overwritten</StatLabel>
  <StatNumber>{item.files_overwritten}</StatNumber>
  <StatHelpText>Replaced existing</StatHelpText>
</Stat>

{item.files_kept_both > 0 && (
  <Stat>
    <StatLabel>Files Kept Both</StatLabel>
    <StatNumber>{item.files_kept_both}</StatNumber>
    <StatHelpText>Backed up old version</StatHelpText>
  </Stat>
)}
```

## Phase 6: Logs Viewer UI

### Feature: Real-time Logs Viewer

**User Story:**
As a user, I want to see download logs in the UI, so I can monitor what's happening and troubleshoot issues without SSH access.

#### 6.1. Backend API Enhancement

**File: `backend/app/api/v1/shots.py`**
```python
@router.get("/tasks/{task_id}/logs")
async def get_task_logs(
    task_id: UUID,
    level: Optional[str] = Query(None, description="Filter by log level"),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db)
):
    """Get logs for a specific download task."""
    # Implementation to fetch logs from database or Docker logs
    pass
```

#### 6.2. Frontend Changes

**File: `frontend/src/pages/ShotDownload/TaskLogsDialog.tsx`**
```typescript
// New component to show task logs
export function TaskLogsDialog({ taskId, isOpen, onClose }) {
  const { data: logs, isLoading } = useQuery(
    ['task-logs', taskId],
    () => shotService.getTaskLogs(taskId),
    { refetchInterval: 2000 } // Auto-refresh every 2 seconds
  );

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="6xl">
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>Task Logs</ModalHeader>
        <ModalCloseButton />
        <ModalBody>
          <Box
            bg="gray.900"
            color="green.300"
            p={4}
            borderRadius="md"
            fontFamily="mono"
            fontSize="sm"
            maxH="600px"
            overflowY="auto"
          >
            {logs?.map((log, i) => (
              <Box key={i} mb={1}>
                <Text as="span" color="gray.500">[{log.timestamp}]</Text>
                <Text as="span" color={getLogColor(log.level)} ml={2}>
                  {log.level}
                </Text>
                <Text as="span" ml={2}>{log.message}</Text>
              </Box>
            ))}
          </Box>
        </ModalBody>
      </ModalContent>
    </Modal>
  );
}
```

## Deployment Checklist

### Phase 5 Deployment

- [ ] Create database migration for new fields
- [ ] Update backend models
- [ ] Implement version listing in comparison service
- [ ] Implement version selection in download service
- [ ] Implement conflict handling in FTP manager
- [ ] Update frontend CreateTaskDialog UI
- [ ] Update frontend TaskDetailsDialog to show statistics
- [ ] Test version selection (latest, specific, all, custom)
- [ ] Test conflict strategies (skip, overwrite, compare, keep_both)
- [ ] Deploy to production
- [ ] User acceptance testing

### Phase 6 Deployment

- [ ] Implement logs API endpoint
- [ ] Create TaskLogsDialog component
- [ ] Add "View Logs" button to task list
- [ ] Test real-time log streaming
- [ ] Deploy to production
- [ ] User acceptance testing

## Testing Scenarios

### Version Selection Testing

1. **Latest Version (Default)**
   - Select multiple shots
   - Verify each shot downloads its latest version
   - Verify different shots can have different latest versions

2. **Specific Version**
   - Select v005 for all shots
   - Verify shots with v005 download successfully
   - Verify shots without v005 are skipped with warning

3. **All Versions**
   - Select one shot
   - Verify all versions are downloaded
   - Verify folder structure is correct

4. **Custom Version**
   - Select multiple shots
   - Set different versions for different shots
   - Verify each shot downloads the selected version

### File Conflict Testing

1. **Skip Existing**
   - Download shot once
   - Download same shot again with "Skip Existing"
   - Verify no files are re-downloaded
   - Verify statistics show skipped files

2. **Compare & Update**
   - Download shot
   - Modify FTP file (newer timestamp)
   - Download again with "Compare & Update"
   - Verify only modified files are downloaded

3. **Overwrite All**
   - Download shot
   - Download again with "Overwrite All"
   - Verify all files are re-downloaded

4. **Keep Both**
   - Download shot
   - Download again with "Keep Both"
   - Verify old files are renamed with timestamp
   - Verify new files are downloaded

## Known Issues & Limitations

1. **Version Detection for Lighting**
   - Lighting versions are extracted from filenames
   - May not work if filename pattern changes

2. **Large File Handling**
   - No resume support for interrupted downloads
   - Consider adding chunked download for large files

3. **Concurrent Downloads**
   - Currently downloads one file at a time
   - Consider adding parallel download option

## Future Enhancements

1. **Download Resume**
   - Support resuming interrupted downloads
   - Track partial downloads

2. **Bandwidth Throttling**
   - Allow users to limit download speed
   - Prevent network congestion

3. **Download Scheduling**
   - Schedule downloads for off-peak hours
   - Automatic retry on failure

4. **Notification System**
   - Email/Slack notifications on completion
   - Alert on errors

5. **Download History**
   - Track all downloads with timestamps
   - Show download history per shot

6. **Batch Operations**
   - Delete multiple tasks at once
   - Retry failed tasks in bulk