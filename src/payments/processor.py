"""
Payment processor for x402 protocol
Handles payment creation, signing, verification, and USDC transfers
"""

import json
import time
import base64
from typing import Optional, Tuple
from decimal import Decimal
from datetime import datetime, timedelta

from eth_account import Account
from eth_account.messages import encode_typed_data
from web3 import Web3
import structlog

from src.payments.models import (
    PaymentRequired,
    PaymentAccepts,
    PaymentPayload,
    PaymentReceipt,
)

logger = structlog.get_logger()

# Minimal ERC20 ABI for USDC transfers + EIP-3009 transferWithAuthorization
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
    # EIP-3009: transferWithAuthorization for gasless transfers
    {
        "inputs": [
            {"name": "from", "type": "address"},
            {"name": "to", "type": "address"},
            {"name": "value", "type": "uint256"},
            {"name": "validAfter", "type": "uint256"},
            {"name": "validBefore", "type": "uint256"},
            {"name": "nonce", "type": "bytes32"},
            {"name": "v", "type": "uint8"},
            {"name": "r", "type": "bytes32"},
            {"name": "s", "type": "bytes32"},
        ],
        "name": "transferWithAuthorization",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # Check if authorization nonce has been used
    {
        "constant": True,
        "inputs": [
            {"name": "authorizer", "type": "address"},
            {"name": "nonce", "type": "bytes32"},
        ],
        "name": "authorizationState",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
]

# USDC has 6 decimals
USDC_DECIMALS = 6


class PaymentProcessor:
    """
    Handles x402 payment flow:
    - Sellers: Create payment requirements, verify signatures, settle payments
    - Buyers: Sign payment authorizations
    
    Supports two modes:
    - testnet_mode=True: Simulate payments (log but don't transfer)
    - testnet_mode=False: Execute real EIP-3009 transferWithAuthorization
    """

    def __init__(
        self,
        private_key: str,
        rpc_url: str = "https://sepolia.base.org",
        usdc_address: str = "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
        network: str = "base-sepolia",
        testnet_mode: bool = True,
    ):
        self.account = Account.from_key(private_key)
        self.address = self.account.address
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.usdc_address = Web3.to_checksum_address(usdc_address)
        self.usdc = self.w3.eth.contract(address=self.usdc_address, abi=ERC20_ABI)
        self.network = network
        self.chain_id = 84532 if network == "base-sepolia" else 8453  # Base Sepolia or Mainnet
        self.testnet_mode = testnet_mode
        
        if testnet_mode:
            logger.info("payment_processor_testnet_mode", message="Payments will be simulated")
        else:
            logger.info("payment_processor_production_mode", message="Real USDC transfers enabled")

    # ===== SELLER METHODS =====

    def create_payment_required(
        self,
        amount_usdc: Decimal,
        job_id: str,
        description: Optional[str] = None,
        expires_in_seconds: int = 300,
    ) -> PaymentRequired:
        """
        Create x402 Payment Required response for a job.
        
        Args:
            amount_usdc: Amount in USD (will be converted to USDC smallest unit)
            job_id: Job identifier
            description: Human-readable description
            expires_in_seconds: How long the payment request is valid
            
        Returns:
            PaymentRequired object ready to send as 402 response
        """
        # Convert USD to USDC smallest unit (6 decimals)
        amount_wei = int(amount_usdc * Decimal(10 ** USDC_DECIMALS))

        return PaymentRequired(
            x402Version="1",
            accepts=[
                PaymentAccepts(
                    network=self.network,
                    scheme="exact",
                    recipient=self.address,
                    amount=str(amount_wei),
                    token="USDC",
                )
            ],
            description=description or f"GPU compute job {job_id}",
            job_id=job_id,
            expires_at=datetime.utcnow() + timedelta(seconds=expires_in_seconds),
        )

    def encode_payment_required(self, payment_required: PaymentRequired) -> str:
        """Encode PaymentRequired as base64 for HTTP header"""
        return base64.b64encode(
            payment_required.model_dump_json().encode()
        ).decode()

    def verify_payment_signature(
        self,
        payment_payload: PaymentPayload,
        expected_amount: int,
        expected_recipient: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify that a payment signature is valid.
        
        Args:
            payment_payload: The payment payload from the buyer
            expected_amount: Expected amount in USDC smallest unit
            expected_recipient: Expected recipient address
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            payload = payment_payload.payload
            signature = payload.get("signature")
            authorization = payload.get("authorization", {})

            # Verify basic fields
            if authorization.get("to", "").lower() != expected_recipient.lower():
                return False, "Recipient mismatch"

            if int(authorization.get("value", 0)) < expected_amount:
                return False, f"Insufficient amount: got {authorization.get('value')}, expected {expected_amount}"

            # Verify signature timing
            valid_before = authorization.get("validBefore", 0)
            if valid_before < int(time.time()):
                return False, "Payment authorization expired"

            # Reconstruct typed data for verification
            typed_data = self._create_typed_data(
                from_address=authorization.get("from"),
                to=authorization.get("to"),
                value=authorization.get("value"),
                valid_after=authorization.get("validAfter", 0),
                valid_before=valid_before,
                nonce=authorization.get("nonce"),
            )

            # Recover signer address
            encoded = encode_typed_data(full_message=typed_data)
            recovered = Account.recover_message(encoded, signature=signature)

            if recovered.lower() != authorization.get("from", "").lower():
                return False, "Invalid signature"

            return True, None

        except Exception as e:
            logger.error("payment_verification_failed", error=str(e))
            return False, f"Verification error: {str(e)}"

    async def settle_payment(
        self,
        from_address: str,
        amount: int,
        job_id: str,
        payment_payload: Optional[PaymentPayload] = None,
    ) -> PaymentReceipt:
        """
        Settle a payment by transferring USDC from buyer to seller.
        
        In testnet_mode: Simulates the transfer (verifies balance, logs, returns fake tx hash)
        In production mode: Executes real EIP-3009 transferWithAuthorization on-chain
        
        Args:
            from_address: Buyer's address
            amount: Amount in USDC smallest unit
            job_id: Job identifier
            payment_payload: Signed payment authorization from buyer (required for production)
            
        Returns:
            PaymentReceipt with transaction details
        """
        try:
            # Check buyer's USDC balance
            buyer_balance = self.usdc.functions.balanceOf(
                Web3.to_checksum_address(from_address)
            ).call()

            if buyer_balance < amount:
                return PaymentReceipt(
                    success=False,
                    amount_usdc=str(amount),
                    from_address=from_address,
                    to_address=self.address,
                    job_id=job_id,
                    error=f"Insufficient USDC balance: {buyer_balance} < {amount}",
                )

            if self.testnet_mode:
                # Testnet mode: Log the settlement but don't execute on-chain
                logger.info(
                    "payment_settlement_simulated",
                    from_address=from_address,
                    to_address=self.address,
                    amount=amount,
                    job_id=job_id,
                    mode="testnet"
                )

                # Return success receipt with simulated tx hash
                return PaymentReceipt(
                    success=True,
                    tx_hash=f"0xsim_{job_id.replace('-', '')}",  # Simulated tx hash
                    amount_usdc=str(amount),
                    from_address=from_address,
                    to_address=self.address,
                    job_id=job_id,
                )
            else:
                # Production mode: Execute real transfer
                return await self._execute_transfer_with_authorization(
                    from_address=from_address,
                    amount=amount,
                    job_id=job_id,
                    payment_payload=payment_payload
                )

        except Exception as e:
            logger.error("payment_settlement_failed", error=str(e), job_id=job_id)
            return PaymentReceipt(
                success=False,
                amount_usdc=str(amount),
                from_address=from_address,
                to_address=self.address,
                job_id=job_id,
                error=str(e),
            )

    async def _execute_transfer_with_authorization(
        self,
        from_address: str,
        amount: int,
        job_id: str,
        payment_payload: Optional[PaymentPayload] = None,
    ) -> PaymentReceipt:
        """
        Execute real EIP-3009 transferWithAuthorization on-chain.
        
        This allows the seller to transfer USDC from buyer's wallet using
        the buyer's signed authorization, without the buyer paying gas.
        
        Args:
            from_address: Buyer's address
            amount: Amount in USDC smallest unit
            job_id: Job identifier
            payment_payload: Signed payment authorization from buyer
            
        Returns:
            PaymentReceipt with real transaction hash
        """
        if not payment_payload:
            return PaymentReceipt(
                success=False,
                amount_usdc=str(amount),
                from_address=from_address,
                to_address=self.address,
                job_id=job_id,
                error="Payment payload with signature required for production mode",
            )
        
        try:
            authorization = payment_payload.payload.get("authorization", {})
            signature = payment_payload.payload.get("signature", "")
            
            if not signature:
                return PaymentReceipt(
                    success=False,
                    amount_usdc=str(amount),
                    from_address=from_address,
                    to_address=self.address,
                    job_id=job_id,
                    error="Missing signature in payment payload",
                )
            
            # Parse signature into v, r, s components
            sig_bytes = bytes.fromhex(signature.replace("0x", ""))
            if len(sig_bytes) != 65:
                return PaymentReceipt(
                    success=False,
                    amount_usdc=str(amount),
                    from_address=from_address,
                    to_address=self.address,
                    job_id=job_id,
                    error=f"Invalid signature length: {len(sig_bytes)}",
                )
            
            r = sig_bytes[:32]
            s = sig_bytes[32:64]
            v = sig_bytes[64]
            
            # Adjust v if needed (some wallets return 0/1 instead of 27/28)
            if v < 27:
                v += 27
            
            # Get nonce as bytes32
            nonce = authorization.get("nonce", "")
            if isinstance(nonce, str):
                if nonce.startswith("0x"):
                    nonce_bytes = bytes.fromhex(nonce[2:])
                else:
                    nonce_bytes = bytes.fromhex(nonce)
            else:
                nonce_bytes = nonce
            
            # Ensure nonce is 32 bytes
            if len(nonce_bytes) < 32:
                nonce_bytes = nonce_bytes.rjust(32, b'\x00')
            
            # Check if this nonce has already been used
            nonce_used = self.usdc.functions.authorizationState(
                Web3.to_checksum_address(from_address),
                nonce_bytes
            ).call()
            
            if nonce_used:
                return PaymentReceipt(
                    success=False,
                    amount_usdc=str(amount),
                    from_address=from_address,
                    to_address=self.address,
                    job_id=job_id,
                    error="Payment authorization nonce already used",
                )
            
            # Check seller has enough ETH for gas
            seller_eth_balance = self.w3.eth.get_balance(self.address)
            gas_estimate = 100000  # Approximate gas for transferWithAuthorization
            gas_price = self.w3.eth.gas_price
            required_gas = gas_estimate * gas_price
            
            if seller_eth_balance < required_gas:
                return PaymentReceipt(
                    success=False,
                    amount_usdc=str(amount),
                    from_address=from_address,
                    to_address=self.address,
                    job_id=job_id,
                    error=f"Insufficient ETH for gas: {seller_eth_balance} < {required_gas}",
                )
            
            # Build the transaction
            tx = self.usdc.functions.transferWithAuthorization(
                Web3.to_checksum_address(from_address),  # from
                Web3.to_checksum_address(self.address),  # to
                int(authorization.get("value", amount)),  # value
                int(authorization.get("validAfter", 0)),  # validAfter
                int(authorization.get("validBefore", 0)),  # validBefore
                nonce_bytes,  # nonce
                v,  # v
                r,  # r
                s,  # s
            ).build_transaction({
                "from": self.address,
                "nonce": self.w3.eth.get_transaction_count(self.address),
                "gas": gas_estimate,
                "gasPrice": gas_price,
            })
            
            # Sign and send the transaction
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.account.key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            
            logger.info(
                "transfer_with_authorization_sent",
                tx_hash=tx_hash.hex(),
                from_address=from_address,
                to_address=self.address,
                amount=amount,
                job_id=job_id
            )
            
            # Wait for transaction receipt
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if receipt.status == 1:
                logger.info(
                    "transfer_with_authorization_confirmed",
                    tx_hash=tx_hash.hex(),
                    block_number=receipt.blockNumber,
                    gas_used=receipt.gasUsed,
                    job_id=job_id
                )
                
                return PaymentReceipt(
                    success=True,
                    tx_hash=tx_hash.hex(),
                    amount_usdc=str(amount),
                    from_address=from_address,
                    to_address=self.address,
                    job_id=job_id,
                )
            else:
                return PaymentReceipt(
                    success=False,
                    tx_hash=tx_hash.hex(),
                    amount_usdc=str(amount),
                    from_address=from_address,
                    to_address=self.address,
                    job_id=job_id,
                    error="Transaction reverted on-chain",
                )
                
        except Exception as e:
            logger.error(
                "transfer_with_authorization_failed",
                error=str(e),
                job_id=job_id,
                from_address=from_address
            )
            return PaymentReceipt(
                success=False,
                amount_usdc=str(amount),
                from_address=from_address,
                to_address=self.address,
                job_id=job_id,
                error=f"Transfer failed: {str(e)}",
            )

    # ===== BUYER METHODS =====

    def sign_payment(
        self,
        payment_required: PaymentRequired,
    ) -> PaymentPayload:
        """
        Sign a payment authorization in response to a 402 Payment Required.
        
        Args:
            payment_required: The payment requirement from the seller
            
        Returns:
            PaymentPayload ready to submit with the request
        """
        if not payment_required.accepts:
            raise ValueError("No payment options available")

        payment_option = payment_required.accepts[0]
        
        # Create authorization with 5 minute validity
        valid_before = int(time.time()) + 300
        nonce = Web3.keccak(text=f"{self.address}-{time.time()}").hex()

        typed_data = self._create_typed_data(
            from_address=self.address,
            to=payment_option.recipient,
            value=payment_option.amount,
            valid_after=0,
            valid_before=valid_before,
            nonce=nonce,
        )

        # Sign the typed data
        encoded = encode_typed_data(full_message=typed_data)
        signed = self.account.sign_message(encoded)

        return PaymentPayload(
            x402Version="1",
            scheme=payment_option.scheme,
            network=payment_option.network,
            payload={
                "signature": signed.signature.hex(),
                "authorization": {
                    "from": self.address,
                    "to": payment_option.recipient,
                    "value": payment_option.amount,
                    "validAfter": 0,
                    "validBefore": valid_before,
                    "nonce": nonce,
                },
            },
        )

    def encode_payment_payload(self, payment_payload: PaymentPayload) -> str:
        """Encode PaymentPayload as base64 for HTTP header"""
        return base64.b64encode(
            payment_payload.model_dump_json().encode()
        ).decode()

    @staticmethod
    def decode_payment_required(encoded: str) -> PaymentRequired:
        """Decode base64 PaymentRequired from HTTP header"""
        decoded = base64.b64decode(encoded).decode()
        return PaymentRequired.model_validate_json(decoded)

    @staticmethod
    def decode_payment_payload(encoded: str) -> PaymentPayload:
        """Decode base64 PaymentPayload from HTTP header"""
        decoded = base64.b64decode(encoded).decode()
        return PaymentPayload.model_validate_json(decoded)

    # ===== UTILITY METHODS =====

    def get_usdc_balance(self, address: Optional[str] = None) -> Decimal:
        """Get USDC balance for an address (defaults to own address)"""
        target = Web3.to_checksum_address(address or self.address)
        balance_wei = self.usdc.functions.balanceOf(target).call()
        return Decimal(balance_wei) / Decimal(10 ** USDC_DECIMALS)

    def _create_typed_data(
        self,
        from_address: str,
        to: str,
        value: str,
        valid_after: int,
        valid_before: int,
        nonce: str,
    ) -> dict:
        """Create EIP-712 typed data for payment authorization"""
        return {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                ],
                "TransferWithAuthorization": [
                    {"name": "from", "type": "address"},
                    {"name": "to", "type": "address"},
                    {"name": "value", "type": "uint256"},
                    {"name": "validAfter", "type": "uint256"},
                    {"name": "validBefore", "type": "uint256"},
                    {"name": "nonce", "type": "bytes32"},
                ],
            },
            "primaryType": "TransferWithAuthorization",
            "domain": {
                "name": "USD Coin",
                "version": "2",
                "chainId": self.chain_id,
                "verifyingContract": self.usdc_address,
            },
            "message": {
                "from": Web3.to_checksum_address(from_address),
                "to": Web3.to_checksum_address(to),
                "value": int(value),
                "validAfter": valid_after,
                "validBefore": valid_before,
                "nonce": nonce if nonce.startswith("0x") else f"0x{nonce}",
            },
        }


def calculate_job_cost(
    execution_time_seconds: Decimal,
    price_per_hour: Decimal,
) -> Tuple[Decimal, int]:
    """
    Calculate job cost based on actual execution time.
    
    Args:
        execution_time_seconds: Actual execution time in seconds
        price_per_hour: Price per hour in USD
        
    Returns:
        Tuple of (cost_usd, cost_usdc_wei)
    """
    price_per_second = price_per_hour / Decimal("3600")
    cost_usd = execution_time_seconds * price_per_second
    cost_usdc_wei = int(cost_usd * Decimal(10 ** USDC_DECIMALS))
    return cost_usd, cost_usdc_wei


def calculate_estimated_cost(
    timeout_seconds: int,
    price_per_hour: Decimal,
    buffer_percent: Decimal = Decimal("1.01"),
) -> Decimal:
    """
    Calculate estimated maximum cost for pre-authorization.
    Uses timeout as worst-case execution time with a buffer for rounding errors.
    
    Args:
        timeout_seconds: Maximum job duration in seconds
        price_per_hour: Price per hour in USD
        buffer_percent: Safety buffer (default 1% = 1.01)
        
    Returns:
        Estimated cost in USD with buffer
    """
    price_per_second = price_per_hour / Decimal("3600")
    max_cost = Decimal(timeout_seconds) * price_per_second
    return max_cost * buffer_percent

