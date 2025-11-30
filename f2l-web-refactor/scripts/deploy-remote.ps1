# Enhanced Remote Deployment Script for F2L Sync
# Supports separate frontend and backend deployment

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("all", "frontend", "backend", "infrastructure")]
    [string]$Component = "all",
    
    [Parameter(Mandatory=$false)]
    [ValidateSet("production", "staging", "development")]
    [string]$Environment = "production",
    
    [Parameter(Mandatory=$false)]
    [string]$SSHKey = "$env:USERPROFILE\.ssh\CaveTeam.pem",
    
    [Parameter(Mandatory=$false)]
    [string]$SSHUser = "ec2-user",
    
    [Parameter(Mandatory=$false)]
    [string]$SSHHost = "10.100.128.193",
    
    [Parameter(Mandatory=$false)]
    [string]$DeployPath = "/opt/f2l-sync",
    
    [switch]$Setup,
    [switch]$Build,
    [switch]$NoBuild,
    [switch]$Restart,
    [switch]$Logs,
    [switch]$Status,
    [switch]$DryRun
)

# Configuration
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# Colors for output
function Write-ColorOutput {
    param([string]$Message, [string]$Color = "White")
    
    $colorMap = @{
        "Red" = [ConsoleColor]::Red
        "Green" = [ConsoleColor]::Green
        "Yellow" = [ConsoleColor]::Yellow
        "Blue" = [ConsoleColor]::Blue
        "Cyan" = [ConsoleColor]::Cyan
        "Magenta" = [ConsoleColor]::Magenta
        "White" = [ConsoleColor]::White
        "Gray" = [ConsoleColor]::Gray
    }
    
    Write-Host $Message -ForegroundColor $colorMap[$Color]
}

function Write-Header {
    param([string]$Title)
    Write-Host ""
    Write-ColorOutput "=== $Title ===" "Cyan"
    Write-Host ""
}

function Write-Step {
    param([string]$Message)
    Write-ColorOutput "→ $Message" "Yellow"
}

function Write-Success {
    param([string]$Message)
    Write-ColorOutput "✓ $Message" "Green"
}

function Write-Error {
    param([string]$Message)
    Write-ColorOutput "✗ $Message" "Red"
}

# Validation functions
function Test-Prerequisites {
    Write-Step "Checking prerequisites..."
    
    # Check SSH key
    if (-not (Test-Path $SSHKey)) {
        Write-Error "SSH key not found: $SSHKey"
        return $false
    }
    
    # Check .env file
    if (-not (Test-Path ".env")) {
        Write-Error ".env file not found! Run: .\generate-env.ps1"
        return $false
    }
    
    # Check WSL for tar command
    if (-not (Get-Command wsl -ErrorAction SilentlyContinue)) {
        Write-Error "WSL required for creating archives. Install WSL first."
        return $false
    }
    
    # Test SSH connection
    try {
        $testResult = ssh -i $SSHKey -o ConnectTimeout=10 -o BatchMode=yes "${SSHUser}@${SSHHost}" "echo 'Connection test successful'"
        if ($LASTEXITCODE -ne 0) {
            Write-Error "SSH connection failed"
            return $false
        }
    } catch {
        Write-Error "SSH connection test failed: $_"
        return $false
    }
    
    Write-Success "All prerequisites met"
    return $true
}

function Get-DeploymentComponents {
    param([string]$Component)
    
    switch ($Component.ToLower()) {
        "all" { return @("frontend", "backend", "infrastructure") }
        "frontend" { return @("frontend") }
        "backend" { return @("backend") }
        "infrastructure" { return @("infrastructure") }
        default { return @("frontend", "backend", "infrastructure") }
    }
}

function New-DeploymentArchive {
    param([array]$Components)
    
    $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $archive = "f2l-sync-$($Component)-$timestamp.tar.gz"
    
    Write-Step "Creating deployment archive: $archive"
    
    $excludePatterns = @(
        "--exclude=*.log",
        "--exclude=__pycache__",
        "--exclude=node_modules",
        "--exclude=.git",
        "--exclude=venv",
        "--exclude=logs",
        "--exclude=*.tar.gz",
        "--exclude=frontend/dist",
        "--exclude=backend/tests",
        "--exclude=.pytest_cache",
        "--exclude=.coverage",
        "--exclude=*.pyc"
    )
    
    $includePatterns = @()
    
    if ($Components -contains "frontend") {
        $includePatterns += "frontend/"
    }
    if ($Components -contains "backend") {
        $includePatterns += "backend/"
    }
    if ($Components -contains "infrastructure") {
        $includePatterns += @("docker-compose.yml", "nginx/", ".env")
    }
    
    # If deploying all components, include everything
    if ($Components.Count -eq 3) {
        $includePatterns = @(".")
    }
    
    $tarCommand = "tar $($excludePatterns -join ' ') -czf $archive $($includePatterns -join ' ')"
    
    if ($DryRun) {
        Write-ColorOutput "DRY RUN: Would execute: wsl $tarCommand" "Gray"
        return $archive
    }
    
    try {
        wsl $tarCommand
        Write-Success "Archive created successfully"
        return $archive
    } catch {
        Write-Error "Failed to create archive: $_"
        throw
    }
}

# Main deployment logic
function Start-Deployment {
    Write-Header "F2L Sync Remote Deployment"
    Write-ColorOutput "Component: $Component" "Yellow"
    Write-ColorOutput "Environment: $Environment" "Yellow"
    Write-ColorOutput "Target: ${SSHUser}@${SSHHost}:${DeployPath}" "Yellow"
    
    if ($DryRun) {
        Write-ColorOutput "DRY RUN MODE - No actual changes will be made" "Magenta"
    }
    
    # Validate prerequisites
    if (-not (Test-Prerequisites)) {
        exit 1
    }
    
    # Get deployment components
    $components = Get-DeploymentComponents -Component $Component
    Write-Success "Deploying components: $($components -join ', ')"
    
    # Create deployment archive
    $archive = New-DeploymentArchive -Components $components
    
    if (-not $DryRun) {
        try {
            # Transfer archive
            Write-Step "Transferring archive to server..."
            scp -i $SSHKey $archive "${SSHUser}@${SSHHost}:/tmp/"
            Write-Success "Archive transferred"
            
            # Execute deployment on server
            Write-Step "Executing deployment on server..."
            $deployScript = Get-ServerDeploymentScript -Archive $archive -Components $components
            ssh -i $SSHKey -tt "${SSHUser}@${SSHHost}" $deployScript
            
            # Cleanup local archive
            Remove-Item $archive -Force
            Write-Success "Local cleanup completed"
            
        } catch {
            Write-Error "Deployment failed: $_"
            if (Test-Path $archive) {
                Remove-Item $archive -Force
            }
            exit 1
        }
    }
    
    Write-Header "Deployment Complete"
    Show-AccessInformation
}

function Get-ServerDeploymentScript {
    param([string]$Archive, [array]$Components)
    
    $script = @"
set -e
echo "Starting server-side deployment..."

# Create deployment directory
sudo mkdir -p $DeployPath
sudo chown ${SSHUser}:${SSHUser} $DeployPath
cd $DeployPath

# Extract archive
echo "Extracting deployment archive..."
tar -xzf /tmp/$Archive
chmod 600 .env 2>/dev/null || true
mkdir -p logs cache nginx/ssl frontend/dist

# Stop existing services
echo "Stopping existing services..."
docker-compose down 2>/dev/null || true

# Build and start services based on components
"@

    if ($components -contains "frontend" -and $components -contains "backend") {
        $script += @"

echo "Building and starting all services..."
docker-compose build
docker-compose up -d
"@
    } elseif ($components -contains "frontend") {
        $script += @"

echo "Building and starting frontend services..."
docker-compose build frontend
docker-compose up -d frontend nginx postgres redis
"@
    } elseif ($components -contains "backend") {
        $script += @"

echo "Building and starting backend services..."
docker-compose build backend celery-worker celery-beat flower
docker-compose up -d backend celery-worker celery-beat flower postgres redis nginx
"@
    }
    
    $script += @"

# Wait for services
echo "Waiting for services to start..."
sleep 15

# Show status
echo "Service status:"
docker-compose ps

# Cleanup
rm -f /tmp/$Archive

echo "Server-side deployment complete!"
"@

    return $script
}

function Show-AccessInformation {
    Write-ColorOutput "Access Information:" "White"
    Write-ColorOutput "  • Main Application: http://${SSHHost}:8080" "Cyan"
    Write-ColorOutput "  • Backend API: http://${SSHHost}:8001" "Cyan"
    Write-ColorOutput "  • Frontend: http://${SSHHost}:3001" "Cyan"
    Write-ColorOutput "  • Flower (Celery): http://${SSHHost}:5556" "Cyan"
    Write-Host ""
    Write-ColorOutput "Management Commands:" "White"
    Write-ColorOutput "  • SSH: ssh -i $SSHKey ${SSHUser}@${SSHHost}" "Gray"
    Write-ColorOutput "  • Logs: docker-compose logs -f [service]" "Gray"
    Write-ColorOutput "  • Status: docker-compose ps" "Gray"
    Write-ColorOutput "  • Restart: docker-compose restart [service]" "Gray"
}

# Handle special operations
if ($Setup) {
    Write-Header "Server Setup"
    Write-Step "Setting up server environment..."
    scp -i $SSHKey "server-setup.sh" "${SSHUser}@${SSHHost}:/tmp/"
    ssh -i $SSHKey -tt "${SSHUser}@${SSHHost}" "chmod +x /tmp/server-setup.sh && sudo /tmp/server-setup.sh"
    Write-Success "Server setup complete. You can now run deployments."
    exit 0
}

if ($Status) {
    Write-Header "Service Status"
    ssh -i $SSHKey -tt "${SSHUser}@${SSHHost}" "cd $DeployPath && docker-compose ps"
    exit 0
}

if ($Logs) {
    Write-Header "Service Logs"
    ssh -i $SSHKey -tt "${SSHUser}@${SSHHost}" "cd $DeployPath && docker-compose logs -f"
    exit 0
}

if ($Restart) {
    Write-Header "Restarting Services"
    $restartComponents = Get-DeploymentComponents -Component $Component
    $services = @()
    
    if ($restartComponents -contains "frontend") { $services += "frontend" }
    if ($restartComponents -contains "backend") { $services += @("backend", "celery-worker", "celery-beat", "flower") }
    if ($restartComponents -contains "infrastructure") { $services += @("nginx", "postgres", "redis") }
    
    $serviceList = $services -join " "
    ssh -i $SSHKey -tt "${SSHUser}@${SSHHost}" "cd $DeployPath && docker-compose restart $serviceList"
    Write-Success "Services restarted: $serviceList"
    exit 0
}

# Main deployment
Start-Deployment
