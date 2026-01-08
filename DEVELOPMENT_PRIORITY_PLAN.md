# ComputeSwarm Development Priority Plan

> **MAINTENANCE PROTOCOL**: This document must be updated continuously whenever changes are made to the codebase. It serves as the single source of truth for project status and priorities.

**Last Updated:** 2026-01-08

## Executive Summary

The project has reached a high level of maturity. Critical blockers (Tier 0), Core Functionality (Tier 1), and Usability features (Tier 2) are **COMPLETED**.
The focus is now on **Tier 3: Advanced Features** (Multi-Node, Storage, Datasets) and verifying system stability.

---

## Feature Priority Ranking & Status

### ✅ **TIER 0: BLOCKING ISSUE** (COMPLETED)

#### 0. **Network Isolation Fix**
**Status**: **FIXED** (Implemented in `src/execution/engine.py`)
- Two-phase execution implemented:
  - Phase 1: Network enabled for setup (pip install, model download)
  - Phase 2: Network disabled (`--network none`) for execution

---

### ✅ **TIER 1: CRITICAL - Core Functionality** (COMPLETED)

#### 1. **Database Integration for Metrics & Experiments**
**Status**: **COMPLETED** (Implemented in `src/database/client.py`)
- Methods: `save_job_metrics`, `create_experiment`, etc.
- Schema: Created and active (`job_metrics`, `experiments` tables)

#### 2. **Checkpoint Auto-Detection & Upload**
**Status**: **COMPLETED** (Implemented in `src/execution/checkpoint_manager.py`)
- Auto-detects `.pt`, `.pth`, `.ckpt` files
- Uploads to storage and saves metadata to DB
- Resume from checkpoint: Support exists in `JobExecutor`

#### 3. **Model Versioning Auto-Detection**
**Status**: **COMPLETED** (Implemented in `src/execution/model_manager.py`)
- Auto-detects model files
- Semantic versioning support
- Model registry in database

---

### ✅ **TIER 2: HIGH VALUE - Usability** (COMPLETED)

#### 4. **Job Templates System**
**Status**: **COMPLETED** (Implemented in `src/templates/__init__.py`)
- Templates available for:
  - PyTorch Training
  - HuggingFace Inference
  - LoRA Fine-tuning
  - Image Classification
  - GPU Benchmarks

#### 5. **Production Readiness - Basics**
**Status**: **COMPLETED** (Implemented in `src/marketplace/server.py`)
- Health checks: `/health`
- Rate limiting: Implemented via `slowapi`
- Logging: Structured logging with `structlog`

#### 6. **CLI Improvements**
**Status**: **COMPLETED** (Implemented in `src/buyer/cli.py`)
- Live monitoring: `wait_for_job` with rich UI
- File downloads: Implemented
- Cost estimation: Implemented

---

### 🟡 **TIER 3: ADVANCED FEATURES** (CURRENT FOCUS)

#### 7. **Multi-Node Coordination**
**Status**: **PARTIALLY IMPLEMENTED**
**Goal**: Enable distributed training across multiple sellers
**Current State**:
- DDP/Horovod detection implemented (`src/execution/distributed.py`)
- Environment variable setup implemented
- Database support for `num_gpus` present
**Remaining Tasks**:
- [ ] Verify multi-node communication between containers on different hosts (if applicable) or verify multi-GPU on single host works flawlessly
- [ ] Implement coordinator logic if strictly P2P multi-node is required

#### 8. **Persistent Storage Volumes**
**Status**: **PENDING**
**Goal**: Useful for workflows that span multiple jobs
**Tasks**:
- [ ] Add persistent storage volume creation
- [ ] Mount volumes to containers: `-v /persistent/{buyer}:/workspace/data`
- [ ] API endpoints for persistent storage

#### 9. **Dataset Management**
**Status**: **PENDING**
**Goal**: Share and version datasets
**Tasks**:
- [ ] Implement dataset versioning logic
- [ ] Add dataset sharing (public/private)
- [ ] Add dataset search and filtering

#### 10. **Advanced Production Features**
**Status**: **PENDING**
**Tasks**:
- [ ] Full Prometheus metrics collection
- [ ] Sentry integration
- [ ] Redis caching layer

---

## Roadmap Status

- **Phase 0: Critical Fixes** -> ✅ **DONE**
- **Phase 1: Core Functionality** -> ✅ **DONE**
- **Phase 2: Usability** -> ✅ **DONE**
- **Phase 3: Advanced Features** -> 🔄 **IN PROGRESS**

## Next Steps

1.  **Verify Multi-Node/Multi-GPU support**: Ensure `distributed.py` logic works in practice with actual GPUs.
2.  **Implement Persistent Storage**: This is the next high-value unlock for users (data persistence).
3.  **End-to-End Testing**: Verify the entire flow from "Template -> Submit -> Execute -> Checkpoint -> Resume".
