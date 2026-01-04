import { ethers } from 'ethers';

// USDC contract ABI (minimal - just balanceOf)
const USDC_ABI = [
  {
    constant: true,
    inputs: [{ name: '_owner', type: 'address' }],
    name: 'balanceOf',
    outputs: [{ name: 'balance', type: 'uint256' }],
    type: 'function',
  },
] as const;

// USDC contract addresses
const USDC_CONTRACTS: Record<string, string> = {
  'base-sepolia': '0x036CbD53842c5426634e7929541eC2318f3dCF7e',
  'base-mainnet': '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
};

// USDC has 6 decimals
const USDC_DECIMALS = 6;

export async function getUSDCBalance(
  provider: ethers.Provider,
  address: string,
  network: string = 'base-sepolia'
): Promise<number> {
  try {
    const usdcAddress = USDC_CONTRACTS[network];
    if (!usdcAddress) {
      throw new Error(`USDC contract not configured for network: ${network}`);
    }

    const contract = new ethers.Contract(usdcAddress, USDC_ABI, provider);
    const balance = await contract.balanceOf(address);
    
    // Convert from wei (6 decimals for USDC) to human-readable
    return parseFloat(ethers.formatUnits(balance, USDC_DECIMALS));
  } catch (error) {
    console.error('Error fetching USDC balance:', error);
    throw error;
  }
}

export function formatUSDC(amount: number): string {
  return `$${amount.toFixed(6)} USDC`;
}

