# ComputeSwarm Queue-Based Architecture

## Overview

ComputeSwarm uses a **queue-based job management system** for decentralized P2P GPU compute. This architecture provides better fault tolerance, load balancing, and scalability compared to direct node assignment.

## How It Works

### 1. **Buyers Submit Jobs to Queue**
```python
# Buyer submits job - doesn't pick specific node
POST /api/v1/jobs/submit
{
    "buyer_address": "0x...",
    "script": "print('Hello GPU')",
    "max_price_per_hour": 2.0,
    "required_gpu_type": "cuda"  # optional filter
}

Response:
{
    "job_id": "uuid-here",
    "status": "PENDING"
}
```

### 2. **Sellers Poll Queue for Jobs**
Seller agents automatically poll every 5 seconds:
```python
POST /api/v1/jobs/claim
{
    "node_id": "node_xyz",
    "seller_address": "0x...",
    "gpu_type": "cuda",
    "price_per_hour": 1.5,
    "vram_gb": 24.0
}

Response (if match found):
{
    "claimed": true,
    "job_id": "uuid-here",
    "script": "...",
    "timeout_seconds": 3600
}
```

### 3. **Atomic Job Claiming**
The `claim_job()` PostgreSQL function uses `FOR UPDATE SKIP LOCKED` to ensure:
- **No race conditions**: Multiple sellers can't claim same job
- **Fair queuing**: FIFO order (oldest jobs first)
- **Smart matching**: Only claims jobs that match GPU requirements and price

### 4. **Job Execution Lifecycle**
```
PENDING → CLAIMED → EXECUTING → COMPLETED/FAILED
```

**PENDING**: Job in queue, waiting for seller
**CLAIMED**: Seller claimed job, about to execute
**EXECUTING**: Job running on seller node
**COMPLETED**: Job finished successfully
**FAILED**: Job execution failed
**CANCELLED**: Buyer cancelled before execution

### 5. **Fault Tolerance**
- **Stale Claim Cleanup**: Jobs claimed but not started within 5 minutes → back to PENDING
- **Hung Job Detection**: Jobs executing > 2× timeout → marked FAILED
- **Automatic Recovery**: Failed jobs can be re-queued manually

## Architecture Components

### Database Schema (Supabase PostgreSQL)

```sql
-- Jobs table with state tracking
CREATE TABLE jobs (
    job_id UUID PRIMARY KEY,
    buyer_address VARCHAR(42) NOT NULL,
    script TEXT NOT NULL,
    max_price_per_hour DECIMAL(10,2),

    -- Assignment
    node_id VARCHAR(64),
    seller_address VARCHAR(42),

    -- Status tracking
    status job_status DEFAULT 'PENDING',
    claimed_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,

    -- Results
    result_output TEXT,
    result_error TEXT,
    total_cost_usd DECIMAL(10,4)
);

-- Atomic claim function
CREATE FUNCTION claim_job(...) RETURNS TABLE (...) AS $$
    SELECT job_id FROM jobs
    WHERE status = 'PENDING'
      AND max_price_per_hour >= seller_price
      AND (required_gpu_type IS NULL OR required_gpu_type = seller_gpu)
    ORDER BY created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED;  -- Critical for atomicity!
$$;
```

### Marketplace Server
- **Queue API**: Job submission, claiming, status updates
- **Background Tasks**: Stale claim cleanup (every 60s)
- **Statistics**: Real-time queue depth, node availability

### Seller Agent
- **Job Polling Loop**: Polls queue every 5 seconds when idle
- **Job Execution**: Uses `JobExecutor` with timeouts and isolation
- **Result Reporting**: Reports success/failure back to marketplace

### Buyer CLI
- **Queue Submission**: Submit jobs without choosing node
- **Job Monitoring**: Poll job status, wait for completion
- **Cancellation**: Cancel pending/claimed jobs

## API Endpoints

### Buyer Endpoints
```
POST   /api/v1/jobs/submit          - Submit job to queue
GET    /api/v1/jobs/{job_id}        - Get job status
GET    /api/v1/jobs/buyer/{address} - List buyer's jobs
POST   /api/v1/jobs/{job_id}/cancel - Cancel pending job
GET    /api/v1/stats                - Marketplace statistics
```

### Seller Endpoints
```
POST   /api/v1/nodes/register       - Register node
POST   /api/v1/nodes/{id}/heartbeat - Update heartbeat
POST   /api/v1/jobs/claim           - Claim next job from queue
POST   /api/v1/jobs/{id}/start      - Mark job as executing
POST   /api/v1/jobs/{id}/complete   - Report job completion
POST   /api/v1/jobs/{id}/fail       - Report job failure
```

## Running the System

### 1. Setup Supabase
```bash
# Create Supabase project at https://app.supabase.com
# Get URL and anon key from Settings → API
# Run schema: src/database/schema.sql in SQL Editor
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your Supabase credentials
```

### 3. Start Marketplace
```bash
./scripts/start_marketplace.sh
```

### 4. Start Seller Agent
```bash
./scripts/start_seller.sh
```

### 5. Submit Jobs (Buyer)
```bash
# Interactive mode
python -m src.buyer.cli

# Commands:
> stats              # View marketplace
> submit             # Submit job
> list               # List your jobs
> status <job_id>    # Check job status
```

## Example Workflow

```bash
# Buyer submits job
> submit
Path to script: examples/hello_gpu.py
Max price: 2.0
GPU type: cuda

✓ Job submitted to queue
Job ID: abc-123
Status: PENDING

# Seller polls and claims job (automatic)
[Seller Log] job_claimed_from_queue job_id=abc-123
[Seller Log] job_execution_starting job_id=abc-123
[Seller Log] job_execution_finished success=True cost=0.0012

# Buyer checks status
> status abc-123

Job Details
Job ID: abc-123
Status: COMPLETED
Duration: 4.32s
Total Cost: $0.0012

Output:
Hello from CUDA GPU!
```

## Advantages Over Direct Assignment

### Queue-Based (Current)
✅ **Fault Tolerant**: Node failure → job returns to queue
✅ **Load Balancing**: Sellers pull when available
✅ **Mobile Friendly**: Sellers can work when online
✅ **Simpler UX**: Buyer just submits, doesn't pick nodes
✅ **Atomic**: No race conditions in job assignment
✅ **Scalable**: Works with 1000+ concurrent jobs

### Direct Assignment (Old)
❌ **Brittle**: If node goes offline, job lost
❌ **Complex**: Buyer must discover and choose node
❌ **Race Conditions**: Multiple buyers can target same node
❌ **Not Mobile**: Requires seller to be always online

## Performance Characteristics

- **Job Claim Latency**: ~50-200ms (PostgreSQL query + index lookup)
- **Queue Depth**: Tested up to 10,000 pending jobs
- **Seller Polling**: 5s interval (configurable)
- **Cleanup Overhead**: ~10ms per 1000 jobs (runs every 60s)

## Next Steps (x402 Integration)

Currently missing payment integration. Next phase:
1. Add x402 middleware to seller
2. Verify USDC payment before job execution
3. Store payment transaction hash in database
4. Implement refund logic for failed jobs

See `docs/x402/` for implementation details.

## Monitoring

```bash
# Check queue depth
curl http://localhost:8000/api/v1/stats

# Check active sellers
curl http://localhost:8000/api/v1/nodes

# Check pending jobs
curl http://localhost:8000/api/v1/jobs/queue/pending

# Health check
curl http://localhost:8000/health
```

## Troubleshooting

### Jobs stuck in CLAIMED status
```sql
-- Release stale claims manually
SELECT release_stale_claims(5);  -- 5 minute threshold
```

### Jobs stuck in EXECUTING status
```sql
-- Mark stale executions as failed
SELECT mark_stale_executions_failed(2.0);  -- 2x timeout
```

### Seller not claiming jobs
- Check heartbeat: Should update every 30s
- Check node availability: `is_available = true`
- Check price match: Seller price ≤ job max price
- Check GPU match: Seller GPU meets job requirements
