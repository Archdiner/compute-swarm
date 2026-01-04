import { useWallets, useWallet } from '@privy-io/react-auth';
import { ethers } from 'ethers';
import { useMemo } from 'react';

export function usePrivyWallet() {
  const { wallets } = useWallets();
  const wallet = useWallet();

  const embeddedWallet = useMemo(() => {
    return wallets.find(w => w.walletClientType === 'privy');
  }, [wallets]);

  const getSigner = async () => {
    if (!embeddedWallet) {
      throw new Error('No embedded wallet found');
    }
    
    // Privy provides a provider we can use
    const provider = await embeddedWallet.getEthereumProvider();
    return new ethers.BrowserProvider(provider).getSigner();
  };

  const getAddress = () => {
    return embeddedWallet?.address || null;
  };

  const isConnected = !!embeddedWallet && wallet.authenticated;

  return {
    wallet: embeddedWallet,
    address: getAddress(),
    isConnected,
    getSigner,
    authenticated: wallet.authenticated,
  };
}

