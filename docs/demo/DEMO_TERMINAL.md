# ComputeSwarm Terminal Demo Guide

## Overview

This guide shows how to run a complete **terminal-based demo** of ComputeSwarm, showcasing:
1. Job creation and submission
2. GPU execution with real-time visualization
3. x402 payment processing
4. Buyer and seller perspectives

All in the terminal - no frontend needed!

---

## Prerequisites

### 1. Supabase Setup (5 minutes)
```bash
# 1. Create account at https://supabase.com
# 2. Create new project
# 3. Get credentials:
#    - SUPABASE_URL
#    - SUPABASE_ANON_KEY
# 4. Run schema in SQL Editor:
#    - src/database/schema_v2.sql
```

### 2. Environment Configuration
Create `.env` file:
```bash
# Database
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJxxx...

# Network (testnet for demo)
NETWORK=base-sepolia
RPC_URL=https://sepolia.base.org
USDC_CONTRACT_ADDRESS=0x036CbD53842c5426634e7929541eC2318f3dCF7e

# Testnet mode (simulates payments - perfect for demo!)
TESTNET_MODE=true

# Optional - wallets (auto-generated if not set)
SELLER_PRIVATE_KEY=0x...
BUYER_PRIVATE_KEY=0x...

# Logging
LOG_LEVEL=INFO
MARKETPLACE_HOST=0.0.0.0
MARKETPLACE_PORT=8000
```

### 3. Install Dependencies
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Verify GPU Detection
```bash
python -c "import torch; print('CUDA:', torch.cuda.is_available()); print('MPS:', hasattr(torch.backends, 'mps') and torch.backends.mps.is_available())"
```

---

## Demo Setup: Three Terminal Windows

You'll need **3 terminal windows** (or tabs):

```
┌─────────────────────────────────────────────────────┐
│  Terminal 1: Marketplace Server                     │
│  (Shows API logs, job processing, payment logs)    │
├─────────────────────────────────────────────────────┤
│  Terminal 2: Seller Agent                           │
│  (Shows GPU detection, job execution, earnings)    │
├─────────────────────────────────────────────────────┤
│  Terminal 3: Buyer CLI                              │
│  (Job submission, monitoring, results)             │
└─────────────────────────────────────────────────────┘
```

---

## Step-by-Step Demo Flow

### Step 1: Start Marketplace Server (Terminal 1)

```bash
python -m src.marketplace.server
```

**What to Show:**
- Server starting on `http://localhost:8000`
- API logs showing server is ready
- Health check endpoint working

**Verify:**
```bash
# In another terminal, test health:
curl http://localhost:8000/health
# Should return: {"status": "ok"}
```

---

### Step 2: Start Seller Agent (Terminal 2)

```bash
python -m src.seller.agent
```

**What to Show:**
- GPU detection output
  - GPU type (CUDA/MPS)
  - GPU name (e.g., "NVIDIA GeForce RTX 4090")
  - VRAM information
- Node registration
- Status: "Available, waiting for jobs"
- Session stats: Earnings $0.00, Jobs Completed: 0

**Key Points:**
- "This machine is now a GPU seller on the marketplace"
- "Agent is polling for jobs to execute"
- "Earnings will update after jobs complete"

**Verify:**
```bash
# In Terminal 3, check nodes:
python -m src.buyer.cli stats
# Should show your node in the list
```

---

### Step 3: Buyer CLI - Interactive Mode (Terminal 3)

```bash
python -m src.buyer.cli
```

You'll see:
```
ComputeSwarm Buyer CLI (Queue-Based)
Commands: stats, submit, status, list, cancel, wait, wallet, quit

>
```

---

### Step 4: Check Marketplace Stats

In Terminal 3 (Buyer CLI):
```
> stats
```

**What to Show:**
- Active nodes (should show your seller from Terminal 2)
- GPUs available by type
- Job queue statistics
- Pricing information

**Example Output:**
```
Marketplace Statistics
Active Nodes: 1

GPUs Available:
  CUDA: 1 nodes ($2.00-$2.00/hr)

Job Queue:
  Pending: 0
  Executing: 0
  Completed: 0
  Failed: 0
```

---

### Step 5: Check Wallet (Optional)

```
> wallet
```

Shows wallet address and USDC balance (if configured).

---

### Step 6: Submit a Job

**Option A: Submit from File (Recommended for Demo)**

```
> submit
Path to Python script: examples/demo_gpu_power.py
Max price per hour (USD) [10.0]: 2.0
Timeout (seconds) [3600]: 3600
Required GPU type (cuda/mps/none) [none]: cuda
Wait for completion? (y/n) [n]: y
```

**Option B: Use Template**

```
> templates
> template
Select template (number or name): 1
[Enter parameters if needed]
Max price per hour (USD) [10.0]: 2.0
Wait for completion? (y/n) [n]: y
```

**What Happens:**
1. Job is submitted to queue
2. Beautiful success panel appears with job ID
3. Live monitoring starts automatically (if `y` to wait)

**Visual Output:**
```
┌─ ✓ Job Submitted ─────────────────────────────────┐
│ Job ID: abc123...                                 │
│ Status: PENDING                                   │
│ Max Price: $2.0/hr                                │
│ Timeout: 3600s                                    │
└───────────────────────────────────────────────────┘

Job submitted to queue. Sellers will claim when available.

Starting live monitoring...
```

---

### Step 7: Live Job Monitoring (Terminal 3)

If you chose to wait, you'll see a **live status dashboard** with:

1. **Job Status Panel:**
   - Job ID
   - Current status (PENDING → CLAIMED → EXECUTING → COMPLETED)
   - Seller information (when claimed)
   - Node information
   - Elapsed time
   - Duration (when completed)
   - Cost

2. **Payment Panel:**
   - Payment status
   - Transaction hash (when processed)
   - Amount in USDC
   - x402 payment status

**Visual Example:**
```
┌─ Job Status ──────────────────────────────────────┐
│ Job ID: abc123...                                 │
│ Status: EXECUTING                                 │
│ Seller: 0xdef456...                               │
│ Node: node_xyz789...                              │
│ Elapsed: 5.2s                                     │
│                                                   │
│ ⚡ GPU compute in progress...                     │
└───────────────────────────────────────────────────┘
┌─ x402 Payment ────────────────────────────────────┐
│ ⏳ Payment processing...                          │
└───────────────────────────────────────────────────┘
```

**Status Transitions:**
- PENDING (yellow) → Waiting for seller
- CLAIMED (blue) → Seller claimed job
- EXECUTING (cyan) → Job running on GPU
- COMPLETED (green) → Job finished successfully
- Payment processing → x402 payment in progress

---

### Step 8: Watch Job Execution (Terminal 2 - Seller)

**What to Watch:**

```
Found matching job: abc123...
Claiming job...
Job claimed successfully!

Starting job execution...
[Container starting...]
[GPU job running...]

=== GPU POWER DEMO OUTPUT ===
GPU Detected: NVIDIA GeForce RTX 4090
GPU Memory: 24.0 GB

[1] MATRIX MULTIPLICATION BENCHMARK
    1000x1000 matrices: 0.15ms per op | 133.33 TFLOPS
    2000x2000 matrices: 1.23ms per op | 130.08 TFLOPS
    4000x4000 matrices: 9.87ms per op | 129.68 TFLOPS

[2] NEURAL NETWORK INFERENCE
    Model size: 67,108,864 parameters
    Throughput: 15,234 samples/second
    Latency: 4.20ms per batch

[3] TRAINING SIMULATION
    Epoch 1/5: Loss=0.1234 | Time=2.34s
    Epoch 2/5: Loss=0.0987 | Time=2.31s
    ...
    Epoch 5/5: Loss=0.0798 | Time=2.32s

TOTAL COMPUTE TIME: 13.45 seconds
GPU MEMORY USED: 2.34 GB

Job execution completed
Exit code: 0

✓ Job abc123... completed - Earned $0.0075 USDC
  Session Total: $0.0075 | Jobs: 1
```

**Key Points to Highlight:**
1. **GPU is being used** - Show CUDA/MPS device
2. **Real compute** - Matrix multiplication, neural networks
3. **Performance metrics** - TFLOPS, throughput
4. **Memory usage** - GPU memory allocated
5. **Duration** - Actual compute time
6. **Earnings** - Payment received

---

### Step 9: Payment Processing (Terminal 1 - Marketplace)

**What to Watch:**

```
[INFO] Job completed: abc123...
[INFO] Calculating payment: Duration=13.45s, Price=$2.00/hr
[INFO] Payment amount: $0.0075 USDC
[INFO] Processing x402 payment...
[INFO] Payment Required (402): Amount=$0.0075 USDC
[INFO] Payment signature verified
[INFO] Settling payment...
[INFO] Payment settled: tx_hash=0xabc123... (testnet_mode: simulated)
[INFO] Job marked as COMPLETED
```

**Key Points:**
1. **Per-second billing** - Duration: 13.45 seconds
2. **Cost calculation** - Price: $2.00/hour = $0.000556/second
3. **Total cost** - 13.45 × $0.000556 = $0.0075 USDC
4. **x402 protocol** - Payment Required (402 status)
5. **Payment settlement** - Trustless micropayment
6. **Testnet mode** - Simulated (logged, not transferred)

---

### Step 10: Final Results (Terminal 3 - Buyer)

**Live Dashboard Updates:**
- Status changes to COMPLETED
- Cost breakdown appears
- Payment transaction hash shown
- Job output displayed

**Final Status Display:**
```
┌─ Job Status ──────────────────────────────────────┐
│ Job ID: abc123...                                 │
│ Status: COMPLETED                                 │
│ Seller: 0xdef456...                               │
│ Duration: 13.45s                                  │
│ Cost: $0.0075 USDC                                │
│                                                   │
│ ✓ Job completed successfully!                     │
└───────────────────────────────────────────────────┘
┌─ x402 Payment ────────────────────────────────────┐
│ Transaction: 0xabc123...                          │
│ ✓ Payment processed via x402                      │
│ Amount: $0.0075 USDC                              │
└───────────────────────────────────────────────────┘

┌─ Job Output ──────────────────────────────────────┐
│ [Full GPU demo output...]                         │
│ [Matrix multiplication results...]                │
│ [Neural network metrics...]                       │
│ [Training simulation results...]                  │
└───────────────────────────────────────────────────┘
```

---

### Step 11: Check Seller Earnings (Terminal 2)

**What to Show:**
- Earnings updated in real-time
- Session total: $0.0075 USDC
- Jobs completed: 1
- Status: Available (ready for next job)

---

## Demo Job Recommendations

### Best for Demo: `examples/demo_gpu_power.py`

**Why:**
- ✅ Clearly shows GPU utilization
- ✅ Demonstrates real compute (matrix multiplication, neural networks, training)
- ✅ Takes ~30-60 seconds (good demo length)
- ✅ Produces clear output showing GPU performance
- ✅ Shows TFLOPS, throughput, memory usage

**Duration:** ~30-60 seconds
**Cost:** ~$0.0075 - $0.03 USDC

### Alternative: `examples/test_gpu.py`

**Why:**
- ✅ Quick 5-second test
- ✅ Simple GPU verification
- ✅ Good for rapid demos

**Duration:** ~5 seconds
**Cost:** ~$0.0001 - $0.0014 USDC

### Alternative: `examples/mnist_train.py`

**Why:**
- ✅ ML training example
- ✅ Shows realistic workload
- ✅ Longer demo (~60 seconds)

**Duration:** ~60 seconds
**Cost:** ~$0.01 - $0.03 USDC

---

## Enhanced Terminal Features

### 1. Live Monitoring (`wait` command)

```
> wait abc123...
```

Shows:
- Real-time status updates
- Live panels for job status and payment
- Status transitions with visual cues
- Payment processing visualization

### 2. Monitor Command (`monitor` command)

```
> monitor abc123...
```

Same as `wait` - shows live dashboard view.

### 3. Job Status Display

```
> status abc123...
```

Shows:
- Beautiful panels with job information
- Timeline of job lifecycle
- Payment details
- Job output (if completed)

### 4. Job List

```
> list
```

Shows:
- Rich table with all your jobs
- Status, duration, cost columns
- Filtered by status

### 5. Marketplace Stats

```
> stats
```

Shows:
- Active nodes
- GPU availability
- Job queue statistics
- Pricing information

---

## Quick Demo Script

**For a 10-minute demo:**

1. **Setup (1 min)**
   - Terminal 1: Start marketplace
   - Terminal 2: Start seller
   - Terminal 3: Start buyer CLI

2. **Show Stats (1 min)**
   - `stats` - Show marketplace
   - `wallet` - Show wallet (optional)

3. **Submit Job (2 min)**
   - `submit` - Use `examples/demo_gpu_power.py`
   - Set price: $2.0/hr
   - Wait for completion: `y`

4. **Watch Execution (5 min)**
   - Terminal 3: Live monitoring dashboard
   - Terminal 2: Job execution output
   - Terminal 1: Payment processing logs

5. **Show Results (1 min)**
   - Terminal 3: Final job status
   - Terminal 2: Earnings update
   - Emphasize: "Pay per second, trustless, decentralized"

---

## Key Talking Points

### x402 Payment Protocol
- "x402 enables trustless micropayments"
- "Payment happens after job completion"
- "Per-second billing - you only pay for what you use"
- "No escrow needed - trustless protocol"
- "Testnet mode simulates payments for demo"

### GPU Utilization
- "This is real GPU compute, not simulation"
- "We're processing 130+ TFLOPS"
- "This same infrastructure scales to thousands of GPUs"
- "Real-time GPU metrics visible in output"

### Decentralization
- "No single point of failure"
- "Anyone with a GPU can become a seller"
- "Marketplace is just a coordinator, payments are on-chain"
- "Terminal-based interface makes it developer-friendly"

### Cost Efficiency
- "$0.0075 for 13 seconds of GPU compute"
- "That's $2.00/hour vs $4.00/hour on AWS"
- "No minimum commitment, pay per second"
- "Payment processed automatically via x402"

---

## Troubleshooting

### Issue: Buyer CLI can't connect to marketplace
**Solution:**
- Check marketplace is running on port 8000
- Verify `MARKETPLACE_URL` in config
- Check firewall/network settings

### Issue: Seller doesn't detect GPU
**Solution:**
```bash
python -c "import torch; print('CUDA:', torch.cuda.is_available())"
# Install PyTorch with CUDA if needed
```

### Issue: Jobs stuck in PENDING
**Solution:**
- Verify seller agent is running
- Check Terminal 2 logs
- Verify seller has matching GPU requirements

### Issue: Payment not processing
**Solution:**
- Check `TESTNET_MODE=true` (for demo)
- Verify RPC_URL is correct
- Check marketplace logs in Terminal 1

---

## Success Indicators

✅ **Demo is successful if you show:**
1. Job created and submitted (Terminal 3)
2. GPU executing the job (Terminal 2 - visible output)
3. Payment calculated and processed (Terminal 1 - logs)
4. Buyer sees results and cost (Terminal 3 - live dashboard)
5. Seller sees earnings update (Terminal 2 - stats)

---

**Good luck with your terminal demo! 🐝🚀**

The terminal interface makes it easy to show the complete flow without the complexity of a web frontend!

