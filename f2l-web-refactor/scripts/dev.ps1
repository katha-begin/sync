# Local Development Script for F2L Sync
# Manages separate frontend and backend containers for development

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("start", "stop", "restart", "build", "logs", "status", "clean")]
    [string]$Action = "start",
    
    [Parameter(Mandatory=$false)]
    [ValidateSet("all", "frontend", "backend", "infrastructure")]
    [string]$Component = "all",
    
    [switch]$Build,
    [switch]$Follow
)

$ErrorActionPreference = "Stop"

# Colors for output
function Write-ColorOutput {
    param([string]$Message, [string]$Color = "White")
    
    $colorMap = @{
        "Red" = [ConsoleColor]::Red
        "Green" = [ConsoleColor]::Green
        "Yellow" = [ConsoleColor]::Yellow
        "Blue" = [ConsoleColor]::Blue
        "Cyan" = [ConsoleColor]::Cyan
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

function Get-ServiceNames {
    param([string]$Component)
    
    switch ($Component.ToLower()) {
        "all" { return @("postgres", "redis", "backend", "frontend", "celery-worker", "flower") }
        "frontend" { return @("frontend") }
        "backend" { return @("backend", "celery-worker", "flower") }
        "infrastructure" { return @("postgres", "redis") }
        default { return @("postgres", "redis", "backend", "frontend", "celery-worker", "flower") }
    }
}

function Test-Prerequisites {
    Write-Step "Checking prerequisites..."
    
    # Check Docker
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Error "Docker not found. Please install Docker Desktop."
        return $false
    }
    
    # Check Docker Compose
    if (-not (Get-Command docker-compose -ErrorAction SilentlyContinue)) {
        Write-Error "Docker Compose not found. Please install Docker Compose."
        return $false
    }
    
    # Check if Docker is running
    try {
        docker info | Out-Null
    } catch {
        Write-Error "Docker is not running. Please start Docker Desktop."
        return $false
    }
    
    Write-Success "Prerequisites met"
    return $true
}

function Start-Services {
    param([array]$Services)
    
    Write-Step "Starting services: $($Services -join ', ')"
    
    if ($Build) {
        Write-Step "Building services first..."
        docker-compose -f docker-compose.dev.yml build $($Services -join ' ')
    }
    
    docker-compose -f docker-compose.dev.yml up -d $($Services -join ' ')
    
    Write-Success "Services started"
    Show-ServiceStatus
}

function Stop-Services {
    param([array]$Services)
    
    Write-Step "Stopping services: $($Services -join ', ')"
    
    if ($Services.Count -eq 6) {
        # Stop all services
        docker-compose -f docker-compose.dev.yml down
    } else {
        # Stop specific services
        docker-compose -f docker-compose.dev.yml stop $($Services -join ' ')
    }
    
    Write-Success "Services stopped"
}

function Restart-Services {
    param([array]$Services)
    
    Write-Step "Restarting services: $($Services -join ', ')"
    docker-compose -f docker-compose.dev.yml restart $($Services -join ' ')
    Write-Success "Services restarted"
    Show-ServiceStatus
}

function Build-Services {
    param([array]$Services)
    
    Write-Step "Building services: $($Services -join ', ')"
    docker-compose -f docker-compose.dev.yml build $($Services -join ' ')
    Write-Success "Build complete"
}

function Show-Logs {
    param([array]$Services)
    
    Write-Step "Showing logs for: $($Services -join ', ')"
    
    if ($Follow) {
        docker-compose -f docker-compose.dev.yml logs -f $($Services -join ' ')
    } else {
        docker-compose -f docker-compose.dev.yml logs --tail=50 $($Services -join ' ')
    }
}

function Show-ServiceStatus {
    Write-Step "Service status:"
    docker-compose -f docker-compose.dev.yml ps
}

function Clean-Environment {
    Write-Step "Cleaning development environment..."
    
    # Stop all services
    docker-compose -f docker-compose.dev.yml down
    
    # Remove volumes (optional - ask user)
    $removeVolumes = Read-Host "Remove development data volumes? (y/N)"
    if ($removeVolumes -eq 'y' -or $removeVolumes -eq 'Y') {
        docker-compose -f docker-compose.dev.yml down -v
        Write-Success "Volumes removed"
    }
    
    # Remove unused images
    docker image prune -f
    
    Write-Success "Environment cleaned"
}

function Show-AccessInformation {
    Write-Header "Development Access Information"
    Write-ColorOutput "Services:" "White"
    Write-ColorOutput "  • Frontend (React): http://localhost:3001" "Cyan"
    Write-ColorOutput "  • Backend API: http://localhost:8001" "Cyan"
    Write-ColorOutput "  • API Docs: http://localhost:8001/docs" "Cyan"
    Write-ColorOutput "  • Flower (Celery): http://localhost:5556" "Cyan"
    Write-ColorOutput "  • PostgreSQL: localhost:5432" "Cyan"
    Write-ColorOutput "  • Redis: localhost:6379" "Cyan"
    Write-Host ""
    Write-ColorOutput "Development Features:" "White"
    Write-ColorOutput "  • Hot reload enabled for both frontend and backend" "Gray"
    Write-ColorOutput "  • Source code mounted as volumes" "Gray"
    Write-ColorOutput "  • Debug logging enabled" "Gray"
    Write-ColorOutput "  • CORS configured for development" "Gray"
    Write-Host ""
    Write-ColorOutput "Useful Commands:" "White"
    Write-ColorOutput "  • View logs: .\scripts\dev.ps1 logs -Follow" "Gray"
    Write-ColorOutput "  • Restart service: .\scripts\dev.ps1 restart -Component backend" "Gray"
    Write-ColorOutput "  • Rebuild: .\scripts\dev.ps1 build -Component frontend" "Gray"
    Write-ColorOutput "  • Clean up: .\scripts\dev.ps1 clean" "Gray"
}

# Main execution
Write-Header "F2L Sync Development Environment"

# Check prerequisites
if (-not (Test-Prerequisites)) {
    exit 1
}

# Get services to operate on
$services = Get-ServiceNames -Component $Component

# Execute action
switch ($Action.ToLower()) {
    "start" {
        Start-Services -Services $services
        Show-AccessInformation
    }
    "stop" {
        Stop-Services -Services $services
    }
    "restart" {
        Restart-Services -Services $services
        Show-AccessInformation
    }
    "build" {
        Build-Services -Services $services
    }
    "logs" {
        Show-Logs -Services $services
    }
    "status" {
        Show-ServiceStatus
    }
    "clean" {
        Clean-Environment
    }
    default {
        Write-Error "Unknown action: $Action"
        Write-ColorOutput "Available actions: start, stop, restart, build, logs, status, clean" "Yellow"
        exit 1
    }
}
