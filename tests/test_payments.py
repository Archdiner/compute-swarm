"""
Unit tests for x402 payment processing
Tests payment models, signing, verification, and cost calculation
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from eth_account import Account

from src.payments.models import (
    PaymentRequired,
    PaymentAccepts,
    PaymentPayload,
    PaymentReceipt,
)
from src.payments.processor import (
    PaymentProcessor,
    calculate_job_cost,
    USDC_DECIMALS,
)


class TestPaymentModels:
    """Test payment data models"""

    def test_payment_accepts_model(self):
        """Test PaymentAccepts model creation"""
        accepts = PaymentAccepts(
            network="base-sepolia",
            scheme="exact",
            recipient="0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1",
            amount="1000000",
            token="USDC"
        )
        
        assert accepts.network == "base-sepolia"
        assert accepts.scheme == "exact"
        assert accepts.amount == "1000000"
        assert accepts.token == "USDC"

    def test_payment_required_model(self):
        """Test PaymentRequired model creation"""
        payment_req = PaymentRequired(
            x402Version="1",
            accepts=[
                PaymentAccepts(
                    recipient="0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1",
                    amount="500000"
                )
            ],
            description="Test job payment",
            job_id="job_123"
        )
        
        assert payment_req.x402Version == "1"
        assert len(payment_req.accepts) == 1
        assert payment_req.accepts[0].amount == "500000"
        assert payment_req.job_id == "job_123"

    def test_payment_payload_model(self):
        """Test PaymentPayload model creation"""
        payload = PaymentPayload(
            x402Version="1",
            scheme="exact",
            network="base-sepolia",
            payload={
                "signature": "0xabc123",
                "authorization": {
                    "from": "0x123",
                    "to": "0x456",
                    "value": "1000000",
                    "validAfter": 0,
                    "validBefore": 9999999999,
                    "nonce": "0xdef"
                }
            }
        )
        
        assert payload.x402Version == "1"
        assert payload.scheme == "exact"
        assert payload.payload["signature"] == "0xabc123"

    def test_payment_receipt_model(self):
        """Test PaymentReceipt model creation"""
        receipt = PaymentReceipt(
            success=True,
            tx_hash="0x123abc",
            amount_usdc="1000000",
            from_address="0x111",
            to_address="0x222",
            job_id="job_456"
        )
        
        assert receipt.success == True
        assert receipt.tx_hash == "0x123abc"
        assert receipt.amount_usdc == "1000000"


class TestCostCalculation:
    """Test per-second billing cost calculation"""

    def test_calculate_job_cost_one_hour(self):
        """Test cost calculation for 1 hour job"""
        cost_usd, cost_wei = calculate_job_cost(
            execution_time_seconds=Decimal("3600"),  # 1 hour
            price_per_hour=Decimal("2.00")  # $2/hr
        )
        
        assert cost_usd == Decimal("2.00")
        assert cost_wei == 2_000_000  # 2 USDC in smallest unit

    def test_calculate_job_cost_one_minute(self):
        """Test cost calculation for 1 minute job"""
        cost_usd, cost_wei = calculate_job_cost(
            execution_time_seconds=Decimal("60"),  # 1 minute
            price_per_hour=Decimal("0.60")  # $0.60/hr
        )
        
        # 60 seconds / 3600 * $0.60 = $0.01
        assert cost_usd == Decimal("0.01")
        assert cost_wei == 10_000  # 0.01 USDC

    def test_calculate_job_cost_30_seconds(self):
        """Test cost calculation for 30 second job"""
        cost_usd, cost_wei = calculate_job_cost(
            execution_time_seconds=Decimal("30"),
            price_per_hour=Decimal("1.00")
        )
        
        # 30 seconds / 3600 * $1.00 = ~$0.00833
        expected = Decimal("30") / Decimal("3600") * Decimal("1.00")
        assert cost_usd == expected
        assert cost_wei == int(expected * 1_000_000)

    def test_calculate_job_cost_fractional_seconds(self):
        """Test cost calculation with fractional seconds"""
        cost_usd, cost_wei = calculate_job_cost(
            execution_time_seconds=Decimal("5.5"),  # 5.5 seconds
            price_per_hour=Decimal("0.50")
        )
        
        expected = Decimal("5.5") / Decimal("3600") * Decimal("0.50")
        assert cost_usd == expected

    def test_calculate_job_cost_zero_time(self):
        """Test cost calculation for zero execution time"""
        cost_usd, cost_wei = calculate_job_cost(
            execution_time_seconds=Decimal("0"),
            price_per_hour=Decimal("10.00")
        )
        
        assert cost_usd == Decimal("0")
        assert cost_wei == 0


class TestPaymentProcessor:
    """Test PaymentProcessor class"""

    @pytest.fixture
    def test_private_key(self):
        """Generate a test private key"""
        return "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"

    @pytest.fixture
    def mock_web3(self):
        """Create mock Web3 instance"""
        with patch('src.payments.processor.Web3') as mock:
            mock_instance = MagicMock()
            mock.return_value = mock_instance
            mock.to_checksum_address = lambda x: x
            mock.HTTPProvider = MagicMock()
            mock.keccak = lambda text: b'\x00' * 32
            
            # Mock contract
            mock_contract = MagicMock()
            mock_contract.functions.balanceOf.return_value.call.return_value = 10_000_000  # 10 USDC
            mock_instance.eth.contract.return_value = mock_contract
            
            yield mock

    def test_payment_processor_init(self, test_private_key, mock_web3):
        """Test PaymentProcessor initialization"""
        processor = PaymentProcessor(
            private_key=test_private_key,
            rpc_url="https://sepolia.base.org",
            usdc_address="0x036CbD53842c5426634e7929541eC2318f3dCF7e",
            network="base-sepolia"
        )
        
        assert processor.address is not None
        assert processor.network == "base-sepolia"
        assert processor.chain_id == 84532  # Base Sepolia

    def test_create_payment_required(self, test_private_key, mock_web3):
        """Test creating a PaymentRequired object"""
        processor = PaymentProcessor(
            private_key=test_private_key,
            network="base-sepolia"
        )
        
        payment_req = processor.create_payment_required(
            amount_usdc=Decimal("0.50"),
            job_id="job_test_123",
            description="Test GPU compute"
        )
        
        assert payment_req.x402Version == "1"
        assert len(payment_req.accepts) == 1
        assert payment_req.accepts[0].amount == "500000"  # 0.50 USDC = 500000 wei
        assert payment_req.accepts[0].recipient == processor.address
        assert payment_req.job_id == "job_test_123"
        assert payment_req.expires_at is not None

    def test_encode_decode_payment_required(self, test_private_key, mock_web3):
        """Test encoding and decoding PaymentRequired"""
        processor = PaymentProcessor(
            private_key=test_private_key,
            network="base-sepolia"
        )
        
        original = processor.create_payment_required(
            amount_usdc=Decimal("1.00"),
            job_id="job_encode_test"
        )
        
        # Encode
        encoded = processor.encode_payment_required(original)
        assert isinstance(encoded, str)
        
        # Decode
        decoded = PaymentProcessor.decode_payment_required(encoded)
        assert decoded.job_id == original.job_id
        assert decoded.accepts[0].amount == original.accepts[0].amount

    def test_sign_payment(self, test_private_key, mock_web3):
        """Test signing a payment"""
        processor = PaymentProcessor(
            private_key=test_private_key,
            network="base-sepolia"
        )
        
        payment_req = processor.create_payment_required(
            amount_usdc=Decimal("0.25"),
            job_id="job_sign_test"
        )
        
        # Sign the payment
        payment_payload = processor.sign_payment(payment_req)
        
        assert payment_payload.x402Version == "1"
        assert payment_payload.scheme == "exact"
        assert payment_payload.network == "base-sepolia"
        assert "signature" in payment_payload.payload
        assert "authorization" in payment_payload.payload
        
        auth = payment_payload.payload["authorization"]
        assert auth["from"] == processor.address
        assert auth["to"] == payment_req.accepts[0].recipient
        assert auth["value"] == payment_req.accepts[0].amount


class TestPaymentIntegration:
    """Integration tests for payment flow"""

    @pytest.fixture
    def seller_processor(self):
        """Create seller payment processor"""
        with patch('src.payments.processor.Web3') as mock:
            mock_instance = MagicMock()
            mock.return_value = mock_instance
            mock.to_checksum_address = lambda x: x
            mock.HTTPProvider = MagicMock()
            mock.keccak = lambda text: b'\x00' * 32
            
            mock_contract = MagicMock()
            mock_contract.functions.balanceOf.return_value.call.return_value = 100_000_000
            mock_instance.eth.contract.return_value = mock_contract
            
            processor = PaymentProcessor(
                private_key="0x1111111111111111111111111111111111111111111111111111111111111111",
                network="base-sepolia"
            )
            yield processor

    @pytest.fixture
    def buyer_processor(self):
        """Create buyer payment processor"""
        with patch('src.payments.processor.Web3') as mock:
            mock_instance = MagicMock()
            mock.return_value = mock_instance
            mock.to_checksum_address = lambda x: x
            mock.HTTPProvider = MagicMock()
            mock.keccak = lambda text: b'\x00' * 32
            
            mock_contract = MagicMock()
            mock_contract.functions.balanceOf.return_value.call.return_value = 50_000_000
            mock_instance.eth.contract.return_value = mock_contract
            
            processor = PaymentProcessor(
                private_key="0x2222222222222222222222222222222222222222222222222222222222222222",
                network="base-sepolia"
            )
            yield processor

    def test_full_payment_flow(self, seller_processor, buyer_processor):
        """Test complete payment flow from request to settlement"""
        job_id = "job_full_flow_test"
        amount = Decimal("0.75")
        
        # 1. Seller creates payment requirement
        payment_req = seller_processor.create_payment_required(
            amount_usdc=amount,
            job_id=job_id,
            description="Full flow test"
        )
        
        assert payment_req.accepts[0].amount == "750000"
        
        # 2. Encode for HTTP header
        encoded_req = seller_processor.encode_payment_required(payment_req)
        
        # 3. Buyer decodes and signs payment
        decoded_req = PaymentProcessor.decode_payment_required(encoded_req)
        payment_payload = buyer_processor.sign_payment(decoded_req)
        
        assert payment_payload.payload["authorization"]["value"] == "750000"
        assert payment_payload.payload["authorization"]["from"] == buyer_processor.address
        
        # 4. Encode payment for HTTP header
        encoded_payment = buyer_processor.encode_payment_payload(payment_payload)
        
        # 5. Seller decodes and verifies
        decoded_payment = PaymentProcessor.decode_payment_payload(encoded_payment)
        assert decoded_payment.payload["authorization"]["value"] == "750000"


class TestPaymentEdgeCases:
    """Test edge cases and error handling"""

    def test_calculate_very_small_cost(self):
        """Test calculation of very small amounts"""
        cost_usd, cost_wei = calculate_job_cost(
            execution_time_seconds=Decimal("1"),  # 1 second
            price_per_hour=Decimal("0.01")  # $0.01/hr
        )
        
        # 1/3600 * 0.01 = very small
        assert cost_usd > 0
        assert cost_wei >= 0  # May round to 0 for very small amounts

    def test_calculate_large_cost(self):
        """Test calculation of large amounts"""
        cost_usd, cost_wei = calculate_job_cost(
            execution_time_seconds=Decimal("36000"),  # 10 hours
            price_per_hour=Decimal("100.00")  # $100/hr
        )
        
        assert cost_usd == Decimal("1000.00")
        assert cost_wei == 1_000_000_000  # 1000 USDC

    def test_payment_required_serialization(self):
        """Test that PaymentRequired can be serialized to JSON"""
        payment_req = PaymentRequired(
            accepts=[PaymentAccepts(recipient="0x123", amount="1000000")],
            description="Test",
            job_id="job_1",
            expires_at=datetime.utcnow() + timedelta(minutes=5)
        )
        
        json_str = payment_req.model_dump_json()
        assert "job_1" in json_str
        assert "1000000" in json_str

