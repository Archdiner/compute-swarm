import React, { useState, useEffect } from 'react';
import { useWallet } from '../hooks/useWallet';
import { useSellerJobs } from '../hooks/useJobs';
import { apiClient } from '../services/api';
import { StatusBadge } from '../components/StatusBadge';
import { Terminal, Cpu, TrendingUp, Clock, DollarSign } from 'lucide-react';

export const SellerView: React.FC = () => {
  const { address, isConnected } = useWallet();
  const { jobs, loading: jobsLoading } = useSellerJobs(address, true);
  const [earnings, setEarnings] = useState<any>(null);
  const [loadingEarnings, setLoadingEarnings] = useState(false);
  const [nodes, setNodes] = useState<any[]>([]);

  useEffect(() => {
    if (address && isConnected) {
      loadEarnings();
      loadNodes();
    }
  }, [address, isConnected]);

  const loadEarnings = async () => {
    if (!address) return;
    setLoadingEarnings(true);
    try {
      const data = await apiClient.getSellerEarnings(address, 30);
      setEarnings(data);
    } catch (err) {
      console.error('Failed to load earnings:', err);
    } finally {
      setLoadingEarnings(false);
    }
  };

  const loadNodes = async () => {
    if (!address) return;
    try {
      const data = await apiClient.listNodes();
      const sellerNodes = data.nodes?.filter((n: any) => n.seller_address === address) || [];
      setNodes(sellerNodes);
    } catch (err) {
      console.error('Failed to load nodes:', err);
    }
  };

  if (!isConnected || !address) {
    return (
      <div className="space-y-12 py-12 text-center">
        <p className="text-zinc-500">Please connect your wallet to view seller dashboard.</p>
      </div>
    );
  }

  return (
    <div className="space-y-12 py-12 animate-in fade-in slide-in-from-top-2 duration-700">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-white">Seller Dashboard</h1>
        <p className="text-zinc-500 text-sm mt-1">Monitor earnings and manage your GPU nodes.</p>
      </header>

      {/* Earnings Summary */}
      {loadingEarnings ? (
        <div className="text-center text-zinc-500 py-8">Loading earnings...</div>
      ) : earnings ? (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-zinc-900/40 border border-zinc-800 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <DollarSign className="w-4 h-4 text-emerald-400" />
              <span className="text-xs text-zinc-500 uppercase tracking-wider">Total</span>
            </div>
            <div className="text-2xl font-bold text-white">
              ${earnings.earnings?.total_usd?.toFixed(4) || '0.0000'}
            </div>
            <div className="text-xs text-zinc-500 mt-1">USDC</div>
          </div>

          <div className="bg-zinc-900/40 border border-zinc-800 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="w-4 h-4 text-amber-400" />
              <span className="text-xs text-zinc-500 uppercase tracking-wider">Today</span>
            </div>
            <div className="text-2xl font-bold text-white">
              ${earnings.earnings?.today_usd?.toFixed(4) || '0.0000'}
            </div>
            <div className="text-xs text-zinc-500 mt-1">USDC</div>
          </div>

          <div className="bg-zinc-900/40 border border-zinc-800 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <Clock className="w-4 h-4 text-blue-400" />
              <span className="text-xs text-zinc-500 uppercase tracking-wider">This Week</span>
            </div>
            <div className="text-2xl font-bold text-white">
              ${earnings.earnings?.week_usd?.toFixed(4) || '0.0000'}
            </div>
            <div className="text-xs text-zinc-500 mt-1">USDC</div>
          </div>

          <div className="bg-zinc-900/40 border border-zinc-800 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <Terminal className="w-4 h-4 text-purple-400" />
              <span className="text-xs text-zinc-500 uppercase tracking-wider">Jobs</span>
            </div>
            <div className="text-2xl font-bold text-white">
              {earnings.jobs?.total_completed || 0}
            </div>
            <div className="text-xs text-zinc-500 mt-1">Completed</div>
          </div>
        </div>
      ) : null}

      {/* Active Nodes */}
      {nodes.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-white mb-4">Active Nodes</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {nodes.map((node) => (
              <div key={node.node_id} className="bg-zinc-900/40 border border-zinc-800 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Cpu className="w-4 h-4 text-amber-400" />
                    <span className="font-mono text-xs text-zinc-400">{node.node_id}</span>
                  </div>
                  <div className={`px-2 py-1 rounded text-xs ${
                    node.is_available 
                      ? 'bg-emerald-400/10 text-emerald-400' 
                      : 'bg-zinc-400/10 text-zinc-400'
                  }`}>
                    {node.is_available ? 'Available' : 'Busy'}
                  </div>
                </div>
                <div className="text-sm text-zinc-300 mb-1">{node.device_name || 'Unknown GPU'}</div>
                <div className="text-xs text-zinc-500">
                  {node.gpu_type?.toUpperCase()} • ${node.price_per_hour?.toFixed(2)}/hr
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Job History */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-4">Job History</h2>
        <div className="border border-zinc-800 rounded-lg overflow-hidden bg-zinc-900/20 shadow-inner">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="bg-zinc-900/40 border-b border-zinc-800">
                <th className="px-6 py-3 font-medium text-zinc-500 text-xs uppercase tracking-wider">Job ID</th>
                <th className="px-6 py-3 font-medium text-zinc-500 text-xs uppercase tracking-wider">Status</th>
                <th className="px-6 py-3 font-medium text-zinc-500 text-xs uppercase tracking-wider">Earnings</th>
                <th className="px-6 py-3 font-medium text-zinc-500 text-xs uppercase tracking-wider">Duration</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/40">
              {jobsLoading ? (
                <tr>
                  <td colSpan={4} className="px-6 py-24 text-center text-zinc-500">
                    Loading jobs...
                  </td>
                </tr>
              ) : jobs.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-6 py-24 text-center">
                    <div className="flex flex-col items-center gap-3 opacity-40">
                      <Terminal className="w-8 h-8 text-zinc-600" />
                      <p className="text-sm font-mono italic">No jobs completed yet.</p>
                    </div>
                  </td>
                </tr>
              ) : (
                jobs.map((job) => (
                  <tr key={job.job_id} className="hover:bg-amber-400/[0.02] transition-colors">
                    <td className="px-6 py-5">
                      <div className="font-mono text-xs text-zinc-400">{job.job_id.slice(0, 12)}...</div>
                    </td>
                    <td className="px-6 py-5">
                      <StatusBadge status={job.status} />
                    </td>
                    <td className="px-6 py-5 font-mono text-zinc-400">
                      {job.total_cost_usd ? `$${parseFloat(job.total_cost_usd.toString()).toFixed(4)}` : '-'}
                    </td>
                    <td className="px-6 py-5 text-zinc-400">
                      {job.execution_duration_seconds
                        ? `${(parseFloat(job.execution_duration_seconds.toString()) / 60).toFixed(1)} min`
                        : '-'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

