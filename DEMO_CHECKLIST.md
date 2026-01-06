# Demo Day Quick Checklist

## Pre-Demo Setup (Do 30 minutes before)

- [ ] **Supabase**: Project created, schema applied, credentials ready
- [ ] **Environment**: `.env` file configured with all credentials
- [ ] **Dependencies**: All Python and npm packages installed
- [ ] **GPU Test**: `python -c "import torch; print('CUDA:', torch.cuda.is_available())"` works
- [ ] **MetaMask**: Installed, Base Sepolia network added, testnet wallet ready
- [ ] **Demo Job**: `examples/demo_gpu_power.py` file exists and is readable
- [ ] **Terminals**: 3 terminal windows ready (or tabs)
- [ ] **Browser**: Clean browser window ready, MetaMask connected

## Demo Flow (In Order)

### Setup (2 minutes)

- [ ] **Terminal 1**: Start marketplace
  ```bash
  python -m src.marketplace.server
  ```
  - [ ] Verify: Server running on http://localhost:8000
  - [ ] Verify: `curl http://localhost:8000/health` returns OK

- [ ] **Terminal 2**: Start seller agent
  ```bash
  python -m src.seller.agent
  ```
  - [ ] Verify: GPU detected
  - [ ] Verify: Node registered
  - [ ] Verify: "Status: Available, waiting for jobs"

- [ ] **Terminal 3**: Start frontend (optional but recommended)
  ```bash
  cd frontend && npm run dev
  ```
  - [ ] Verify: Frontend on http://localhost:3000
  - [ ] Browser opens automatically

### Job Submission (3 minutes)

- [ ] **Browser**: Open http://localhost:3000
- [ ] **Browser**: Connect MetaMask wallet (Base Sepolia)
- [ ] **Browser**: Navigate to "Buyer" view
- [ ] **Browser**: Click "Create Job" or "Submit Job"
- [ ] **Browser**: Paste contents of `examples/demo_gpu_power.py` OR upload file
- [ ] **Browser**: Set price: $2.00/hour
- [ ] **Browser**: Set timeout: 3600 seconds
- [ ] **Browser**: Submit job
- [ ] **Browser**: Verify job appears with status "PENDING"

### Execution (5 minutes)

- [ ] **Terminal 2**: Watch seller agent claim job
  - [ ] Look for: "Found matching job"
  - [ ] Look for: "Job claimed successfully"
  
- [ ] **Browser**: Job status changes to "CLAIMED" then "RUNNING"

- [ ] **Terminal 2**: Watch job execution output
  - [ ] GPU Power Demo output appears
  - [ ] Matrix multiplication benchmarks
  - [ ] Neural network inference
  - [ ] Training simulation
  - [ ] GPU metrics (TFLOPS, memory usage)

### Payment (2 minutes)

- [ ] **Terminal 1**: Watch marketplace logs
  - [ ] Job completed message
  - [ ] Payment calculation
  - [ ] x402 payment processing
  - [ ] Payment settlement (testnet_mode)

- [ ] **Terminal 2**: Seller earnings update
  - [ ] Earnings: $0.0075+ USDC
  - [ ] Jobs Completed: 1

- [ ] **Browser**: Job status changes to "COMPLETED"
  - [ ] Results output visible
  - [ ] Cost breakdown shown
  - [ ] Payment transaction hash (or testnet indicator)

### Wrap-up (1 minute)

- [ ] Show seller earnings summary
- [ ] Show buyer job results
- [ ] Emphasize: "Pay per second, trustless, decentralized"
- [ ] **Q&A**: Be ready for questions

## Troubleshooting Quick Reference

| Issue | Quick Fix |
|-------|-----------|
| Marketplace won't start | Check `.env` file, verify Supabase credentials |
| Seller can't detect GPU | Check PyTorch installation, verify CUDA/MPS available |
| Jobs stuck in PENDING | Verify seller agent is running, check Terminal 2 logs |
| Frontend won't connect | Check marketplace is running, verify CORS settings |
| Payment not processing | Check TESTNET_MODE=true in .env |
| MetaMask connection fails | Ensure Base Sepolia network is added |

## Key Metrics to Highlight

- **Job Duration**: ~13-60 seconds (depending on job)
- **Cost**: $0.0075 - $0.03 USDC (pennies!)
- **GPU Performance**: 130+ TFLOPS
- **Payment**: Per-second billing
- **Time to Complete**: < 1 minute end-to-end

## Demo Script Talking Points

1. **Opening**: "ComputeSwarm democratizes AI compute through decentralized GPU marketplace with x402 micropayments"

2. **During Execution**: "This is real GPU compute - we're processing 130+ trillion operations per second. The GPU is actually being used right now."

3. **Payment**: "Payment is processed automatically via x402 protocol - trustless, per-second billing. You only pay for what you use."

4. **Wrap-up**: "This same infrastructure scales to thousands of GPUs globally. Anyone can become a seller, anyone can become a buyer."

## Success Indicators

✅ Job submitted successfully
✅ GPU executing job (visible output)
✅ Payment processed (testnet mode)
✅ Seller earnings updated
✅ Buyer sees results and cost

---

**Good luck! 🐝🚀**

