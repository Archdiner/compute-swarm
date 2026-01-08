# Show HN: ComputeSwarm – The General-Purpose Compute API for AI Agents

**TL;DR**: We built a GPU marketplace where the buyer is software. Train, infer, process, generate—all via streaming micropayments.

---

**The Problem**:
AI Agents are getting smarter, but they're stuck. When they need heavy compute—fine-tuning, large model inference, data processing—they can't access it.

Why? Because cloud infrastructure is built for *humans*:
*   It requires KYC. Agents don't have passports.
*   It requires credit cards. Agents have wallets.
*   It requires clicking dashboards. Agents use APIs.

**The Solution**:
**ComputeSwarm** is a decentralized compute API for autonomous software.

*   **Wallet-Native Auth**: The Agent's private key *is* its login.
*   **Streaming Payments**: Pay USDC per second via **x402 Protocol** on Base L2.
*   **Any Workload**: Fine-tuning is just one capability. Agents can also run heavy inference, process datasets, or generate images.

**Example Use Cases**:
| Capability | What the Agent Does |
|---|---|
| Self-Improvement | Fine-tunes a LoRA adapter on a new domain |
| Heavy Inference | Runs a 70B model it can't run locally |
| Data Processing | Indexes 10GB of documents for RAG |
| Image Generation | Creates assets for a user request |

**Technical Highlights**:
*   **Two-Phase Isolation**: Phase 1 (network on) downloads weights; Phase 2 (network off) runs the job air-gapped.
*   **Consumer GPU Support**: Optimized for 3090s/4090s with gradient accumulation.
*   **Open Source**: 100% MIT licensed.

**Why We Built This**:
We believe that in 3 years, most GPUs will be leased by software, not people. ComputeSwarm is infrastructure for that future.

Built for the **x402 Hackathon**.

**Repo**: https://github.com/Archdiner/compute-swarm
