-- Migration: Add gpu_memory_limit_per_gpu and distributed_backend columns to jobs table
-- Run this in Supabase SQL Editor

-- Add gpu_memory_limit_per_gpu column to jobs table
ALTER TABLE jobs 
ADD COLUMN IF NOT EXISTS gpu_memory_limit_per_gpu VARCHAR(20);

-- Add distributed_backend column to jobs table
ALTER TABLE jobs 
ADD COLUMN IF NOT EXISTS distributed_backend VARCHAR(20) CHECK (distributed_backend IN ('ddp', 'horovod', 'none') OR distributed_backend IS NULL);

-- Add resume_from_checkpoint column to jobs table
ALTER TABLE jobs 
ADD COLUMN IF NOT EXISTS resume_from_checkpoint UUID REFERENCES checkpoints(id) ON DELETE SET NULL;

-- Add comment for documentation
COMMENT ON COLUMN jobs.gpu_memory_limit_per_gpu IS 'Per-GPU memory limit (e.g., "8g")';
COMMENT ON COLUMN jobs.distributed_backend IS 'Distributed training backend: ddp, horovod, or none';
COMMENT ON COLUMN jobs.resume_from_checkpoint IS 'Checkpoint ID to resume training from';

