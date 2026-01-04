import { useEffect, useState } from 'react';
import { useWallet } from './useWallet';
import { getUSDCBalance } from '../services/usdc';

export function useUSDCBalance() {
  const { address, isConnected, getProvider } = useWallet();
  const [balance, setBalance] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchBalance = async () => {
      if (!address || !isConnected) {
        setBalance(null);
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const provider = await getProvider();
        const network = import.meta.env.VITE_NETWORK || 'base-sepolia';
        const usdcBalance = await getUSDCBalance(provider, address, network);
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
  }, [address, isConnected, getProvider]);

  return { balance, loading, error };
}
