# F2L Sync - Deployment Guide

Deploy F2L Sync to your server in 3 simple steps.

## Quick Start

```powershell
# 1. Generate .env file
.\generate-env.ps1

# 2. Deploy to server
.\deploy.ps1

# 3. SSH and start
ssh -i %USERPROFILE%\.ssh\CaveTeam.pem ec2-user@10.100.128.193
cd /opt/f2l-sync
docker-compose up -d
```

**Done!** Access at: http://10.100.128.193:8080

---

## Detailed Steps

### Step 1: Generate .env File

```powershell
.\generate-env.ps1
```

This will:
- Prompt for PostgreSQL password (or auto-generate)
- Prompt for Flower password (or auto-generate)
- Generate secure encryption keys
- Create `.env` file

**Save the displayed passwords!**

### Step 2: Deploy to Server

```powershell
.\deploy.ps1
```

This will:
- Check `.env` file exists
- Create archive of project files
- Transfer to server via SSH
- Extract to `/opt/f2l-sync`

### Step 3: Start Services

SSH to server:
```bash
ssh -i %USERPROFILE%\.ssh\CaveTeam.pem ec2-user@10.100.128.193
```

Start Docker containers:
```bash
cd /opt/f2l-sync
docker-compose up -d
```

Check status:
```bash
docker-compose ps
docker-compose logs -f
```

---

## First Time Setup

If this is your first deployment, setup the server first:

```powershell
.\deploy.ps1 -Setup
```

This installs:
- Docker and Docker Compose
- Python 3.11
- Opens firewall ports (8080, 8443, 5555)

**Important:** After setup, log out and log back in to the server.

---

## Access Your Application

- **Web UI**: http://10.100.128.193:8080
- **API Docs**: http://10.100.128.193:8080/api/docs
- **Flower Monitoring**: http://10.100.128.193:5555
  - Username: `admin`
  - Password: From your `.env` file

---

## Configuration

### Server Details
- **Host**: 10.100.128.193
- **Domain**: lightingbolt.com (internal VPC)
- **SSH Key**: `%USERPROFILE%\.ssh\CaveTeam.pem`
- **User**: ec2-user
- **Deploy Path**: /opt/f2l-sync

### Ports
- **8080** - HTTP (Web UI)
- **8443** - HTTPS
- **5555** - Flower (Celery monitoring)
- **8000** - API (internal)

---

## Troubleshooting

### .env File Not Found

```powershell
# Check if .env exists
Test-Path .env

# If not, generate it
.\generate-env.ps1
```

### Cannot Connect to Server

Check SSH key path:
```powershell
Test-Path $env:USERPROFILE\.ssh\CaveTeam.pem
```

### Buildx Error

If you get "compose build requires buildx 0.17 or later":

SSH to server and install Buildx:
```bash
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -L "https://github.com/docker/buildx/releases/download/v0.17.1/buildx-v0.17.1.linux-amd64" -o /usr/local/lib/docker/cli-plugins/docker-buildx
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-buildx
```

Then rebuild:
```bash
cd /opt/f2l-sync
docker-compose up -d --build
```

### Services Won't Start

SSH to server and check logs:
```bash
cd /opt/f2l-sync
docker-compose logs
```

Common issues:
- Ports already in use
- Docker not running
- Permission issues

### Update .env File

Edit `.env` on Windows, then redeploy:
```powershell
notepad .env
.\deploy.ps1
```

Then restart services on server:
```bash
docker-compose restart
```

---

## Project Structure

```
f2l-web-refactor/
├── generate-env.ps1      # Generate .env file
├── deploy.ps1            # Deploy to server
├── server-setup.sh       # Server setup script
├── docker-compose.yml    # Docker services
├── backend/              # FastAPI application
├── frontend/             # React application
└── nginx/                # Nginx config
```

---

## Update Deployment

To update after code changes:

```powershell
# Just redeploy
.\deploy.ps1
```

Then restart on server:
```bash
cd /opt/f2l-sync
docker-compose down
docker-compose up -d --build
```

---

## Technology Stack

**Backend:**
- FastAPI (Python 3.11)
- PostgreSQL 15
- Celery + Redis
- boto3 for S3

**Frontend:**
- React 18 + TypeScript
- Material-UI (MUI)
- Vite

**Infrastructure:**
- Docker + Docker Compose
- Nginx reverse proxy
- Amazon Linux 2

---

## Support

For issues or questions:
1. Check logs: `docker-compose logs`
2. Check service status: `docker-compose ps`
3. Review this README

---

**That's it!** Simple deployment with just 2 scripts and 3 steps.
