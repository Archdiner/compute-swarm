import { useState, useEffect } from 'react';
import { LandingPage } from './pages/LandingPage';
import { FlyingBee } from './components/FlyingBee';
import { Wallet } from 'lucide-react';
import { useWallet } from './hooks/useWallet';
import { TerminalProvider, useTerminalContext } from './services/context';
import { ModeToggle } from './components/ModeToggle';
import { BuyerInterface } from './components/BuyerInterface';
import { SellerInterface } from './components/SellerInterface';

function AppContent() {
  const { address, isConnected, isLoading, error, connect, disconnect } = useWallet();
  const { mode, setMode } = useTerminalContext();
  const [view, setView] = useState<'landing' | 'terminal'>('landing');

  // Auto-switch to terminal view when wallet connects
  useEffect(() => {
    if (isConnected && address) {
      if (view === 'landing') {
        setView('terminal');
      }
    } else if (!isConnected && view !== 'landing') {
      // Stay in terminal view but show connect prompt
    }
  }, [isConnected, address, view]);

  const handleConnect = async () => {
    try {
      await connect();
    } catch (err: any) {
      console.error('Connection failed:', err);
    }
  };

  const handleDisconnect = () => {
    disconnect();
    setView('landing');
  };

  if (view === 'landing') {
    return (
      <div className="min-h-screen bg-[#121214] text-[#e1e1e3] font-sans selection:bg-amber-400/30 selection:text-amber-200">
        <nav className="border-b border-zinc-800/60 bg-[#121214]/80 backdrop-blur-md sticky top-0 z-50">
          <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 group cursor-pointer" onClick={() => setView('landing')}>
                <FlyingBee className="w-5 h-5" />
                <span className="text-sm font-medium tracking-tight text-zinc-100 group-hover:text-amber-400 transition-colors">
                  ComputeSwarm
                </span>
              </div>
            </div>
            {isConnected && address ? (
              <button
                onClick={handleDisconnect}
                className="flex items-center gap-2 px-3 py-1.5 rounded-md text-[11px] font-mono transition-all border border-zinc-800 hover:bg-zinc-900 text-zinc-400 hover:text-white"
              >
                Disconnect
              </button>
            ) : (
              <button
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  handleConnect();
                }}
                disabled={isLoading}
                className="flex items-center gap-2 px-3 py-1.5 rounded-md text-[11px] font-mono transition-all bg-zinc-100 text-zinc-950 border border-white hover:bg-zinc-200 disabled:opacity-50 cursor-pointer"
              >
                <Wallet className="w-3.5 h-3.5" />
                {isLoading ? 'Connecting...' : 'Connect Wallet'}
              </button>
            )}
          </div>
        </nav>
        <LandingPage onGetStarted={handleConnect} />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#121214] text-[#e1e1e3] font-sans selection:bg-amber-400/30 selection:text-amber-200">
      {/* Navigation */}
      <nav className="border-b border-zinc-800/60 bg-[#121214]/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 group cursor-pointer" onClick={() => setView('landing')}>
              <FlyingBee className="w-5 h-5" />
              <span className="text-sm font-medium tracking-tight text-zinc-100 group-hover:text-amber-400 transition-colors">
                ComputeSwarm
              </span>
            </div>
            <div className="h-4 w-[1px] bg-zinc-800 mx-2" />
            <ModeToggle mode={mode} onModeChange={setMode} />
          </div>

          <div className="flex items-center gap-3">
            {error && (
              <div className="text-xs text-rose-400 max-w-xs truncate" title={error}>
                {error}
              </div>
            )}
            {isConnected && address ? (
              <>
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-md text-[11px] font-mono transition-all border bg-amber-400/5 text-amber-400 border-amber-400/20">
                  <Wallet className="w-3.5 h-3.5" />
                  {address.slice(0, 6)}...{address.slice(-4)}
                </div>
                <button
                  onClick={handleDisconnect}
                  className="px-3 py-1.5 rounded-md text-[11px] font-mono transition-all border border-zinc-800 hover:bg-zinc-900 text-zinc-400 hover:text-white"
                >
                  Disconnect
                </button>
              </>
            ) : (
              <button
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  handleConnect();
                }}
                disabled={isLoading}
                className="px-3 py-1.5 rounded-md text-[11px] font-mono transition-all bg-zinc-100 text-zinc-950 border border-white hover:bg-zinc-200 disabled:opacity-50 cursor-pointer"
              >
                {isLoading ? 'Connecting...' : 'Connect'}
              </button>
            )}
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-6 py-6 h-[calc(100vh-3.5rem)]">
        {error && !isConnected && (
          <div className="mb-4 p-4 bg-rose-400/10 border border-rose-400/20 rounded-lg text-sm text-rose-400">
            {error.includes('not installed') ? (
              <div>
                <p className="font-semibold mb-2">MetaMask is required</p>
                <p className="text-rose-300 mb-3">
                  Please install MetaMask browser extension to connect your wallet.
                </p>
                <a
                  href="https://metamask.io/download/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-amber-400 hover:underline font-medium"
                >
                  Install MetaMask →
                </a>
              </div>
            ) : (
              error
            )}
          </div>
        )}
        {!isConnected ? (
          <div className="space-y-12 py-12 text-center">
            <p className="text-zinc-500">Please connect your wallet to continue.</p>
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                handleConnect();
              }}
              disabled={isLoading}
              className="bg-amber-400 hover:bg-amber-300 disabled:opacity-50 text-zinc-950 px-6 py-3 rounded-md font-semibold transition-all cursor-pointer"
            >
              {isLoading ? 'Connecting...' : 'Connect Wallet'}
            </button>
          </div>
        ) : mode === 'buyer' ? (
          <BuyerInterface
            onWalletConnect={handleConnect}
            onWalletDisconnect={handleDisconnect}
          />
        ) : (
          <SellerInterface
            onWalletConnect={handleConnect}
            onWalletDisconnect={handleDisconnect}
          />
        )}
      </main>
    </div>
  );
}

function App() {
  const { address } = useWallet();
  
  return (
    <TerminalProvider walletAddress={address}>
      <AppContent />
    </TerminalProvider>
  );
}

export default App;
