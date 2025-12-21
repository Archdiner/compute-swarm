# x402 Quick Reference Guide

## Installation

```bash
pip install x402>=0.2.1
```

## Basic Concepts

### The Flow

1. **Client requests resource** → Server responds `402 Payment Required` + `PAYMENT-REQUIRED` header
2. **Client creates payment** → Signs EIP-712 authorization
3. **Client retries with proof** → Sends `PAYMENT-SIGNATURE` header
4. **Server verifies & settles** → Returns `200 OK` + `PAYMENT-RESPONSE` header

### Key Components

- **Network:** `base-sepolia` (testnet) or `base-mainnet` (production)
- **Scheme:** `exact` (exact amount transfer)
- **Token:** USDC (6 decimals)
- **Signature:** EIP-712 typed data signature

---

## Seller Implementation (FastAPI)

### Minimal Setup

```python
from fastapi import FastAPI
from x402.servers.fastapi import require_payment

app = FastAPI()

# Apply x402 middleware to specific path
app.middleware("http")(
    require_payment(
        path="/protected-resource",
        price="1000000",  # $1.00 in USDC (6 decimals)
        pay_to_address="0xYOUR_SELLER_ADDRESS",
        network="base-sepolia"
    )
)

@app.get("/protected-resource")
async def protected():
    return {"data": "This costs $1"}
```

### Dynamic Pricing

```python
from fastapi import Request

def calculate_price(request: Request) -> str:
    """Calculate price based on request parameters"""
    # Example: price based on duration
    params = request.query_params
    duration = int(params.get("duration", 60))

    price_per_hour_usd = 0.50
    price_usd = (duration / 3600) * price_per_hour_usd

    # Convert to USDC wei (6 decimals)
    price_usdc = int(price_usd * 1_000_000)

    return str(price_usdc)

app.middleware("http")(
    require_payment(
        path="/compute",
        price=calculate_price,  # Function instead of fixed amount
        pay_to_address="0xYOUR_ADDRESS",
        network="base-sepolia"
    )
)
```

### Per-Path Configuration

```python
# Different prices for different endpoints
app.middleware("http")(
    require_payment(
        path="/expensive",
        price="10000000",  # $10
        pay_to_address=SELLER_ADDRESS,
        network="base-sepolia"
    )
)

app.middleware("http")(
    require_payment(
        path="/cheap",
        price="100000",  # $0.10
        pay_to_address=SELLER_ADDRESS,
        network="base-sepolia"
    )
)
```

---

## Buyer Implementation

### Using httpx (Async)

```python
from eth_account import Account
from x402.clients.httpx import x402HttpxClient

# Load your private key
account = Account.from_key("0xYOUR_PRIVATE_KEY")

# Create x402-enabled client
async with x402HttpxClient(account=account, base_url="https://api.example.com") as client:
    # Automatically handles 402 and retries with payment
    response = await client.get("/protected-resource")

    print(response.json())

    # Check payment details
    if "PAYMENT-RESPONSE" in response.headers:
        print(f"Payment confirmed: {response.headers['PAYMENT-RESPONSE']}")
```

### Using requests (Sync)

```python
from eth_account import Account
from x402.clients.requests import x402_requests

account = Account.from_key("0xYOUR_PRIVATE_KEY")

# Create session
session = x402_requests(account)

# Make request (payment handled automatically)
response = session.get("https://api.example.com/protected-resource")
print(response.json())
```

### Manual Payment Handling

```python
import httpx
import base64
import json
from eth_account import Account

account = Account.from_key("0xYOUR_PRIVATE_KEY")

# 1. Make initial request
response = httpx.get("https://api.example.com/protected")

if response.status_code == 402:
    # 2. Parse payment required
    payment_required_b64 = response.headers["PAYMENT-REQUIRED"]
    payment_required = json.loads(base64.b64decode(payment_required_b64))

    print(f"Payment required: {payment_required}")

    # 3. Create payment payload (using x402 SDK)
    from x402 import create_payment_payload

    payment_payload = create_payment_payload(
        account=account,
        payment_required=payment_required,
        selected_accept_index=0  # Use first accepted payment method
    )

    # 4. Encode payload
    payment_signature = base64.b64encode(
        json.dumps(payment_payload).encode()
    ).decode()

    # 5. Retry with payment
    response = httpx.get(
        "https://api.example.com/protected",
        headers={"PAYMENT-SIGNATURE": payment_signature}
    )

    print(response.json())
```

---

## Headers Reference

### PAYMENT-REQUIRED (Server → Client)

Base64-encoded JSON with structure:

```json
{
  "x402Version": "1",
  "accepts": [
    {
      "network": "base-sepolia",
      "scheme": "exact",
      "recipient": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
      "amount": "1000000",
      "token": "USDC"
    }
  ],
  "description": "Access to premium API",
  "error": null
}
```

### PAYMENT-SIGNATURE (Client → Server)

Base64-encoded JSON with structure:

```json
{
  "x402Version": "1",
  "scheme": "exact",
  "network": "base-sepolia",
  "payload": {
    "signature": "0xabc123...",
    "authorization": {
      "from": "0x123abc...",
      "to": "0x742d35...",
      "value": "1000000",
      "validAfter": 0,
      "validBefore": 9999999999,
      "nonce": "0x..."
    }
  }
}
```

### PAYMENT-RESPONSE (Server → Client)

Base64-encoded JSON with structure:

```json
{
  "success": true,
  "transaction": "0xdef456...",
  "network": "base-sepolia",
  "payer": "0x123abc..."
}
```

---

## Price Calculation Helper

```python
def usd_to_usdc_wei(usd_amount: float) -> str:
    """
    Convert USD to USDC smallest unit (6 decimals)

    Examples:
        $1.00 → "1000000"
        $0.50 → "500000"
        $0.001 → "1000"
    """
    usdc_wei = int(usd_amount * 1_000_000)
    return str(usdc_wei)

def usdc_wei_to_usd(usdc_wei: str) -> float:
    """
    Convert USDC smallest unit to USD

    Examples:
        "1000000" → $1.00
        "500000" → $0.50
        "1000" → $0.001
    """
    return int(usdc_wei) / 1_000_000
```

---

## Testing with Base Sepolia

### Get Test Tokens

1. **Get Sepolia ETH:**
   - Visit: https://www.coinbase.com/faucets/base-ethereum-sepolia-faucet
   - Connect your wallet
   - Request testnet ETH (for gas fees)

2. **Get Test USDC:**
   - Contract: `0x036CbD53842c5426634e7929541eC2318f3dCF7e`
   - Use a faucet or bridge from Sepolia ETH

### Verify Transactions

- **Base Sepolia Explorer:** https://sepolia.basescan.org/
- Search for your wallet address or transaction hash

### Check Balance

```python
from web3 import Web3

w3 = Web3(Web3.HTTPProvider("https://sepolia.base.org"))

# USDC contract on Base Sepolia
USDC_ADDRESS = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"

# Minimal ABI for balanceOf
ABI = [{"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]

usdc = w3.eth.contract(address=USDC_ADDRESS, abi=ABI)

# Check balance
balance = usdc.functions.balanceOf("0xYOUR_ADDRESS").call()
print(f"Balance: {balance / 1_000_000} USDC")
```

---

## Common Patterns

### ComputeSwarm: Per-Second Pricing

```python
def calculate_gpu_price(duration_seconds: int, gpu_type: str) -> str:
    """Calculate price for GPU compute time"""
    PRICES = {
        "cuda": 2.00,  # $2/hour for NVIDIA
        "mps": 0.50,   # $0.50/hour for Apple Silicon
        "cpu": 0.10    # $0.10/hour for CPU
    }

    price_per_hour = PRICES.get(gpu_type, 0.10)
    price_usd = (duration_seconds / 3600) * price_per_hour

    return usd_to_usdc_wei(price_usd)

# Example: 30 seconds on MPS
price = calculate_gpu_price(30, "mps")
# Result: "4167" (approximately $0.00417)
```

### Job-Based Pricing

```python
def price_by_job_type(job_type: str) -> str:
    """Different prices for different job types"""
    PRICES = {
        "inference": 0.01,      # $0.01 per inference
        "training": 0.10,       # $0.10 per training run
        "benchmark": 0.001,     # $0.001 per benchmark
    }

    price_usd = PRICES.get(job_type, 0.05)
    return usd_to_usdc_wei(price_usd)
```

---

## Debugging

### Enable Verbose Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
```

### Inspect Headers

```python
# Client side
response = await client.get("/resource")
print("Status:", response.status_code)
print("Headers:", dict(response.headers))

# Decode PAYMENT-REQUIRED
if "PAYMENT-REQUIRED" in response.headers:
    import base64, json
    decoded = json.loads(base64.b64decode(response.headers["PAYMENT-REQUIRED"]))
    print("Payment Required:", json.dumps(decoded, indent=2))
```

### Test Payment Without Actual Transfer

For development, you can use a mock facilitator or test mode (check x402 SDK docs for test mode).

---

## Security Best Practices

1. **Never commit private keys**
   ```bash
   # Always use environment variables
   SELLER_PRIVATE_KEY=0x...
   BUYER_PRIVATE_KEY=0x...
   ```

2. **Validate payment amounts**
   ```python
   # Server side: verify amount matches expected price
   assert payment["amount"] == expected_price
   ```

3. **Set reasonable validBefore**
   ```python
   # Payment should expire (e.g., 5 minutes)
   validBefore = current_timestamp + 300
   ```

4. **Rate limiting**
   ```python
   # Prevent payment spam
   from slowapi import Limiter
   limiter = Limiter(key_func=get_remote_address)

   @app.get("/resource")
   @limiter.limit("10/minute")
   async def resource():
       ...
   ```

5. **Verify on-chain settlement**
   ```python
   # For critical operations, verify transaction on Base
   from web3 import Web3
   w3 = Web3(Web3.HTTPProvider("https://sepolia.base.org"))

   receipt = w3.eth.get_transaction_receipt(tx_hash)
   assert receipt["status"] == 1  # Success
   ```

---

## Resources

- **x402 Website:** https://www.x402.org/
- **GitHub:** https://github.com/coinbase/x402
- **PyPI:** https://pypi.org/project/x402/
- **Docs:** https://docs.cdp.coinbase.com/x402/welcome
- **Whitepaper:** https://www.x402.org/x402-whitepaper.pdf
- **Base Sepolia:** https://sepolia.basescan.org/

---

## Troubleshooting

### "Insufficient balance"
- Check your USDC balance on Base Sepolia
- Ensure you have ETH for gas fees

### "Invalid signature"
- Verify private key is correct
- Check network matches (base-sepolia vs base-mainnet)
- Ensure EIP-712 domain is correct

### "Payment not found"
- May need to wait for blockchain confirmation (2-5 seconds)
- Check transaction on Base Sepolia explorer

### "402 but no PAYMENT-REQUIRED header"
- Server middleware not configured correctly
- Check server logs for errors

---

Ready to implement x402 in ComputeSwarm! 🚀
