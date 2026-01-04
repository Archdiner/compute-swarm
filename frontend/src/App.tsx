import React, { useState } from 'react';
import { PrivyProvider, usePrivy } from '@privy-io/react-auth';
import { PRIVY_APP_ID, privyConfig } from './services/privy';
import { LandingPage } from './pages/LandingPage';
import { BuyerView } from './pages/BuyerView';
import { SellerView } from './pages/SellerView';
import { FlyingBee } from './components/FlyingBee';
import { Wallet, Globe } from 'lucide-react';

function AppContent() {
  const { ready, authenticated, login, logout, user } = usePrivy();
  const [view, setView] = useState<'landing' | 'buyer' | 'seller'>('landing');

  const handleLogin = async () => {
    await login();
    setView('buyer');
  };

  const handleLogout = async () => {
    await logout();
    setView('landing');
  };

  if (!ready) {
    return (
      <div className="min-h-screen bg-[#121214] flex items-center justify-center">
        <div className="text-zinc-400">Loading...</div>
      </div>
    );
  }

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
            {authenticated ? (
              <button
                onClick={handleLogout}
                className="flex items-center gap-2 px-3 py-1.5 rounded-md text-[11px] font-mono transition-all border border-zinc-800 hover:bg-zinc-900 text-zinc-400 hover:text-white"
              >
                Logout
              </button>
            ) : (
              <button
                onClick={handleLogin}
                className="flex items-center gap-2 px-3 py-1.5 rounded-md text-[11px] font-mono transition-all bg-zinc-100 text-zinc-950 border border-white hover:bg-zinc-200"
              >
                <Wallet className="w-3.5 h-3.5" />
                Connect
              </button>
            )}
          </div>
        </nav>
        <LandingPage onGetStarted={handleLogin} />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#121214] text-[#e1e1e3] font-sans selection:bg-amber-400/30 selection:text-amber-200">
      {/* Navigation */}
      <nav className="border-b border-zinc-800/60 bg-[#121214]/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 group cursor-pointer" onClick={() => setView('landing')}>
              <FlyingBee className="w-5 h-5" />
              <span className="text-sm font-medium tracking-tight text-zinc-100 group-hover:text-amber-400 transition-colors">
                ComputeSwarm
              </span>
            </div>
            <div className="h-4 w-[1px] bg-zinc-800 mx-2" />
            <button
              onClick={() => setView('buyer')}
              className={`text-xs font-medium transition-colors ${
                view === 'buyer' ? 'text-amber-400' : 'text-zinc-500 hover:text-zinc-300'
              }`}
            >
              Buy Compute
            </button>
            <button
              onClick={() => setView('seller')}
              className={`text-xs font-medium transition-colors ${
                view === 'seller' ? 'text-amber-400' : 'text-zinc-500 hover:text-zinc-300'
              }`}
            >
              Sell Compute
            </button>
          </div>

          <div className="flex items-center gap-3">
            {authenticated && user?.wallet?.address && (
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-md text-[11px] font-mono transition-all border bg-amber-400/5 text-amber-400 border-amber-400/20">
                <Wallet className="w-3.5 h-3.5" />
                {user.wallet.address.slice(0, 6)}...{user.wallet.address.slice(-4)}
              </div>
            )}
            <button
              onClick={handleLogout}
              className="px-3 py-1.5 rounded-md text-[11px] font-mono transition-all border border-zinc-800 hover:bg-zinc-900 text-zinc-400 hover:text-white"
            >
              Logout
            </button>
          </div>
        </div>
      </nav>

      <main className="max-w-5xl mx-auto px-6">
        {!authenticated ? (
          <div className="space-y-12 py-12 text-center">
            <p className="text-zinc-500">Please connect your wallet to continue.</p>
            <button
              onClick={handleLogin}
              className="bg-amber-400 hover:bg-amber-300 text-zinc-950 px-6 py-3 rounded-md font-semibold transition-all"
            >
              Connect Wallet
            </button>
          </div>
        ) : view === 'buyer' ? (
          <BuyerView />
        ) : (
          <SellerView />
        )}
      </main>

      <footer className="pt-8 pb-8 border-t border-zinc-800/40 flex justify-between items-center text-[10px] text-zinc-600 font-mono uppercase tracking-[0.2em] max-w-5xl mx-auto px-6">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> API: Online
          </span>
          <span className="flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> Mesh: Connected
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Globe className="w-3 h-3" />
          Global Deployment Mesh v1.0.4
        </div>
      </footer>
    </div>
  );
}

function App() {
  if (!PRIVY_APP_ID) {
    return (
      <div className="min-h-screen bg-[#121214] flex items-center justify-center">
        <div className="text-center text-zinc-400 max-w-md mx-auto p-6">
          <h1 className="text-xl font-semibold text-white mb-4">Configuration Required</h1>
          <p className="mb-4">
            Please set VITE_PRIVY_APP_ID in your .env.local file. Get your Privy App ID from{' '}
            <a
              href="https://privy.io"
              target="_blank"
              rel="noopener noreferrer"
              className="text-amber-400 hover:underline"
            >
              privy.io
            </a>
          </p>
          <p className="text-sm text-zinc-500">
            Copy .env.local.example to .env.local and add your Privy App ID.
          </p>
        </div>
      </div>
    );
  }

  return (
    <PrivyProvider appId={PRIVY_APP_ID} config={privyConfig}>
      <AppContent />
    </PrivyProvider>
  );
}

export default App;

