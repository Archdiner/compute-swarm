import { useEffect, useState } from 'react';
import { usePrivyWallet } from './useWallet';
import { getUSDCBalance } from '../services/usdc';
import { ethers } from 'ethers';

export function useUSDCBalance() {
  const { wallet, address, isConnected } = usePrivyWallet();
  const [balance, setBalance] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchBalance = async () => {
      if (!wallet || !address || !isConnected) {
        setBalance(null);
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const provider = await wallet.getEthereumProvider();
        const ethersProvider = new ethers.BrowserProvider(provider);
        
        const network = import.meta.env.VITE_NETWORK || 'base-sepolia';
        const usdcBalance = await getUSDCBalance(ethersProvider, address, network);
        setBalance(usdcBalance);
      } catch (err: any) {
        setError(err.message || 'Failed to fetch balance');
        console.error('Error fetching USDC balance:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchBalance();
    
    // Refresh balance every 30 seconds
    const interval = setInterval(fetchBalance, 30000);
    return () => clearInterval(interval);
  }, [wallet, address, isConnected]);

  return { balance, loading, error };
}

