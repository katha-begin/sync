# Deploy F2L Sync to server with separate Frontend and Backend containers

param(
    [switch]$Setup,
    [switch]$Frontend,
    [switch]$Backend,
    [switch]$All,
    [string]$Environment = "production"
)

# Default to All if no specific component is selected
if (-not $Frontend -and -not $Backend -and -not $Setup) {
    $All = $true
}

$SSH_KEY = "$env:USERPROFILE\.ssh\CaveTeam.pem"
$SSH_USER = "ec2-user"
$SSH_HOST = "10.100.128.193"

Write-Host ""
Write-Host "=== F2L Sync Deployment (Separate Containers) ===" -ForegroundColor Cyan
Write-Host "Environment: $Environment" -ForegroundColor Yellow
Write-Host ""

# Check SSH key
if (-not (Test-Path $SSH_KEY)) {
    Write-Host "ERROR: SSH key not found: $SSH_KEY" -ForegroundColor Red
    exit 1
}

# Setup server (first time only)
if ($Setup) {
    Write-Host "Setting up server..." -ForegroundColor Green
    scp -i $SSH_KEY "server-setup.sh" "${SSH_USER}@${SSH_HOST}:/tmp/"

    $setupCmd = @'
chmod +x /tmp/server-setup.sh
sudo /tmp/server-setup.sh
'@
    ssh -i $SSH_KEY -tt "${SSH_USER}@${SSH_HOST}" $setupCmd

    Write-Host ""
    Write-Host "Setup complete! Log out and back in to server, then run: .\deploy.ps1" -ForegroundColor Green
    Write-Host ""
    exit 0
}

# Check .env exists
if (-not (Test-Path ".env")) {
    Write-Host "ERROR: .env file not found!" -ForegroundColor Red
    Write-Host "Run: .\generate-env.ps1" -ForegroundColor Yellow
    exit 1
}

Write-Host "Found .env file" -ForegroundColor Green

# Determine what to deploy
$deployComponents = @()
if ($All) {
    $deployComponents = @("frontend", "backend", "infrastructure")
    Write-Host "Deploying: All components (Frontend + Backend + Infrastructure)" -ForegroundColor Green
} else {
    if ($Frontend) {
        $deployComponents += "frontend"
        Write-Host "Deploying: Frontend only" -ForegroundColor Green
    }
    if ($Backend) {
        $deployComponents += "backend"
        Write-Host "Deploying: Backend only" -ForegroundColor Green
    }
}

# Create archive
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$archive = "f2l-sync-$timestamp.tar.gz"
Write-Host "Creating deployment archive..." -ForegroundColor Gray

if (Get-Command wsl -ErrorAction SilentlyContinue) {
    # Create different archives based on what's being deployed
    if ($deployComponents -contains "frontend" -and $deployComponents -contains "backend") {
        # Full deployment
        wsl tar --exclude='*.log' --exclude='__pycache__' --exclude='node_modules' --exclude='.git' --exclude='venv' --exclude='logs' --exclude='*.tar.gz' --exclude='frontend/dist' --exclude='backend/tests' -czf $archive .
    } elseif ($deployComponents -contains "frontend") {
        # Frontend only
        wsl tar --exclude='*.log' --exclude='__pycache__' --exclude='node_modules' --exclude='.git' --exclude='venv' --exclude='logs' --exclude='*.tar.gz' --exclude='frontend/dist' -czf $archive frontend/ nginx/ docker-compose.yml .env
    } elseif ($deployComponents -contains "backend") {
        # Backend only
        wsl tar --exclude='*.log' --exclude='__pycache__' --exclude='node_modules' --exclude='.git' --exclude='venv' --exclude='logs' --exclude='*.tar.gz' --exclude='backend/tests' -czf $archive backend/ docker-compose.yml .env
    }
} else {
    Write-Host "ERROR: WSL required. Install WSL first." -ForegroundColor Red
    exit 1
}

# Transfer
Write-Host "Transferring to server..." -ForegroundColor Gray
scp -i $SSH_KEY $archive "${SSH_USER}@${SSH_HOST}:/tmp/"

# Extract and setup
Write-Host "Extracting on server..." -ForegroundColor Gray

$extractCmd = @'
sudo mkdir -p /opt/f2l-sync
sudo chown ec2-user:ec2-user /opt/f2l-sync
cd /opt/f2l-sync
tar -xzf /tmp/ARCHIVE_NAME
chmod 600 .env
mkdir -p logs cache nginx/ssl frontend/dist
rm -f /tmp/ARCHIVE_NAME
echo "Deployment complete"
'@

$extractCmd = $extractCmd.Replace('ARCHIVE_NAME', $archive)
ssh -i $SSH_KEY -tt "${SSH_USER}@${SSH_HOST}" $extractCmd

# Deploy specific components
Write-Host "Deploying components on server..." -ForegroundColor Gray

$deployCmd = @'
cd /opt/f2l-sync

# Stop existing containers
docker-compose down

# Build and start based on deployment type
DEPLOY_COMPONENTS

# Wait for services to be ready
echo "Waiting for services to start..."
sleep 10

# Show status
docker-compose ps
echo "Deployment complete!"
'@

if ($deployComponents -contains "frontend" -and $deployComponents -contains "backend") {
    $deployCmd = $deployCmd.Replace('DEPLOY_COMPONENTS', @'
echo "Building and starting all services..."
docker-compose build
docker-compose up -d
'@)
} elseif ($deployComponents -contains "frontend") {
    $deployCmd = $deployCmd.Replace('DEPLOY_COMPONENTS', @'
echo "Building and starting frontend services..."
docker-compose build frontend nginx
docker-compose up -d frontend nginx postgres redis
'@)
} elseif ($deployComponents -contains "backend") {
    $deployCmd = $deployCmd.Replace('DEPLOY_COMPONENTS', @'
echo "Building and starting backend services..."
docker-compose build backend celery-worker celery-beat flower
docker-compose up -d backend celery-worker celery-beat flower postgres redis nginx
'@)
}

ssh -i $SSH_KEY -tt "${SSH_USER}@${SSH_HOST}" $deployCmd

# Cleanup
Remove-Item $archive -Force

Write-Host ""
Write-Host "=== DEPLOYMENT COMPLETE ===" -ForegroundColor Green
Write-Host ""
Write-Host "Deployed components: $($deployComponents -join ', ')" -ForegroundColor Yellow
Write-Host ""
Write-Host "Access points:" -ForegroundColor White
Write-Host "  • Main Application: http://10.100.128.193:8080" -ForegroundColor Cyan
Write-Host "  • Backend API: http://10.100.128.193:8001" -ForegroundColor Cyan
Write-Host "  • Frontend: http://10.100.128.193:3001" -ForegroundColor Cyan
Write-Host "  • Flower (Celery): http://10.100.128.193:5556" -ForegroundColor Cyan
Write-Host ""
Write-Host "Management commands:" -ForegroundColor White
Write-Host "  • SSH to server: ssh -i $SSH_KEY ${SSH_USER}@${SSH_HOST}" -ForegroundColor Gray
Write-Host "  • View logs: docker-compose logs -f [service]" -ForegroundColor Gray
Write-Host "  • Restart service: docker-compose restart [service]" -ForegroundColor Gray
Write-Host "  • Stop all: docker-compose down" -ForegroundColor Gray
Write-Host ""
