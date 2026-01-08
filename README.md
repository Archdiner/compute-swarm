# ComputeSwarm 🐝

**The Hardware Layer for the Agentic Economy**

Give your AI Agents the compute they need to evolve. Rent GPUs by the second. Pay permissionlessly with USDC on Base.

[![x402 Protocol](https://img.shields.io/badge/x402-Protocol-blue)](https://x402.org)
[![Base L2](https://img.shields.io/badge/Base-Sepolia-0052FF)](https://base.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## The Problem

**Legacy cloud infrastructure is built for humans, not Agents.**

### For Autonomous Agents
- **Identity Wall**: Agents can't pass KYC or sign up for AWS/GCP.
- **Payment Barrier**: Credit cards and bank accounts are for humans. Agents have wallets.
- **The "Brain" Gap**: Local hardware (MacBooks) is too weak for fine-tuning. Agents need high-VRAM GPUs for self-improvement.
- **Manual Overhead**: Provisioning instances in a dashboard is a human-only task.

### For Resource Owners
- **Untapped Supply**: Millions of idle 3090s/4090s sit in gaming rigs and workstations.
- **Friction**: Monetizing a single GPU is too complex for most owners.
- **Trust**: No secure way to rent out hardware to anonymous software.

**The result?** Most AI agents are "locked" in their current state, unable to scale their own intelligence because they can't access hardware.

## The Solution

ComputeSwarm is **The General-Purpose Compute API for Autonomous Software**.

### For Agents
- **Permissionless**: No signups. Auth is a wallet signature.
- **Pay Per Second**: No minimums. Stream USDC as the code executes.
- **Any Workload**: Fine-tune, infer, process data, generate images—send any Docker job.
- **API-First**: Designed to be integrated into autonomous loops.

### For Resource Owners
- **Bee-Simple Setup**: The "One-Click Hive" agent turns your GPU into a worker node.
- **Streamed Income**: Watch USDC flow into your wallet in real-time.
- **Sandboxed Security**: Two-phase execution ensures jobs are air-gapped and safe.

**x402 Protocol** enables trustless, per-second micropayments in USDC on Base L2.

No middleman. No minimum commitment. No trust required.

---

## x402 Integration

This project is built for the **x402 hackathon** and demonstrates real-world use of the x402 payment protocol:

```
+-------------+    Submit Job    +-------------+    x402 Payment    +-------------+
|   Buyer     | ---------------> | Marketplace | <----------------> |   Seller    |
|  (has $)    |                  |   (queue)   |                    |  (has GPU)  |
+-------------+                  +-------------+                    +-------------+
       |                                                                    |
       |                         USDC on Base                               |
       +--------------------------------------------------------------------+
```

**How x402 is used:**
1. Buyer submits job with max price - escrowed in smart contract
2. Seller claims job - validates buyer has funds via x402
3. Job executes - per-second billing tracked
4. Job completes - x402 settles USDC payment to seller

---

## Features

| Feature | Description |
|---------|-------------|
| **x402 Payments** | Trustless USDC micropayments on Base L2 |
| **GPU Auto-Detection** | NVIDIA CUDA, Apple Silicon MPS, AMD ROCm |
| **Multi-GPU Support** | Use all your GPUs (2x RTX 4090? No problem) |
| **Docker Sandboxing** | Secure execution with network isolation |
| **Job Templates** | Pre-built templates for PyTorch, HuggingFace, LoRA |
| **Model Caching** | Persistent HuggingFace/PyTorch cache across jobs |
| **Real-time Earnings** | Track your earnings as a seller |
| **Cost Estimation** | Know costs before submitting |

---

## Who Benefits

### For Individuals & Small Teams
**Powerful AI compute, finally affordable for everyone:**

```bash
# Instead of $200/month for cloud GPU access...
# Train your AI model for $0.50 on ComputeSwarm
```

- **Students**: Experiment with cutting-edge AI without department budgets
- **Researchers**: Run experiments that would cost thousands in cloud fees
- **Indie developers**: Train custom AI models for your apps and games
- **Small businesses**: Add AI capabilities without massive infrastructure costs
- **Hobbyists**: Turn your ideas into reality with real GPU power

### For Tech Giants
**Better utilization of your existing compute infrastructure:**

```bash
# Your idle data center GPUs can now earn revenue
# Instead of wasting electricity, generate income
```

- **Cloud providers**: Offer cheaper GPU access through decentralized network
- **Tech companies**: Monetize overnight idle time in development workstations
- **Gaming companies**: Utilize player GPUs during off-peak hours
- **Research institutions**: Share compute across departments and universities
- **Hardware manufacturers**: Create new revenue streams for GPU owners

**The market opportunity:** Millions of GPUs worldwide sit idle 80% of the time. That's billions in wasted compute capacity that can now be unlocked.

### Economic Impact
- **GPU Market Size**: $50B annually (gaming, workstations, data centers)
- **Idle Capacity**: 80% of GPUs unused globally = $40B in wasted hardware
- **Current Cloud GPU Pricing**: $2-4/hour = $17,520-35,040/month
- **ComputeSwarm Pricing**: $0.50-2.00/hour = 75-90% cost reduction
- **Addressable Market**: Anyone currently paying for cloud GPUs (developers, researchers, companies)

**We're not competing with cloud providers. We're utilizing the compute they can't access.**

---

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 20+ (for frontend)
- Docker (for sandboxed execution)
- NVIDIA GPU with CUDA (or Apple Silicon)

### 1. Clone and Install

```bash
git clone https://github.com/Archdiner/compute-swarm.git
cd compute-swarm
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your settings:
#   SUPABASE_URL=your-project-url
#   SUPABASE_ANON_KEY=your-anon-key
#   SELLER_PRIVATE_KEY=0x...  (for receiving payments)
#   BUYER_PRIVATE_KEY=0x...   (for sending payments)
```

### 3. Run the Marketplace

#### Option A: Using Web UI (Recommended)

```bash
# Terminal 1: Start marketplace server
python -m src.marketplace.server

# Terminal 2: Start frontend web UI
cd frontend
# Create .env.local (already created if following setup)
npm install
npm run dev
# Note: Users need MetaMask browser extension to connect wallets

# Terminal 3: Start seller agent (on GPU machine)
python -m src.seller.agent
```

Then visit http://localhost:3000 in your browser.

#### Option B: Using CLI

```bash
# Terminal 1: Start marketplace server
python -m src.marketplace.server

# Terminal 2: Start seller agent (on GPU machine)
python -m src.seller.agent

# Terminal 3: Submit jobs as buyer
python -m src.buyer.cli
```

---

## Usage Examples

### As a Buyer (Need GPU Compute)

```bash
# Interactive mode
python -m src.buyer.cli

> templates                    # See available job templates
> template                     # Submit using a template
  Select: pytorch_train
  epochs: 10
  batch_size: 64
  ...

> status abc-123              # Check job status
Status: COMPLETED
Output: Training complete! Accuracy: 94.2%
Cost: $0.0847 USDC
```

### As a Seller (Have GPU to Share)

```bash
# One-click setup
./scripts/setup_seller.sh

# Start earning
python -m src.seller.agent

# Output:
# ============================================================
#   ComputeSwarm Seller Agent
# ============================================================
#   Node ID:      node_a1b2c3d4e5f6
#   GPU:          NVIDIA GeForce RTX 4090
#   Price:        $2.00/hr
#   Status:       Available
# ------------------------------------------------------------
#   Session Earnings:  $0.0000 USDC
#   Jobs Completed:    0
# ============================================================
```

---

## Architecture

```
compute-swarm/
├── frontend/            # React web UI with Privy embedded wallets
│   ├── src/
│   │   ├── components/  # React components
│   │   ├── pages/       # Buyer/Seller views
│   │   ├── services/    # API client, Privy config
│   │   └── hooks/       # Custom React hooks
│   └── package.json
├── src/
│   ├── marketplace/     # FastAPI server (job queue, matching, payments)
│   ├── seller/          # Seller agent (GPU detection, job execution)
│   ├── buyer/           # Buyer CLI (job submission, templates)
│   ├── execution/       # Docker sandboxing, GPU passthrough
│   ├── payments/        # x402 USDC payment processing
│   ├── templates/       # Pre-built ML job templates
│   └── config.py        # Configuration management
├── docker/              # Docker images for sandboxed execution
├── scripts/             # Setup and helper scripts
└── tests/               # Test suite
```

**Tech Stack:**
- **Frontend**: React, TypeScript, Vite, MetaMask (wallet connection), Tailwind CSS
- **Backend**: FastAPI, Python 3.11
- **Database**: Supabase (PostgreSQL)
- **Payments**: x402 SDK, Web3.py, USDC on Base
- **Compute**: PyTorch, Docker, NVIDIA Container Toolkit
- **Authentication**: MetaMask wallet connection

---

## Job Templates

Pre-built templates for common ML tasks:

| Template | Description | GPU Required |
|----------|-------------|--------------|
| `pytorch_train` | Train PyTorch models | Yes |
| `huggingface_inference` | Run HuggingFace models | Yes |
| `lora_finetune` | LoRA fine-tuning | Yes |
| `image_classification` | Classify images with pretrained models | Yes |
| `gpu_benchmark` | Benchmark GPU performance | Yes |

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/jobs/submit` | POST | Submit a job to the queue |
| `/api/v1/jobs/estimate` | POST | Estimate job cost |
| `/api/v1/jobs/{id}` | GET | Get job status |
| `/api/v1/nodes` | GET | List available GPU nodes |
| `/api/v1/stats` | GET | Marketplace statistics |
| `/api/v1/sellers/{addr}/earnings` | GET | Seller earnings dashboard |

Full API docs at `/docs` when running.

---

## Roadmap

- [x] x402 USDC payment integration
- [x] Multi-GPU support
- [x] Docker sandboxing
- [x] Job templates
- [x] Seller earnings dashboard
- [x] Web dashboard for buyers and sellers
- [x] Privy embedded wallet integration
- [ ] Reputation system
- [ ] Spot pricing / auctions
- [ ] Model marketplace integration

---

## The Vision

**ComputeSwarm is building the decentralized infrastructure for the AI economy.**

By connecting idle GPUs with compute demand through trustless micropayments, we're:

- **Democratizing AI development** - Making powerful compute accessible to everyone
- **Optimizing global compute efficiency** - Turning waste into wealth
- **Accelerating AI innovation** - Removing cost barriers to experimentation
- **Building resilient infrastructure** - Decentralized compute that can't be controlled by any single entity

**This isn't just a marketplace. It's a fundamental shift in how compute resources are allocated globally.**

---

## Built for x402 Hackathon

This project demonstrates how x402 can enable:
- **Micropayments for compute** - Pay per second, not per hour
- **Trustless transactions** - No escrow service needed
- **The agentic economy** - AI agents can autonomously purchase compute

---

## License

MIT License - See [LICENSE](LICENSE) for details.

---

**Made for the x402 Hackathon**
