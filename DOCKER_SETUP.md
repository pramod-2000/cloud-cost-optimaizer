# Docker Setup Guide - AI Cloud Cost Detective

## Overview

This application is fully containerized with:
- **Frontend**: React + Vite served via Nginx on port 4173
- **Backend**: FastAPI with Uvicorn on port 8000
- **Database**: PostgreSQL 16 on port 5432
- **Network**: Custom bridge network for service-to-service communication

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Docker Network                     │
│              (app-network, bridge driver)           │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────┐ │
│  │  Frontend    │  │   Backend    │  │   DB     │ │
│  │  (Nginx)     │  │  (FastAPI)   │  │(Postgres)│ │
│  │ :4173        │  │   :8000      │  │ :5432    │ │
│  └──────────────┘  └──────────────┘  └──────────┘ │
│                                                     │
│  Nginx handles:                                     │
│  - Frontend SPA routing                             │
│  - /api/* → proxy to backend:8000                   │
│  - /docs → proxy to backend:8000/docs              │
│  - /openapi.json → proxy to backend:8000/openapi   │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## Files Created/Modified

### New Files:
1. **frontend/Dockerfile** - Multi-stage build for React app with Nginx
2. **frontend/nginx.conf** - Nginx configuration with SPA routing and API proxy
3. **DOCKER_SETUP.md** - This file

### Modified Files:
1. **backend/docker-compose.yml** - Added frontend service, networks, and environment variables
2. **frontend/vite.config.ts** - Enhanced build configuration for production

## Quick Start

### Prerequisites
- Docker and Docker Compose installed
- All environment variables configured in `backend/.env`

### Build and Start

From the `backend/` directory (where docker-compose.yml is located):

```bash
# Build all images and start containers
sudo docker compose up --build -d

# View logs
docker compose logs -f

# Stop containers
docker compose down

# Remove all data (including database volume)
docker compose down -v
```

## Service Details

### Frontend Service (Nginx)
- **Container name**: ai-cloud-cost-detective-frontend
- **Port**: 4173 (configurable via `FRONTEND_PORT` env var)
- **Features**:
  - Multi-stage Docker build (optimized size)
  - GZIP compression enabled
  - Static asset caching (1 year expiry)
  - SPA fallback routing (all routes → index.html)
  - API proxy to backend
  - Health check every 10s

### Backend Service (FastAPI)
- **Container name**: ai-cloud-cost-detective-api
- **Port**: 8000 (configurable via `API_PORT` env var)
- **Dependencies**: Waits for DB health check
- **Features**:
  - Python 3.12 slim image
  - AWS CLI included
  - Uvicorn ASGI server
  - Automatic restart on failure

### Database Service (PostgreSQL)
- **Container name**: ai-cloud-cost-detective-db
- **Port**: 5432 (configurable via `POSTGRES_PORT` env var)
- **Volume**: `postgres_data` (persists data between restarts)
- **Health Check**: Validates DB readiness every 10s

## Access Points

Once running, access the application at:

- **Frontend**: http://PUBLIC_IP:4173
- **Backend Swagger UI**: http://PUBLIC_IP:4173/docs (proxied via Nginx)
- **Backend Direct**: http://PUBLIC_IP:8000/docs
- **OpenAPI Schema**: http://PUBLIC_IP:4173/openapi.json (proxied)

## Environment Variables

Set in `backend/.env`:
```
API_PORT=8000                          # Backend API port
FRONTEND_PORT=4173                     # Frontend Nginx port
POSTGRES_PORT=5432                     # Database port
POSTGRES_DB=ai_cloud_cost_detective    # Database name
POSTGRES_USER=ai_cost_user             # Database user
POSTGRES_PASSWORD=<secure_password>    # Database password
```

## Nginx Routing

The frontend Nginx container handles:

1. **Static Assets** (`/.*\.(js|css|png|jpg|etc)$`)
   - Cached for 1 year
   - Immutable headers

2. **SPA Routing** (`/*`)
   - All non-API, non-static routes → index.html
   - Enables React Router functionality

3. **API Proxy** (`/api/*`)
   - Proxies to backend at `http://api:8000/`
   - Proper headers for CORS and real IP

4. **Backend Documentation** (`/docs`, `/openapi.json`)
   - Proxies to backend FastAPI endpoints

## Troubleshooting

### Frontend not accessible
```bash
# Check if container is running
docker ps | grep frontend

# View frontend logs
docker compose logs frontend

# Check port binding
netstat -tlnp | grep 4173
```

### Backend connection issues
```bash
# Check backend container
docker compose logs api

# Verify network connectivity
docker compose exec frontend ping api
```

### Database issues
```bash
# Check database status
docker compose logs db

# Verify database is healthy
docker compose exec db pg_isready -U ai_cost_user -d ai_cloud_cost_detective
```

### Rebuild from scratch
```bash
docker compose down -v
docker system prune -a
docker compose up --build -d
```

## Performance Notes

- **Frontend build time**: ~30-60 seconds (first build)
- **Total startup time**: ~15-30 seconds (all services healthy)
- **Image sizes**:
  - Frontend: ~100-150 MB (Nginx + React bundle)
  - Backend: ~200-300 MB (Python + dependencies)
  - Database: ~50-100 MB (PostgreSQL)

## Security Considerations

- Hidden files denied (/.*)
- CORS headers properly set
- X-Forwarded-* headers for proxy transparency
- WebSockets support enabled
- Client body size limit: 20 MB

## Development vs Production

This setup is **production-ready**:
- ✅ Multi-stage builds for optimal image sizes
- ✅ Health checks on all services
- ✅ Automatic restart policies
- ✅ Proper network isolation
- ✅ Nginx for static asset optimization
- ✅ GZIP compression enabled
- ✅ No unnecessary volumes

For local development:
- Run `npm run dev` in frontend/ for hot reload (separate from Docker)
- Or modify docker-compose.yml to mount source volumes

## Integration with Backend API

The backend API is accessible from the frontend in two ways:

1. **Via Nginx proxy** (recommended for production):
   ```javascript
   fetch('http://localhost:4173/api/endpoint')
   ```

2. **Direct to backend** (for development):
   ```javascript
   fetch('http://localhost:8000/endpoint')
   ```

Update frontend API calls based on your environment configuration.
