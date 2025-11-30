# Generate .env file for F2L Sync

Write-Host ""
Write-Host "=== F2L Sync - Generate .env ===" -ForegroundColor Cyan
Write-Host ""

# Generate secure key
function New-SecureKey {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    $key = [Convert]::ToBase64String($bytes)
    $rng.Dispose()
    return $key
}

# Get passwords
Write-Host "Enter PostgreSQL password (or press Enter to auto-generate):" -ForegroundColor Yellow
$securePostgres = Read-Host -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePostgres)
$PostgresPassword = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)

if (-not $PostgresPassword) {
    $PostgresPassword = "F2L_DB_" + (New-SecureKey).Substring(0, 16).Replace('/', '_').Replace('+', '-')
}

Write-Host "Enter Flower password (or press Enter to auto-generate):" -ForegroundColor Yellow
$secureFlower = Read-Host -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureFlower)
$FlowerPassword = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)

if (-not $FlowerPassword) {
    $FlowerPassword = "F2L_Flower_" + (New-SecureKey).Substring(0, 16).Replace('/', '_').Replace('+', '-')
}

# Generate keys
$SecretKey = New-SecureKey
$JwtSecretKey = New-SecureKey
$EncryptionKey = New-SecureKey

# Create .env content
$env = @"
# F2L Sync Production Configuration
# Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

# Database
POSTGRES_DB=f2l_sync
POSTGRES_USER=f2luser
POSTGRES_PASSWORD=$PostgresPassword
POSTGRES_PORT=5432

# Redis
REDIS_PORT=6379

# Security Keys
SECRET_KEY=$SecretKey
JWT_SECRET_KEY=$JwtSecretKey
ENCRYPTION_KEY=$EncryptionKey

# Application
APP_ENV=production
LOG_LEVEL=INFO
WORKERS=4
DEBUG=false

# CORS
CORS_ORIGINS=http://lightingbolt.com:8080,http://10.100.128.193:8080,http://localhost:8080

# Ports
API_PORT=8000
HTTP_PORT=8080
HTTPS_PORT=8443
FLOWER_PORT=5555

# Flower Authentication
FLOWER_USER=admin
FLOWER_PASSWORD=$FlowerPassword

# AWS S3 - Add your credentials here
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_DEFAULT_REGION=us-east-1

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=100

# Sync Settings
DEFAULT_SCAN_WORKERS=5
DEFAULT_TRANSFER_WORKERS=3
SCAN_CACHE_ENABLED=true
SCAN_CACHE_TTL_HOURS=24

# Health Check
HEALTH_CHECK_INTERVAL_SECONDS=30

# Monitoring
PROMETHEUS_ENABLED=false
SENTRY_DSN=
"@

# Save file without BOM
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText((Join-Path $PWD ".env"), $env, $utf8NoBom)

Write-Host ""
Write-Host "=== SUCCESS ===" -ForegroundColor Green
Write-Host ""
Write-Host "File created: .env" -ForegroundColor Yellow
Write-Host ""
Write-Host "Credentials:" -ForegroundColor Cyan
Write-Host "  PostgreSQL Password: $PostgresPassword"
Write-Host "  Flower Username: admin"
Write-Host "  Flower Password: $FlowerPassword"
Write-Host ""
Write-Host "Next step: .\deploy.ps1" -ForegroundColor Yellow
Write-Host ""
