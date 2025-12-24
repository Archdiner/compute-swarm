-- ComputeSwarm Database Schema for Supabase
-- Queue-based job management system

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Job States: PENDING -> CLAIMED -> EXECUTING -> COMPLETED/FAILED/CANCELLED
CREATE TYPE job_status AS ENUM (
    'PENDING',      -- Job submitted, waiting to be claimed
    'CLAIMED',      -- Seller has claimed the job
    'EXECUTING',    -- Job is currently running
    'COMPLETED',    -- Job finished successfully
    'FAILED',       -- Job execution failed
    'CANCELLED'     -- Job cancelled by buyer
);

CREATE TYPE gpu_type AS ENUM ('CUDA', 'MPS', 'CPU');

-- Compute Nodes (Sellers)
CREATE TABLE compute_nodes (
    node_id VARCHAR(64) PRIMARY KEY,
    seller_address VARCHAR(42) NOT NULL,

    -- GPU Information
    gpu_type gpu_type NOT NULL,
    device_name VARCHAR(255) NOT NULL,
    vram_gb DECIMAL(6,2),
    compute_capability VARCHAR(10),

    -- Pricing
    price_per_hour DECIMAL(10,2) NOT NULL,

    -- Status
    is_available BOOLEAN DEFAULT true,
    last_heartbeat TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Indexes
    CONSTRAINT valid_seller_address CHECK (seller_address ~ '^0x[a-fA-F0-9]{40}$'),
    CONSTRAINT positive_price CHECK (price_per_hour >= 0)
);

CREATE INDEX idx_nodes_available ON compute_nodes(is_available, gpu_type, price_per_hour);
CREATE INDEX idx_nodes_seller ON compute_nodes(seller_address);
CREATE INDEX idx_nodes_heartbeat ON compute_nodes(last_heartbeat);

-- Jobs Queue
CREATE TABLE jobs (
    job_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    buyer_address VARCHAR(42) NOT NULL,

    -- Job Details
    script TEXT NOT NULL,
    requirements TEXT,  -- Python requirements (optional)
    max_price_per_hour DECIMAL(10,2) NOT NULL,
    timeout_seconds INTEGER DEFAULT 3600,

    -- GPU Requirements (optional filters)
    required_gpu_type gpu_type,
    min_vram_gb DECIMAL(6,2),

    -- Assignment
    node_id VARCHAR(64),
    seller_address VARCHAR(42),
    claimed_at TIMESTAMP WITH TIME ZONE,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,

    -- Status
    status job_status DEFAULT 'PENDING' NOT NULL,

    -- Results
    result_output TEXT,
    result_error TEXT,
    exit_code INTEGER,

    -- Payment
    execution_duration_seconds DECIMAL(10,2),
    total_cost_usd DECIMAL(10,4),
    payment_tx_hash VARCHAR(66),

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_buyer_address CHECK (buyer_address ~ '^0x[a-fA-F0-9]{40}$'),
    CONSTRAINT positive_max_price CHECK (max_price_per_hour >= 0),
    CONSTRAINT positive_timeout CHECK (timeout_seconds > 0),
    CONSTRAINT valid_node_assignment CHECK (
        (status = 'PENDING' AND node_id IS NULL) OR
        (status != 'PENDING' AND node_id IS NOT NULL)
    ),
    FOREIGN KEY (node_id) REFERENCES compute_nodes(node_id) ON DELETE SET NULL
);

-- Critical indexes for queue operations
CREATE INDEX idx_jobs_queue ON jobs(status, created_at) WHERE status = 'PENDING';
CREATE INDEX idx_jobs_claiming ON jobs(status, required_gpu_type, max_price_per_hour) WHERE status = 'PENDING';
CREATE INDEX idx_jobs_buyer ON jobs(buyer_address, created_at DESC);
CREATE INDEX idx_jobs_seller ON jobs(seller_address, status);
CREATE INDEX idx_jobs_node ON jobs(node_id, status);
CREATE INDEX idx_jobs_status ON jobs(status, updated_at DESC);

-- Job State Transition Log (for audit trail)
CREATE TABLE job_state_transitions (
    id BIGSERIAL PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    from_status job_status,
    to_status job_status NOT NULL,
    node_id VARCHAR(64),
    reason TEXT,
    transitioned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT different_states CHECK (from_status IS DISTINCT FROM to_status)
);

CREATE INDEX idx_transitions_job ON job_state_transitions(job_id, transitioned_at);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_compute_nodes_updated_at BEFORE UPDATE ON compute_nodes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_jobs_updated_at BEFORE UPDATE ON jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Trigger to log state transitions
CREATE OR REPLACE FUNCTION log_job_state_transition()
RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'UPDATE' AND OLD.status IS DISTINCT FROM NEW.status) THEN
        INSERT INTO job_state_transitions (job_id, from_status, to_status, node_id)
        VALUES (NEW.job_id, OLD.status, NEW.status, NEW.node_id);
    ELSIF (TG_OP = 'INSERT') THEN
        INSERT INTO job_state_transitions (job_id, from_status, to_status, node_id)
        VALUES (NEW.job_id, NULL, NEW.status, NULL);
    END IF;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER log_job_transitions AFTER INSERT OR UPDATE ON jobs
    FOR EACH ROW EXECUTE FUNCTION log_job_state_transition();

-- Function to claim next available job (atomic operation)
CREATE OR REPLACE FUNCTION claim_job(
    p_node_id VARCHAR(64),
    p_seller_address VARCHAR(42),
    p_gpu_type gpu_type,
    p_price_per_hour DECIMAL(10,2),
    p_vram_gb DECIMAL(6,2)
)
RETURNS TABLE (
    job_id UUID,
    script TEXT,
    requirements TEXT,
    timeout_seconds INTEGER,
    max_price_per_hour DECIMAL(10,2)
) AS $$
DECLARE
    v_job_id UUID;
BEGIN
    -- Find and claim the best matching job atomically
    SELECT j.job_id INTO v_job_id
    FROM jobs j
    WHERE j.status = 'PENDING'
      AND j.max_price_per_hour >= p_price_per_hour
      AND (j.required_gpu_type IS NULL OR j.required_gpu_type = p_gpu_type)
      AND (j.min_vram_gb IS NULL OR j.min_vram_gb <= p_vram_gb)
    ORDER BY j.created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED;  -- Critical: prevents race conditions

    IF v_job_id IS NOT NULL THEN
        UPDATE jobs
        SET status = 'CLAIMED',
            node_id = p_node_id,
            seller_address = p_seller_address,
            claimed_at = NOW()
        WHERE jobs.job_id = v_job_id;

        RETURN QUERY
        SELECT j.job_id, j.script, j.requirements, j.timeout_seconds, j.max_price_per_hour
        FROM jobs j
        WHERE j.job_id = v_job_id;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Function to clean up stale claims (jobs claimed but never started)
CREATE OR REPLACE FUNCTION release_stale_claims(stale_minutes INTEGER DEFAULT 5)
RETURNS INTEGER AS $$
DECLARE
    affected_rows INTEGER;
BEGIN
    UPDATE jobs
    SET status = 'PENDING',
        node_id = NULL,
        seller_address = NULL,
        claimed_at = NULL
    WHERE status = 'CLAIMED'
      AND claimed_at < NOW() - (stale_minutes || ' minutes')::INTERVAL;

    GET DIAGNOSTICS affected_rows = ROW_COUNT;
    RETURN affected_rows;
END;
$$ LANGUAGE plpgsql;

-- Function to clean up stale executing jobs (hung jobs)
CREATE OR REPLACE FUNCTION mark_stale_executions_failed(timeout_multiplier DECIMAL DEFAULT 2.0)
RETURNS INTEGER AS $$
DECLARE
    affected_rows INTEGER;
BEGIN
    UPDATE jobs
    SET status = 'FAILED',
        result_error = 'Job execution timed out (no updates from seller)',
        completed_at = NOW()
    WHERE status = 'EXECUTING'
      AND started_at < NOW() - (timeout_seconds * timeout_multiplier || ' seconds')::INTERVAL;

    GET DIAGNOSTICS affected_rows = ROW_COUNT;
    RETURN affected_rows;
END;
$$ LANGUAGE plpgsql;

-- View for queue statistics
CREATE OR REPLACE VIEW queue_stats AS
SELECT
    status,
    COUNT(*) as job_count,
    AVG(max_price_per_hour) as avg_max_price,
    MIN(created_at) as oldest_job,
    MAX(created_at) as newest_job
FROM jobs
GROUP BY status;

-- View for active sellers
CREATE OR REPLACE VIEW active_sellers AS
SELECT
    node_id,
    seller_address,
    gpu_type,
    device_name,
    price_per_hour,
    is_available,
    last_heartbeat,
    NOW() - last_heartbeat as time_since_heartbeat
FROM compute_nodes
WHERE last_heartbeat > NOW() - INTERVAL '5 minutes'
ORDER BY gpu_type, price_per_hour;
