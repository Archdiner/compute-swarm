# ComputeSwarm Hackathon Demo Plan

## Demo Overview

**Goal**: Show end-to-end flow of creating a job, submitting it, watching it execute with GPU acceleration, and demonstrating x402 payment processing.

**Duration**: ~10-15 minutes

**Key Highlights**:
1. ✅ Create and submit a GPU compute job
2. ✅ Real-time job execution with GPU utilization
3. ✅ x402 payment protocol demonstration
4. ✅ Buyer and seller perspectives

---

## Prerequisites Setup (Do This First!)

### 1. Supabase Setup (5 minutes)
```bash
# 1. Go to https://supabase.com and create free account
# 2. Create new project
# 3. Get your credentials:
#    - Project URL (e.g., https://xxxxx.supabase.co)
#    - Anon Key (starts with eyJ...)
# 4. Run database schema:
#    - Go to SQL Editor in Supabase dashboard
#    - Run: src/database/schema_v2.sql
```

### 2. Environment Configuration
Create `.env` file in project root:
```bash
# Database
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJxxx...

# Network (use testnet for demo)
NETWORK=base-sepolia
RPC_URL=https://sepolia.base.org
USDC_CONTRACT_ADDRESS=0x036CbD53842c5426634e7929541eC2318f3dCF7e

# Testnet mode (simulates payments - perfect for demo!)
TESTNET_MODE=true

# Seller (optional - auto-generated if not set)
SELLER_PRIVATE_KEY=0x...  # Generate test wallet
BUYER_PRIVATE_KEY=0x...   # Generate test wallet

# Optional
LOG_LEVEL=INFO
MARKETPLACE_HOST=0.0.0.0
MARKETPLACE_PORT=8000
FRONTEND_URL=http://localhost:3000
```

### 3. Install Dependencies
```bash
# Python dependencies
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Frontend dependencies
cd frontend
npm install
cd ..
```

### 4. Test GPU Detection
```bash
# Verify GPU is detected
python -c "import torch; print('CUDA:', torch.cuda.is_available()); print('MPS:', hasattr(torch.backends, 'mps') and torch.backends.mps.is_available())"
```

### 5. MetaMask Setup (for frontend)
- Install MetaMask browser extension
- Add Base Sepolia testnet:
  - Network Name: Base Sepolia
  - RPC URL: https://sepolia.base.org
  - Chain ID: 84532
  - Currency Symbol: ETH
  - Block Explorer: https://sepolia-explorer.base.org
- Get testnet ETH (from faucet if needed)
- Get testnet USDC (if using real payments - but we'll use testnet_mode=True)

---

## Demo Job: GPU Power Demo

**Recommended Job**: `examples/demo_gpu_power.py`

**Why This Job?**
- ✅ Clearly shows GPU utilization
- ✅ Demonstrates real compute (matrix multiplication, neural networks, training)
- ✅ Takes ~30-60 seconds (good demo length)
- ✅ Produces clear output showing GPU performance
- ✅ Shows TFLOPS, throughput, memory usage

**Alternative Jobs**:
- `examples/test_gpu.py` - Quick 5-second test
- `examples/mnist_train.py` - ML training (longer, ~60 seconds)

---

## Demo Script

### Terminal Layout

```
┌─────────────────────────────────────────────────────────┐
│  Terminal 1: Marketplace Server                         │
│  (Shows API logs, job processing, payment logs)         │
├─────────────────────────────────────────────────────────┤
│  Terminal 2: Seller Agent                               │
│  (Shows GPU detection, job execution, earnings)         │
├─────────────────────────────────────────────────────────┤
│  Terminal 3: Frontend (Optional - can use browser UI)   │
│  (Shows frontend build logs)                            │
└─────────────────────────────────────────────────────────┘

Browser Window: http://localhost:3000
(Shows buyer/seller views, job submission, status updates)
```

### Step-by-Step Demo

#### Step 1: Start Marketplace Server
```bash
# Terminal 1
python -m src.marketplace.server
```

**What to Show**:
- Server starting on http://localhost:8000
- API docs available at http://localhost:8000/docs
- Logs showing server is ready

**Checkpoint**: Verify server is running:
```bash
curl http://localhost:8000/health
# Should return: {"status": "ok"}
```

---

#### Step 2: Start Seller Agent
```bash
# Terminal 2
python -m src.seller.agent
```

**What to Show**:
- GPU detection output (NVIDIA/Apple Silicon)
- Node registration with marketplace
- Agent polling for jobs
- Session stats: Earnings $0.00, Jobs Completed: 0

**Key Points**:
- "This machine is now a GPU seller on the marketplace"
- "Agent is polling for jobs to execute"
- "Earnings will update after jobs complete"

**Checkpoint**: Verify seller is registered:
```bash
curl http://localhost:8000/api/v1/nodes
# Should show your node in the list
```

---

#### Step 3: Start Frontend (Optional but Recommended)
```bash
# Terminal 3
cd frontend
npm run dev
```

**What to Show**:
- Frontend starting on http://localhost:3000
- Browser opens automatically

**Checkpoint**: Open http://localhost:3000 in browser

---

#### Step 4: Show Seller View (Browser)
1. Open http://localhost:3000
2. Navigate to "Seller" view (if available)
3. Show:
   - GPU registered
   - Status: Available
   - Earnings: $0.00
   - Jobs Completed: 0

**Or show Terminal 2**:
- Point to seller agent output
- Highlight GPU information
- Show "Status: Available, waiting for jobs"

---

#### Step 5: Create and Submit Job (Browser - Buyer View)
1. Switch to "Buyer" view in browser
2. Click "Create Job" or "Submit Job"
3. **Use the demo job**:
   - **Option A: Upload file**
     - Use `examples/demo_gpu_power.py`
     - Paste contents into script editor
   - **Option B: Use template** (if available)
     - Select "GPU Benchmark" or similar
4. Configure job:
   - **Max Price**: $2.00/hour (reasonable for demo)
   - **Timeout**: 3600 seconds (1 hour)
   - **GPU Type**: Leave empty (any GPU) or select your GPU type
5. **Connect Wallet** (MetaMask):
   - Connect MetaMask
   - Ensure on Base Sepolia testnet
   - Show wallet address
6. **Submit Job**

**What Happens**:
- Job submitted to marketplace
- Job ID generated
- Job status: PENDING
- Job appears in job list

**Show in Browser**:
- Job in "Pending" status
- Job ID visible
- "Waiting for seller to claim..."

---

#### Step 6: Show Job Claiming (Terminal 2 - Seller)
**What to Watch**:
- Seller agent logs: "Found matching job: {job_id}"
- "Claiming job..."
- "Job claimed successfully"
- "Preparing job execution..."

**What to Show**:
- Real-time logs in Terminal 2
- Job transitioning from PENDING → CLAIMED → RUNNING

**Browser Update**:
- Job status changes to "Claimed"
- Seller address appears
- Status changes to "Running"

---

#### Step 7: Show Job Execution (Terminal 2 - Seller)
**What to Watch**:
```
Starting job execution...
Running: demo_gpu_power.py

[GPU POWER DEMO OUTPUT]
============================================================
  ComputeSwarm GPU Power Demo
============================================================

GPU Detected: NVIDIA GeForce RTX 4090
GPU Memory: 24.0 GB
CUDA Version: 12.1

Using device: cuda
------------------------------------------------------------

[1] MATRIX MULTIPLICATION BENCHMARK
    (This is what AI/ML models do millions of times)
    
    1000x1000 matrices: 0.15ms per op | 133.33 TFLOPS
    2000x2000 matrices: 1.23ms per op | 130.08 TFLOPS
    4000x4000 matrices: 9.87ms per op | 129.68 TFLOPS

[2] NEURAL NETWORK INFERENCE
    (Simulating AI model prediction)
    
    Model size: 67,108,864 parameters (256.4 MB)
    Batch size: 64
    Throughput: 15,234 samples/second
    Latency: 4.20ms per batch

[3] TRAINING SIMULATION
    (What happens when you train an AI model)
    
    Epoch 1/5: Loss=0.1234 | Time=2.34s
    Epoch 2/5: Loss=0.0987 | Time=2.31s
    Epoch 3/5: Loss=0.0876 | Time=2.33s
    Epoch 4/5: Loss=0.0821 | Time=2.30s
    Epoch 5/5: Loss=0.0798 | Time=2.32s

============================================================
  TOTAL COMPUTE TIME: 13.45 seconds
  DEVICE USED: cuda
  GPU: NVIDIA GeForce RTX 4090
  GPU MEMORY USED: 2.34 GB
============================================================

This compute was paid for with USDC via x402 protocol!

Job execution completed
Exit code: 0
```

**Key Points to Highlight**:
1. **GPU is being used** - Show CUDA/MPS device
2. **Real compute** - Matrix multiplication, neural networks
3. **Performance metrics** - TFLOPS, throughput
4. **Memory usage** - GPU memory allocated
5. **Duration** - Actual compute time

**Visual Impact**:
- Point to TFLOPS numbers: "This GPU is processing 130+ trillion operations per second"
- Point to training simulation: "This is what happens when training AI models"
- Point to memory: "2.3 GB of GPU memory being used"

---

#### Step 8: Show Payment Processing (Terminal 1 - Marketplace)
**What to Watch**:
```
[INFO] Job completed: {job_id}
[INFO] Calculating payment: Duration=13.45s, Price=$2.00/hr
[INFO] Payment amount: $0.0075 USDC
[INFO] Processing x402 payment...
[INFO] Payment Required (402): Amount=$0.0075 USDC
[INFO] Payment signature verified
[INFO] Settling payment...
[INFO] Payment settled: tx_hash=0xabc123... (testnet_mode: simulated)
[INFO] Job marked as COMPLETED
```

**Key Points**:
1. **Payment calculation**: Per-second billing
   - Duration: 13.45 seconds
   - Price: $2.00/hour = $0.000556/second
   - Cost: 13.45 × $0.000556 = $0.0075 USDC

2. **x402 Protocol**:
   - Payment Required (402 status code)
   - Payment signature verification
   - Trustless micropayment

3. **Payment Settlement**:
   - In testnet_mode: Simulated (logged, not transferred)
   - In production: Real USDC transfer via EIP-3009

**Show in Browser**:
- Job status: COMPLETED
- Execution duration: 13.45 seconds
- Total cost: $0.0075 USDC
- Payment transaction hash (if real) or "Simulated (testnet)"

---

#### Step 9: Show Seller Earnings (Terminal 2 - Seller)
**What to Watch**:
```
Job completed successfully
Payment received: $0.0075 USDC
===========================================================
  ComputeSwarm Seller Agent
===========================================================
  Node ID:      node_abc123...
  GPU:          NVIDIA GeForce RTX 4090
  Status:       Available
-----------------------------------------------------------
  Session Earnings:  $0.0075 USDC
  Jobs Completed:    1
===========================================================
```

**Key Points**:
- Earnings updated in real-time
- Job count incremented
- Seller is ready for next job

**Show in Browser (Seller View)**:
- Earnings: $0.0075 USDC
- Jobs Completed: 1
- Status: Available (ready for next job)

---

#### Step 10: Show Results (Browser - Buyer View)
**What to Show**:
1. Job status: COMPLETED
2. Results output (full GPU demo output)
3. Cost breakdown:
   - Execution duration: 13.45 seconds
   - Price: $2.00/hour
   - Total cost: $0.0075 USDC
4. Payment transaction (if real) or testnet indicator

**Key Points**:
- Complete job output visible
- Payment processed successfully
- Total cost very low (pennies)

---

## Demo Script Summary

### Opening (1 min)
- "ComputeSwarm is a decentralized GPU marketplace using x402 micropayments"
- "Today I'll show you the full flow: job creation, GPU execution, and payment"

### Setup (2 min)
1. Show marketplace server running (Terminal 1)
2. Show seller agent running with GPU detected (Terminal 2)
3. Show frontend/browser (Terminal 3/Browser)

### Job Submission (2 min)
4. Create job using `demo_gpu_power.py`
5. Show job configuration (price, timeout)
6. Submit job with wallet connected

### Execution (5 min)
7. Show job being claimed by seller
8. **Highlight**: Real-time GPU execution with metrics
9. Show compute output (TFLOPS, neural networks, training)
10. Point out GPU utilization

### Payment (2 min)
11. Show payment calculation (per-second billing)
12. Show x402 payment processing
13. Show payment settlement (testnet mode)

### Wrap-up (1 min)
14. Show seller earnings updated
15. Show buyer results and cost
16. Emphasize: "Pay per second, trustless, decentralized"

---

## Troubleshooting

### Issue: Seller doesn't detect GPU
**Solution**:
```bash
# Check GPU detection
python -c "import torch; print('CUDA:', torch.cuda.is_available())"
# Install PyTorch with CUDA if needed
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

### Issue: Marketplace can't connect to Supabase
**Solution**:
- Check SUPABASE_URL and SUPABASE_ANON_KEY in .env
- Verify Supabase project is active
- Check database schema is applied

### Issue: Frontend can't connect to marketplace
**Solution**:
- Check marketplace is running on port 8000
- Check CORS settings in marketplace config
- Verify FRONTEND_URL in .env matches frontend URL

### Issue: Jobs stuck in PENDING
**Solution**:
- Verify seller agent is running
- Check seller can see jobs: Look at Terminal 2 logs
- Verify seller has matching GPU requirements

### Issue: Payment not processing
**Solution**:
- Check TESTNET_MODE=true (for demo)
- Verify RPC_URL is correct
- Check wallet has testnet ETH/USDC (if using real payments)

---

## Alternative Demo Flows

### Quick Demo (5 minutes)
1. Use `examples/test_gpu.py` (faster, ~5 seconds)
2. Skip frontend, use CLI buyer
3. Focus on: Submit → Execute → Payment

### Technical Deep Dive (20 minutes)
1. Use `examples/mnist_train.py` (ML training)
2. Show Docker containerization
3. Show detailed payment flow
4. Show multiple jobs in queue

### Multi-Node Demo
1. Run seller agent on 2 machines
2. Show job matching across multiple GPUs
3. Show price competition

---

## Key Talking Points

### x402 Payment Protocol
- "x402 enables trustless micropayments"
- "Payment happens after job completion"
- "Per-second billing - you only pay for what you use"
- "No escrow needed - trustless protocol"

### GPU Utilization
- "This is real GPU compute, not simulation"
- "We're processing 130+ TFLOPS"
- "This same infrastructure scales to thousands of GPUs"

### Decentralization
- "No single point of failure"
- "Anyone with a GPU can become a seller"
- "Marketplace is just a coordinator, payments are on-chain"

### Cost Efficiency
- "$0.0075 for 13 seconds of GPU compute"
- "That's $2.00/hour vs $4.00/hour on AWS"
- "No minimum commitment, pay per second"

---

## Success Criteria

✅ **Demo is successful if you show**:
1. Job created and submitted
2. GPU executing the job (visible output)
3. Payment calculated and processed
4. Buyer sees results and cost
5. Seller sees earnings update

✅ **Bonus points for**:
- Showing multiple jobs
- Showing different GPU types
- Showing real-time status updates
- Showing payment transaction (if real)

---

## Post-Demo Q&A Preparation

**Common Questions**:
1. **"Can this scale?"** → Yes, marketplace is stateless, uses Supabase
2. **"What about security?"** → Docker sandboxing, network isolation
3. **"What about payment disputes?"** → x402 is trustless, no disputes needed
4. **"Real-world use cases?"** → AI training, inference, scientific computing
5. **"How does this compare to AWS?"** → Cheaper, pay-per-second, no minimums

---

Good luck with your demo! 🐝🚀

