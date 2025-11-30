#!/bin/bash
# F2L Sync - Server Setup Script
# Run this on the server to prepare the environment

set -e  # Exit on error

echo "========================================"
echo "F2L Sync - Server Setup Script"
echo "========================================"
echo ""

# Configuration
DEPLOY_PATH="/opt/f2l-sync"
DOCKER_COMPOSE_VERSION="2.24.5"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root or with sudo
if [ "$EUID" -eq 0 ]; then
    SUDO=""
else
    SUDO="sudo"
fi

echo -e "${GREEN}[1/6] Updating system packages...${NC}"
$SUDO yum update -y

echo ""
echo -e "${GREEN}[2/6] Installing Docker...${NC}"
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    $SUDO yum install -y docker
    $SUDO systemctl start docker
    $SUDO systemctl enable docker
    $SUDO usermod -aG docker ec2-user
    echo -e "${GREEN}Docker installed successfully${NC}"
else
    echo "Docker already installed"
fi

echo ""
echo -e "${GREEN}[3/6] Installing Docker Compose and Buildx...${NC}"
if ! command -v docker-compose &> /dev/null; then
    echo "Installing Docker Compose..."
    $SUDO curl -L "https://github.com/docker/compose/releases/download/v${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    $SUDO chmod +x /usr/local/bin/docker-compose
    $SUDO ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose
    echo -e "${GREEN}Docker Compose installed successfully${NC}"
else
    echo "Docker Compose already installed"
fi

# Install Docker Buildx
echo "Installing Docker Buildx..."
BUILDX_VERSION="v0.17.1"
$SUDO mkdir -p /usr/local/lib/docker/cli-plugins
$SUDO curl -L "https://github.com/docker/buildx/releases/download/${BUILDX_VERSION}/buildx-${BUILDX_VERSION}.linux-amd64" -o /usr/local/lib/docker/cli-plugins/docker-buildx
$SUDO chmod +x /usr/local/lib/docker/cli-plugins/docker-buildx
echo -e "${GREEN}Docker Buildx installed successfully${NC}"

echo ""
echo -e "${GREEN}[4/6] Installing Python 3.11...${NC}"
if ! command -v python3.11 &> /dev/null; then
    echo "Installing Python 3.11..."
    $SUDO yum install -y python3.11 python3.11-pip
    echo -e "${GREEN}Python 3.11 installed successfully${NC}"
else
    echo "Python 3.11 already installed"
fi

echo ""
echo -e "${GREEN}[5/6] Creating deployment directory...${NC}"
$SUDO mkdir -p $DEPLOY_PATH
$SUDO chown ec2-user:ec2-user $DEPLOY_PATH
echo "Deployment directory created at: $DEPLOY_PATH"

echo ""
echo -e "${GREEN}[6/6] Configuring firewall...${NC}"
# Open required ports
if command -v firewall-cmd &> /dev/null; then
    echo "Configuring firewalld..."
    $SUDO firewall-cmd --permanent --add-port=8080/tcp  # HTTP
    $SUDO firewall-cmd --permanent --add-port=8443/tcp  # HTTPS
    $SUDO firewall-cmd --permanent --add-port=5555/tcp  # Flower
    $SUDO firewall-cmd --reload
    echo -e "${GREEN}Firewall configured${NC}"
else
    echo -e "${YELLOW}firewalld not found, skipping firewall configuration${NC}"
    echo "Make sure ports 8080, 8443, and 5555 are accessible"
fi

echo ""
echo "========================================"
echo -e "${GREEN}Server setup completed!${NC}"
echo "========================================"
echo ""
echo "Installed components:"
docker --version
docker-compose --version
python3.11 --version
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Deploy the application from your local machine:"
echo "   ./deploy.ps1 -Transfer -Deploy"
echo ""
echo "2. On the server, review the .env file:"
echo "   nano $DEPLOY_PATH/.env"
echo ""
echo "3. Generate secure keys (run on server):"
echo "   python3.11 -c \"import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))\""
echo "   python3.11 -c \"import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))\""
echo ""
echo "4. Install cryptography package for encryption key:"
echo "   pip3.11 install cryptography"
echo "   python3.11 -c \"from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())\""
echo ""
echo "5. Start the application:"
echo "   cd $DEPLOY_PATH"
echo "   docker-compose up -d"
echo ""
echo "6. Check status:"
echo "   docker-compose ps"
echo "   docker-compose logs -f api"
echo ""
echo -e "${YELLOW}Important:${NC} Log out and log back in for Docker group changes to take effect"
echo ""
