import React, { useEffect, useState } from 'react';
import { apiClient } from '../../services/api';
import { Cpu, Wifi, WifiOff } from 'lucide-react';

interface NodeStatusPanelProps {
  sellerAddress: string;
}

export const NodeStatusPanel: React.FC<NodeStatusPanelProps> = ({ sellerAddress }) => {
  const [nodes, setNodes] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadNodes = async () => {
      try {
        const data = await apiClient.listNodes();
        const sellerNodes = data.nodes?.filter((n: any) => n.seller_address === sellerAddress) || [];
        setNodes(sellerNodes);
      } catch (error) {
        console.error('Failed to load nodes:', error);
      } finally {
        setLoading(false);
      }
    };

    if (sellerAddress) {
      loadNodes();
      const interval = setInterval(loadNodes, 5000);
      return () => clearInterval(interval);
    }
  }, [sellerAddress]);

  if (loading) {
    return (
      <div className="bg-zinc-900/40 border border-zinc-800 rounded-lg p-4">
        <div className="text-zinc-500 text-sm">Loading node status...</div>
      </div>
    );
  }

  if (nodes.length === 0) {
    return (
      <div className="bg-zinc-900/40 border border-zinc-800 rounded-lg p-4">
        <div className="flex items-center gap-2 mb-2">
          <Cpu className="w-4 h-4 text-zinc-500" />
          <span className="text-xs text-zinc-500 uppercase tracking-wider">Node Status</span>
        </div>
        <div className="text-sm text-zinc-500">No nodes registered. Use "swarm register" to register your GPU.</div>
      </div>
    );
  }

  const node = nodes[0];
  const isOnline = node.is_available;

  return (
    <div className="bg-zinc-900/40 border border-zinc-800 rounded-lg p-4">
      <div className="flex items-center gap-2 mb-4">
        <Cpu className="w-4 h-4 text-cyan-400" />
        <span className="text-xs text-zinc-500 uppercase tracking-wider">Node Status</span>
      </div>
      <div className="space-y-3">
        <div>
          <div className="text-xs text-zinc-500 mb-1">GPU</div>
          <div className="text-sm font-semibold text-white">{node.device_name || 'Unknown'}</div>
        </div>
        <div>
          <div className="text-xs text-zinc-500 mb-1">Type</div>
          <div className="text-sm text-zinc-300 uppercase">{node.gpu_type || 'N/A'}</div>
        </div>
        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs text-zinc-500 mb-1">Status</div>
            <div className="flex items-center gap-2">
              {isOnline ? (
                <>
                  <Wifi className="w-4 h-4 text-emerald-400" />
                  <span className="text-sm text-emerald-400">Online</span>
                </>
              ) : (
                <>
                  <WifiOff className="w-4 h-4 text-red-400" />
                  <span className="text-sm text-red-400">Offline</span>
                </>
              )}
            </div>
          </div>
          <div>
            <div className="text-xs text-zinc-500 mb-1">Price</div>
            <div className="text-sm font-semibold text-amber-400">
              ${(node.price_per_hour || 0).toFixed(2)}/hr
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

