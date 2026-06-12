# Application Architecture

## System Overview

```
                              ┌─────────────────────────────────┐
                              │      Your Browser/Client        │
                              │   (Any machine on network)      │
                              └────────────┬────────────────────┘
                                           │
                                           │ HTTP/HTTPS
                                           │
                    ┌──────────────────────▼──────────────────────┐
                    │          Docker Host Machine                │
                    │      (Linux with Docker installed)          │
                    │                                              │
                    │  ┌────────────────────────────────────────┐ │
                    │  │    Docker Network (app-network)        │ │
                    │  │                                        │ │
                    │  │  ┌──────────────────────────────────┐  │ │
                    │  │  │  Frontend Container (Nginx)     │  │ │
                    │  │  │  ───────────────────────────────│  │ │
                    │  │  │  Port: 4173                      │  │ │
                    │  │  │  Serves: React SPA              │  │ │
                    │  │  │  - index.html                   │  │ │
                    │  │  │  - main.tsx bundle              │  │ │
                    │  │  │  - CSS/JS assets                │  │ │
                    │  │  │                                  │  │ │
                    │  │  │  Routes:                         │  │ │
                    │  │  │  - /* → index.html (SPA)        │  │ │
                    │  │  │  - /api/* → api:8000 (proxy)    │  │ │
                    │  │  │  - /docs → api:8000/docs        │  │ │
                    │  │  └───┬──────────────────────────────┘  │ │
                    │  │      │                                   │ │
                    │  │      │ Internal DNS                      │ │
                    │  │      │ (api:8000)                        │ │
                    │  │      │                                   │ │
                    │  │  ┌───▼──────────────────────────────┐  │ │
                    │  │  │  Backend Container (FastAPI)    │  │ │
                    │  │  │  ──────────────────────────────│  │ │
                    │  │  │  Port: 8000                     │  │ │
                    │  │  │  Framework: Uvicorn            │  │ │
                    │  │  │  Endpoints:                     │  │ │
                    │  │  │  - /docs (Swagger UI)          │  │ │
                    │  │  │  - /openapi.json               │  │ │
                    │  │  │  - /api/* (custom endpoints)   │  │ │
                    │  │  │                                │  │ │
                    │  │  │  Internal DNS (db:5432)        │  │ │
                    │  │  └───┬──────────────────────────────┘  │ │
                    │  │      │                                   │ │
                    │  │      │ TCP 5432                          │ │
                    │  │      │                                   │ │
                    │  │  ┌───▼──────────────────────────────┐  │ │
                    │  │  │  Database Container (PostgreSQL)│  │ │
                    │  │  │  ─────────────────────────────│  │ │
                    │  │  │  Port: 5432                     │  │ │
                    │  │  │  Database: ai_cloud_cost_..    │  │ │
                    │  │  │  Users: ai_cost_user           │  │ │
                    │  │  │  Storage: postgres_data volume │  │ │
                    │  │  └──────────────────────────────────┘  │ │
                    │  │                                        │ │
                    │  └────────────────────────────────────────┘ │
                    │                                              │
                    │  ┌────────────────────────────────────────┐ │
                    │  │      Docker Volumes                    │ │
                    │  │  ┌──────────────────────────────────┐  │ │
                    │  │  │  postgres_data                   │  │ │
                    │  │  │  └─ Database files persist      │  │ │
                    │  │  │    across restarts              │  │ │
                    │  │  └──────────────────────────────────┘  │ │
                    │  └────────────────────────────────────────┘ │
                    │                                              │
                    │  EXPOSED PORTS:                             │
                    │  ┌─────────────────────────────────────┐   │
                    │  │  Host Port │ Container │ Service   │   │
                    │  ├─────────────────────────────────────┤   │
                    │  │    4173    │   4173    │ Frontend  │   │
                    │  │    8000    │   8000    │ Backend   │   │
                    │  │    5432    │   5432    │ Database  │   │
                    │  └─────────────────────────────────────┘   │
                    │                                              │
                    └──────────────────────────────────────────────┘
```

## Data Flow

### User visits http://localhost:4173

```
Browser Request → Nginx (4173)
  ├─ Check if request is for static file (*.js, *.css, *.woff2, etc)
  │  ├─ YES: Serve from cache (1 year TTL)
  │  └─ NO: Continue
  ├─ Check if request is for /api/*
  │  ├─ YES: Proxy to api:8000, return response
  │  └─ NO: Continue
  ├─ Check if request is for /docs or /openapi.json
  │  ├─ YES: Proxy to api:8000, return response
  │  └─ NO: Continue
  └─ Default: Serve index.html (SPA routing)
     └─ Browser downloads React app
        ├─ index.html
        ├─ main.tsx (bundled React app)
        ├─ vendor.js (React, React-DOM, Router)
        └─ styles.css
```

### User clicks button to fetch data → API call

```
React Component → fetch('/api/endpoint')
  ↓
Nginx proxy (4173)
  ├─ Matches /api/*
  ├─ Strips /api prefix (optional, depends on backend routing)
  ├─ Proxies to http://api:8000/endpoint
  ↓
FastAPI Backend (8000)
  ├─ Receives request
  ├─ Processes (queries database if needed)
  ├─ Returns JSON response
  ↓
Nginx receives response
  ├─ Applies GZIP compression if applicable
  ├─ Sends to browser
  ↓
Browser receives JSON
  ├─ React component updates state
  └─ UI re-renders with new data
```

### Backend queries Database

```
FastAPI endpoint handler
  ├─ Receives request
  ├─ Uses asyncpg to connect to db:5432 (via Docker DNS)
  ├─ Executes SQL query
  │  ├─ INSERT (create)
  │  ├─ SELECT (read)
  │  ├─ UPDATE (modify)
  │  └─ DELETE (remove)
  ├─ PostgreSQL processes query
  │  └─ Reads/writes to postgres_data volume
  ├─ Returns result to FastAPI
  └─ FastAPI returns JSON to client
```

## Container Lifecycle

### Startup Sequence

```
1. docker compose up --build -d
   ├─ Build frontend image
   │  ├─ npm install
   │  └─ npm run build → produces /app/dist
   ├─ Build backend image
   │  └─ pip install -r requirements.txt
   ├─ Pull PostgreSQL image (already built)
   └─ Start containers in order:

2. Database container starts first (no dependencies)
   ├─ PostgreSQL initializes
   ├─ Waits 10s
   ├─ Health check: pg_isready
   ├─ Status: Up (healthy) ✓

3. Backend container starts (depends_on: db health)
   ├─ Connects to database
   ├─ Initializes FastAPI app
   ├─ Uvicorn starts listening on :8000
   ├─ Status: Up ✓

4. Frontend container starts (depends_on: api)
   ├─ Nginx loads configuration
   ├─ Nginx starts listening on :4173
   ├─ Health check: wget http://localhost:4173/
   └─ Status: Up (healthy) ✓

Total startup time: 15-30 seconds (first run)
```

### Shutdown Sequence

```
docker compose down

1. Signal all containers (SIGTERM)
   ├─ Frontend (Nginx) stops listening
   ├─ Backend (FastAPI) closes connections
   └─ Database (PostgreSQL) flushes to disk

2. Wait graceful shutdown (default 10s)
   └─ If not stopped, force stop (SIGKILL)

3. Remove stopped containers
   └─ Keep volumes (postgres_data persists)

Data persistence: ✓ postgres_data volume still exists
```

### Restart Behavior

```
Container crash or restart

Each service configured: restart: unless-stopped

Scenario 1: Backend crashes
├─ Docker restarts container automatically
├─ Backend reconnects to database
├─ Frontend still works (retry API calls)
└─ User may see temporary loading state

Scenario 2: Database crashes
├─ Docker restarts container automatically
├─ Backend reconnects when ready
├─ Frontend requests fail temporarily
└─ Backend returns error responses

Scenario 3: Frontend crashes
├─ Docker restarts container automatically
├─ User must refresh browser
└─ Static assets still cached locally
```

## Network Communication

### Service Discovery (DNS)

Inside `app-network` bridge:

```
Service Name    Internal DNS     IP Address (assigned by Docker)
─────────────────────────────────────────────────
frontend       frontend:4173    172.20.0.2 (example)
api            api:8000        172.20.0.3 (example)
db             db:5432         172.20.0.4 (example)
```

### Nginx → Backend Proxy

```yaml
# In nginx.conf
upstream api_backend {
    server api:8000;  # Resolves to backend container via DNS
}

location /api/ {
    proxy_pass http://api_backend/;  # Forwards request to backend
}
```

### Backend → Database Connection

```python
# In FastAPI backend
DATABASE_URL = "postgresql+asyncpg://ai_cost_user:password@db:5432/ai_cloud_cost_detective"
# db:5432 resolves to database container via Docker DNS
```

## Storage & Persistence

### Database Volume

```
├─ Type: Docker Named Volume
├─ Name: cloud-cost-optimaizer_postgres_data
├─ Driver: local
├─ Mount point in container: /var/lib/postgresql/data
└─ Host location: /var/lib/docker/volumes/...
    └─ Contains: PostgreSQL files, databases, tables, indexes
```

**Persistence**:
- ✓ Survives container restart
- ✓ Survives container stop/start
- ✗ Removed with `docker compose down -v`

### Frontend Build Artifacts

```
├─ Type: Docker image layer (read-only)
├─ Contents: /app/dist/
│  ├─ index.html
│  ├─ main-<hash>.js
│  ├─ vendor-<hash>.js
│  └─ style-<hash>.css
└─ Served by Nginx from /usr/share/nginx/html/
```

**Persistence**:
- Stored in Docker image
- Rebuilt on `docker compose up --build`
- Cache disabled with `docker compose build --no-cache`

## Port Mapping

### Host Machine → Container

```
┌─────────────────────────────────────────┐
│   Host Machine (Linux)                  │
│                                         │
│   localhost:4173 ─┐                     │
│                   ├─→ Docker Bridge     │
│   localhost:8000 ─┤   172.20.0.0/16     │
│                   │                     │
│   localhost:5432 ─┘                     │
│                                         │
│   ┌─────────────────────────────────┐   │
│   │ app-network                     │   │
│   │                                 │   │
│   │ ├─ 172.20.0.2:4173 (frontend)  │   │
│   │ ├─ 172.20.0.3:8000 (api)       │   │
│   │ └─ 172.20.0.4:5432 (db)        │   │
│   └─────────────────────────────────┘   │
│                                         │
└─────────────────────────────────────────┘
```

## Performance Characteristics

### Frontend (Nginx)

```
Request Type          Typical Response Time
────────────────────────────────────
Initial HTML          50-200ms
Static JS/CSS         10-50ms (cached)
API Call              Depends on backend
    ├─ Simple query   50-200ms
    └─ Complex query  200-2000ms
```

### Caching Strategy

```
Resource              Cache Duration    Cache Location
──────────────────────────────────────────────────────
index.html            None (no-cache)   Memory + Disk
main.js/vendor.js     1 year            Browser + CDN
styles.css            1 year            Browser + CDN
Images/Fonts          1 year            Browser + CDN
API Responses         Depends on API    (no caching)
```

### Compression

```
GZIP enabled for:
├─ text/plain
├─ text/css
├─ text/xml
├─ text/javascript
├─ application/json
├─ application/javascript
├─ application/xml+rss
├─ font/* (woff, woff2, ttf, eot)
└─ image/svg+xml

Compression ratio: ~60-80% reduction for text
```

## Security Model

### Network Isolation

```
┌─ Docker host machine (trusted)
│  ├─ Host OS firewall: open ports 4173, 8000, 5432
│  │
│  └─ Docker app-network (isolated)
│     ├─ Frontend ← can only reach backend via network
│     ├─ Backend ← can only reach database via network
│     └─ Database ← isolated from host/internet
│        └─ Only accessible via docker network
│
└─ External attacker
   ├─ Cannot reach database directly
   ├─ Can reach frontend on :4173
   ├─ Can reach backend on :8000
   └─ Cannot access internal Docker network
```

### Access Control

```
Entry Point: Port 4173 (public)
  ├─ HTTP only (no encryption by default)
  ├─ Can reach /static assets
  ├─ Can reach /api/* (proxied to backend)
  └─ Can reach /docs (proxied to backend)

Backend: Port 8000 (public, behind Nginx in production)
  ├─ Should require authentication
  ├─ Should validate API keys
  └─ Should implement rate limiting

Database: Port 5432 (internal, exposed for development)
  ├─ Requires password (from .env)
  ├─ Limited to Docker network only
  └─ Should be further restricted in production
```

## Disaster Recovery

### Data Loss Scenarios

```
Scenario 1: Container crashes → Automatic restart ✓
- No data loss
- Service briefly unavailable

Scenario 2: Volume corruption → Manual recovery
- Need to restore from backup
- Download backup before corruption
- docker compose exec db psql < backup.sql

Scenario 3: Host machine fails → Complete data loss
- No built-in backup
- Must implement: automated backups, replication

Scenario 4: docker compose down -v → Complete data wipe
- postgres_data volume deleted
- All data lost permanently
- No recovery possible (unless backup exists)
```

### Backup Strategy

```
Before production, implement:
1. Automated daily backups
   └─ docker compose exec db pg_dump > backup-$(date).sql
   
2. Off-site storage
   └─ Upload backups to S3/cloud storage
   
3. Recovery testing
   └─ Periodically restore from backup and verify
   
4. Retention policy
   └─ Keep last 30 days of daily backups
```

---

**Summary**: This architecture provides a complete, containerized, production-ready stack with proper networking, persistence, and scalability considerations.
