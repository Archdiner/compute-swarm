# ComputeSwarm Production Tech Stack

## Core Stack

### Backend Framework
- **FastAPI** - Async-native, type-safe, high-performance
- **Uvicorn** with Gunicorn workers for production (multi-core)
- **Pydantic V2** - Data validation and serialization

### Database
- **PostgreSQL 15+** - Primary datastore
  - ACID compliance for payment tracking
  - JSONB for flexible GPU metadata
  - Connection pooling via SQLAlchemy async
- **Redis 7+** - Caching and session management
  - Node heartbeat tracking (TTL-based)
  - Rate limiting
  - Job queue (optional: use Redis Streams)

### Blockchain/Web3
- **web3.py** - Ethereum interaction
- **eth-account** - Wallet management and signing
- **x402** - Payment protocol SDK
- **Base (L2)** - Primary network (lower fees than mainnet)

### Payment Processing
- **x402 Protocol** - HTTP 402 payment standard
- **USDC** - Stablecoin for settlements
- **EIP-712** - Typed data signing

### Testing
- **pytest** - Test framework
- **pytest-asyncio** - Async test support
- **httpx** - Async HTTP client for testing
- **eth-tester** - Local Ethereum blockchain for tests
- **pytest-cov** - Code coverage
- **Factory Boy** - Test data factories

### Deployment & Infrastructure
- **Docker** - Containerization
- **Docker Compose** - Local multi-service orchestration
- **Gunicorn + Uvicorn workers** - Production ASGI server
- **Nginx** - Reverse proxy and load balancing
- **PostgreSQL + Redis** - Data layer

### Monitoring & Observability
- **structlog** - Structured logging (JSON)
- **Prometheus** - Metrics collection (future)
- **Grafana** - Metrics visualization (future)
- **Sentry** - Error tracking (future)

### CI/CD
- **GitHub Actions** - CI/CD pipeline
- **pytest + coverage** - Automated testing
- **Black + isort + flake8** - Code quality
- **mypy** - Type checking

---

## Architecture Decisions

### Why PostgreSQL over others?
- **ACID compliance** critical for payment tracking
- **JSONB** allows flexible GPU metadata without schema changes
- **Mature ecosystem** with excellent Python support
- **Async SQLAlchemy** for non-blocking queries

### Why Redis?
- **Sub-millisecond latency** for heartbeat checks
- **TTL support** for automatic node cleanup
- **Atomic operations** for rate limiting
- **Pub/Sub** for real-time updates (future WebSocket support)

### Why FastAPI?
- **Async-native** - Essential for I/O-heavy workloads
- **Type safety** - Pydantic integration catches errors early
- **Auto-documentation** - OpenAPI/Swagger out of box
- **Performance** - Comparable to Node.js and Go

### Why Base (L2)?
- **Low fees** (~$0.0001 per transaction vs $1-50 on mainnet)
- **Fast finality** (~2 seconds vs 12-15 seconds on mainnet)
- **Coinbase backing** - Strong x402 support
- **EVM compatible** - Same tooling as Ethereum

---

## Database Schema (PostgreSQL)

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

## Redis Keys

```
# Node heartbeat (TTL: 60s)
heartbeat:{node_id} → timestamp

# Node status cache (TTL: 30s)
node:{node_id} → JSON

# Rate limiting (TTL: 60s)
ratelimit:{ip}:{endpoint} → counter

# Job status cache (TTL: 300s)
job:{job_id} → JSON

# Active jobs by node
node:{node_id}:jobs → SET of job_ids
```

---

## Testing Strategy

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
sqlalchemy[asyncio]==2.0.25
asyncpg==0.29.0  # PostgreSQL async driver
redis[hiredis]==5.0.1
x402>=0.2.1
web3==6.15.0
eth-account==0.10.0
structlog==24.1.0

# Development & Testing
pytest==7.4.4
pytest-asyncio==0.23.3
pytest-cov==4.1.0
httpx==0.26.0
eth-tester==0.9.1b1
factory-boy==3.3.0
black==23.12.1
isort==5.13.2
mypy==1.8.0
```

---

## References

- [FastAPI Production Best Practices](https://render.com/articles/fastapi-production-deployment-best-practices)
- [Testing Async FastAPI](https://testdriven.io/blog/fastapi-crud/)
- [Web3.py Testing Guide](https://github.com/ethereum/web3.py/blob/main/tests/)
- [PostgreSQL for Python](https://www.fullstackpython.com/postgresql.html)
- [Redis Patterns](https://redis.io/docs/manual/patterns/)
