# Critical Network Isolation Fix Plan

## Problem Statement

Current system uses `--network none` which:
- ✅ Prevents data exfiltration (good for security)
- ❌ Blocks package installation (breaks requirements)
- ❌ Blocks model downloads (breaks ML workflows)
- ❌ Prevents multi-node training (blocks distributed training)

## Solution: Two-Phase Execution with Controlled Network Access

### Phase 1: Network-Enabled Setup (Limited Time Window)
- Install requirements from PyPI
- Download models from HuggingFace
- Download datasets
- Time-limited (e.g., 5 minutes max)
- Whitelisted domains only

### Phase 2: Network-Disabled Execution
- Run actual job script
- No network access (security maintained)
- All dependencies already installed

## Implementation Plan

### Step 1: Add Network Configuration to Config

```python
# src/config.py - SellerConfig
docker_network_enabled: bool = Field(
    default=False,
    description="Enable network access during setup phase"
)
docker_network_whitelist: List[str] = Field(
    default=["pypi.org", "files.pythonhosted.org", "huggingface.co", "github.com"],
    description="Whitelisted domains for network access"
)
docker_setup_timeout: int = Field(
    default=300,
    description="Maximum time for network-enabled setup phase (seconds)"
)
```

### Step 2: Modify Execution Engine

**Current flow:**
```
1. Create container with --network none
2. Install requirements (FAILS - no network)
3. Run script
```

**New flow:**
```
1. Create container with network (if setup needed)
2. Install requirements (SUCCEEDS - has network)
3. Download models/datasets (SUCCEEDS - has network)
4. Stop container
5. Create new container with --network none
6. Copy installed packages and models
7. Run script (no network, but everything pre-installed)
```

### Step 3: Two-Container Approach

**Option A: Setup Container + Execution Container**
- Setup container: Network enabled, installs everything
- Execution container: Network disabled, runs job
- Share volumes between containers

**Option B: Single Container with Network Toggle**
- Start with network enabled
- Run setup script
- Disable network (if possible)
- Run job script

**Option C: Pre-setup Service (Recommended)**
- Seller runs a setup service that pre-downloads common packages/models
- Jobs run with network disabled but have everything cached
- Marketplace provides model/package cache API

## Recommended Implementation: Option C + Fallback to Option A

### Architecture

```
┌─────────────────────────────────────────┐
│         Setup Phase (Network ON)        │
│  - Install requirements                 │
│  - Download models                      │
│  - Download datasets                    │
│  - Time limit: 5 minutes                │
│  - Whitelisted domains only             │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│      Execution Phase (Network OFF)       │
│  - Run job script                       │
│  - All dependencies available          │
│  - No network access                    │
│  - Full security isolation              │
└─────────────────────────────────────────┘
```

### Code Changes Needed

1. **Split `_run_in_docker` into two methods:**
   - `_setup_container()` - Network enabled, installs dependencies
   - `_run_job_container()` - Network disabled, runs script

2. **Add network whitelisting:**
   - Use Docker's `--dns` and firewall rules
   - Or use a proxy that filters domains

3. **Volume sharing:**
   - Setup container writes to shared volume
   - Execution container reads from shared volume

4. **Timeout enforcement:**
   - Setup phase has strict timeout
   - If setup fails/times out, job fails early

## Security Considerations

### Whitelisted Domains
- `pypi.org` - Python packages
- `files.pythonhosted.org` - Package files
- `huggingface.co` - Models and datasets
- `github.com` - Git repositories (optional)
- `raw.githubusercontent.com` - Raw files (optional)

### Network Restrictions
- DNS resolution only for whitelisted domains
- HTTPS only (no HTTP)
- Time-limited network window
- Rate limiting on downloads

### Fallback Security
- If setup fails, job fails (no partial execution)
- Setup logs are audited
- Network access is logged

## Implementation Priority

**CRITICAL** - This blocks most real ML workloads

Should be implemented **before** Phase 2 (Templates) because:
- Templates won't work if packages can't be installed
- Users will hit this immediately
- Breaks core functionality

## Estimated Effort

- **Option A (Two containers)**: 3-4 days
- **Option C (Pre-setup service)**: 5-7 days (better long-term)
- **Hybrid approach**: 4-5 days (recommended)

## Testing Strategy

1. Test package installation works
2. Test model downloads work
3. Test network is disabled during execution
4. Test setup timeout enforcement
5. Test whitelist filtering
6. Test security (can't access non-whitelisted domains)

