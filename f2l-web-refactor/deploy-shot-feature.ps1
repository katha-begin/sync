# Quick Deployment Script for Shot Download Feature
# This script deploys the shot download feature and runs the database migration

param(
    [Parameter(Mandatory=$false)]
    [string]$SSHKey = "$env:USERPROFILE\.ssh\CaveTeam.pem",
    
    [Parameter(Mandatory=$false)]
    [string]$SSHUser = "ec2-user",
    
    [Parameter(Mandatory=$false)]
    [string]$SSHHost = "10.100.128.193",
    
    [switch]$SkipMigration,
    [switch]$BackendOnly,
    [switch]$FrontendOnly
)

$ErrorActionPreference = "Stop"

# Colors
function Write-Step { param([string]$Message) Write-Host "[*] $Message" -ForegroundColor Yellow }
function Write-Success { param([string]$Message) Write-Host "[+] $Message" -ForegroundColor Green }
function Write-Error { param([string]$Message) Write-Host "[-] $Message" -ForegroundColor Red }
function Write-Header { param([string]$Title) Write-Host "`n=== $Title ===`n" -ForegroundColor Cyan }

Write-Header "Shot Download Feature Deployment"

# Step 1: Validate prerequisites
Write-Step "Checking prerequisites..."

if (-not (Test-Path $SSHKey)) {
    Write-Error "SSH key not found: $SSHKey"
    exit 1
}

if (-not (Test-Path ".env")) {
    Write-Error ".env file not found! Run: .\generate-env.ps1"
    exit 1
}

Write-Success "Prerequisites OK"

# Step 2: Determine what to deploy
if ($BackendOnly) {
    Write-Step "Deploying BACKEND only"
} elseif ($FrontendOnly) {
    Write-Step "Deploying FRONTEND only"
} else {
    Write-Step "Deploying ALL components"
}

# Step 3: Deploy using existing script
Write-Header "Deploying to Server"

try {
    if ($BackendOnly) {
        & ".\deploy.ps1" -Backend
    } elseif ($FrontendOnly) {
        & ".\deploy.ps1" -Frontend
    } else {
        & ".\deploy.ps1" -All
    }
    Write-Success "Deployment completed"
} catch {
    Write-Error "Deployment failed: $_"
    exit 1
}

# Step 4: Run database migration
if (-not $SkipMigration -and -not $FrontendOnly) {
    Write-Header "Running Database Migration"

    Write-Step "Running Alembic migration on server..."

    $migrationCmd = 'cd /opt/f2l-sync && echo "Current migration status:" && docker-compose exec -T backend alembic current && echo "" && echo "Running migration..." && docker-compose exec -T backend alembic upgrade head && echo "" && echo "New migration status:" && docker-compose exec -T backend alembic current && echo "" && echo "Verifying new tables..." && docker-compose exec -T postgres psql -U f2luser -d f2l_sync -c "\dt shot_*"'

    try {
        $sshTarget = "$SSHUser@$SSHHost"
        ssh -i $SSHKey $sshTarget $migrationCmd
        Write-Success "Migration completed"
    } catch {
        Write-Error "Migration failed: $_"
        Write-Host "You may need to run migration manually:" -ForegroundColor Yellow
        Write-Host "  ssh -i $SSHKey $SSHUser@$SSHHost" -ForegroundColor Gray
        Write-Host "  cd /opt/f2l-sync" -ForegroundColor Gray
        Write-Host "  docker-compose exec backend alembic upgrade head" -ForegroundColor Gray
    }
}

# Step 5: Verify deployment
Write-Header "Verifying Deployment"

Write-Step "Checking service status..."

$statusCmd = 'cd /opt/f2l-sync && echo "Container Status:" && docker-compose ps && echo "" && echo "Recent Backend Logs:" && docker-compose logs --tail=20 backend'

try {
    $sshTarget = "$SSHUser@$SSHHost"
    ssh -i $SSHKey $sshTarget $statusCmd
    Write-Success "Services are running"
} catch {
    Write-Error "Failed to check status: $_"
}

# Step 6: Display access information
Write-Header "Deployment Complete!"

Write-Host ""
Write-Host "Access URLs:" -ForegroundColor Cyan
Write-Host "  Main App:     http://${SSHHost}:8080" -ForegroundColor White
Write-Host "  Frontend:     http://${SSHHost}:3001" -ForegroundColor White
Write-Host "  Backend API:  http://${SSHHost}:8001" -ForegroundColor White
Write-Host "  API Docs:     http://${SSHHost}:8001/docs" -ForegroundColor White
Write-Host ""

Write-Host "New Features:" -ForegroundColor Cyan
Write-Host "  • Shot Download page (sidebar navigation)" -ForegroundColor White
Write-Host "  • Download Tasks page (sidebar navigation)" -ForegroundColor White
Write-Host "  • 10 new API endpoints under /api/v1/shots/*" -ForegroundColor White
Write-Host ""

Write-Host "Testing Steps:" -ForegroundColor Cyan
Write-Host "  1. Navigate to 'Shot Download' in sidebar" -ForegroundColor White
Write-Host "  2. Select an endpoint" -ForegroundColor White
Write-Host "  3. Click 'Scan Structure'" -ForegroundColor White
Write-Host "  4. Filter episodes/sequences/shots" -ForegroundColor White
Write-Host "  5. Click 'Compare Shots'" -ForegroundColor White
Write-Host "  6. Review comparison results" -ForegroundColor White
Write-Host "  7. Click 'Create Download Task'" -ForegroundColor White
Write-Host "  8. Navigate to 'Download Tasks'" -ForegroundColor White
Write-Host "  9. Execute and monitor task" -ForegroundColor White
Write-Host ""

Write-Host "View Logs:" -ForegroundColor Cyan
Write-Host "  ssh -i $SSHKey ${SSHUser}@${SSHHost} 'cd /opt/f2l-sync && docker-compose logs -f backend'" -ForegroundColor Gray
Write-Host ""

Write-Host "Troubleshooting:" -ForegroundColor Cyan
Write-Host "  See: SHOT_DOWNLOAD_DEPLOYMENT.md" -ForegroundColor White
Write-Host ""

Write-Success "Ready for integration testing!"

