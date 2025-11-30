# F2L Sync Deployment Guide

This guide covers deployment of the F2L Sync application with **separate frontend and backend containers**.

## Architecture Overview

The application is now split into separate containers:

- **Frontend**: React application served by Nginx (Port 3001)
- **Backend**: FastAPI application (Port 8001)
- **Nginx**: Reverse proxy routing traffic (Port 8080)
- **PostgreSQL**: Database (Port 5432)
- **Redis**: Cache and message broker (Port 6379)
- **Celery Worker**: Background task processing
- **Celery Beat**: Task scheduler
- **Flower**: Celery monitoring (Port 5556)

## Quick Start

### Local Development

1. **Start all services**:
   ```powershell
   .\scripts\dev.ps1 start -Build
   ```

2. **Access the application**:
   - Frontend: http://localhost:3001
   - Backend API: http://localhost:8001
   - API Docs: http://localhost:8001/docs
   - Flower: http://localhost:5556

3. **View logs**:
   ```powershell
   .\scripts\dev.ps1 logs -Follow
   ```

4. **Stop services**:
   ```powershell
   .\scripts\dev.ps1 stop
   ```

### Production Deployment

1. **Setup server** (first time only):
   ```powershell
   .\scripts\deploy-remote.ps1 -Setup
   ```

2. **Deploy all components**:
   ```powershell
   .\scripts\deploy-remote.ps1 -Component all
   ```

3. **Deploy specific components**:
   ```powershell
   # Frontend only
   .\scripts\deploy-remote.ps1 -Component frontend
   
   # Backend only
   .\scripts\deploy-remote.ps1 -Component backend
   ```

## Development Commands

### Local Development Script (`.\scripts\dev.ps1`)

```powershell
# Start all services with build
.\scripts\dev.ps1 start -Build

# Start specific component
.\scripts\dev.ps1 start -Component frontend
.\scripts\dev.ps1 start -Component backend
.\scripts\dev.ps1 start -Component infrastructure

# View logs
.\scripts\dev.ps1 logs -Component backend -Follow

# Restart services
.\scripts\dev.ps1 restart -Component frontend

# Build services
.\scripts\dev.ps1 build -Component all

# Clean environment
.\scripts\dev.ps1 clean

# Check status
.\scripts\dev.ps1 status
```

### Manual Docker Compose Commands

```bash
# Development environment
docker-compose -f docker-compose.dev.yml up -d
docker-compose -f docker-compose.dev.yml logs -f
docker-compose -f docker-compose.dev.yml down

# Production environment
docker-compose up -d
docker-compose logs -f
docker-compose down
```

## Remote Deployment

### Enhanced Deployment Script (`.\scripts\deploy-remote.ps1`)

```powershell
# Full deployment
.\scripts\deploy-remote.ps1 -Component all -Environment production

# Component-specific deployment
.\scripts\deploy-remote.ps1 -Component frontend
.\scripts\deploy-remote.ps1 -Component backend
.\scripts\deploy-remote.ps1 -Component infrastructure

# Different environments
.\scripts\deploy-remote.ps1 -Environment staging
.\scripts\deploy-remote.ps1 -Environment development

# Management operations
.\scripts\deploy-remote.ps1 -Status
.\scripts\deploy-remote.ps1 -Logs
.\scripts\deploy-remote.ps1 -Restart -Component backend

# Dry run (test without changes)
.\scripts\deploy-remote.ps1 -DryRun -Component all
```

### Legacy Deployment Script (`.\deploy.ps1`)

```powershell
# Setup server (first time)
.\deploy.ps1 -Setup

# Deploy all components
.\deploy.ps1

# Deploy specific components
.\deploy.ps1 -Frontend
.\deploy.ps1 -Backend
```

## Configuration

### Environment Variables

Create `.env` file using the generator:
```powershell
.\generate-env.ps1
```

Key variables for separate containers:
```env
# Frontend
FRONTEND_PORT=3001
VITE_API_BASE_URL=http://localhost:8001

# Backend
API_PORT=8001
CORS_ORIGINS=http://localhost:3001,http://frontend:3000

# Infrastructure
HTTP_PORT=8080
POSTGRES_PORT=5432
REDIS_PORT=6379
FLOWER_PORT=5556
```

### Docker Compose Files

- `docker-compose.yml`: Production configuration
- `docker-compose.dev.yml`: Development configuration with hot reload

## Container Details

### Frontend Container

**Dockerfile**: `frontend/Dockerfile`
- **Base**: `node:18-alpine` → `nginx:alpine`
- **Build**: Multi-stage build with Vite
- **Port**: 3001
- **Features**: Gzip compression, security headers, client-side routing

**Development**: `frontend/Dockerfile.dev`
- **Base**: `node:18-alpine`
- **Features**: Hot reload, source mounting

### Backend Container

**Dockerfile**: `backend/Dockerfile`
- **Base**: `python:3.11-slim`
- **Features**: Multi-stage build, non-root user, health checks
- **Port**: 8001
- **Commands**: API, Celery Worker, Celery Beat, Flower

### Nginx Reverse Proxy

Routes traffic to appropriate containers:
- `/api/*` → Backend (port 8001)
- `/socket.io/*` → Backend WebSocket
- `/*` → Frontend (port 3001)

## Monitoring and Logs

### Service Status
```bash
# Local
docker-compose -f docker-compose.dev.yml ps

# Remote
ssh -i ~/.ssh/CaveTeam.pem ec2-user@10.100.128.193 "cd /opt/f2l-sync && docker-compose ps"
```

### Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f celery-worker
```

### Health Checks

All containers include health checks:
- **Frontend**: HTTP check on port 3001
- **Backend**: HTTP check on `/health` endpoint
- **PostgreSQL**: `pg_isready` check
- **Redis**: `redis-cli ping` check

## Troubleshooting

### Common Issues

1. **Port conflicts**:
   ```bash
   # Check what's using ports
   netstat -tulpn | grep :3001
   netstat -tulpn | grep :8001
   ```

2. **Container build failures**:
   ```bash
   # Rebuild without cache
   docker-compose build --no-cache
   ```

3. **Database connection issues**:
   ```bash
   # Check PostgreSQL logs
   docker-compose logs postgres
   
   # Test connection
   docker-compose exec postgres psql -U f2luser -d f2l_sync
   ```

4. **Frontend not loading**:
   ```bash
   # Check nginx configuration
   docker-compose exec nginx nginx -t
   
   # Check frontend build
   docker-compose logs frontend
   ```

### Reset Environment

```bash
# Stop all services
docker-compose down

# Remove volumes (data will be lost)
docker-compose down -v

# Remove images
docker-compose down --rmi all

# Clean system
docker system prune -a
```

## Security Considerations

### Production Security

1. **Environment Variables**: Never commit `.env` files
2. **SSL/TLS**: Configure SSL certificates in `nginx/ssl/`
3. **Firewall**: Restrict access to necessary ports only
4. **Updates**: Regularly update base images
5. **Secrets**: Use Docker secrets for sensitive data

### Network Security

- All containers communicate through internal Docker network
- Only necessary ports are exposed to host
- Nginx acts as reverse proxy and security layer

## Performance Optimization

### Production Optimizations

1. **Frontend**:
   - Static asset caching (1 year)
   - Gzip compression
   - Minified builds

2. **Backend**:
   - Multiple Uvicorn workers
   - Connection pooling
   - Redis caching

3. **Database**:
   - Connection pooling
   - Proper indexing
   - Regular maintenance

### Scaling

- **Horizontal**: Add more backend/worker containers
- **Vertical**: Increase container resource limits
- **Load Balancing**: Use multiple nginx instances

## Backup and Recovery

### Database Backup
```bash
# Create backup
docker-compose exec postgres pg_dump -U f2luser f2l_sync > backup.sql

# Restore backup
docker-compose exec -T postgres psql -U f2luser f2l_sync < backup.sql
```

### Volume Backup
```bash
# Backup volumes
docker run --rm -v f2l-web-refactor_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_backup.tar.gz -C /data .
```

## Support

For issues and questions:
1. Check logs: `docker-compose logs -f`
2. Verify configuration: `docker-compose config`
3. Test connectivity: `docker-compose exec backend curl http://localhost:8001/health`
4. Review this documentation
