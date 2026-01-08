# Strategic Pivot Implementation Plan: "Swarm Fine-Tuning"

## Goal
Transform `compute-swarm` from a generic (and theoretically impossible) pre-training platform into a robust **decentralized fine-tuning (LoRA) and inference network**.

## Execution Strategy: The "Virtual Team"
To accelerate development, work is divided into three independent tracks assigned to specialized "Virtual Employees". 
**Manager (User/Agent)**: Coordinates integration points and final system validation.

---

## 👥 Staffing & Assignments

### 🔴 Employee A: "The Architect" (Senior Systems Engineer)
**Focus**: Core Compute Engine & AI Workloads.
**Responsibility**: Ensure the Python backend can actually run LoRA fine-tuning efficiently and handle "Hyperparameter Sweeps" without crashing.
**Complexity**: High. Requires deep PyTorch and System knowledge.

### 🔵 Employee B: "The Connector" (Network & DevOps Engineer)
**Focus**: Connectivity & P2P Layer.
**Responsibility**: Solves the "Home Internet" problem. Implements the tunneling/VPN logic so Node A can talk to Node B (or Server) through Firewalls.
**Complexity**: High. Requires Networking, Docker Networking, security.

### 🟢 Employee C: "The Product Builder" (Full-Stack Developer)
**Focus**: User Experience (UI/CLI).
**Responsibility**: Builds the interfaces that make this usable for "Gamers" (Sellers) and "Indie Devs" (Buyers).
**Complexity**: Medium. React, API design, CLI usability.

---

## 📅 Roadmap & Tasks

### Phase 1: Foundation (Weeks 1-2)

#### 🔴 Track A: Core Engine Refactor
- [ ] **[MODIFY] `src/templates/lora_finetune`**: Optimize the LoRA template. Add "Gradient Accumulation" support to handle low bandwidth (sync less often).
- [ ] **[NEW] `src/execution/pipeline.py`**: Create a specific executor for "Param Sweeps" (running the same job 50 times with different args).
- [ ] **[MODIFY] `src/execution/engine.py`**: Add specialized resource checks for LoRA (RAM vs VRAM execution).

#### 🔵 Track B: Connectivity Prototype
- [ ] **[RESEARCH] Tunneling Solution**: Evaluate `frp`, `ngrok` (embedded), or `tailscale` for the project.
- [ ] **[NEW] `src/networking/tunnel.py`**: Create a module that auto-starts a secure tunnel for the API server so it's accessible publicly without port forwarding.
- [ ] **[MODIFY] `src/marketplace/server.py`**: Update node heartbeat logic to include "P2P Reachability" status.

#### 🟢 Track C: The "Miner" Experience
- [ ] **[NEW] `src/seller/dashboard`**: Create a simple local web dashboard for the Seller Agent (view earnings, stop/start, GPU temp) served locally.
- [ ] **[MODIFY] `src/seller/agent.py`**: Add a "One-Click Start" mode that auto-configures defaults for gamers.

### Phase 2: Integration (Weeks 3-4)

#### 🔴 Track A: Verification System
- [ ] **[NEW] `src/verification/probabilistic.py`**: Implement "Optimistic Verification" (randomly re-run 5% of jobs on a trusted node to catch cheaters).

#### 🔵 Track B: Secure Data Transport
- [ ] **[MODIFY] `src/storage/transfer.py`**: Implement heavy-weight file transfer (Models/Datasets) using the Tunnel layer instead of direct HTTP, creating a "Swarm Transfer Protocol".

#### 🟢 Track C: Buyer "Sweep" UI
- [ ] **[MODIFY] `frontend/src/pages/BuyerDashboard`**: Add a specific UI for "Launch Hyperparameter Sweep".
- [ ] **[NEW] `src/buyer/sdk.py`**: A Python SDK for data scientists to launch jobs from Jupyter Notebooks (critical for adoption).

---

## 🚦 Integration Points (The Manager's Job)
1.  **Metric Standardization**: Ensure simple "Miner" UI (Track C) accurately displays the complex LoRA metrics (Track A).
2.  **Network-Aware Scheduling**: The Scheduler (Track A/B intersection) must strictly match "Public" nodes with "Public" requirements, and use Tunnels for the rest.

## Immediate Next Steps (Task Assignments)

1.  **Assign Track A**: Create the optimized `lora_finetune.py` template with gradient accumulation.
2.  **Assign Track B**: Implement `src/networking/tunnel.py` (POC with `ngrok` or similar) to prove connectivity.
3.  **Assign Track C**: Build the basic "Seller Local Dashboard" HTML/API.
