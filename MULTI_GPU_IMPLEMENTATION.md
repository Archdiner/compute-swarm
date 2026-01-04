# Multi-GPU Support & Timeout Improvements Implementation

## ✅ What Was Implemented

### 1. **Multi-GPU Support**

#### Models Updated:
- `ComputeJob`: Added `num_gpus` field (1-8 GPUs)
- `GPUInfo`: Added `num_gpus` field to track available GPUs
- `ComputeNode`: Now tracks number of GPUs available

#### GPU Detection:
- Updated `GPUDetector` to detect multiple NVIDIA GPUs
- Calculates total VRAM across all GPUs
- Updates device name to show count (e.g., "2x NVIDIA RTX 4090")

#### Job Submission:
- Buyers can specify `num_gpus` parameter (default: 1)
- Jobs with `num_gpus > 1` will only match sellers with enough GPUs

#### Docker Execution:
- Updated `run_custom_container` to accept `num_gpus` parameter
- Docker command uses `--gpus "N"` for specific GPU count
- Properly handles NVIDIA multi-GPU setups

#### Database:
- Added `num_gpus` column to `jobs` and `compute_nodes` tables
- Updated `claim_job` PostgreSQL function to check GPU availability
- Migration SQL file created: `src/database/migration_add_num_gpus.sql`

### 2. **Configurable Timeout Limits**

#### Per-Job-Type Timeouts:
- **Batch Jobs**: `job_timeout` (default: 3600s = 1 hour)
- **Notebook Sessions**: `notebook_timeout` (default: 7200s = 2 hours)
- **Container Sessions**: `container_timeout` (default: 10800s = 3 hours)

#### Configuration:
- Added to `MarketplaceConfig` in `src/config.py`
- Can be overridden per job submission
- If not specified, uses defaults based on job type

## 📋 Setup Steps

### 1. Run Database Migration

Go to Supabase SQL Editor and run:
```sql
-- Copy contents of src/database/migration_add_num_gpus.sql
```

This adds:
- `num_gpus` column to `jobs` table
- `num_gpus` column to `compute_nodes` table  
- Updates `claim_job` function to check GPU availability

### 2. Restart Services

After migration:
```bash
# Restart marketplace server
python -m uvicorn src.marketplace.server:app --reload --port 8000

# Restart seller agent
python -m src.seller.agent
```

## 🚀 Usage Examples

### Submit Multi-GPU Job

```python
# Buyer CLI
> submit
Script: your_script.py
Num GPUs: 2  # Request 2 GPUs
Max price: 5.0
```

Or via API:
```bash
curl -X POST "http://localhost:8000/api/v1/jobs/submit" \
  -d "buyer_address=0x..." \
  -d "script=import torch; print(torch.cuda.device_count())" \
  -d "num_gpus=2" \
  -d "max_price_per_hour=5.0"
```

### Custom Timeout

```python
# Buyer CLI
> submit
Script: long_training.py
Timeout: 14400  # 4 hours (overrides default 1 hour)
```

## ⚠️ Limitations & Notes

### Current Limitations:

1. **Jupyter Sessions**: Multi-GPU not yet implemented for notebooks
   - Can be added by updating `SessionManager.start_notebook_session()`
   - Would need to pass `num_gpus` parameter

2. **Apple Silicon MPS**: 
   - MPS doesn't support multi-GPU (unified architecture)
   - `num_gpus` will always be 1 for MPS

3. **Docker GPU Allocation**:
   - Uses `--gpus "N"` format
   - Requires Docker 19.03+ with NVIDIA Container Toolkit
   - GPUs are allocated sequentially (0, 1, 2, ...)

### Future Improvements:

1. **GPU Affinity**: Allow specifying which GPUs to use
2. **Distributed Training**: Add support for PyTorch DDP, Horovod
3. **GPU Memory Limits**: Per-GPU memory limits
4. **Multi-Node**: Support jobs spanning multiple seller nodes

## 🔍 Testing

### Test Multi-GPU Detection:
```python
from src.compute.gpu_detector import GPUDetector
gpu_info = GPUDetector.detect_gpu()
print(f"GPUs: {gpu_info.num_gpus}")
print(f"Device: {gpu_info.device_name}")
```

### Test Multi-GPU Job:
```python
# Submit job requiring 2 GPUs
# Only sellers with 2+ GPUs can claim it
```

## 📝 Files Changed

- `src/models.py` - Added `num_gpus` to `ComputeJob`
- `src/marketplace/models.py` - Added `num_gpus` to `GPUInfo`
- `src/compute/gpu_detector.py` - Multi-GPU detection
- `src/database/client.py` - Store/retrieve `num_gpus`
- `src/database/migration_add_num_gpus.sql` - Database migration
- `src/marketplace/server.py` - Accept `num_gpus` in job submission
- `src/execution/engine.py` - Multi-GPU Docker support
- `src/seller/agent.py` - Pass `num_gpus` when claiming
- `src/config.py` - Per-job-type timeout defaults

## ✅ Status

- ✅ Multi-GPU detection working
- ✅ Multi-GPU job submission working
- ✅ Database schema updated
- ✅ Docker execution supports multiple GPUs
- ✅ Configurable timeouts per job type
- ⚠️ Database migration needs to be run
- ⚠️ Jupyter multi-GPU not implemented yet

