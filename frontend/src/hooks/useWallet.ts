import { useState, useEffect, useCallback } from 'react';
import { ethers } from 'ethers';

interface WalletState {
  address: string | null;
  isConnected: boolean;
  isLoading: boolean;
  error: string | null;
}

// Base network configuration
const BASE_SEPOLIA_CHAIN_ID = '0x14a34'; // 84532 in hex
const BASE_MAINNET_CHAIN_ID = '0x2105'; // 8453 in hex

const getNetworkConfig = () => {
  const network = import.meta.env.VITE_NETWORK || 'base-sepolia';
  const isMainnet = network === 'base-mainnet';
  
  return {
    chainId: isMainnet ? BASE_MAINNET_CHAIN_ID : BASE_SEPOLIA_CHAIN_ID,
    chainName: isMainnet ? 'Base' : 'Base Sepolia',
    nativeCurrency: { name: 'Ether', symbol: 'ETH', decimals: 18 },
    rpcUrls: [isMainnet ? 'https://mainnet.base.org' : 'https://sepolia.base.org'],
    blockExplorerUrls: [isMainnet ? 'https://basescan.org' : 'https://sepolia.basescan.org'],
  };
};

export function useWallet() {
  const [state, setState] = useState<WalletState>({
    address: null,
    isConnected: false,
    isLoading: true,
    error: null,
  });

  const checkConnection = useCallback(async () => {
    if (typeof window.ethereum === 'undefined') {
      setState({
        address: null,
        isConnected: false,
        isLoading: false,
        error: 'MetaMask is not installed',
      });
      return;
    }

    try {
      const provider = new ethers.BrowserProvider(window.ethereum);
      const accounts = await provider.listAccounts();
      
      if (accounts.length > 0) {
        const signer = await provider.getSigner();
        const address = await signer.getAddress();
        
        setState({
          address,
          isConnected: true,
          isLoading: false,
          error: null,
        });
      } else {
        setState({
          address: null,
          isConnected: false,
          isLoading: false,
          error: null,
        });
      }
    } catch (error: any) {
      setState({
        address: null,
        isConnected: false,
        isLoading: false,
        error: error.message || 'Failed to check wallet connection',
      });
    }
  }, []);

  useEffect(() => {
    checkConnection();

    // Listen for account changes
    if (window.ethereum) {
      const handleAccountsChanged = (accounts: string[]) => {
        if (accounts.length > 0) {
          setState(prev => ({ ...prev, address: accounts[0], isConnected: true, error: null }));
        } else {
          setState(prev => ({ ...prev, address: null, isConnected: false }));
        }
      };

      const handleChainChanged = () => {
        // Reload page when chain changes
        window.location.reload();
      };

      window.ethereum.on('accountsChanged', handleAccountsChanged);
      window.ethereum.on('chainChanged', handleChainChanged);

      return () => {
        if (window.ethereum) {
          window.ethereum.removeListener('accountsChanged', handleAccountsChanged);
          window.ethereum.removeListener('chainChanged', handleChainChanged);
        }
      };
    }
  }, [checkConnection]);

  const connect = useCallback(async () => {
    if (typeof window.ethereum === 'undefined') {
      setState(prev => ({ 
        ...prev, 
        error: 'MetaMask is not installed. Please install MetaMask to continue.',
        isLoading: false 
      }));
      return;
    }

    try {
      setState(prev => ({ ...prev, isLoading: true, error: null }));

      const provider = new ethers.BrowserProvider(window.ethereum);
      
      // Request account access - this opens MetaMask popup
      const accounts = await window.ethereum.request({
        method: 'eth_requestAccounts',
      });

      if (!accounts || accounts.length === 0) {
        throw new Error('No accounts found. Please unlock MetaMask.');
      }

      const address = accounts[0];
      
      // Check if we need to switch networks
      const network = await provider.getNetwork();
      const targetChainId = BigInt(parseInt(getNetworkConfig().chainId, 16));
      
      if (network.chainId !== targetChainId) {
        try {
          await window.ethereum.request({
            method: 'wallet_switchEthereumChain',
            params: [{ chainId: getNetworkConfig().chainId }],
          });
        } catch (switchError: any) {
          // If the chain doesn't exist, add it
          if (switchError.code === 4902) {
            const networkConfig = getNetworkConfig();
            await window.ethereum.request({
              method: 'wallet_addEthereumChain',
              params: [{
                chainId: networkConfig.chainId,
                chainName: networkConfig.chainName,
                nativeCurrency: networkConfig.nativeCurrency,
                rpcUrls: networkConfig.rpcUrls,
                blockExplorerUrls: networkConfig.blockExplorerUrls,
              }],
            });
          } else {
            // User rejected or other error
            throw switchError;
          }
        }
      }

      // Verify connection by getting signer address
      const signer = await provider.getSigner();
      const verifiedAddress = await signer.getAddress();
      
      if (!verifiedAddress || verifiedAddress.toLowerCase() !== address.toLowerCase()) {
        throw new Error('Address verification failed');
      }

      // Update state with connected address
      console.log('Wallet connected:', verifiedAddress);
      setState({
        address: verifiedAddress,
        isConnected: true,
        isLoading: false,
        error: null,
      });
    } catch (error: any) {
      console.error('Wallet connection error:', error);
      const errorMessage = error.code === 4001 
        ? 'Connection rejected. Please approve the connection request in MetaMask.'
        : error.code === -32002
        ? 'Connection request already pending. Please check MetaMask.'
        : error.message || 'Failed to connect wallet';
      
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: errorMessage,
      }));
      // Re-throw to let caller know it failed
      throw error;
    }
  }, []);

  const disconnect = useCallback(() => {
    setState({
      address: null,
      isConnected: false,
      isLoading: false,
      error: null,
    });
  }, []);

  const getSigner = useCallback(async () => {
    if (!state.isConnected || !window.ethereum) {
      throw new Error('Wallet not connected');
    }
    const provider = new ethers.BrowserProvider(window.ethereum);
    return provider.getSigner();
  }, [state.isConnected]);

  const getProvider = useCallback(async () => {
    if (!window.ethereum) {
      throw new Error('MetaMask is not installed');
    }
    return new ethers.BrowserProvider(window.ethereum);
  }, []);

  return {
    address: state.address,
    isConnected: state.isConnected,
    isLoading: state.isLoading,
    error: state.error,
    connect,
    disconnect,
    getSigner,
    getProvider,
  };
}

// Extend Window interface for TypeScript
declare global {
  interface Window {
    ethereum?: any;
  }
}
