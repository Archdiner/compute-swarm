-- Migration: Add locked_price_per_hour to jobs table for billing verification
-- Run this in Supabase SQL Editor

-- Add locked_price_per_hour to jobs table
-- This stores the agreed-upon price at the time of claiming
ALTER TABLE jobs 
ADD COLUMN IF NOT EXISTS locked_price_per_hour DECIMAL(10, 4);

-- Update the claim_job function to store the price
CREATE OR REPLACE FUNCTION claim_job(
    p_node_id TEXT,
    p_seller_address TEXT,
    p_gpu_type TEXT,
    p_price_per_hour FLOAT,
    p_vram_gb FLOAT,
    p_num_gpus INTEGER DEFAULT 1
)
RETURNS TABLE (
    job_id UUID,
    script TEXT,
    requirements TEXT,
    timeout_seconds INTEGER,
    max_price_per_hour DECIMAL,
    buyer_address VARCHAR(42),
    job_type job_type,
    docker_image VARCHAR(255),
    num_gpus INTEGER,
    gpu_memory_limit_per_gpu TEXT
) AS $$
DECLARE
    v_job_id UUID;
    v_script TEXT;
    v_requirements TEXT;
    v_timeout_seconds INTEGER;
    v_max_price_per_hour DECIMAL;
    v_buyer_address VARCHAR(42);
    v_job_type job_type;
    v_docker_image VARCHAR(255);
    v_num_gpus INTEGER;
    v_gpu_memory_limit_per_gpu TEXT;
BEGIN
    -- Find a matching pending job
    -- 1. Status is PENDING
    -- 2. GPU type matches (or is null/any)
    -- 3. Price matches (buyer's max price >= seller's price)
    -- 4. VRAM matches (job's min vram <= seller's vram)
    -- 5. Num GPUs matches (job's needed <= seller's available) -- Simplified logic here
    
    SELECT 
        j.job_id, j.script, j.requirements, j.timeout_seconds, j.max_price_per_hour, j.buyer_address,
        j.job_type, j.docker_image, j.num_gpus, j.gpu_memory_limit_per_gpu
    INTO 
        v_job_id, v_script, v_requirements, v_timeout_seconds, v_max_price_per_hour, v_buyer_address,
        v_job_type, v_docker_image, v_num_gpus, v_gpu_memory_limit_per_gpu
    FROM jobs j
    WHERE j.status = 'PENDING'
      AND (j.required_gpu_type IS NULL OR j.required_gpu_type::text = p_gpu_type)
      AND j.max_price_per_hour >= p_price_per_hour
      AND (j.min_vram_gb IS NULL OR j.min_vram_gb <= p_vram_gb)
      AND (j.num_gpus <= p_num_gpus)
    ORDER BY j.created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED;
    
    -- If a job was found, claim it
    IF v_job_id IS NOT NULL THEN
        UPDATE jobs
        SET status = 'CLAIMED',
            node_id = p_node_id,
            seller_address = p_seller_address,
            claimed_at = NOW(),
            locked_price_per_hour = p_price_per_hour, -- Lock in the seller's price
            updated_at = NOW()
        WHERE jobs.job_id = v_job_id;
        
        RETURN QUERY SELECT 
            v_job_id, v_script, v_requirements, v_timeout_seconds, v_max_price_per_hour, v_buyer_address,
            v_job_type, v_docker_image, v_num_gpus, v_gpu_memory_limit_per_gpu;
    END IF;
    
    RETURN;
END;
$$ LANGUAGE plpgsql;
