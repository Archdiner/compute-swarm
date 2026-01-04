import { PrivyProviderConfig, PrivyProvider } from '@privy-io/react-auth';

export const privyConfig: PrivyProviderConfig = {
  appearance: {
    theme: 'dark',
    accentColor: '#FBBF24', // amber-400
    logo: undefined,
  },
  embeddedWallets: {
    createOnLogin: 'users-without-wallets',
    requireUserPasswordOnCreate: false,
    noPromptOnSignature: false,
  },
  loginMethods: ['email', 'google', 'twitter', 'discord'],
  defaultChain: import.meta.env.VITE_NETWORK === 'base-mainnet' 
    ? {
        id: 8453,
        name: 'Base',
        network: 'base',
        nativeCurrency: { name: 'Ether', symbol: 'ETH', decimals: 18 },
        rpcUrls: {
          default: { http: ['https://mainnet.base.org'] },
          public: { http: ['https://mainnet.base.org'] },
        },
        blockExplorers: {
          default: { name: 'BaseScan', url: 'https://basescan.org' },
        },
      }
    : {
        id: 84532,
        name: 'Base Sepolia',
        network: 'base-sepolia',
        nativeCurrency: { name: 'Ether', symbol: 'ETH', decimals: 18 },
        rpcUrls: {
          default: { http: ['https://sepolia.base.org'] },
          public: { http: ['https://sepolia.base.org'] },
        },
        blockExplorers: {
          default: { name: 'BaseScan Sepolia', url: 'https://sepolia.basescan.org' },
        },
      },
  supportedChains: import.meta.env.VITE_NETWORK === 'base-mainnet'
    ? [
        {
          id: 8453,
          name: 'Base',
          network: 'base',
          nativeCurrency: { name: 'Ether', symbol: 'ETH', decimals: 18 },
          rpcUrls: {
            default: { http: ['https://mainnet.base.org'] },
            public: { http: ['https://mainnet.base.org'] },
          },
          blockExplorers: {
            default: { name: 'BaseScan', url: 'https://basescan.org' },
          },
        },
      ]
    : [
        {
          id: 84532,
          name: 'Base Sepolia',
          network: 'base-sepolia',
          nativeCurrency: { name: 'Ether', symbol: 'ETH', decimals: 18 },
          rpcUrls: {
            default: { http: ['https://sepolia.base.org'] },
            public: { http: ['https://sepolia.base.org'] },
          },
          blockExplorers: {
            default: { name: 'BaseScan Sepolia', url: 'https://sepolia.basescan.org' },
          },
        },
      ],
};

export const PRIVY_APP_ID = import.meta.env.VITE_PRIVY_APP_ID || '';

