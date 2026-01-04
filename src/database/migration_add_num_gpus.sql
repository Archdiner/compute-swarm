-- Migration: Add num_gpus column to jobs and compute_nodes tables
-- Run this in Supabase SQL Editor

-- Add num_gpus column to jobs table
ALTER TABLE jobs 
ADD COLUMN IF NOT EXISTS num_gpus INTEGER DEFAULT 1 CHECK (num_gpus >= 1 AND num_gpus <= 8);

-- Add num_gpus column to compute_nodes table  
ALTER TABLE compute_nodes
ADD COLUMN IF NOT EXISTS num_gpus INTEGER DEFAULT 1 CHECK (num_gpus >= 1);

-- Update the claim_job function to check GPU availability
CREATE OR REPLACE FUNCTION claim_job(
    p_node_id TEXT,
    p_seller_address TEXT,
    p_gpu_type TEXT,
    p_price_per_hour NUMERIC,
    p_vram_gb NUMERIC,
    p_num_gpus INTEGER DEFAULT 1
)
RETURNS TABLE (job_id TEXT, script TEXT, requirements TEXT, timeout_seconds INTEGER, max_price_per_hour NUMERIC, buyer_address TEXT, job_type TEXT, docker_image TEXT) AS $$
DECLARE
    claimed_job RECORD;
BEGIN
    -- Atomically claim the next available job matching seller's capabilities
    UPDATE jobs j
    SET 
        status = 'CLAIMED',
        node_id = p_node_id,
        seller_address = p_seller_address,
        claimed_at = NOW()
    WHERE j.job_id = (
        SELECT j2.job_id
        FROM jobs j2
        WHERE j2.status = 'PENDING'
        AND (j2.required_gpu_type IS NULL OR UPPER(j2.required_gpu_type) = UPPER(p_gpu_type))
        AND j2.max_price_per_hour >= p_price_per_hour
        AND (j2.min_vram_gb IS NULL OR j2.min_vram_gb <= p_vram_gb)
        AND (j2.num_gpus IS NULL OR j2.num_gpus <= p_num_gpus)  -- Check GPU count
        ORDER BY j2.created_at ASC
        LIMIT 1
        FOR UPDATE SKIP LOCKED
    )
    RETURNING j.* INTO claimed_job;
    
    IF claimed_job IS NOT NULL THEN
        RETURN QUERY SELECT 
            claimed_job.job_id,
            claimed_job.script,
            claimed_job.requirements,
            claimed_job.timeout_seconds,
            claimed_job.max_price_per_hour,
            claimed_job.buyer_address,
            COALESCE(claimed_job.job_type, 'batch_job')::TEXT,
            claimed_job.docker_image;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Add index for efficient job claiming by GPU count
CREATE INDEX IF NOT EXISTS idx_jobs_num_gpus ON jobs(num_gpus) WHERE status = 'PENDING';
