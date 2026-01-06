-- Migration: Add experiment tracking, checkpoints, and model versioning tables
-- Run this in Supabase SQL Editor

-- ============================================================================
-- EXPERIMENTS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS experiments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    buyer_address VARCHAR(42) NOT NULL,
    
    -- Experiment details
    name VARCHAR(255) NOT NULL,
    description TEXT,
    tags TEXT[],  -- Array of tags
    
    -- Hyperparameters (stored as JSONB for flexibility)
    hyperparameters JSONB,
    
    -- Status
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'archived', 'deleted')),
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_buyer_address CHECK (buyer_address ~ '^0x[a-fA-F0-9]{40}$')
);

CREATE INDEX idx_experiments_buyer ON experiments(buyer_address, created_at DESC);
CREATE INDEX idx_experiments_status ON experiments(status) WHERE status = 'active';
CREATE INDEX idx_experiments_tags ON experiments USING GIN(tags);

-- ============================================================================
-- JOB METRICS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS job_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    experiment_id UUID REFERENCES experiments(id) ON DELETE SET NULL,
    
    -- Metric details
    metric_name VARCHAR(100) NOT NULL,
    value DECIMAL(20, 10) NOT NULL,
    step INTEGER,
    epoch INTEGER,
    
    -- Timestamps
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_metric_name CHECK (LENGTH(metric_name) > 0)
);

CREATE INDEX idx_job_metrics_job ON job_metrics(job_id, timestamp);
CREATE INDEX idx_job_metrics_name ON job_metrics(job_id, metric_name, step);
CREATE INDEX idx_job_metrics_experiment ON job_metrics(experiment_id) WHERE experiment_id IS NOT NULL;

-- ============================================================================
-- CHECKPOINTS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS checkpoints (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    experiment_id UUID REFERENCES experiments(id) ON DELETE SET NULL,
    
    -- Checkpoint details
    checkpoint_name VARCHAR(255),
    storage_path TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    checksum VARCHAR(64),  -- SHA256
    
    -- Training state
    epoch INTEGER,
    step INTEGER,
    loss DECIMAL(20, 10),
    metric_values JSONB,  -- Store key metrics at this checkpoint
    
    -- Metadata
    description TEXT,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT positive_file_size CHECK (file_size_bytes > 0)
);

CREATE INDEX idx_checkpoints_job ON checkpoints(job_id, created_at DESC);
CREATE INDEX idx_checkpoints_experiment ON checkpoints(experiment_id) WHERE experiment_id IS NOT NULL;
CREATE INDEX idx_checkpoints_epoch ON checkpoints(job_id, epoch DESC);

-- ============================================================================
-- MODELS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS models (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID REFERENCES jobs(job_id) ON DELETE SET NULL,
    experiment_id UUID REFERENCES experiments(id) ON DELETE SET NULL,
    buyer_address VARCHAR(42) NOT NULL,
    
    -- Model details
    name VARCHAR(255) NOT NULL,
    version VARCHAR(50) NOT NULL,  -- Semantic versioning: major.minor.patch
    description TEXT,
    
    -- Model artifacts
    storage_path TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    checksum VARCHAR(64),  -- SHA256
    format VARCHAR(20),  -- pt, pth, safetensors, onnx, h5
    
    -- Model metadata
    architecture VARCHAR(255),
    framework VARCHAR(50),  -- pytorch, tensorflow, onnx, etc.
    metrics JSONB,  -- Key metrics from training
    
    -- Status
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'archived', 'deleted')),
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_buyer_address CHECK (buyer_address ~ '^0x[a-fA-F0-9]{40}$'),
    CONSTRAINT positive_file_size CHECK (file_size_bytes > 0),
    CONSTRAINT unique_model_version UNIQUE (name, version, buyer_address)
);

CREATE INDEX idx_models_buyer ON models(buyer_address, created_at DESC);
CREATE INDEX idx_models_experiment ON models(experiment_id) WHERE experiment_id IS NOT NULL;
CREATE INDEX idx_models_name_version ON models(name, version);
CREATE INDEX idx_models_status ON models(status) WHERE status = 'active';

-- ============================================================================
-- DATASETS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS datasets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    buyer_address VARCHAR(42) NOT NULL,
    
    -- Dataset details
    name VARCHAR(255) NOT NULL,
    description TEXT,
    tags TEXT[],
    
    -- Sharing
    is_public BOOLEAN DEFAULT FALSE,
    
    -- Metadata
    schema_info JSONB,  -- Dataset schema/structure
    total_size_bytes BIGINT DEFAULT 0,
    
    -- Status
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'archived', 'deleted')),
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_buyer_address CHECK (buyer_address ~ '^0x[a-fA-F0-9]{40}$')
);

CREATE INDEX idx_datasets_buyer ON datasets(buyer_address, created_at DESC);
CREATE INDEX idx_datasets_public ON datasets(is_public, status) WHERE is_public = TRUE AND status = 'active';
CREATE INDEX idx_datasets_tags ON datasets USING GIN(tags);

-- ============================================================================
-- DATASET VERSIONS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS dataset_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    
    -- Version details
    version VARCHAR(50) NOT NULL,  -- Semantic versioning
    description TEXT,
    
    -- Storage
    storage_path TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    checksum VARCHAR(64),
    
    -- Metadata
    format VARCHAR(50),  -- csv, json, parquet, etc.
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT positive_file_size CHECK (file_size_bytes > 0),
    CONSTRAINT unique_dataset_version UNIQUE (dataset_id, version)
);

CREATE INDEX idx_dataset_versions_dataset ON dataset_versions(dataset_id, created_at DESC);
CREATE INDEX idx_dataset_versions_version ON dataset_versions(dataset_id, version);

-- ============================================================================
-- ADD EXPERIMENT_ID TO JOBS TABLE
-- ============================================================================

ALTER TABLE jobs 
ADD COLUMN IF NOT EXISTS experiment_id UUID REFERENCES experiments(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_jobs_experiment ON jobs(experiment_id) WHERE experiment_id IS NOT NULL;

-- ============================================================================
-- TRIGGERS FOR UPDATED_AT
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_experiments_updated_at BEFORE UPDATE ON experiments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_models_updated_at BEFORE UPDATE ON models
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_datasets_updated_at BEFORE UPDATE ON datasets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

