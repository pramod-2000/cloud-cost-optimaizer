#!/bin/bash

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Docker Setup Verification${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check Docker installation
echo -e "${YELLOW}1. Checking Docker installation...${NC}"
if command -v docker &> /dev/null; then
    echo -e "${GREEN}✓ Docker is installed${NC}"
    docker --version
else
    echo -e "${RED}✗ Docker is not installed${NC}"
    exit 1
fi
echo ""

# Check Docker Compose
echo -e "${YELLOW}2. Checking Docker Compose...${NC}"
if docker compose version &> /dev/null; then
    echo -e "${GREEN}✓ Docker Compose is installed${NC}"
    docker compose version
else
    echo -e "${RED}✗ Docker Compose is not installed${NC}"
    exit 1
fi
echo ""

# Check required files
echo -e "${YELLOW}3. Checking required files...${NC}"
FILES=(
    "backend/docker-compose.yml"
    "backend/Dockerfile"
    "backend/requirements.txt"
    "frontend/Dockerfile"
    "frontend/nginx.conf"
    "frontend/package.json"
    "frontend/vite.config.ts"
)

for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓ $file${NC}"
    else
        echo -e "${RED}✗ $file (missing)${NC}"
    fi
done
echo ""

# Check docker-compose.yml syntax
echo -e "${YELLOW}4. Validating docker-compose.yml syntax...${NC}"
if docker compose -f backend/docker-compose.yml config > /dev/null 2>&1; then
    echo -e "${GREEN}✓ docker-compose.yml is valid${NC}"
else
    echo -e "${RED}✗ docker-compose.yml has syntax errors${NC}"
    docker compose -f backend/docker-compose.yml config
    exit 1
fi
echo ""

# Check for running containers
echo -e "${YELLOW}5. Checking for running containers...${NC}"
RUNNING=$(docker ps --format "{{.Names}}" | grep -c ai-cloud-cost-detective || true)
if [ $RUNNING -gt 0 ]; then
    echo -e "${GREEN}✓ Found $RUNNING running containers:${NC}"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep ai-cloud-cost-detective
else
    echo -e "${YELLOW}→ No containers running (expected on first check)${NC}"
fi
echo ""

# Check environment file
echo -e "${YELLOW}6. Checking environment configuration...${NC}"
if [ -f "backend/.env" ]; then
    echo -e "${GREEN}✓ backend/.env exists${NC}"
    # Only check key variables exist, don't display values
    if grep -q "POSTGRES_USER" backend/.env; then
        echo -e "${GREEN}✓ POSTGRES_USER is configured${NC}"
    else
        echo -e "${YELLOW}⚠ POSTGRES_USER not found in .env${NC}"
    fi
else
    echo -e "${RED}✗ backend/.env not found${NC}"
    echo -e "${YELLOW}  Copy from backend/.env.example if needed${NC}"
fi
echo ""

# Network test (if containers are running)
echo -e "${YELLOW}7. Testing service connectivity...${NC}"
if docker ps --format "{{.Names}}" | grep -q api; then
    echo -e "${GREEN}✓ Backend API container is running${NC}"
    
    # Try to reach API health check
    if docker exec ai-cloud-cost-detective-api curl -s http://localhost:8000/docs > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Backend API is responding${NC}"
    else
        echo -e "${YELLOW}⚠ Backend API not yet responding (starting up?)${NC}"
    fi
else
    echo -e "${YELLOW}→ Backend not running (start with: docker compose up --build -d)${NC}"
fi

if docker ps --format "{{.Names}}" | grep -q frontend; then
    echo -e "${GREEN}✓ Frontend Nginx container is running${NC}"
    
    # Try to reach frontend
    if docker exec ai-cloud-cost-detective-frontend wget -q -O /dev/null http://localhost:4173/ 2>&1; then
        echo -e "${GREEN}✓ Frontend is responding${NC}"
    else
        echo -e "${YELLOW}⚠ Frontend not yet responding (starting up?)${NC}"
    fi
else
    echo -e "${YELLOW}→ Frontend not running (start with: docker compose up --build -d)${NC}"
fi
echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Verification Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Navigate to: cd backend/"
echo "2. Start containers: sudo docker compose up --build -d"
echo "3. View logs: docker compose logs -f"
echo "4. Access frontend: http://localhost:4173"
echo "5. Access backend docs: http://localhost:4173/docs"
echo ""
echo -e "${GREEN}Setup verification complete!${NC}"
