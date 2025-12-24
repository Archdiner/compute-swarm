# ComputeSwarm Production Tech Stack

## Core Stack (100% Free Tier)

### Backend Framework
- **FastAPI** - Async-native, type-safe, high-performance
- **Uvicorn** with Gunicorn workers for production
- **Pydantic V2** - Data validation and serialization

### Database
- **Supabase** - Managed PostgreSQL with real-time features
  - **Free Tier**: 500MB database, 2GB bandwidth/month, 50,000 monthly active users
  - Built-in auth, real-time subscriptions, storage
  - PostgreSQL 15+ under the hood
  - Connection pooling included
  - Row-level security (RLS)
  - Auto-generated REST API

### Caching & Queue
- **Upstash Redis** - Serverless Redis (free tier)
  - **Free Tier**: 10,000 commands/day
  - Global edge caching
  - Durable storage
  - No cold starts
- **Alternative**: Supabase Edge Functions + PostgreSQL for simple caching

### Blockchain/Web3
- **web3.py** - Ethereum interaction (free, open source)
- **eth-account** - Wallet management (free)
- **x402** - Payment protocol SDK (free)
- **Base Sepolia** - L2 testnet (free, no gas fees on testnet)
- **Base Mainnet** - L2 production (very low fees, ~$0.0001/tx)

### Payment Processing
- **x402 Protocol** - HTTP 402 standard (free SDK)
- **USDC** - Stablecoin for settlements (free to use)
- **EIP-712** - Typed data signing (free standard)

### Testing
- **pytest** - Test framework (free)
- **pytest-asyncio** - Async support (free)
- **httpx** - HTTP client (free)
- **eth-tester** - Local Ethereum blockchain (free)
- **pytest-cov** - Code coverage (free)
- **Factory Boy** - Test data factories (free)

### Deployment & Infrastructure
- **Render** - Free tier hosting
  - **Free Tier**: 750 hours/month, auto-sleep after inactivity
  - Native support for FastAPI
  - Auto SSL certificates
- **Alternative**: Railway (500 hours/month free)
- **Alternative**: Fly.io (3 shared VMs free)
- **Docker** - Containerization (free)

### Monitoring & Observability
- **structlog** - Structured logging (free)
- **Sentry** - Error tracking (free tier: 5K errors/month)
- **BetterStack** - Free logs (1GB/month)

### CI/CD
- **GitHub Actions** - Free for public repos, 2000 min/month private
- **pytest + coverage** - Automated testing (free)

---

## Cost Breakdown (Monthly)

| Service | Free Tier | Paid (if needed) |
|---------|-----------|------------------|
| Supabase | 500MB DB, 2GB bandwidth | $25/month (8GB DB) |
| Upstash Redis | 10K commands/day | $0.20/100K commands |
| Render Hosting | 750 hours/month | $7/month (always-on) |
| Base Sepolia | Free (testnet) | N/A |
| Base Mainnet | Pay per tx (~$0.0001) | Variable |
| GitHub Actions | 2000 min/month | $0.008/minute |
| Sentry | 5K errors/month | $26/month |

**Total for MVP**: $0/month (all free tiers)
**Total for production**: ~$32/month (Supabase + Render always-on)

---

## Why Supabase over Self-Hosted PostgreSQL?

1. **Zero DevOps** - No need to manage database servers
2. **Free Tier** - 500MB database is enough for MVP (thousands of jobs)
3. **Built-in Features** - Auth, real-time, storage included
4. **Auto-scaling** - Handles traffic spikes automatically
5. **Backups** - Daily backups included in free tier
6. **Global CDN** - Edge caching for read queries
7. **Dashboard** - Visual database management
8. **SQL Editor** - Built-in query tool

### Why Upstash Redis?

1. **Serverless** - Pay only for what you use
2. **Free Tier** - 10K commands/day covers dev + light production
3. **Global** - Edge locations for low latency
4. **Durable** - Persistent storage (not just cache)
5. **No Cold Starts** - Always ready

### Why Render for Hosting?

1. **Free Tier** - 750 hours/month (enough for 24/7 with sleep)
2. **Zero Config** - Detects FastAPI automatically
3. **Auto SSL** - Free HTTPS certificates
4. **Git Deploy** - Push to deploy
5. **Health Checks** - Auto-restart on failure

---

## Database Schema (Supabase/PostgreSQL)

### Tables

```sql
-- Compute nodes registered in marketplace
CREATE TABLE nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seller_address VARCHAR(42) NOT NULL,
    gpu_info JSONB NOT NULL,
    price_per_hour DECIMAL(10,2) NOT NULL,
    endpoint VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'available',
    registered_at TIMESTAMP DEFAULT NOW(),
    last_heartbeat TIMESTAMP DEFAULT NOW(),
    total_jobs INT DEFAULT 0,
    total_compute_hours DECIMAL(10,2) DEFAULT 0,
    INDEX idx_status (status),
    INDEX idx_seller (seller_address)
);

-- Jobs submitted to nodes
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    buyer_address VARCHAR(42) NOT NULL,
    node_id UUID REFERENCES nodes(id),
    job_type VARCHAR(50) NOT NULL,
    script TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    output TEXT,
    error TEXT,
    cost_usd DECIMAL(10,6),
    payment_tx_hash VARCHAR(66),
    INDEX idx_buyer (buyer_address),
    INDEX idx_node (node_id),
    INDEX idx_status (status)
);

-- Payment records for auditing
CREATE TABLE payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES jobs(id),
    from_address VARCHAR(42) NOT NULL,
    to_address VARCHAR(42) NOT NULL,
    amount_usdc DECIMAL(18,6) NOT NULL,
    tx_hash VARCHAR(66) UNIQUE NOT NULL,
    network VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    confirmed_at TIMESTAMP,
    INDEX idx_tx_hash (tx_hash),
    INDEX idx_job (job_id)
);
```

---

## Upstash Redis Keys

```python
# Node heartbeat (TTL: 60s)
heartbeat:{node_id} → timestamp

# Rate limiting (TTL: 60s)
ratelimit:{ip}:{endpoint} → counter

# Job status cache (TTL: 300s)
job:{job_id} → JSON

# Note: Use Supabase for persistent data, Upstash only for caching/rate limiting
```

---

## Supabase Configuration

### Setup

```bash
# 1. Create project at supabase.com
# 2. Get connection string from project settings
# 3. Add to .env

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key
DATABASE_URL=postgresql://postgres:[password]@db.your-project.supabase.co:5432/postgres
```

### Python Client

```python
from supabase import create_client, Client

supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_ANON_KEY")
)

# Insert data
data = supabase.table("nodes").insert({
    "seller_address": "0x123...",
    "gpu_info": {"type": "cuda", "vram": 24},
    "price_per_hour": 2.00
}).execute()

# Query data
nodes = supabase.table("nodes").select("*").eq("status", "available").execute()
```

### Real-time Subscriptions (Bonus)

```python
# Subscribe to new jobs
def handle_new_job(payload):
    print(f"New job: {payload}")

supabase.table("jobs").on("INSERT", handle_new_job).subscribe()
```

---

## Upstash Redis Setup

```bash
# 1. Create database at upstash.com
# 2. Get REST URL and token
# 3. Add to .env

UPSTASH_REDIS_REST_URL=https://your-db.upstash.io
UPSTASH_REDIS_REST_TOKEN=your-token
```

### Python Client

```python
from upstash_redis import Redis

redis = Redis(
    url=os.getenv("UPSTASH_REDIS_REST_URL"),
    token=os.getenv("UPSTASH_REDIS_REST_TOKEN")
)

# Set with TTL
redis.setex("heartbeat:node_123", 60, "2025-01-01T12:00:00")

# Get
heartbeat = redis.get("heartbeat:node_123")

# Increment (rate limiting)
count = redis.incr("ratelimit:192.168.1.1:/api/v1/jobs")
redis.expire("ratelimit:192.168.1.1:/api/v1/jobs", 60)
```

---

## Deployment Architecture

### Development (Free)
```
Local Machine
├── FastAPI app (localhost:8000)
├── Supabase (cloud, free tier)
└── Upstash Redis (cloud, free tier)
```

### Production (Free Tier)
```
Render (free tier)
  └── FastAPI app (auto-sleep after 15min inactivity)
Supabase (free tier)
  └── PostgreSQL database
Upstash Redis (free tier)
  └── Caching & rate limiting
GitHub Actions (free)
  └── CI/CD pipeline
```

### Production (Paid, ~$32/month)
```
Render ($7/month, always-on)
  ├── FastAPI instance 1
  └── FastAPI instance 2 (load balanced)
Supabase ($25/month, 8GB)
  └── PostgreSQL with backups
Upstash Redis ($0-5/month)
  └── Pro tier with more commands
Sentry (free tier)
  └── Error tracking
```

### Unit Tests
- Individual functions and classes
- Mock external dependencies (DB, blockchain, HTTP)
- Fast (<1ms per test)

### Integration Tests
- API endpoints with test database
- Database transactions (rollback after each test)
- Mock blockchain with eth-tester

### Contract Tests
- x402 payment flow
- Real USDC transfers on testnet
- End-to-end job execution

### Load Tests (Future)
- Locust or K6
- Simulate 100+ concurrent jobs
- Identify bottlenecks

---

## Deployment Architecture

### Development
```
docker-compose.dev.yml
├── marketplace (FastAPI)
├── postgres (PostgreSQL 15)
├── redis (Redis 7)
└── seller-agent (Python)
```

### Production
```
nginx (reverse proxy)
  ├── marketplace-1 (Gunicorn + Uvicorn workers)
  ├── marketplace-2 (Gunicorn + Uvicorn workers)
  └── ...
PostgreSQL (managed: AWS RDS / Render)
Redis (managed: AWS ElastiCache / Upstash)
Seller agents (distributed, user-run)
```

---

## Configuration Management

### Environment-based configs
```python
# config/settings.py
class Settings(BaseSettings):
    # Auto-loads from .env, supports multiple environments
    environment: Literal["dev", "test", "prod"] = "dev"
    database_url: PostgresDsn
    redis_url: RedisDsn
    ...
```

### Secrets Management
- **Development**: `.env` file (git-ignored)
- **Production**: Environment variables or secret manager
- **Never commit**: Private keys, API secrets

---

## Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| API Response Time | <100ms | p95 for discovery endpoints |
| Job Submission | <200ms | Excluding payment verification |
| Payment Verification | <2s | Blockchain confirmation time |
| Node Registration | <50ms | In-memory + DB write |
| Heartbeat Processing | <10ms | Redis-cached |
| Concurrent Jobs | 1000+ | Per marketplace instance |
| Database Connections | 20-50 | Pool size based on load |

---

## Security Considerations

### Authentication
- **Wallet signatures** for seller registration
- **Payment proofs** for buyer authentication
- **No passwords** - cryptographic auth only

### Rate Limiting
- **10 req/min** per IP for discovery
- **1 req/min** per IP for job submission
- **Redis-based** sliding window

### Input Validation
- **Pydantic models** for all inputs
- **SQL injection prevention** via SQLAlchemy parameterization
- **Script sandboxing** via Docker (Phase 2)

### Payment Security
- **EIP-712 signatures** verified on-chain
- **Replay prevention** via nonces
- **Amount validation** before execution

---

## Migration Path

### Phase 1 (Current): In-Memory
- Dict-based storage for nodes/jobs
- No persistence
- Fast development iteration

### Phase 2 (Day 5-7): PostgreSQL + Redis
- Migrate to real databases
- Add connection pooling
- Implement caching layer

### Phase 3 (Day 8+): Production-Ready
- Multi-region deployment
- Load balancing
- Monitoring and alerting

---

## Dependencies Summary

```txt
# Production
fastapi==0.109.0
uvicorn[standard]==0.27.0
gunicorn==21.2.0
pydantic==2.5.3
pydantic-settings==2.1.0

# Database
supabase==2.3.4  # Supabase Python client
upstash-redis==0.15.0  # Upstash Redis client

# HTTP Client
httpx==0.26.0

# GPU Compute
torch==2.1.2
torchvision==0.16.2

# Blockchain & Payments
web3==6.15.0
eth-account==0.10.0
x402>=0.2.1

# Logging
structlog==24.1.0

# Configuration
python-dotenv==1.0.0

# CLI
rich==13.7.0

# Performance
uvloop==0.19.0

# Development & Testing
pytest==7.4.4
pytest-asyncio==0.23.3
pytest-cov==4.1.0
pytest-mock==3.12.0
factory-boy==3.3.0
eth-tester==0.10.0b4
black==23.12.1
isort==5.13.2
flake8==7.0.0
mypy==1.8.0
ipython==8.18.1
```

---

## References

- [FastAPI Production Best Practices](https://render.com/articles/fastapi-production-deployment-best-practices)
- [Testing Async FastAPI](https://testdriven.io/blog/fastapi-crud/)
- [Web3.py Testing Guide](https://github.com/ethereum/web3.py/blob/main/tests/)
- [PostgreSQL for Python](https://www.fullstackpython.com/postgresql.html)
- [Redis Patterns](https://redis.io/docs/manual/patterns/)
