-- Add p2p_url column to compute_nodes table
-- Used for direct P2P connectivity via tunnels (ngrok, etc.)

ALTER TABLE compute_nodes ADD COLUMN IF NOT EXISTS p2p_url TEXT;

COMMENT ON COLUMN compute_nodes.p2p_url IS 'Public URL for P2P connectivity (e.g. ngrok tunnel)';
