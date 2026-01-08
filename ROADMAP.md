# ComputeSwarm Roadmap 🐝

This document serves as the single source of truth for the project's current status and future development priorities.

## 🏁 Vision Summary
ComputeSwarm is building the decentralized infrastructure for the AI economy, pivoting to specialize in **Low-Bandwidth Distributed Workloads** (LoRA fine-tuning, Inference, and Hyperparameter Sweeps) where consumer hardware (RTX 3090/4090s) provides the most competitive price-to-performance ratio.

---

## 🏎 Current Status: Phase 3 (Advanced Features)

### ✅ Completed Milestones
- **Tier 0 (Critical)**: Network Isolation Fix (Two-phase Docker execution).
- **Tier 1 (Core)**: Database Integration (Metrics & Experiments), Checkpoint Auto-Detection, Model Versioning.
- **Tier 2 (Usability)**: Job Template System, Production Readiness Basics (Health checks, Rate limiting), CLI Live Monitoring.

### 🔄 In Progress: Tier 3 (Advanced Features)
- **Multi-Node Coordination**: Distributed training logic (`src/execution/distributed.py`) is implemented; currently verifying multi-node comms.
- **Persistent Storage Volumes**: Adding support for volume mounts that span multiple jobs (`-v /persistent/{buyer}:/workspace/data`).
- **Dataset Management**: Implementing dataset versioning and sharing logic.

---

## 🗺 Strategic Tracks

### 🔴 Core Engine (Track A)
- [x] LoRA Template optimization (Gradient Accumulation).
- [ ] Pipeline Parallelism (Layer splitting across nodes).
- [ ] Optimistic Verification (Random re-runs on trusted nodes to catch cheating).

### 🔵 Connectivity & Networking (Track B)
- [x] Secure Tunneling Prototype (`src/networking/tunnel.py`).
- [ ] Swarm Transfer Protocol (Heavy-weight file transfer via tunnel layer).
- [ ] P2P Hole-punching/VPN implementation (Tailscale/Libp2p).

### 🟢 User Experience (Track C)
- [x] Seller Agent One-Click Start.
- [ ] Seller Local Dashboard (Local web UI for earnings and monitoring).
- [ ] Buyer Python SDK (Launch jobs from Jupyter Notebooks).
- [ ] Desktop GUI (Electron/Tauri) to replace CLI for wider adoption.

---

## 📅 Roadmap Summary
- **Phase 0-2**: Consolidated as stable core.
- **Phase 3 (Current)**: Focus on Persistence, Storage, and Multi-Node polish.
- **Phase 4 (Future)**: Trust/Verification systems and Mass-Market Desktop GUI.
