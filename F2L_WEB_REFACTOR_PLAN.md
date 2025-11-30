# F2L Web Application - Complete Refactoring Plan
## S3-Only Cloud Sync with Modern Web Stack

**Document Version:** 1.0
**Last Updated:** 2025-01-29
**Target Deployment:** Docker Linux

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Technology Stack](#technology-stack)
3. [Architecture Overview](#architecture-overview)
4. [Database Schema](#database-schema)
5. [Backend Implementation](#backend-implementation)
6. [Frontend Architecture](#frontend-architecture)
7. [Docker Deployment](#docker-deployment)
8. [API Specifications](#api-specifications)
9. [Sample User Journeys](#sample-user-journeys)
10. [Migration Guide](#migration-guide)
11. [Implementation Timeline](#implementation-timeline)

---

## 1. Executive Summary

This document outlines the complete refactoring of the F2L sync tool from a Tkinter desktop application to a modern web-based application with the following goals:

### Primary Objectives
- **Replace Tkinter GUI** with a React-based web dashboard
- **Add S3 support** using boto3 (AWS SDK for Python)
- **Maintain ALL existing features** from the original application
- **Docker-ready deployment** for Linux environments
- **Production-ready** architecture with proper separation of concerns

### Key Features Retained
✅ Multi-endpoint management (FTP/SFTP/S3/Local)
✅ Bidirectional sync with conflict resolution
✅ Folder and file filtering (exact/contains/startswith)
✅ Scheduling with auto-start capability
✅ Multi-session manager
✅ Real-time progress monitoring
✅ Comprehensive logging system
✅ Health monitoring
✅ Dry run/preview mode
✅ Force overwrite option
✅ Scan result caching

### New Capabilities
🆕 S3 integration with multipart uploads
🆕 Web-based UI accessible from any device
🆕 RESTful API for external integrations
🆕 WebSocket for real-time updates
🆕 Docker containerization
🆕 Horizontal scalability
🆕 Multi-user support (optional)

---

## 2. Technology Stack

### Backend Stack
```yaml
Language: Python 3.11+
Web Framework: FastAPI 0.109+
Database: PostgreSQL 15+ (primary) / SQLite 3.x (fallback)
ORM: SQLAlchemy 2.x with Alembic migrations
Task Queue: Celery 5.3+ with Redis 7.x
S3 SDK: boto3 1.34+
Authentication: JWT (PyJWT)
Password Encryption: cryptography (Fernet)
WebSocket: python-socketio with asyncio
ASGI Server: Uvicorn with Gunicorn workers
```

### Frontend Stack
```yaml
Framework: React 18.2+ with TypeScript 5.3+
Build Tool: Vite 5.x
UI Library: Material-UI (MUI) v5 or Ant Design v5
State Management: Zustand 4.x + React Query (TanStack Query)
Forms: React Hook Form + Zod validation
HTTP Client: Axios
WebSocket: Socket.IO client
Charts: Recharts or Chart.js
Routing: React Router v6
Styling: Emotion (CSS-in-JS) or Tailwind CSS
```

### Infrastructure Stack
```yaml
Container: Docker 24.x with multi-stage builds
Orchestration: Docker Compose v2
Reverse Proxy: Nginx 1.25+ (Alpine)
Database: PostgreSQL 15-alpine
Cache/Queue: Redis 7-alpine
Monitoring: Prometheus + Grafana (optional)
Logging: ELK Stack or Loki (optional)
```

---

## 3. Architecture Overview

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        CLIENT TIER (Browser)                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │              React Frontend (TypeScript + MUI)                    │  │
│  │                                                                   │  │
│  │  Components:                                                      │  │
│  │  ├─ Dashboard (Overview & Statistics)                            │  │
│  │  ├─ Endpoints Manager (FTP/SFTP/S3/Local)                       │  │
│  │  ├─ Sessions Manager (Sync Configuration)                       │  │
│  │  ├─ Multi-Session Dashboard (Parallel Executions)              │  │
│  │  ├─ Execution Monitor (Real-time Progress)                     │  │
│  │  ├─ Log Viewer (Filter by Level/Session)                       │  │
│  │  ├─ Settings Page (App Configuration)                          │  │
│  │  └─ Authentication (Login/Logout)                              │  │
│  │                                                                   │  │
│  │  State: Zustand (Global) + React Query (Server State)           │  │
│  │  Real-time: Socket.IO client for live updates                   │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                 │                                         │
│                                 │ HTTPS / WSS                            │
│                                 ▼                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                        WEB TIER (Nginx Proxy)                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │              Nginx Reverse Proxy (Alpine)                         │  │
│  │                                                                   │  │
│  │  Routes:                                                          │  │
│  │  ├─ /api/*        → Backend API (FastAPI)                       │  │
│  │  ├─ /socket.io/*  → WebSocket Server                            │  │
│  │  ├─ /*            → Static Frontend Assets                       │  │
│  │                                                                   │  │
│  │  Features: SSL termination, CORS, Rate limiting, Compression    │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                 │                                         │
│                                 ▼                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                      APPLICATION TIER (FastAPI)                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                FastAPI Backend (Async Python)                     │  │
│  │                                                                   │  │
│  │  API Routes (REST):                                               │  │
│  │  ├─ /api/v1/endpoints      (CRUD for FTP/SFTP/S3/Local)        │  │
│  │  ├─ /api/v1/sessions       (Sync session management)            │  │
│  │  ├─ /api/v1/executions     (Start/Stop/Monitor syncs)          │  │
│  │  ├─ /api/v1/logs           (Query logs with filters)            │  │
│  │  ├─ /api/v1/settings       (App settings CRUD)                  │  │
│  │  └─ /api/v1/auth           (JWT authentication)                 │  │
│  │                                                                   │  │
│  │  WebSocket Namespace:                                             │  │
│  │  ├─ /socket.io/executions  (Real-time progress updates)        │  │
│  │  └─ /socket.io/logs        (Real-time log streaming)           │  │
│  │                                                                   │  │
│  │  Core Modules:                                                    │  │
│  │  ├─ S3Manager (boto3)        → S3 operations                    │  │
│  │  ├─ FTPManager               → FTP operations                    │  │
│  │  ├─ SFTPManager (paramiko)   → SFTP operations                  │  │
│  │  ├─ LocalManager             → Local file operations            │  │
│  │  ├─ SyncEngine               → Orchestration logic              │  │
│  │  ├─ Scheduler                → Cron/interval scheduling         │  │
│  │  └─ CacheManager             → Scan result caching              │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                          │                    │                          │
│                          │                    │                          │
│                          ▼                    ▼                          │
│         ┌─────────────────────────┐  ┌──────────────────────┐          │
│         │   Celery Workers        │  │  Celery Beat         │          │
│         │   (Background Tasks)    │  │  (Scheduler)         │          │
│         │                         │  │                      │          │
│         │  ├─ Sync Tasks          │  │  Triggers scheduled  │          │
│         │  ├─ Scan Tasks          │  │  sync sessions       │          │
│         │  └─ Health Checks       │  │                      │          │
│         └─────────────────────────┘  └──────────────────────┘          │
│                          │                                               │
│                          ▼                                               │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                        DATA TIER (Persistence)                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────────────┐    ┌──────────────────────┐                  │
│  │   PostgreSQL 15      │    │      Redis 7         │                  │
│  │   (Primary DB)       │    │   (Cache + Queue)    │                  │
│  │                      │    │                      │                  │
│  │  Tables:             │    │  Uses:               │                  │
│  │  ├─ endpoints        │    │  ├─ Celery broker    │                  │
│  │  ├─ sync_sessions    │    │  ├─ Celery results   │                  │
│  │  ├─ sync_executions  │    │  ├─ Session cache    │                  │
│  │  ├─ sync_operations  │    │  ├─ Rate limiting    │                  │
│  │  ├─ logs             │    │  └─ Pub/Sub          │                  │
│  │  ├─ scan_cache       │    │                      │                  │
│  │  ├─ users            │    │                      │                  │
│  │  └─ app_settings     │    │                      │                  │
│  │                      │    │                      │                  │
│  │  Volumes: pgdata     │    │  Volumes: redis-data │                  │
│  └──────────────────────┘    └──────────────────────┘                  │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                      STORAGE TIER (Sync Targets)                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │  FTP Server  │  │ SFTP Server  │  │  Amazon S3   │  │ Local FS   │ │
│  │              │  │              │  │  (or MinIO)  │  │            │ │
│  │  Port: 21    │  │  Port: 22    │  │              │  │  /data/*   │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘ │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

#### **React Frontend**
- **Responsibility**: User interface and experience
- **Features**:
  - Dashboard with statistics and charts
  - CRUD operations for endpoints and sessions
  - Real-time monitoring of sync operations
  - Log viewing with filtering
  - Settings management
  - Authentication UI

#### **FastAPI Backend**
- **Responsibility**: Business logic and API
- **Features**:
  - RESTful API endpoints
  - WebSocket server for real-time updates
  - Authentication and authorization
  - Request validation with Pydantic
  - Async request handling

#### **Celery Workers**
- **Responsibility**: Background task execution
- **Features**:
  - Sync task execution
  - Directory scanning
  - Health monitoring
  - Scheduled job execution

#### **PostgreSQL**
- **Responsibility**: Primary data storage
- **Features**:
  - ACID compliance
  - Complex queries and joins
  - Full-text search
  - JSON field support

#### **Redis**
- **Responsibility**: Caching and message broker
- **Features**:
  - Celery task queue
  - Result backend
  - Session caching
  - Rate limiting

#### **Nginx**
- **Responsibility**: Reverse proxy and static file serving
- **Features**:
  - SSL/TLS termination
  - Load balancing
  - Static file serving (React build)
  - WebSocket proxying

---

## 4. Database Schema

See the complete PostgreSQL schema in [Section 3.2 of the original plan](#32-postgresql-schema).

Key tables:
- `endpoints` - FTP/SFTP/S3/Local endpoints
- `sync_sessions` - Sync session configurations
- `sync_executions` - Execution history and status
- `sync_operations` - Individual file operations
- `logs` - Application logs
- `scan_cache` - Directory scan caching
- `app_settings` - Application settings
- `users` - User accounts (optional)

---

## 5. Backend Implementation

### 5.1 Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app entry
│   ├── config.py                  # Settings management
│   ├── dependencies.py            # Dependency injection
│   │
│   ├── api/                       # API routes
│   │   ├── v1/
│   │   │   ├── endpoints.py
│   │   │   ├── sessions.py
│   │   │   ├── executions.py
│   │   │   ├── logs.py
│   │   │   ├── settings.py
│   │   │   └── auth.py
│   │   └── websocket.py           # Socket.IO handlers
│   │
│   ├── core/                      # Core business logic
│   │   ├── s3_manager.py          # boto3 S3 operations
│   │   ├── ftp_manager.py         # FTP operations
│   │   ├── sftp_manager.py        # SFTP operations
│   │   ├── local_manager.py       # Local file operations
│   │   ├── sync_engine.py         # Sync orchestration
│   │   ├── scheduler.py           # Job scheduling
│   │   ├── cache_manager.py       # Caching layer
│   │   └── logger.py              # Logging system
│   │
│   ├── database/                  # Database layer
│   │   ├── models.py              # SQLAlchemy ORM models
│   │   ├── session.py             # DB session management
│   │   └── repositories/          # Data access layer
│   │
│   ├── schemas/                   # Pydantic schemas
│   │   ├── endpoint.py
│   │   ├── session.py
│   │   └── execution.py
│   │
│   ├── tasks/                     # Celery tasks
│   │   ├── celery_app.py
│   │   ├── sync_tasks.py
│   │   └── scheduled_tasks.py
│   │
│   └── utils/                     # Utilities
│       ├── encryption.py
│       ├── validators.py
│       └── helpers.py
│
├── tests/
├── alembic/                       # DB migrations
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

### 5.2 Key Backend Files

#### S3Manager (Complete Implementation)

See the complete boto3-based S3Manager implementation in the previous response.

Key features:
- Multipart uploads/downloads
- Progress tracking
- Pagination for large buckets
- Presigned URLs
- S3-compatible service support
- Connection pooling
- Error handling and retries

---

## 6. Frontend Architecture

### 6.1 Project Structure

```
frontend/
├── public/
│   ├── index.html
│   └── favicon.ico
│
├── src/
│   ├── App.tsx                    # Main app component
│   ├── main.tsx                   # Entry point
│   ├── vite-env.d.ts
│   │
│   ├── components/                # Reusable components
│   │   ├── common/
│   │   │   ├── Button.tsx
│   │   │   ├── Input.tsx
│   │   │   ├── Modal.tsx
│   │   │   ├── Table.tsx
│   │   │   └── Toast.tsx
│   │   │
│   │   ├── layout/
│   │   │   ├── AppLayout.tsx      # Main layout wrapper
│   │   │   ├── Sidebar.tsx        # Navigation sidebar
│   │   │   ├── Header.tsx         # Top header
│   │   │   └── Footer.tsx
│   │   │
│   │   ├── endpoints/
│   │   │   ├── EndpointList.tsx
│   │   │   ├── EndpointForm.tsx
│   │   │   ├── EndpointCard.tsx
│   │   │   └── TestConnection.tsx
│   │   │
│   │   ├── sessions/
│   │   │   ├── SessionList.tsx
│   │   │   ├── SessionForm.tsx
│   │   │   ├── SessionCard.tsx
│   │   │   └── ScheduleConfig.tsx
│   │   │
│   │   ├── executions/
│   │   │   ├── ExecutionMonitor.tsx
│   │   │   ├── ExecutionProgress.tsx
│   │   │   ├── ExecutionLogs.tsx
│   │   │   └── ExecutionStats.tsx
│   │   │
│   │   └── logs/
│   │       ├── LogViewer.tsx
│   │       ├── LogFilter.tsx
│   │       └── LogExport.tsx
│   │
│   ├── pages/                     # Page components
│   │   ├── Dashboard.tsx
│   │   ├── Endpoints.tsx
│   │   ├── Sessions.tsx
│   │   ├── MultiSession.tsx
│   │   ├── Executions.tsx
│   │   ├── Logs.tsx
│   │   ├── Settings.tsx
│   │   └── Login.tsx
│   │
│   ├── services/                  # API services
│   │   ├── api.ts                 # Axios instance
│   │   ├── endpointService.ts
│   │   ├── sessionService.ts
│   │   ├── executionService.ts
│   │   ├── logService.ts
│   │   └── authService.ts
│   │
│   ├── hooks/                     # Custom React hooks
│   │   ├── useEndpoints.ts
│   │   ├── useSessions.ts
│   │   ├── useExecutions.ts
│   │   ├── useRealtime.ts         # Socket.IO hook
│   │   └── useAuth.ts
│   │
│   ├── stores/                    # Zustand stores
│   │   ├── authStore.ts
│   │   ├── uiStore.ts
│   │   └── wsStore.ts
│   │
│   ├── types/                     # TypeScript types
│   │   ├── endpoint.ts
│   │   ├── session.ts
│   │   ├── execution.ts
│   │   └── api.ts
│   │
│   ├── utils/                     # Utility functions
│   │   ├── formatters.ts
│   │   ├── validators.ts
│   │   └── constants.ts
│   │
│   └── styles/                    # Global styles
│       ├── theme.ts               # MUI theme
│       └── global.css
│
├── package.json
├── tsconfig.json
├── vite.config.ts
└── .env.example
```

### 6.2 Key Frontend Components

*(Will provide React component implementations in the next section)*

---

## 7. Docker Deployment

### 7.1 Multi-Stage Dockerfile

```dockerfile
# Stage 1: Build Frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /frontend

# Copy package files
COPY frontend/package*.json ./
RUN npm ci --only=production

# Copy source and build
COPY frontend/ ./
RUN npm run build

# Stage 2: Python Dependencies
FROM python:3.11-slim AS python-builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt ./
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 3: Final Runtime Image
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 f2luser

WORKDIR /app

# Copy Python dependencies from builder
COPY --from=python-builder /root/.local /home/f2luser/.local

# Copy frontend build
COPY --from=frontend-builder /frontend/dist /app/frontend/dist

# Copy backend code
COPY backend/app /app/app
COPY backend/alembic /app/alembic
COPY backend/alembic.ini /app/

# Set environment
ENV PATH=/home/f2luser/.local/bin:$PATH \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

# Create required directories
RUN mkdir -p /app/data /app/logs /app/cache && \
    chown -R f2luser:f2luser /app

USER f2luser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5)"

EXPOSE 8000

# Default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### 7.2 Docker Compose Configuration

```yaml
version: '3.8'

services:
  # PostgreSQL Database
  postgres:
    image: postgres:15-alpine
    container_name: f2l-postgres
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-f2l_sync}
      POSTGRES_USER: ${POSTGRES_USER:-f2luser}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_INITDB_ARGS: "-E UTF8"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-f2luser}"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - f2l-network

  # Redis Cache & Queue
  redis:
    image: redis:7-alpine
    container_name: f2l-redis
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    ports:
      - "${REDIS_PORT:-6379}:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - f2l-network

  # Main API Application
  api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: f2l-api
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      # Database
      DATABASE_URL: postgresql://${POSTGRES_USER:-f2luser}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-f2l_sync}

      # Redis
      REDIS_URL: redis://redis:6379/0

      # Celery
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/1

      # Security
      SECRET_KEY: ${SECRET_KEY}
      JWT_SECRET_KEY: ${JWT_SECRET_KEY}
      ENCRYPTION_KEY: ${ENCRYPTION_KEY}

      # Application
      APP_ENV: ${APP_ENV:-production}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
      WORKERS: ${WORKERS:-4}

      # CORS
      CORS_ORIGINS: ${CORS_ORIGINS:-http://localhost,http://localhost:3000}

    volumes:
      # Sync data
      - sync_data:/app/data
      - ./logs:/app/logs
      - ./cache:/app/cache

      # Optional: Mount host directories for local sync
      # - /path/to/local/sync:/mnt/sync

    ports:
      - "${API_PORT:-8000}:8000"
    restart: unless-stopped
    networks:
      - f2l-network

  # Celery Worker
  celery-worker:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: f2l-celery-worker
    command: celery -A app.tasks.celery_app worker --loglevel=info --concurrency=4 --pool=prefork
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER:-f2luser}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-f2l_sync}
      REDIS_URL: redis://redis:6379/0
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/1
      SECRET_KEY: ${SECRET_KEY}
      ENCRYPTION_KEY: ${ENCRYPTION_KEY}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    volumes:
      - sync_data:/app/data
      - ./logs:/app/logs
      - ./cache:/app/cache
    restart: unless-stopped
    networks:
      - f2l-network

  # Celery Beat (Scheduler)
  celery-beat:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: f2l-celery-beat
    command: celery -A app.tasks.celery_app beat --loglevel=info
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER:-f2luser}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-f2l_sync}
      REDIS_URL: redis://redis:6379/0
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/1
      SECRET_KEY: ${SECRET_KEY}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    restart: unless-stopped
    networks:
      - f2l-network

  # Flower (Celery Monitoring)
  flower:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: f2l-flower
    command: celery -A app.tasks.celery_app flower --port=5555 --basic_auth=${FLOWER_USER:-admin}:${FLOWER_PASSWORD:-admin}
    depends_on:
      - redis
      - celery-worker
    environment:
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/1
    ports:
      - "${FLOWER_PORT:-5555}:5555"
    restart: unless-stopped
    networks:
      - f2l-network

  # Nginx Reverse Proxy
  nginx:
    image: nginx:alpine
    container_name: f2l-nginx
    depends_on:
      - api
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro  # SSL certificates (optional)
    ports:
      - "${HTTP_PORT:-80}:80"
      - "${HTTPS_PORT:-443}:443"
    restart: unless-stopped
    networks:
      - f2l-network

volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local
  sync_data:
    driver: local

networks:
  f2l-network:
    driver: bridge
```

### 7.3 Environment Configuration (.env)

```bash
# Database Configuration
POSTGRES_DB=f2l_sync
POSTGRES_USER=f2luser
POSTGRES_PASSWORD=your_secure_password_here
POSTGRES_PORT=5432

# Redis Configuration
REDIS_PORT=6379

# Security Keys (Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")
SECRET_KEY=your_secret_key_here
JWT_SECRET_KEY=your_jwt_secret_here
ENCRYPTION_KEY=your_encryption_key_here

# Application Settings
APP_ENV=production
LOG_LEVEL=INFO
WORKERS=4

# CORS Settings (comma-separated origins)
CORS_ORIGINS=http://localhost,http://localhost:3000,https://yourdomain.com

# Ports
API_PORT=8000
HTTP_PORT=80
HTTPS_PORT=443
FLOWER_PORT=5555

# Flower Authentication
FLOWER_USER=admin
FLOWER_PASSWORD=secure_flower_password

# AWS S3 (Optional: For default S3 endpoint)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_DEFAULT_REGION=us-east-1
```

---

## 8. API Specifications

### 8.1 Endpoints API

```
BASE URL: /api/v1
```

#### List Endpoints
```http
GET /endpoints

Query Parameters:
  - type: string (optional) - Filter by type: 'ftp', 'sftp', 's3', 'local'
  - status: string (optional) - Filter by status: 'connected', 'disconnected'
  - page: integer (default: 1)
  - limit: integer (default: 50)

Response: 200 OK
{
  "data": [
    {
      "id": "uuid",
      "name": "Production S3",
      "endpoint_type": "s3",
      "s3_bucket": "my-bucket",
      "s3_region": "us-east-1",
      "connection_status": "connected",
      "last_health_check": "2025-01-29T10:00:00Z",
      "created_at": "2025-01-01T00:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total": 5
  }
}
```

#### Create Endpoint
```http
POST /endpoints

Request Body:
{
  "name": "Production S3",
  "endpoint_type": "s3",
  "s3_bucket": "my-bucket",
  "s3_region": "us-east-1",
  "s3_access_key": "AKIAIOSFODNN7EXAMPLE",
  "s3_secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
  "s3_endpoint_url": null,  // For S3-compatible services
  "s3_use_ssl": true
}

Response: 201 Created
{
  "id": "uuid",
  "name": "Production S3",
  "endpoint_type": "s3",
  ...
}
```

#### Test Endpoint Connection
```http
POST /endpoints/{id}/test

Response: 200 OK
{
  "success": true,
  "message": "Successfully connected to bucket 'my-bucket'",
  "latency_ms": 123
}
```

### 8.2 Sessions API

#### Create Sync Session
```http
POST /sessions

Request Body:
{
  "name": "Daily S3 Backup",
  "source_endpoint_id": "uuid",
  "destination_endpoint_id": "uuid",
  "source_path": "/data",
  "destination_path": "backups/daily",
  "sync_direction": "source_to_dest",
  "folder_filter_enabled": true,
  "folder_names": ["images", "documents"],
  "folder_match_mode": "contains",
  "folder_case_sensitive": false,
  "file_pattern_enabled": true,
  "file_patterns": ["*.jpg", "*.pdf"],
  "force_overwrite": false,
  "schedule_enabled": true,
  "schedule_interval": 1,
  "schedule_unit": "days",
  "auto_start_enabled": true
}

Response: 201 Created
{
  "id": "uuid",
  "name": "Daily S3 Backup",
  ...
}
```

#### Start Sync Session
```http
POST /sessions/{id}/start

Request Body (optional):
{
  "dry_run": false,
  "force_overwrite": false
}

Response: 202 Accepted
{
  "execution_id": "uuid",
  "status": "queued",
  "message": "Sync job queued successfully"
}
```

### 8.3 WebSocket Events

#### Connect to Execution Updates
```javascript
// Client-side Socket.IO connection
const socket = io('http://localhost:8000', {
  path: '/socket.io'
});

// Subscribe to execution updates
socket.emit('subscribe_execution', { execution_id: 'uuid' });

// Listen for progress updates
socket.on('execution_progress', (data) => {
  console.log(data);
  /*
  {
    execution_id: "uuid",
    status: "running",
    progress_percentage: 45.5,
    files_synced: 1000,
    total_files: 2200,
    current_file: "/data/images/photo.jpg",
    bytes_transferred: 1024000000
  }
  */
});

// Listen for completion
socket.on('execution_completed', (data) => {
  console.log('Sync completed:', data);
});

// Listen for errors
socket.on('execution_error', (data) => {
  console.error('Sync failed:', data);
});
```

---

## 9. Sample User Journeys

### Journey 1: Setting Up S3 Endpoint and First Sync

**Persona**: DevOps Engineer migrating FTP data to AWS S3

**Steps**:

1. **Access Web Dashboard**
   ```
   Navigate to: https://f2l-sync.yourdomain.com
   Login with credentials
   ```

2. **Add S3 Endpoint**
   - Click "Endpoints" in sidebar
   - Click "+ Add Endpoint" button
   - Fill form:
     - Name: "Production S3"
     - Type: S3
     - Bucket: "company-backups"
     - Region: "us-east-1"
     - Access Key: (IAM credentials)
     - Secret Key: (IAM credentials)
   - Click "Test Connection" → ✓ Success
   - Click "Save"

3. **Add Existing FTP Endpoint**
   - Click "+ Add Endpoint"
   - Fill form:
     - Name: "Legacy FTP Server"
     - Type: FTP
     - Host: "ftp.company.com"
     - Port: 21
     - Username: "ftpuser"
     - Password: "******"
     - Remote Path: "/data"
   - Click "Test Connection" → ✓ Success
   - Click "Save"

4. **Create Sync Session**
   - Click "Sessions" in sidebar
   - Click "+ Create Session"
   - Fill form:
     - Name: "FTP to S3 Migration"
     - Source: "Legacy FTP Server"
     - Source Path: "/data"
     - Destination: "Production S3"
     - Destination Path: "ftp-migration/"
     - Direction: "Source → Destination"
     - Folder Filter: Enabled
       - Folders: "images, documents, reports"
       - Match Mode: "Contains"
     - File Patterns: Enabled
       - Patterns: "*.jpg, *.pdf, *.docx"
   - Click "Save"

5. **Preview Sync (Dry Run)**
   - Click "Preview" button on session card
   - Review list of files to be synced
   - See: "2,456 files (15.3 GB) will be uploaded"
   - Click "Close"

6. **Start Sync**
   - Click "Start Sync" button
   - Monitor real-time progress:
     - Progress bar: 45% complete
     - Files: 1,105 / 2,456
     - Speed: 2.5 MB/s
     - ETA: 15 minutes
   - View live log updates

7. **Verify Completion**
   - Receive notification: "Sync completed successfully"
   - View summary:
     - Files synced: 2,456
     - Bytes transferred: 15.3 GB
     - Duration: 18m 35s
     - Errors: 0

**Expected Outcome**: FTP data successfully migrated to S3 with filtering applied.

---

### Journey 2: Scheduled Bi-Directional Sync

**Persona**: Data Manager maintaining sync between local server and S3

**Steps**:

1. **Create Scheduled Session**
   - Navigate to "Sessions"
   - Click "+ Create Session"
   - Configure:
     - Name: "Hourly Local-S3 Sync"
     - Source: "Local File Server" (/mnt/data)
     - Destination: "Production S3" (daily-sync/)
     - Direction: "Bidirectional"
     - Schedule: Enabled
       - Interval: 1 hour
       - Auto-start on launch: Yes
   - Click "Save"

2. **Monitor Scheduled Runs**
   - View "Multi-Session Dashboard"
   - See session card showing:
     - Status: "Active"
     - Next run: "in 47 minutes"
     - Last run: "13 minutes ago" (Success)
     - Files synced today: 145 files

3. **View Execution History**
   - Click on session card
   - View history table:
     ```
     Time               Status     Files    Bytes       Duration
     12:00 PM          Success    145      1.2 GB      2m 15s
     11:00 AM          Success    98       850 MB      1m 45s
     10:00 AM          Success    112      950 MB      1m 58s
     ```

4. **Pause and Resume**
   - Click "Pause Schedule" button
   - Status changes to "Paused"
   - Click "Resume Schedule" button
   - Status changes to "Active"
   - Next run scheduled

**Expected Outcome**: Automated bidirectional sync running every hour.

---

### Journey 3: Downloading Specific Folders from S3

**Persona**: Developer needing specific datasets

**Steps**:

1. **Create Download-Only Session**
   - Navigate to "Sessions"
   - Click "+ Create Session"
   - Configure:
     - Name: "Download ML Datasets"
     - Source: "Production S3"
     - Source Path: "ml-data/"
     - Destination: "Local File Server"
     - Destination Path: "/mnt/ml-datasets"
     - Direction: "Source → Destination"
     - Folder Filter: Enabled
       - Folders: "training, validation"
       - Match Mode: "Exact"
     - File Patterns: Enabled
       - Patterns: "*.csv, *.parquet"
   - Click "Preview" to see: "1,234 files (45 GB)"
   - Click "Save"

2. **Start One-Time Download**
   - Click "Start Sync" (not scheduled, manual run)
   - Monitor progress with real-time updates

3. **Verify Downloaded Files**
   - Check local directory:
     ```
     /mnt/ml-datasets/
     ├── training/
     │   ├── dataset1.csv
     │   ├── dataset2.parquet
     │   └── ...
     └── validation/
         ├── val1.csv
         └── ...
     ```

**Expected Outcome**: Selective download of only ML dataset files.

---

### Journey 4: Getting Metadata from S3

**Persona**: System Administrator auditing S3 storage

**Steps**:

1. **Browse S3 Endpoint**
   - Navigate to "Endpoints"
   - Click on "Production S3" endpoint
   - Click "Browse Files" button

2. **View Directory Metadata**
   - Navigate to folder: "backups/2025/"
   - View metadata summary:
     ```
     Total Files: 12,456
     Total Size: 156.7 GB
     Last Modified: 2025-01-29
     Storage Class: STANDARD
     ```

3. **View Individual File Metadata**
   - Click on file: "backup-2025-01-29.tar.gz"
   - View details:
     ```
     File Name: backup-2025-01-29.tar.gz
     Size: 2.5 GB
     Last Modified: 2025-01-29 03:00:00 UTC
     ETag: "a1b2c3d4e5f6..."
     Storage Class: STANDARD
     Content-Type: application/gzip
     ```

4. **Generate Presigned URL**
   - Click "Generate Download Link" button
   - Set expiration: 1 hour
   - Copy generated URL:
     ```
     https://company-backups.s3.amazonaws.com/backups/2025/backup-2025-01-29.tar.gz?
     X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=...
     ```
   - Share URL with team member for temporary access

**Expected Outcome**: Metadata retrieved without downloading files, presigned URL generated for secure sharing.

---

## 10. Migration Guide

### 10.1 Migrating from Tkinter SQLite to Web PostgreSQL

**Step 1: Backup Existing Data**
```bash
# Backup SQLite database
cp f2l_sync.db f2l_sync.db.backup

# Export to SQL
sqlite3 f2l_sync.db .dump > f2l_backup.sql
```

**Step 2: Install New System**
```bash
# Clone repository
git clone https://github.com/yourorg/f2l-web.git
cd f2l-web

# Copy environment template
cp .env.example .env

# Edit .env with your settings
nano .env
```

**Step 3: Run Migration Script**
```bash
# Run migration script
python scripts/migrate_from_tkinter.py \
  --sqlite-db /path/to/f2l_sync.db \
  --postgres-url postgresql://user:pass@localhost:5432/f2l_sync
```

**Step 4: Verify Migration**
```bash
# Start Docker stack
docker-compose up -d

# Check logs
docker-compose logs -f api

# Access web UI
open http://localhost
```

**Step 5: Test Functionality**
- Verify endpoints are imported
- Check sessions are configured correctly
- Test connection to endpoints
- Run test sync

### 10.2 Feature Mapping

| Tkinter Feature | Web Equivalent | Notes |
|----------------|----------------|-------|
| Endpoints Tab | Endpoints Page | Full feature parity |
| Sync Operations Tab | Executions Page | Enhanced with real-time updates |
| Local Sync Tab | Sessions Page (Local type) | Unified interface |
| Multi-Session Manager | Multi-Session Dashboard | Enhanced visualization |
| Reports Tab | Logs Page + Dashboard | Better filtering and export |
| Settings Tab | Settings Page | Additional cloud settings |
| System Tray | Browser Notifications | Modern alternative |

---

## 11. Implementation Timeline

### Phase 1: Foundation (Weeks 1-3)

**Week 1: Database & Backend Core**
- ✓ Set up PostgreSQL schema
- ✓ Create Alembic migrations
- ✓ Implement SQLAlchemy models
- ✓ Create repository pattern
- ✓ Write unit tests

**Week 2: Core Managers**
- ✓ Implement S3Manager (boto3)
- ✓ Refactor FTPManager
- ✓ Refactor SFTPManager
- ✓ Implement LocalManager
- ✓ Create SyncEngine orchestrator

**Week 3: API Layer**
- ✓ Set up FastAPI application
- ✓ Implement REST API endpoints
- ✓ Add Pydantic schemas
- ✓ Implement WebSocket handlers
- ✓ Write API tests

**Deliverables**: Working backend API with S3 support

---

### Phase 2: Frontend (Weeks 4-6)

**Week 4: React Setup & Layout**
- ✓ Initialize Vite + React + TypeScript
- ✓ Set up MUI theme
- ✓ Create layout components
- ✓ Implement routing
- ✓ Set up state management (Zustand + React Query)

**Week 5: Core Pages**
- ✓ Dashboard page
- ✓ Endpoints page (CRUD)
- ✓ Sessions page (CRUD)
- ✓ Authentication pages

**Week 6: Advanced Features**
- ✓ Execution monitoring
- ✓ Log viewer
- ✓ Multi-session dashboard
- ✓ Settings page
- ✓ Real-time updates (Socket.IO)

**Deliverables**: Fully functional web UI

---

### Phase 3: Integration & Testing (Weeks 7-8)

**Week 7: Integration**
- ✓ Connect frontend to backend
- ✓ Implement WebSocket communication
- ✓ Add error handling
- ✓ Implement authentication flow
- ✓ Write integration tests

**Week 8: Testing & Polish**
- ✓ End-to-end testing
- ✓ Performance optimization
- ✓ UI/UX improvements
- ✓ Documentation
- ✓ Bug fixes

**Deliverables**: Production-ready application

---

### Phase 4: Deployment & Migration (Weeks 9-10)

**Week 9: Docker & Deployment**
- ✓ Create Dockerfile (multi-stage)
- ✓ Create docker-compose.yml
- ✓ Configure Nginx
- ✓ Set up CI/CD pipeline
- ✓ Deploy to staging

**Week 10: Migration & Launch**
- ✓ Write migration scripts
- ✓ Migrate production data
- ✓ User acceptance testing
- ✓ Documentation
- ✓ Production deployment

**Deliverables**: Live production system

---

## Appendix A: Technology Justifications

### Why React over Vue?

**Advantages:**
- ✅ Larger ecosystem and community
- ✅ Better TypeScript support
- ✅ More third-party libraries
- ✅ Better job market for future maintenance
- ✅ Material-UI has excellent React support

### Why boto3 over rclone?

**Advantages:**
- ✅ Native Python integration (no subprocess)
- ✅ Better error handling and retries
- ✅ Progress tracking built-in
- ✅ Async support with aioboto3
- ✅ More control over S3 operations
- ✅ No external dependencies
- ✅ Better for multipart uploads

### Why FastAPI over Flask?

**Advantages:**
- ✅ Built-in async/await support
- ✅ Automatic API documentation
- ✅ Pydantic validation
- ✅ Better performance
- ✅ Modern Python features
- ✅ WebSocket support out of the box

### Why PostgreSQL over MySQL?

**Advantages:**
- ✅ Better JSON support (JSONB)
- ✅ Array data types
- ✅ Full-text search
- ✅ Better for complex queries
- ✅ ACID compliance
- ✅ Open source with permissive license

---

## Appendix B: Security Considerations

### Password Encryption
- All passwords encrypted using Fernet (symmetric encryption)
- Encryption key stored in environment variable
- Keys rotated periodically

### JWT Authentication
- Access tokens expire after 1 hour
- Refresh tokens expire after 7 days
- Tokens signed with HS256 algorithm
- Secure HTTP-only cookies for web UI

### S3 Credentials
- IAM roles preferred over access keys
- Credentials encrypted at rest
- Never logged or exposed in API responses
- Support for temporary credentials (STS)

### API Security
- Rate limiting (100 requests/minute per IP)
- CORS configured with allowed origins
- Input validation with Pydantic
- SQL injection prevention (SQLAlchemy)
- XSS prevention (React escaping)

---

## Appendix C: Monitoring & Observability

### Application Metrics
- Request latency (p50, p95, p99)
- Error rates by endpoint
- Celery queue depth
- Active sync sessions
- Database connection pool usage

### Business Metrics
- Total bytes transferred per day
- Sync success/failure rates
- Average sync duration
- Most active endpoints
- Storage usage by endpoint

### Logging Strategy
- Structured logging (JSON format)
- Log levels: DEBUG, INFO, WARNING, ERROR
- Centralized logging (optional: ELK or Loki)
- Log rotation and retention policies

### Alerting
- Failed sync sessions
- High error rates
- Database connection failures
- Celery worker failures
- Disk space warnings

---

## Conclusion

This refactoring plan provides a complete roadmap for transforming the F2L sync tool from a Tkinter desktop application to a modern, scalable, cloud-ready web application with S3 support.

**Key Achievements:**
- ✅ Maintains all existing features
- ✅ Adds S3 cloud storage support
- ✅ Modern web-based UI
- ✅ Docker-ready deployment
- ✅ Production-ready architecture
- ✅ Real-time monitoring
- ✅ Horizontal scalability

**Next Steps:**
1. Review and approve this plan
2. Set up development environment
3. Begin Phase 1 implementation
4. Establish CI/CD pipeline
5. Schedule weekly progress reviews

---

**End of Document**
