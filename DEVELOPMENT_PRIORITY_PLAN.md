# ComputeSwarm Development Priority Plan

## Executive Summary

This document ranks remaining features by priority and provides a structured plan to complete development. Features are evaluated based on:
- **User Value**: Impact on end-user experience
- **Dependencies**: Blocks other features or is foundational
- **Complexity**: Implementation effort vs. value
- **Production Readiness**: Required for stable deployment

---

## Feature Priority Ranking

### 🔴 **TIER 0: BLOCKING ISSUE - Fix Immediately** (System Doesn't Work)

#### 0. **Network Isolation Fix** ⚠️ CRITICAL BLOCKER
**Status**: NOT FIXED - System is broken for most ML workloads
**Impact**: Requirements installation fails, model downloads fail, multi-node impossible
**Effort**: Medium-High (3-5 days)
**Dependencies**: Blocks everything else

**The Problem**:
- Containers run with `--network none` (security feature)
- This blocks `pip install` (requirements fail silently)
- This blocks HuggingFace model downloads
- This blocks multi-node distributed training
- Jobs fail silently when packages aren't installed

**Solution**: Two-phase execution
- Phase 1: Network-enabled setup (install packages, download models) - 5 min timeout
- Phase 2: Network-disabled execution (run job) - full security

**Tasks**:
- [ ] Add network configuration options to SellerConfig
- [ ] Implement two-phase container execution
- [ ] Add domain whitelisting (pypi.org, huggingface.co, etc.)
- [ ] Add setup timeout enforcement
- [ ] Test package installation works
- [ ] Test model downloads work
- [ ] Test network is disabled during execution
- [ ] Update security documentation

**Why First**: Without this, the system doesn't work for real ML workloads. Templates won't help if packages can't be installed.

---

### 🔴 **TIER 1: CRITICAL - Must Complete First** (Blocks Core Functionality)

#### 1. **Database Integration for Metrics & Experiments** ⚠️ HIGHEST PRIORITY
**Status**: Schemas created, but no database client methods
**Impact**: Metrics/experiments collected but not persisted - features don't work
**Effort**: Medium (2-3 days)
**Dependencies**: Blocks all experiment tracking features

**Tasks**:
- [ ] Add `save_job_metrics()` to DatabaseClient
- [ ] Add `create_experiment()`, `get_experiment()`, `list_experiments()` methods
- [ ] Add `save_checkpoint()`, `list_checkpoints()` methods
- [ ] Add `save_model()`, `list_models()` methods
- [ ] Integrate metrics saving into execution engine after job completion
- [ ] Update API endpoints to use database methods instead of placeholders

**Why First**: Without this, all the experiment tracking work is non-functional. Users can't actually use metrics/experiments.

---

#### 2. **Checkpoint Auto-Detection & Upload** ⚠️ HIGH PRIORITY
**Status**: Not implemented
**Impact**: Critical for ML workflows - users need to resume training
**Effort**: Medium (2-3 days)
**Dependencies**: Requires database integration (#1)

**Tasks**:
- [ ] Add checkpoint monitoring in execution engine (watch `/workspace/checkpoints/`)
- [ ] Auto-upload checkpoints to storage when detected
- [ ] Parse checkpoint metadata (epoch, step, loss) from filenames or metadata files
- [ ] Store checkpoint records in database
- [ ] Add `--resume-from checkpoint_id` parameter to job submission
- [ ] Implement checkpoint download/restore logic

**Why Second**: Essential for production ML training. Users will lose work without this.

---

#### 3. **Model Versioning Auto-Detection** ⚠️ HIGH PRIORITY
**Status**: Not implemented
**Impact**: Users need to track and retrieve trained models
**Effort**: Medium (2 days)
**Dependencies**: Requires database integration (#1)

**Tasks**:
- [ ] Add model file detection in execution engine (watch `/workspace/models/`)
- [ ] Auto-upload models to storage
- [ ] Extract model metadata (architecture, framework, size)
- [ ] Implement semantic versioning (auto-increment)
- [ ] Store model records in database
- [ ] Add model download endpoints with signed URLs

**Why Third**: Critical for ML workflows - users need to save and retrieve models.

---

### 🟡 **TIER 2: HIGH VALUE - Major UX Improvements** (Complete After Tier 1)

#### 4. **Job Templates System** ⚠️ HIGH VALUE
**Status**: Not implemented
**Impact**: **Huge UX improvement** - makes platform actually usable for non-experts
**Effort**: Medium-High (3-4 days)
**Dependencies**: None (can work independently)

**Tasks**:
- [ ] Create `examples/templates/` directory structure
- [ ] Create template YAML format (script, requirements, params, description)
- [ ] Implement 5 core templates:
  - PyTorch DDP training
  - HuggingFace fine-tuning
  - LoRA/QLoRA
  - Image generation (Stable Diffusion)
  - LLM inference
- [ ] Add template validation and parameter checking
- [ ] Add `computeswarm templates list` CLI command
- [ ] Add `--template` parameter to job submission
- [ ] Add template endpoints to API

**Why Fourth**: This is the difference between "powerful but hard to use" and "actually usable". Templates reduce friction by 90%.

---

#### 5. **Production Readiness - Basics** ⚠️ REQUIRED FOR LAUNCH
**Status**: Not implemented
**Impact**: Required for stable production deployment
**Effort**: Medium (2-3 days)
**Dependencies**: None

**Tasks**:
- [ ] Add health check endpoints: `/health`, `/health/ready`, `/health/live`
- [ ] Add basic Prometheus metrics endpoint: `/metrics`
- [ ] Improve error handling with proper HTTP status codes
- [ ] Add request ID correlation for logging
- [ ] Add basic rate limiting improvements
- [ ] Add graceful shutdown handling

**Why Fifth**: Can't deploy to production without health checks and basic monitoring.

---

#### 6. **CLI Improvements** ⚠️ HIGH UX VALUE
**Status**: Partially implemented
**Impact**: Significantly improves developer experience
**Effort**: Medium (2-3 days)
**Dependencies**: Requires database integration for some features

**Tasks**:
- [ ] Add `computeswarm status --watch` (live updates)
- [ ] Add `computeswarm logs {job_id} --follow` (streaming)
- [ ] Add `computeswarm download {job_id}` (download results)
- [ ] Add interactive job submission with prompts
- [ ] Add progress bars for uploads/downloads
- [ ] Improve error messages with actionable suggestions

**Why Sixth**: Makes the platform much more pleasant to use. Developers will actually use it.

---

### 🟢 **TIER 3: NICE-TO-HAVE - Advanced Features** (Complete After Tier 2)

#### 7. **Multi-Node Coordination** 
**Status**: Not implemented
**Impact**: Enables distributed training across multiple sellers
**Effort**: High (5-7 days)
**Dependencies**: Requires DDP to be working well first

**Tasks**:
- [ ] Create `job_nodes` table migration
- [ ] Implement coordinator pattern in marketplace
- [ ] Add multi-node job submission endpoint
- [ ] Implement coordinator/worker handshake
- [ ] Add network discovery and communication
- [ ] Test with 2+ seller nodes

**Why Seventh**: Advanced feature. Most users won't need this initially. Get single-node working perfectly first.

---

#### 8. **Persistent Storage Volumes**
**Status**: Not implemented
**Impact**: Useful for workflows that span multiple jobs
**Effort**: Medium (2-3 days)
**Dependencies**: None

**Tasks**:
- [ ] Add persistent storage volume creation
- [ ] Mount volumes to containers: `-v /persistent/{buyer}:/workspace/data`
- [ ] Implement cleanup after expiration
- [ ] Add storage quota management
- [ ] Add API endpoints for persistent storage

**Why Eighth**: Nice feature but not critical. Users can work around with dataset uploads.

---

#### 9. **Dataset Management - Full Implementation**
**Status**: Basic structure exists, needs database integration
**Impact**: Useful for sharing and versioning datasets
**Effort**: Medium (2-3 days)
**Dependencies**: Requires database integration

**Tasks**:
- [ ] Complete database integration for datasets
- [ ] Implement dataset versioning logic
- [ ] Add dataset sharing (public/private)
- [ ] Add dataset search and filtering
- [ ] Complete API endpoints

**Why Ninth**: Useful but not blocking. Users can upload files directly for now.

---

#### 10. **Horovod Support**
**Status**: Not implemented
**Impact**: Alternative distributed training framework
**Effort**: Medium (2-3 days)
**Dependencies**: Requires DDP to be working first

**Tasks**:
- [ ] Add Horovod detection in distributed.py
- [ ] Set up Horovod environment variables
- [ ] Install Horovod in Docker image
- [ ] Test Horovod jobs

**Why Tenth**: Lower priority. PyTorch DDP covers most use cases. Can add later.

---

#### 11. **Advanced Production Features**
**Status**: Not implemented
**Impact**: Enterprise-grade reliability
**Effort**: High (5-7 days)
**Dependencies**: Requires basic production features first

**Tasks**:
- [ ] Full Prometheus metrics collection
- [ ] Sentry integration for error tracking
- [ ] Redis caching layer
- [ ] Database query optimization
- [ ] Comprehensive monitoring dashboard
- [ ] Auto-scaling logic
- [ ] Disaster recovery procedures

**Why Eleventh**: Can iterate on this after launch. Get basics working first.

---

## Recommended Development Phases

### **Phase 0: Critical Fixes** (Week 1) - **DO THIS FIRST**
**Goal**: Fix fundamental issues that break the system

1. ⚠️ **Network Isolation Fix** - Enable controlled network access for setup
   - Two-phase execution (setup with network, execution without)
   - Whitelisted domains only
   - Time-limited setup window

**Deliverable**: System actually works for real ML workloads

---

### **Phase 1: Core Functionality** (Week 2-3)
**Goal**: Make existing features actually work

1. ✅ Database Integration for Metrics & Experiments
2. ✅ Checkpoint Auto-Detection & Upload
3. ✅ Model Versioning Auto-Detection

**Deliverable**: Users can track experiments, save checkpoints, and version models

---

### **Phase 2: Usability** (Week 3-4)
**Goal**: Make platform actually usable

4. ✅ Job Templates System
5. ✅ Production Readiness - Basics
6. ✅ CLI Improvements

**Deliverable**: Platform is user-friendly and production-ready

---

### **Phase 3: Advanced Features** (Week 5+)
**Goal**: Add advanced capabilities

7. ✅ Multi-Node Coordination
8. ✅ Persistent Storage Volumes
9. ✅ Dataset Management - Full Implementation
10. ✅ Horovod Support (optional)

**Deliverable**: Advanced features for power users

---

## Implementation Strategy

### **Approach**
1. **Complete Tier 1 first** - These are blockers
2. **Test each feature** - Don't move on until it works end-to-end
3. **Integration testing** - Test features together, not in isolation
4. **Documentation** - Update docs as you build

### **Testing Strategy**
- Unit tests for each new database method
- Integration tests for checkpoint/model detection
- End-to-end test: Submit job → Checkpoint saved → Resume from checkpoint
- Manual testing with real ML training scripts

### **Risk Mitigation**
- **Database migrations**: Test on staging first
- **Checkpoint detection**: Handle edge cases (corrupted files, missing metadata)
- **Templates**: Start with 1-2 templates, expand later
- **Production features**: Start minimal, iterate

---

## Success Metrics

### **Phase 1 Complete When**:
- ✅ Metrics are saved to database and queryable via API
- ✅ Checkpoints auto-upload and can be resumed from
- ✅ Models are versioned and downloadable

### **Phase 2 Complete When**:
- ✅ Users can submit jobs using templates
- ✅ Health checks return proper status
- ✅ CLI is intuitive and helpful

### **Phase 3 Complete When**:
- ✅ Multi-node jobs work with 2+ sellers
- ✅ Persistent storage persists across jobs
- ✅ Datasets can be shared and versioned

---

## Estimated Timeline

- **Phase 0**: 1 week (3-5 days of focused work) - **CRITICAL**
- **Phase 1**: 2 weeks (6-7 days of focused work)
- **Phase 2**: 2 weeks (6-7 days of focused work)
- **Phase 3**: 3-4 weeks (10-14 days of focused work)

**Total**: 7-9 weeks to complete all features

**Minimum Viable**: Phase 0 + Phase 1 + Phase 2 = 5 weeks for production-ready platform

**⚠️ WARNING**: Phase 0 must be completed first, otherwise Phase 1-2 features won't work for real workloads.

---

## Next Steps

1. **⚠️ FIX NETWORK ISOLATION FIRST** - System is broken without this
2. **Start with Database Integration** - This unblocks everything else
3. **Implement checkpoint detection** - Critical for ML workflows
4. **Add model versioning** - Complete the ML workflow
5. **Build templates** - Make it usable
6. **Add production basics** - Make it deployable

## Critical Notes

- **Network isolation fix is blocking** - Most ML workloads won't work without it
- **Don't proceed to Phase 2 until Phase 0 is complete** - Templates won't help if packages can't install
- **This is a security vs. functionality tradeoff** - Need controlled network access, not full isolation

---

## Notes

- **Don't skip Tier 1** - These are foundational
- **Templates are high-value** - Consider doing earlier if time permits
- **Production features can iterate** - Get basics working, improve later
- **Multi-node is complex** - Save for after core features are solid
