# Shot Download Feature - Deployment Guide

This guide covers deploying the new Shot Download feature to the server for integration testing.

## 📋 Pre-Deployment Checklist

### ✅ What's Been Implemented:

**Backend (Phase 1 & 2):**
- ✅ Path utilities (`shot_path_utils.py`)
- ✅ Database models (4 new tables)
- ✅ Database migration (`002_add_shot_download_tables.py`)
- ✅ Structure scanner service (`shot_structure_scanner.py`)
- ✅ Comparison service (`shot_comparison_service.py`)
- ✅ Download service (`shot_download_service.py`)
- ✅ REST API endpoints (`api/v1/shots.py` - 10 endpoints)

**Frontend (Phase 3):**
- ✅ TypeScript types (`types/shot.ts`)
- ✅ API service (`services/shotService.ts`)
- ✅ Shot Download page (`pages/ShotDownload.tsx`)
- ✅ Download Tasks page (`pages/DownloadTasks.tsx`)
- ✅ Comparison table component (`components/shots/ShotComparisonTable.tsx`)
- ✅ Create task dialog (`components/shots/CreateTaskDialog.tsx`)
- ✅ Task details dialog (`components/shots/TaskDetailsDialog.tsx`)
- ✅ Routes and navigation added

---

## 🚀 Deployment Steps

### Step 1: Run Database Migration (REQUIRED)

The new feature requires 4 new database tables. You MUST run the migration before deploying.

**Option A: Run migration on server after deployment**
```bash
# SSH to server
ssh -i ~/.ssh/CaveTeam.pem ec2-user@10.100.128.193

# Navigate to deployment directory
cd /opt/f2l-sync

# Run migration inside backend container
docker-compose exec backend alembic upgrade head

# Verify migration
docker-compose exec backend alembic current
```

**Option B: Run migration locally first (if testing locally)**
```powershell
# From f2l-web-refactor/backend directory
cd backend
alembic upgrade head
alembic current
```

---

### Step 2: Deploy to Server

**Option 1: Deploy All Components (Recommended for first deployment)**
```powershell
# From f2l-web-refactor directory
.\scripts\deploy-remote.ps1 -Component all -Build
```

**Option 2: Deploy Backend Only (if frontend unchanged)**
```powershell
.\scripts\deploy-remote.ps1 -Component backend -Build
```

**Option 3: Deploy Frontend Only (if backend unchanged)**
```powershell
.\scripts\deploy-remote.ps1 -Component frontend -Build
```

---

### Step 3: Verify Deployment

**Check service status:**
```bash
ssh -i ~/.ssh/CaveTeam.pem ec2-user@10.100.128.193 "cd /opt/f2l-sync && docker-compose ps"
```

**Check backend logs:**
```bash
ssh -i ~/.ssh/CaveTeam.pem ec2-user@10.100.128.193 "cd /opt/f2l-sync && docker-compose logs -f backend"
```

**Check frontend logs:**
```bash
ssh -i ~/.ssh/CaveTeam.pem ec2-user@10.100.128.193 "cd /opt/f2l-sync && docker-compose logs -f frontend"
```

---

### Step 4: Test API Endpoints

**Access API documentation:**
- URL: `http://10.100.128.193:8001/docs`
- Look for new `/api/v1/shots/*` endpoints

**Test endpoints manually:**
```bash
# Get shot structure (replace {endpoint_id} with actual UUID)
curl http://10.100.128.193:8001/api/v1/shots/structure/{endpoint_id}

# Scan structure
curl -X POST http://10.100.128.193:8001/api/v1/shots/structure/{endpoint_id}/scan

# List tasks
curl http://10.100.128.193:8001/api/v1/shots/tasks
```

---

### Step 5: Test Frontend

**Access application:**
- Main URL: `http://10.100.128.193:8080`
- Direct Frontend: `http://10.100.128.193:3001`
- Direct Backend: `http://10.100.128.193:8001`

**Test user flow:**
1. Navigate to "Shot Download" in sidebar
2. Select an endpoint
3. Click "Scan Structure"
4. Filter episodes/sequences/shots
5. Click "Compare Shots"
6. Review comparison results
7. Click "Create Download Task"
8. Navigate to "Download Tasks"
9. View task details
10. Execute task

---

## 🔍 Troubleshooting

### Issue: Migration fails

**Solution:**
```bash
# Check current migration status
docker-compose exec backend alembic current

# Check migration history
docker-compose exec backend alembic history

# If stuck, check database directly
docker-compose exec postgres psql -U f2luser -d f2l_sync -c "\dt"
```

### Issue: API endpoints not found (404)

**Solution:**
```bash
# Check if shots router is registered
docker-compose exec backend python -c "from app.api.v1 import api_router; print(api_router.routes)"

# Restart backend
docker-compose restart backend
```

### Issue: Frontend shows old version

**Solution:**
```bash
# Clear browser cache (Ctrl+Shift+R)
# Or rebuild frontend without cache
docker-compose build --no-cache frontend
docker-compose up -d frontend
```

### Issue: Database connection errors

**Solution:**
```bash
# Check PostgreSQL status
docker-compose ps postgres

# Check database logs
docker-compose logs postgres

# Test connection
docker-compose exec postgres psql -U f2luser -d f2l_sync -c "SELECT 1"
```

---

## 📊 Database Schema

The migration creates 4 new tables:

1. **shot_structure_cache** - Stores Episodes/Sequences/Shots structure
2. **shot_cache_metadata** - Tracks cache validity (24-hour TTL)
3. **shot_download_tasks** - Download task records
4. **shot_download_items** - Individual shot-department items per task

---

## 🔄 Rollback Plan

If deployment fails, rollback:

```bash
# SSH to server
ssh -i ~/.ssh/CaveTeam.pem ec2-user@10.100.128.193

cd /opt/f2l-sync

# Rollback migration
docker-compose exec backend alembic downgrade -1

# Restore previous version
git checkout <previous-commit>
docker-compose down
docker-compose up -d --build
```

---

## ✅ Post-Deployment Verification

- [ ] Database migration completed successfully
- [ ] All containers running (backend, frontend, postgres, redis, nginx)
- [ ] API docs show new `/api/v1/shots/*` endpoints
- [ ] Frontend shows "Shot Download" and "Download Tasks" in sidebar
- [ ] Can scan structure for an endpoint
- [ ] Can compare shots
- [ ] Can create download task
- [ ] Can view task details
- [ ] Can execute task

---

## 📝 Notes

- **Cache TTL**: Structure cache expires after 24 hours
- **Parallel Scanning**: Disabled by default (can be enabled in settings)
- **FTP Connections**: Uses existing FTPManager with connection pooling
- **File Transfers**: Reuses existing SyncEngine for downloads
- **Progress Tracking**: Real-time updates via polling (5s for tasks, 2s for running tasks)

---

## 🆘 Support

If issues occur:
1. Check logs: `docker-compose logs -f backend`
2. Check API docs: `http://10.100.128.193:8001/docs`
3. Check database: `docker-compose exec postgres psql -U f2luser -d f2l_sync`
4. Review this guide

