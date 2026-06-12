# Full Stack Deployment Guide

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Browser Client                              │
│                                                                   │
│  http://PUBLIC_IP:4173                                            │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Nginx Container                                │
│                   (port 4173)                                     │
│                                                                   │
│  ├─ Serves React SPA (dist files)                                │
│  ├─ Static asset caching (1 year TTL)                           │
│  ├─ GZIP compression enabled                                     │
│  ├─ SPA routing (/* → index.html)                                │
│  └─ API proxy (/api/* → backend:8000)                            │
└─────────────┬──────────────────────────────┬────────────────────┘
              │ (HTTP)                       │ (HTTP)
              │                              │
              ▼                              ▼
      ┌───────────────────┐      ┌──────────────────────┐
      │  FastAPI Backend  │      │  PostgreSQL Database │
      │  (port 8000)      │      │  (port 5432)         │
      │                   │      │                      │
      │ • /docs           │      │ • Data persistence   │
      │ • /api/*          │      │ • Health checks      │
      │ • /openapi.json   │      │ • Volumes            │
      └───────────────────┘      └──────────────────────┘
                                  
              All inside Docker Network (app-network)
```

## Complete Deployment Steps

### Step 1: Prerequisites Check

```bash
# Verify Docker and Docker Compose are installed
docker --version
docker compose version

# Expected output:
# Docker version 20.10+ 
# Docker Compose version 2.0+
```

### Step 2: Environment Configuration

The `.env` file should already exist in `backend/`. Verify essential variables:

```bash
# Check if .env exists and has required keys
grep -E "POSTGRES_|API_PORT|FRONTEND_PORT" backend/.env
```

Required variables (should auto-default if not set):
- `API_PORT` (default: 8000)
- `FRONTEND_PORT` (default: 4173)
- `POSTGRES_DB` (default: ai_cloud_cost_detective)
- `POSTGRES_USER` (default: ai_cost_user)
- `POSTGRES_PASSWORD` (required - must be set)

### Step 3: Build and Start Services

```bash
# Navigate to backend directory (where docker-compose.yml lives)
cd backend/

# Build images and start all containers in background
sudo docker compose up --build -d

# Watch startup progress
docker compose logs -f

# Wait for all services to be healthy (2-3 minutes on first run)
# Ctrl+C to exit logs when ready
```

### Step 4: Verify All Services

```bash
# Check all containers are running
docker compose ps

# Expected output:
# NAME                                STATUS              PORTS
# ai-cloud-cost-detective-frontend   Up (healthy)        0.0.0.0:4173->4173/tcp
# ai-cloud-cost-detective-api        Up (healthy)        0.0.0.0:8000->8000/tcp
# ai-cloud-cost-detective-db         Up (healthy)        0.0.0.0:5432->5432/tcp
```

### Step 5: Access the Application

#### Frontend (React UI)
```
http://localhost:4173
```
or from another machine:
```
http://{PUBLIC_IP}:4173
```

#### Backend API Documentation
```
http://localhost:4173/docs        (via Nginx proxy)
http://localhost:8000/docs        (direct access)
```

#### OpenAPI Schema
```
http://localhost:4173/openapi.json  (via Nginx proxy)
http://localhost:8000/openapi.json  (direct access)
```

## Common Operations

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f frontend
docker compose logs -f api
docker compose logs -f db

# Last 50 lines
docker compose logs --tail=50 api
```

### Stop Services

```bash
# Stop without removing containers
docker compose stop

# Stop and remove containers (volumes persist)
docker compose down

# Stop and remove everything including database
docker compose down -v
```

### Restart Services

```bash
# Restart all services
docker compose restart

# Restart specific service
docker compose restart api
```

### Check Service Health

```bash
# Database health
docker compose exec db pg_isready -U ai_cost_user -d ai_cloud_cost_detective

# Backend API
curl -s http://localhost:8000/docs | head -20

# Frontend
curl -s -o /dev/null -w "%{http_code}" http://localhost:4173
# Should return 200
```

### Access Container Shell

```bash
# Frontend container
docker compose exec frontend sh

# Backend container
docker compose exec api bash

# Database container
docker compose exec db psql -U ai_cost_user -d ai_cloud_cost_detective
```

## Troubleshooting

### Issue: Frontend not accessible on port 4173

**Symptoms**: `Connection refused` when accessing http://localhost:4173

**Solutions**:
```bash
# Check if container is running
docker compose ps frontend

# View frontend logs
docker compose logs frontend

# Check port binding
netstat -tlnp | grep 4173
sudo lsof -i :4173

# If port is in use, stop the service and restart
docker compose down
docker compose up --build -d
```

### Issue: Backend returns 502/503 errors

**Symptoms**: Backend API returns error codes, or times out

**Solutions**:
```bash
# Check backend container status
docker compose logs api

# Verify database connection
docker compose exec api curl -s http://localhost:8000/health

# Restart backend service
docker compose restart api

# Check database is running
docker compose exec db pg_isready
```

### Issue: Database connection fails

**Symptoms**: Backend logs show "could not connect to database"

**Solutions**:
```bash
# Check database container
docker compose logs db

# Verify database is healthy
docker compose exec db pg_isready -U ai_cost_user -d ai_cloud_cost_detective

# Check if volume exists
docker volume ls | grep postgres_data

# Force restart database
docker compose restart db
```

### Issue: "Address already in use" error

**Symptoms**: `Error: bind: address already in use`

**Solutions**:
```bash
# Kill process on specific port
sudo lsof -ti:4173 | xargs kill -9  # Frontend
sudo lsof -ti:8000 | xargs kill -9  # Backend
sudo lsof -ti:5432 | xargs kill -9  # Database

# Or change port in .env
echo "FRONTEND_PORT=4174" >> backend/.env
docker compose down && docker compose up --build -d
```

### Issue: Out of disk space

**Symptoms**: Docker build fails with "disk full" error

**Solutions**:
```bash
# Clean up unused Docker resources
docker system prune -a --volumes

# Remove specific volume
docker volume rm cloud-cost-optimaizer_postgres_data

# Check Docker disk usage
docker system df
```

## Performance Monitoring

### Monitor Container Resources

```bash
# Real-time stats
docker stats

# One-time snapshot
docker compose stats --no-stream
```

### Check Container Startup Times

```bash
# Container creation time
docker compose logs | grep -E "Started|listening"

# Database readiness
docker compose logs db | grep "ready"
```

## Database Management

### Backup Database

```bash
# Create backup
docker compose exec db pg_dump -U ai_cost_user ai_cloud_cost_detective > backup.sql

# Verify backup
wc -l backup.sql
```

### Restore Database

```bash
# Restore from backup (database must exist)
docker compose exec -T db psql -U ai_cost_user ai_cloud_cost_detective < backup.sql
```

### Access Database Directly

```bash
# Start psql shell
docker compose exec db psql -U ai_cost_user -d ai_cloud_cost_detective

# Common commands in psql
\dt                 # List tables
\l                  # List databases
SELECT * FROM ...;  # Run query
\q                  # Quit
```

## Production Deployment Checklist

- [ ] Docker and Docker Compose installed on server
- [ ] `.env` file configured with secure passwords
- [ ] SSL/TLS certificates obtained (for HTTPS)
- [ ] Firewall rules configured (allow 4173, 8000)
- [ ] Database backups scheduled
- [ ] Monitor logs for errors
- [ ] Test frontend at http://SERVER_IP:4173
- [ ] Test API at http://SERVER_IP:8000/docs
- [ ] Verify database persistence (restart and check data)

## Production Security Recommendations

1. **Use HTTPS**: Configure reverse proxy (nginx/HAProxy) in front
2. **Secure passwords**: Use strong, randomly generated `POSTGRES_PASSWORD`
3. **Network isolation**: Use Docker networks (already configured)
4. **Resource limits**: Add `deploy` section in docker-compose for resource constraints
5. **Monitoring**: Set up health check endpoints and alerting
6. **Backup strategy**: Automate database backups
7. **Log aggregation**: Centralize container logs for analysis
8. **Restart policy**: Already configured to `unless-stopped`

## File Structure

```
cloud-cost-optimaizer/
├── backend/
│   ├── docker-compose.yml        ← Main orchestration file
│   ├── Dockerfile                ← Backend image build
│   ├── requirements.txt
│   ├── main.py
│   ├── .env                       ← Environment config (not committed)
│   └── ...
├── frontend/
│   ├── Dockerfile                ← Frontend image build
│   ├── nginx.conf                ← Nginx configuration
│   ├── package.json
│   ├── vite.config.ts
│   └── ...
├── DOCKER_SETUP.md               ← Technical reference
├── DEPLOYMENT.md                 ← This file
└── verify-setup.sh               ← Verification script
```

## Quick Reference Commands

```bash
# Start everything
cd backend && sudo docker compose up --build -d

# Check status
docker compose ps

# View logs
docker compose logs -f

# Stop everything
docker compose down

# Rebuild images
docker compose build --no-cache

# Remove all data
docker compose down -v

# Access container
docker compose exec frontend sh
docker compose exec api bash
docker compose exec db psql -U ai_cost_user

# Cleanup system
docker system prune -a --volumes
```

## Getting Help

If services don't start:

1. Run verification script:
   ```bash
   bash verify-setup.sh
   ```

2. Check docker-compose syntax:
   ```bash
   docker compose config
   ```

3. View detailed logs:
   ```bash
   docker compose logs api
   docker compose logs frontend
   docker compose logs db
   ```

4. Rebuild from scratch:
   ```bash
   docker compose down -v
   docker system prune -a
   docker compose up --build -d
   ```
