-- ComputeSwarm Database Schema V2
-- Adds: Seller profiles, ratings, file storage, sessions, job types
-- Run this AFTER schema.sql

-- ============================================================================
-- NEW ENUM TYPES
-- ============================================================================

-- Job types: batch execution, interactive notebook, or custom container
CREATE TYPE job_type AS ENUM ('batch_job', 'notebook_session', 'container_session');

-- Seller verification status
CREATE TYPE verification_status AS ENUM ('unverified', 'pending', 'verified');

-- File types for job attachments
CREATE TYPE file_type AS ENUM ('input', 'output', 'checkpoint', 'model', 'dataset');

-- Session status for notebook/container sessions
CREATE TYPE session_status AS ENUM ('starting', 'running', 'stopping', 'stopped', 'failed');

-- ============================================================================
-- SELLER PROFILES TABLE
-- ============================================================================

CREATE TABLE seller_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    seller_address VARCHAR(42) UNIQUE NOT NULL,
    
    -- GitHub OAuth fields
    github_id BIGINT UNIQUE,
    github_username VARCHAR(255),
    github_avatar_url TEXT,
    github_profile_url TEXT,
    
    -- Verification
    verification_status verification_status DEFAULT 'unverified',
    verified_at TIMESTAMP WITH TIME ZONE,
    
    -- Reputation (calculated from ratings)
    reputation_score DECIMAL(3,2) DEFAULT 0.00,  -- 0.00 to 5.00
    total_ratings INTEGER DEFAULT 0,
    total_jobs_completed INTEGER DEFAULT 0,
    total_earnings_usd DECIMAL(12,2) DEFAULT 0.00,
    
    -- Profile
    display_name VARCHAR(255),
    bio TEXT,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_seller_address CHECK (seller_address ~ '^0x[a-fA-F0-9]{40}$'),
    CONSTRAINT valid_reputation CHECK (reputation_score >= 0 AND reputation_score <= 5)
);

CREATE INDEX idx_seller_profiles_address ON seller_profiles(seller_address);
CREATE INDEX idx_seller_profiles_github ON seller_profiles(github_id);
CREATE INDEX idx_seller_profiles_reputation ON seller_profiles(reputation_score DESC);
CREATE INDEX idx_seller_profiles_verified ON seller_profiles(verification_status) WHERE verification_status = 'verified';

-- ============================================================================
-- SELLER RATINGS TABLE
-- ============================================================================

CREATE TABLE seller_ratings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    buyer_address VARCHAR(42) NOT NULL,
    seller_address VARCHAR(42) NOT NULL,
    
    -- Rating details
    rating INTEGER NOT NULL,  -- 1-5 stars
    comment TEXT,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_rating CHECK (rating >= 1 AND rating <= 5),
    CONSTRAINT valid_buyer_address CHECK (buyer_address ~ '^0x[a-fA-F0-9]{40}$'),
    CONSTRAINT valid_seller_address CHECK (seller_address ~ '^0x[a-fA-F0-9]{40}$'),
    CONSTRAINT one_rating_per_job UNIQUE (job_id)  -- Only one rating per job
);

CREATE INDEX idx_ratings_seller ON seller_ratings(seller_address, created_at DESC);
CREATE INDEX idx_ratings_buyer ON seller_ratings(buyer_address);
CREATE INDEX idx_ratings_job ON seller_ratings(job_id);

-- ============================================================================
-- JOB FILES TABLE
-- ============================================================================

CREATE TABLE job_files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    
    -- File details
    file_type file_type NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    storage_path TEXT NOT NULL,  -- Path in Supabase storage
    file_size_bytes BIGINT NOT NULL,
    mime_type VARCHAR(100),
    checksum VARCHAR(64),  -- SHA256 hash
    
    -- Metadata
    uploaded_by VARCHAR(42) NOT NULL,  -- buyer or seller address
    description TEXT,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,  -- Auto-delete after this time
    
    -- Constraints
    CONSTRAINT valid_uploader CHECK (uploaded_by ~ '^0x[a-fA-F0-9]{40}$'),
    CONSTRAINT positive_file_size CHECK (file_size_bytes > 0)
);

CREATE INDEX idx_files_job ON job_files(job_id);
CREATE INDEX idx_files_type ON job_files(job_id, file_type);
CREATE INDEX idx_files_expires ON job_files(expires_at) WHERE expires_at IS NOT NULL;

-- ============================================================================
-- SESSIONS TABLE (for notebook and container sessions)
-- ============================================================================

CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    node_id VARCHAR(64) NOT NULL REFERENCES compute_nodes(node_id) ON DELETE CASCADE,
    
    -- Session details
    session_type job_type NOT NULL,
    status session_status DEFAULT 'starting',
    
    -- Access
    session_url TEXT,  -- URL to access the session (e.g., Jupyter URL)
    session_token VARCHAR(64),  -- Authentication token
    session_port INTEGER,  -- Port on seller's machine
    
    -- Docker container info
    container_id VARCHAR(64),
    docker_image VARCHAR(255),
    
    -- Timing
    started_at TIMESTAMP WITH TIME ZONE,
    last_heartbeat TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,  -- Session timeout
    stopped_at TIMESTAMP WITH TIME ZONE,
    
    -- Billing
    billed_minutes INTEGER DEFAULT 0,
    total_cost_usd DECIMAL(10,4) DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_session_type CHECK (session_type IN ('notebook_session', 'container_session')),
    CONSTRAINT valid_port CHECK (session_port IS NULL OR (session_port >= 1024 AND session_port <= 65535))
);

CREATE INDEX idx_sessions_job ON sessions(job_id);
CREATE INDEX idx_sessions_node ON sessions(node_id);
CREATE INDEX idx_sessions_status ON sessions(status) WHERE status IN ('starting', 'running');
CREATE INDEX idx_sessions_expires ON sessions(expires_at) WHERE status = 'running';

-- ============================================================================
-- ALTER EXISTING TABLES
-- ============================================================================

-- Add new columns to jobs table
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS job_type job_type DEFAULT 'batch_job';
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS docker_image VARCHAR(255);
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS session_url TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS session_port INTEGER;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS buyer_address_verified BOOLEAN DEFAULT false;

-- Add seller profile reference to compute_nodes
ALTER TABLE compute_nodes ADD COLUMN IF NOT EXISTS seller_profile_id UUID REFERENCES seller_profiles(id);

-- ============================================================================
-- FUNCTIONS
-- ============================================================================

-- Function to calculate seller reputation from ratings
CREATE OR REPLACE FUNCTION calculate_seller_reputation(p_seller_address VARCHAR(42))
RETURNS TABLE (
    reputation_score DECIMAL(3,2),
    total_ratings INTEGER,
    recent_average DECIMAL(3,2)
) AS $$
DECLARE
    v_total_ratings INTEGER;
    v_weighted_sum DECIMAL;
    v_weight_sum DECIMAL;
    v_recent_avg DECIMAL;
BEGIN
    -- Count total ratings
    SELECT COUNT(*) INTO v_total_ratings
    FROM seller_ratings
    WHERE seller_ratings.seller_address = p_seller_address;
    
    IF v_total_ratings = 0 THEN
        RETURN QUERY SELECT 0.00::DECIMAL(3,2), 0, 0.00::DECIMAL(3,2);
        RETURN;
    END IF;
    
    -- Calculate weighted average (more recent = higher weight)
    -- Weight decays by 10% per month
    SELECT 
        SUM(r.rating * POWER(0.9, EXTRACT(EPOCH FROM (NOW() - r.created_at)) / 2592000)),
        SUM(POWER(0.9, EXTRACT(EPOCH FROM (NOW() - r.created_at)) / 2592000))
    INTO v_weighted_sum, v_weight_sum
    FROM seller_ratings r
    WHERE r.seller_address = p_seller_address;
    
    -- Calculate recent average (last 30 days)
    SELECT COALESCE(AVG(r.rating), 0)
    INTO v_recent_avg
    FROM seller_ratings r
    WHERE r.seller_address = p_seller_address
      AND r.created_at > NOW() - INTERVAL '30 days';
    
    RETURN QUERY SELECT 
        ROUND(v_weighted_sum / v_weight_sum, 2)::DECIMAL(3,2),
        v_total_ratings,
        ROUND(v_recent_avg, 2)::DECIMAL(3,2);
END;
$$ LANGUAGE plpgsql;

-- Function to update seller profile reputation
CREATE OR REPLACE FUNCTION update_seller_reputation()
RETURNS TRIGGER AS $$
DECLARE
    v_reputation DECIMAL(3,2);
    v_total INTEGER;
BEGIN
    -- Calculate new reputation
    SELECT cr.reputation_score, cr.total_ratings
    INTO v_reputation, v_total
    FROM calculate_seller_reputation(NEW.seller_address) cr;
    
    -- Update seller profile
    UPDATE seller_profiles
    SET reputation_score = v_reputation,
        total_ratings = v_total,
        updated_at = NOW()
    WHERE seller_address = NEW.seller_address;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update reputation on new rating
CREATE TRIGGER update_reputation_on_rating
    AFTER INSERT ON seller_ratings
    FOR EACH ROW
    EXECUTE FUNCTION update_seller_reputation();

-- Function to clean up expired sessions
CREATE OR REPLACE FUNCTION cleanup_expired_sessions()
RETURNS INTEGER AS $$
DECLARE
    affected_rows INTEGER;
BEGIN
    UPDATE sessions
    SET status = 'stopped',
        stopped_at = NOW()
    WHERE status = 'running'
      AND expires_at < NOW();
    
    GET DIAGNOSTICS affected_rows = ROW_COUNT;
    RETURN affected_rows;
END;
$$ LANGUAGE plpgsql;

-- Function to clean up expired files
CREATE OR REPLACE FUNCTION cleanup_expired_files()
RETURNS INTEGER AS $$
DECLARE
    affected_rows INTEGER;
BEGIN
    DELETE FROM job_files
    WHERE expires_at IS NOT NULL
      AND expires_at < NOW();
    
    GET DIAGNOSTICS affected_rows = ROW_COUNT;
    RETURN affected_rows;
END;
$$ LANGUAGE plpgsql;

-- Function to extend a session
CREATE OR REPLACE FUNCTION extend_session(
    p_job_id UUID,
    p_additional_minutes INTEGER
)
RETURNS BOOLEAN AS $$
DECLARE
    v_updated BOOLEAN;
BEGIN
    UPDATE sessions
    SET expires_at = expires_at + (p_additional_minutes || ' minutes')::INTERVAL,
        updated_at = NOW()
    WHERE job_id = p_job_id
      AND status = 'running';
    
    GET DIAGNOSTICS v_updated = ROW_COUNT;
    RETURN v_updated > 0;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- UPDATED VIEWS
-- ============================================================================

-- View for seller profiles with reputation
CREATE OR REPLACE VIEW seller_profiles_with_stats AS
SELECT 
    sp.*,
    COALESCE(cn.node_count, 0) as active_nodes,
    COALESCE(j.completed_jobs, 0) as recent_completed_jobs
FROM seller_profiles sp
LEFT JOIN (
    SELECT seller_address, COUNT(*) as node_count
    FROM compute_nodes
    WHERE last_heartbeat > NOW() - INTERVAL '5 minutes'
    GROUP BY seller_address
) cn ON sp.seller_address = cn.seller_address
LEFT JOIN (
    SELECT seller_address, COUNT(*) as completed_jobs
    FROM jobs
    WHERE status = 'COMPLETED'
      AND completed_at > NOW() - INTERVAL '30 days'
    GROUP BY seller_address
) j ON sp.seller_address = j.seller_address;

-- View for active sessions
CREATE OR REPLACE VIEW active_sessions AS
SELECT 
    s.*,
    j.buyer_address,
    j.max_price_per_hour,
    cn.device_name,
    cn.gpu_type,
    NOW() - s.started_at as session_duration,
    s.expires_at - NOW() as time_remaining
FROM sessions s
JOIN jobs j ON s.job_id = j.job_id
JOIN compute_nodes cn ON s.node_id = cn.node_id
WHERE s.status IN ('starting', 'running');

-- ============================================================================
-- TRIGGERS FOR UPDATED_AT
-- ============================================================================

CREATE TRIGGER update_seller_profiles_updated_at 
    BEFORE UPDATE ON seller_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_sessions_updated_at 
    BEFORE UPDATE ON sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- ROW LEVEL SECURITY (optional, for Supabase)
-- ============================================================================

-- Enable RLS on new tables
ALTER TABLE seller_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE seller_ratings ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_files ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;

-- Policies for seller_profiles (public read, owner write)
CREATE POLICY "Seller profiles are publicly readable"
    ON seller_profiles FOR SELECT
    USING (true);

CREATE POLICY "Sellers can update own profile"
    ON seller_profiles FOR UPDATE
    USING (true);  -- In production, add auth check

-- Policies for seller_ratings (public read, buyer can insert)
CREATE POLICY "Ratings are publicly readable"
    ON seller_ratings FOR SELECT
    USING (true);

CREATE POLICY "Anyone can insert ratings"
    ON seller_ratings FOR INSERT
    WITH CHECK (true);  -- In production, verify buyer completed job

-- Policies for job_files
CREATE POLICY "Job files readable by job participants"
    ON job_files FOR SELECT
    USING (true);  -- In production, check buyer/seller address

CREATE POLICY "Anyone can upload files"
    ON job_files FOR INSERT
    WITH CHECK (true);

-- Policies for sessions
CREATE POLICY "Sessions readable by participants"
    ON sessions FOR SELECT
    USING (true);

CREATE POLICY "Nodes can manage sessions"
    ON sessions FOR ALL
    USING (true);

