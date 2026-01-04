import React from 'react';
import { ArrowRight, Network, Zap, Cpu as GpuIcon } from 'lucide-react';
import { FlyingBee } from '../components/FlyingBee';
import { FeatureCard } from '../components/FeatureCard';

interface LandingPageProps {
  onGetStarted: () => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({ onGetStarted }) => {
  return (
    <div className="min-h-screen flex flex-col items-center animate-in fade-in duration-1000">
      {/* Hero Section */}
      <div className="max-w-3xl w-full pt-32 pb-24 text-center space-y-8">
        <div className="flex justify-center mb-6">
          <FlyingBee size={48} className="text-amber-400" />
        </div>
        <h1 className="text-5xl md:text-6xl font-semibold tracking-tight text-white leading-tight">
          The Distributed <span className="text-amber-400">GPU Mesh</span>
        </h1>
        <p className="text-zinc-400 text-lg md:text-xl max-w-xl mx-auto leading-relaxed">
          Access high-performance compute resources through a peer-to-peer swarm. Low latency, decentralized scaling, pay only for what you use.
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-6">
          <button
            onClick={onGetStarted}
            className="w-full sm:w-auto bg-amber-400 hover:bg-amber-300 text-zinc-950 px-8 py-3 rounded-md font-semibold text-base transition-all flex items-center justify-center gap-2 group shadow-[0_0_30px_rgba(251,191,36,0.1)]"
          >
            Launch Swarm <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
          </button>
          <a
            href="https://github.com/Archdiner/compute-swarm"
            target="_blank"
            rel="noopener noreferrer"
            className="w-full sm:w-auto px-8 py-3 rounded-md border border-zinc-800 text-zinc-400 hover:text-white hover:bg-zinc-900/50 transition-all text-sm font-medium"
          >
            Read Documentation
          </a>
        </div>
      </div>

      {/* Feature Grid */}
      <div className="max-w-5xl w-full grid grid-cols-1 md:grid-cols-3 gap-6 px-6 pb-32">
        <FeatureCard
          icon={<Network className="w-5 h-5 text-amber-400" />}
          title="Peer-to-Peer"
          description="A direct connection between GPU owners and users without middleman fees."
        />
        <FeatureCard
          icon={<Zap className="text-amber-400" />}
          title="Instant Allocation"
          description="Jobs are matched to nodes in seconds using our global dispatcher mesh."
        />
        <FeatureCard
          icon={<GpuIcon className="text-amber-400" />}
          title="Unified Scaling"
          description="Combine multiple nodes into a single virtual cluster for massive workloads."
        />
      </div>

      {/* Terminal Preview */}
      <div className="max-w-3xl w-full px-6 pb-40">
        <div className="bg-[#050505] border border-zinc-800 rounded-lg overflow-hidden shadow-2xl">
          <div className="flex items-center gap-2 px-4 py-2 bg-zinc-900/40 border-b border-zinc-800">
            <div className="flex gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-zinc-800" />
              <div className="w-2.5 h-2.5 rounded-full bg-zinc-800" />
            </div>
            <span className="text-[10px] text-zinc-500 font-mono ml-2 uppercase tracking-widest">
              swarm.sh — status
            </span>
          </div>
          <div className="p-6 font-mono text-sm leading-relaxed text-zinc-400">
            <div className="flex gap-3 mb-2">
              <span className="text-amber-500 font-bold">$</span>
              <span>computeswarm status --mesh</span>
            </div>
            <div className="text-zinc-500 mb-1">Checking network health...</div>
            <div className="text-emerald-400/80 mb-1">✓ Connection established with Hive-Core</div>
            <div className="text-emerald-400/80 mb-4">✓ 2,481 nodes available globally</div>
            <div className="grid grid-cols-2 gap-4 text-xs">
              <div className="bg-zinc-900/50 p-3 rounded border border-zinc-800">
                <div className="text-zinc-500 mb-1">ACTIVE LOAD</div>
                <div className="text-white text-lg">1.4 EH/s</div>
              </div>
              <div className="bg-zinc-900/50 p-3 rounded border border-zinc-800">
                <div className="text-zinc-500 mb-1">AVG LATENCY</div>
                <div className="text-white text-lg">42ms</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

