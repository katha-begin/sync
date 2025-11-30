# Filtering Flow Diagram

## Two-Stage Filtering Process

```
┌─────────────────────────────────────────────────────────────────────┐
│                         SYNC SESSION START                          │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    LOAD FILTER CONFIGURATION                        │
│                                                                     │
│  • Include Directories: */2024/*                                    │
│  • Exclude Directories: cache/*, temp/*                             │
│  • Include Files: *.pdf, *.xlsx                                     │
│  • Exclude Files: *.tmp, *.log                                      │
│  • Path Mode: Maintain Full Path                                    │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  STAGE 1: DIRECTORY FILTERING                       │
│                                                                     │
│  1. Scan source directory tree                                      │
│  2. For each directory:                                             │
│     a. Check against INCLUDE patterns                               │
│     b. Check against EXCLUDE patterns                               │
│     c. Mark as MATCHED or FILTERED                                  │
│                                                                     │
│  Example:                                                           │
│  /data/documents/reports/2024/  ✓ MATCHED (*/2024/*)               │
│  /data/documents/reports/2023/  ✗ FILTERED (not matching)          │
│  /data/cache/                   ✗ FILTERED (cache/*)               │
│  /data/temp/                    ✗ FILTERED (temp/*)                │
│                                                                     │
│  Statistics:                                                        │
│  • Directories Scanned: 45                                          │
│  • Directories Matched: 12                                          │
│  • Directories Filtered: 33                                         │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   STAGE 2: FILE FILTERING                           │
│                                                                     │
│  1. Scan files ONLY in matched directories                          │
│  2. For each file:                                                  │
│     a. Check against INCLUDE patterns                               │
│     b. Check against EXCLUDE patterns                               │
│     c. Mark as MATCHED or FILTERED                                  │
│                                                                     │
│  Example (in /data/documents/reports/2024/):                        │
│  report.pdf      ✓ MATCHED (*.pdf)                                  │
│  data.xlsx       ✓ MATCHED (*.xlsx)                                 │
│  notes.txt       ✗ FILTERED (not matching *.pdf or *.xlsx)         │
│  debug.log       ✗ FILTERED (*.log excluded)                        │
│  temp.tmp        ✗ FILTERED (*.tmp excluded)                        │
│                                                                     │
│  Statistics:                                                        │
│  • Files Scanned: 234                                               │
│  • Files Matched: 67                                                │
│  • Files Filtered: 167                                              │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 STAGE 3: PATH RECONSTRUCTION                        │
│                                                                     │
│  For each matched file, construct destination path:                │
│                                                                     │
│  MODE A: MAINTAIN FULL PATH (Default)                              │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Source:      /data/documents/reports/2024/report.pdf        │   │
│  │ Source Root: /data/                                         │   │
│  │ Relative:    documents/reports/2024/report.pdf              │   │
│  │ Dest Root:   /backup/data/                                  │   │
│  │ Destination: /backup/data/documents/reports/2024/report.pdf │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  MODE B: FLATTEN STRUCTURE                                          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Source:      /data/documents/reports/2024/report.pdf        │   │
│  │ Filename:    report.pdf                                     │   │
│  │ Dest Root:   /backup/data/                                  │   │
│  │ Destination: /backup/data/report.pdf                        │   │
│  │                                                             │   │
│  │ If conflict exists:                                         │   │
│  │ Destination: /backup/data/report_1.pdf                      │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    STAGE 4: CONFLICT DETECTION                      │
│                                                                     │
│  For each file, check if destination already exists:               │
│                                                                     │
│  IF destination exists AND modified since last sync:               │
│    ┌─────────────────────────────────────────────────────────┐     │
│    │ CONFLICT DETECTED                                       │     │
│    │                                                         │     │
│    │ Apply resolution strategy:                             │     │
│    │ • newer_wins    → Compare modification times           │     │
│    │ • source_wins   → Always use source file               │     │
│    │ • dest_wins     → Keep destination file                │     │
│    │ • skip          → Skip this file                       │     │
│    │ • ask           → Mark for manual resolution           │     │
│    │                                                         │     │
│    │ If backup_before_overwrite = true:                     │     │
│    │   Create backup: file.pdf.backup.20240115_143022       │     │
│    └─────────────────────────────────────────────────────────┘     │
│                                                                     │
│  ELSE:                                                              │
│    Proceed to sync                                                  │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      STAGE 5: FILE TRANSFER                         │
│                                                                     │
│  For each file to sync:                                             │
│  1. Create intermediate directories (if maintain path mode)         │
│  2. Transfer file from source to destination                        │
│  3. Preserve timestamps (if enabled)                                │
│  4. Verify checksum (if enabled)                                    │
│  5. Record operation in database                                    │
│                                                                     │
│  Progress:                                                          │
│  [████████████████████████████████████░░░░░░] 67/67 files          │
│  Current: /data/documents/reports/2024/report.pdf                   │
│  Status: Transferring... 2.5 MB / 5.0 MB (50%)                     │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         SYNC COMPLETE                               │
│                                                                     │
│  Summary:                                                           │
│  • Directories Scanned: 45                                          │
│  • Directories Matched: 12                                          │
│  • Files Scanned: 234                                               │
│  • Files Matched: 67                                                │
│  • Files Transferred: 65                                            │
│  • Files Skipped: 2 (conflicts)                                     │
│  • Files Failed: 0                                                  │
│  • Total Size: 1.2 GB                                               │
│  • Duration: 5m 32s                                                 │
└─────────────────────────────────────────────────────────────────────┘
```

## Example Scenarios

### Scenario 1: Sync Only 2024 Reports (Maintain Path)

**Configuration**:
```yaml
Source: /data/
Destination: /backup/data/
Include Directories: */2024/*
Include Files: *.pdf, *.xlsx
Path Mode: Maintain Full Path
```

**Flow**:
```
STAGE 1: Directory Filtering
├─ /data/documents/reports/2024/  ✓ MATCHED (*/2024/*)
├─ /data/documents/reports/2023/  ✗ FILTERED
├─ /data/images/2024/              ✓ MATCHED (*/2024/*)
└─ /data/cache/                    ✗ FILTERED

STAGE 2: File Filtering (in matched directories)
├─ /data/documents/reports/2024/report.pdf   ✓ MATCHED (*.pdf)
├─ /data/documents/reports/2024/data.xlsx    ✓ MATCHED (*.xlsx)
├─ /data/documents/reports/2024/notes.txt    ✗ FILTERED
├─ /data/images/2024/photo.jpg               ✗ FILTERED
└─ /data/images/2024/manual.pdf              ✓ MATCHED (*.pdf)

STAGE 3: Path Reconstruction (Maintain Full Path)
├─ report.pdf  → /backup/data/documents/reports/2024/report.pdf
├─ data.xlsx   → /backup/data/documents/reports/2024/data.xlsx
└─ manual.pdf  → /backup/data/images/2024/manual.pdf

STAGE 4: Conflict Detection
├─ report.pdf  → No conflict, proceed
├─ data.xlsx   → No conflict, proceed
└─ manual.pdf  → No conflict, proceed

STAGE 5: File Transfer
├─ Transfer report.pdf  ✓ Success
├─ Transfer data.xlsx   ✓ Success
└─ Transfer manual.pdf  ✓ Success

RESULT: 3 files transferred
```

---

### Scenario 2: Sync All PDFs (Flatten Structure)

**Configuration**:
```yaml
Source: /data/
Destination: /backup/data/
Include Files: *.pdf
Path Mode: Flatten Structure
```

**Flow**:
```
STAGE 1: Directory Filtering
├─ No directory filters, all directories matched
└─ All directories proceed to Stage 2

STAGE 2: File Filtering (in all directories)
├─ /data/documents/reports/2024/report.pdf   ✓ MATCHED (*.pdf)
├─ /data/documents/reports/2024/notes.txt    ✗ FILTERED
├─ /data/images/manual.pdf                   ✓ MATCHED (*.pdf)
└─ /data/cache/temp.txt                      ✗ FILTERED

STAGE 3: Path Reconstruction (Flatten Structure)
├─ report.pdf  → /backup/data/report.pdf
└─ manual.pdf  → /backup/data/manual.pdf

STAGE 4: Conflict Detection
├─ report.pdf  → No conflict, proceed
└─ manual.pdf  → No conflict, proceed

STAGE 5: File Transfer
├─ Transfer report.pdf  ✓ Success
└─ Transfer manual.pdf  ✓ Success

RESULT: 2 files transferred
```

---

### Scenario 3: Exclude Cache and Temp

**Configuration**:
```yaml
Source: /data/
Destination: /backup/data/
Exclude Directories: cache/*, temp/*, */tmp/*
Include Files: *
Path Mode: Maintain Full Path
```

**Flow**:
```
STAGE 1: Directory Filtering
├─ /data/documents/                ✓ MATCHED
├─ /data/documents/tmp/            ✗ FILTERED (*/tmp/*)
├─ /data/cache/                    ✗ FILTERED (cache/*)
└─ /data/temp/                     ✗ FILTERED (temp/*)

STAGE 2: File Filtering (in matched directories)
├─ /data/documents/report.pdf      ✓ MATCHED (*)
└─ /data/documents/notes.txt       ✓ MATCHED (*)

STAGE 3: Path Reconstruction (Maintain Full Path)
├─ report.pdf  → /backup/data/documents/report.pdf
└─ notes.txt   → /backup/data/documents/notes.txt

STAGE 4: Conflict Detection
├─ report.pdf  → No conflict, proceed
└─ notes.txt   → No conflict, proceed

STAGE 5: File Transfer
├─ Transfer report.pdf  ✓ Success
└─ Transfer notes.txt   ✓ Success

RESULT: 2 files transferred
```

## Filter Pattern Syntax

### Wildcard Patterns

| Pattern | Matches | Example |
|---------|---------|---------|
| `*` | Any characters | `*.pdf` matches `report.pdf`, `data.pdf` |
| `documents/*` | All subdirectories under documents | Matches `documents/reports/`, `documents/images/` |
| `*/2024/*` | Any path containing 2024 | Matches `/data/reports/2024/`, `/images/2024/` |
| `report_*` | Files starting with report_ | Matches `report_2024.pdf`, `report_final.xlsx` |
| `*.{pdf,txt}` | Multiple extensions (if supported) | Matches `file.pdf`, `file.txt` |

### Exact Patterns

| Pattern | Matches | Example |
|---------|---------|---------|
| `/data/documents/` | Exact path only | Only matches this exact directory |
| `report.pdf` | Exact filename only | Only matches this exact file |
| `/data/documents/report.pdf` | Exact full path | Only matches this exact file path |

### Combining Patterns

**Multiple Include Patterns** (OR logic):
```
Include Files: *.pdf, *.txt, *.xlsx
→ Matches files ending with .pdf OR .txt OR .xlsx
```

**Include + Exclude Patterns** (AND NOT logic):
```
Include Files: *
Exclude Files: *.tmp, *.log
→ Matches all files EXCEPT those ending with .tmp or .log
```

**Directory + File Patterns** (AND logic):
```
Include Directories: */2024/*
Include Files: *.pdf
→ Matches .pdf files ONLY in directories containing 2024
```

