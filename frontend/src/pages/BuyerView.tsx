import React, { useState } from 'react';
import { Plus, Trash2, Terminal, ChevronRight, ArrowRight, Cpu, Activity, Wallet } from 'lucide-react';
import { useWallet } from '../hooks/useWallet';
import { useBuyerJobs, useJobStatus } from '../hooks/useJobs';
import { useUSDCBalance } from '../hooks/useUSDCBalance';
import { apiClient } from '../services/api';
import { StatusBadge } from '../components/StatusBadge';
import { Label } from '../components/Label';
import { FlyingBee } from '../components/FlyingBee';

const TEMPLATES = [
  { id: 'pytorch', name: 'PyTorch Training', icon: <Cpu className="w-4 h-4" />, cost: 1.25 },
  { id: 'blender', name: 'Blender Render', icon: <Activity className="w-4 h-4" />, cost: 1.50 },
  { id: 'custom', name: 'Custom Script', icon: <Terminal className="w-4 h-4" />, cost: 0.95 },
];

export const BuyerView: React.FC = () => {
  const { address, isConnected } = useWallet();
  const { jobs, loading: jobsLoading, refresh } = useBuyerJobs(address, true);
  const { balance: usdcBalance, loading: balanceLoading } = useUSDCBalance();
  const [view, setView] = useState<'list' | 'create'>('list');
  const [selectedTemplate, setSelectedTemplate] = useState(TEMPLATES[0]);
  const [script, setScript] = useState('import torch\n\n# ComputeSwarm Script\ndef main():\n    print("Allocating GPU resources...")\n    device = "cuda" if torch.cuda.is_available() else "cpu"\n    print(f"Using device: {device}")\n\nif __name__ == "__main__":\n    main()');
  const [price, setPrice] = useState(1.20);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [timeoutSeconds, setTimeoutSeconds] = useState(3600);
  const [gpuType, setGpuType] = useState<string>('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isConnected || !address) return;

    setIsSubmitting(true);
    try {
      await apiClient.submitJob({
        buyer_address: address,
        script,
        max_price_per_hour: parseFloat(price.toString()),
        timeout_seconds: timeoutSeconds,
        required_gpu_type: gpuType || undefined,
      });
      setView('list');
      refresh();
    } catch (err: any) {
      console.error('Job submission failed:', err);
      alert(`Failed to submit job: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancel = async (jobId: string) => {
    if (!address) return;
    if (!confirm('Are you sure you want to cancel this job?')) return;

    try {
      await apiClient.cancelJob(jobId, address);
      refresh();
    } catch (err: any) {
      console.error('Failed to cancel job:', err);
      alert(`Failed to cancel job: ${err.message}`);
    }
  };

  if (view === 'create') {
    return (
      <div className="max-w-2xl mx-auto space-y-12 py-12 animate-in slide-in-from-bottom-4 duration-500">
        <header className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setView('list')}
              className="p-1 hover:bg-zinc-800 rounded text-zinc-500 transition-colors"
            >
              <ChevronRight className="w-5 h-5 rotate-180" />
            </button>
            <h2 className="text-xl font-semibold text-white">Create Deployment</h2>
          </div>
          <FlyingBee className="w-6 h-6" />
        </header>

        <form onSubmit={handleSubmit} className="space-y-10">
          <section className="space-y-4">
            <Label>1. Environment Template</Label>
            <div className="grid grid-cols-3 gap-3">
              {TEMPLATES.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => { setSelectedTemplate(t); setPrice(t.cost); }}
                  className={`p-4 rounded-lg border text-left transition-all flex flex-col items-center justify-center gap-2 group ${
                    selectedTemplate.id === t.id
                      ? 'border-amber-400 bg-amber-400/[0.03] text-amber-400 ring-1 ring-amber-400/20'
                      : 'border-zinc-800 bg-zinc-900/20 hover:border-zinc-700 text-zinc-500 hover:text-zinc-300'
                  }`}
                >
                  <div className="mb-1">{t.icon}</div>
                  <div className="text-[10px] font-bold uppercase tracking-widest">{t.name}</div>
                </button>
              ))}
            </div>
          </section>

          <section className="space-y-4">
            <div className="flex items-center justify-between">
              <Label>2. Initialization Script</Label>
              <span className="text-[10px] font-mono text-zinc-600">python-3.11</span>
            </div>
            <div className="bg-[#050505] border border-zinc-800 rounded-lg overflow-hidden group focus-within:border-amber-400/40 transition-colors shadow-inner">
              <div className="flex items-center gap-2 px-4 py-2 bg-zinc-900/40 border-b border-zinc-800">
                <div className="w-2 h-2 rounded-full bg-zinc-800" />
                <div className="w-2 h-2 rounded-full bg-zinc-800" />
                <span className="text-[10px] text-zinc-500 font-mono ml-2">swarm_init.py</span>
              </div>
              <textarea
                value={script}
                onChange={(e) => setScript(e.target.value)}
                spellCheck={false}
                className="w-full h-48 bg-transparent p-4 font-mono text-[13px] text-zinc-300 focus:outline-none resize-none leading-relaxed"
              />
            </div>
          </section>

          <section className="grid grid-cols-2 gap-8">
            <div className="space-y-4">
              <Label>3. Hourly Bid (USDC)</Label>
              <div className="flex items-center gap-4">
                <input
                  type="range"
                  min="0.5"
                  max="5.0"
                  step="0.1"
                  value={price}
                  onChange={(e) => setPrice(parseFloat(e.target.value))}
                  className="flex-1 accent-amber-400 h-1.5 bg-zinc-800 rounded-full appearance-none cursor-pointer"
                />
                <div className="font-mono text-sm text-amber-400 bg-amber-400/5 px-2 py-1 rounded border border-amber-400/10">
                  ${price.toFixed(2)}
                </div>
              </div>
            </div>
            <div className="space-y-4">
              <Label>4. Timeout (seconds)</Label>
              <input
                type="number"
                value={timeoutSeconds}
                onChange={(e) => setTimeoutSeconds(parseInt(e.target.value))}
                min={60}
                max={86400}
                className="w-full h-[42px] px-4 bg-zinc-900/40 border border-zinc-800 rounded-lg text-sm text-zinc-300 focus:outline-none focus:border-amber-400/40"
              />
            </div>
          </section>

          <section className="space-y-4">
            <Label>5. GPU Type (optional)</Label>
            <select
              value={gpuType}
              onChange={(e) => setGpuType(e.target.value)}
              className="w-full h-[42px] px-4 bg-zinc-900/40 border border-zinc-800 rounded-lg text-sm text-zinc-300 focus:outline-none focus:border-amber-400/40"
            >
              <option value="">Any</option>
              <option value="cuda">CUDA (NVIDIA)</option>
              <option value="mps">MPS (Apple Silicon)</option>
            </select>
          </section>

          <div className="pt-6 flex items-center gap-4">
            <button
              type="submit"
              disabled={isSubmitting || !isConnected}
              className="flex-1 bg-amber-400 hover:bg-amber-300 disabled:opacity-40 text-zinc-950 py-3 rounded-md font-bold text-sm transition-all flex items-center justify-center gap-2 shadow-[0_4px_20px_rgba(251,191,36,0.1)] active:scale-[0.98]"
            >
              {isSubmitting ? 'Dispatching...' : isConnected ? 'Deploy to Mesh' : 'Connect Wallet'}
              {!isSubmitting && <ArrowRight className="w-4 h-4" />}
            </button>
            <button
              type="button"
              onClick={() => setView('list')}
              className="px-6 py-3 rounded-md border border-zinc-800 hover:bg-zinc-900 text-zinc-400 text-sm font-medium transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    );
  }

  return (
    <div className="space-y-12 py-12 animate-in fade-in slide-in-from-top-2 duration-700">
      <header className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white flex items-center gap-3">
            My Deployments
          </h1>
          <p className="text-zinc-500 text-sm mt-1">Manage and monitor your active compute workloads.</p>
          {isConnected && (
            <div className="mt-2 flex items-center gap-2 text-xs text-zinc-400">
              <Wallet className="w-3 h-3" />
              <span>Balance: </span>
              {balanceLoading ? (
                <span className="text-zinc-500">Loading...</span>
              ) : (
                <span className="font-mono text-amber-400">
                  ${usdcBalance !== null ? usdcBalance.toFixed(4) : '0.0000'} USDC
                </span>
              )}
            </div>
          )}
        </div>
        <button
          onClick={() => setView('create')}
          className="flex items-center gap-2 bg-amber-400 hover:bg-amber-300 text-zinc-950 px-4 py-2 rounded-md text-sm font-semibold transition-all"
        >
          <Plus className="w-4 h-4" /> New Deployment
        </button>
      </header>

      <div className="border border-zinc-800 rounded-lg overflow-hidden bg-zinc-900/20 shadow-inner">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="bg-zinc-900/40 border-b border-zinc-800">
              <th className="px-6 py-3 font-medium text-zinc-500 text-xs uppercase tracking-wider">Environment</th>
              <th className="px-6 py-3 font-medium text-zinc-500 text-xs uppercase tracking-wider">Status</th>
              <th className="px-6 py-3 font-medium text-zinc-500 text-xs uppercase tracking-wider">Hourly Bid</th>
              <th className="px-6 py-3 font-medium text-zinc-500 text-xs uppercase tracking-wider">Cost</th>
              <th className="px-6 py-3 font-medium text-zinc-500 text-xs uppercase tracking-wider text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/40">
            {jobsLoading ? (
              <tr>
                <td colSpan={5} className="px-6 py-24 text-center text-zinc-500">
                  Loading jobs...
                </td>
              </tr>
            ) : jobs.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-24 text-center">
                  <div className="flex flex-col items-center gap-3 opacity-40">
                    <Terminal className="w-8 h-8 text-zinc-600" />
                    <p className="text-sm font-mono italic">The hive is empty. Create a deployment to begin.</p>
                  </div>
                </td>
              </tr>
            ) : (
              jobs.map((job) => (
                <tr key={job.job_id} className="hover:bg-amber-400/[0.02] transition-colors group">
                  <td className="px-6 py-5">
                    <div className="flex items-center gap-3">
                      <div className="text-zinc-500 group-hover:text-amber-400 transition-colors">
                        <Terminal className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="font-medium text-zinc-200">Custom Script</div>
                        <div className="text-[10px] font-mono text-zinc-600 uppercase tracking-widest">
                          {job.job_id.slice(0, 8)}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-5">
                    <StatusBadge status={job.status} />
                  </td>
                  <td className="px-6 py-5 font-mono text-zinc-400">
                    ${parseFloat(job.max_price_per_hour.toString()).toFixed(2)}
                  </td>
                  <td className="px-6 py-5 font-mono text-zinc-400">
                    {job.total_cost_usd ? `$${parseFloat(job.total_cost_usd.toString()).toFixed(4)}` : '-'}
                  </td>
                  <td className="px-6 py-5 text-right">
                    <button
                      onClick={() => handleCancel(job.job_id)}
                      disabled={!['PENDING', 'CLAIMED'].includes(job.status)}
                      className="p-2 hover:bg-zinc-800 rounded-md text-zinc-600 hover:text-rose-400 transition-all disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

