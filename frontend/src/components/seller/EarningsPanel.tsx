import React, { useEffect, useState } from 'react';
import { apiClient } from '../../services/api';
import { DollarSign, TrendingUp, Clock, Calendar } from 'lucide-react';

interface EarningsPanelProps {
  sellerAddress: string;
}

export const EarningsPanel: React.FC<EarningsPanelProps> = ({ sellerAddress }) => {
  const [earnings, setEarnings] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadEarnings = async () => {
      try {
        const data = await apiClient.getSellerEarnings(sellerAddress, 30);
        setEarnings(data);
      } catch (error) {
        console.error('Failed to load earnings:', error);
      } finally {
        setLoading(false);
      }
    };

    if (sellerAddress) {
      loadEarnings();
      const interval = setInterval(loadEarnings, 5000); // Poll every 5 seconds
      return () => clearInterval(interval);
    }
  }, [sellerAddress]);

  if (loading) {
    return (
      <div className="bg-zinc-900/40 border border-zinc-800 rounded-lg p-4">
        <div className="text-zinc-500 text-sm">Loading earnings...</div>
      </div>
    );
  }

  const earningsData = earnings?.earnings || {};

  return (
    <div className="bg-zinc-900/40 border border-zinc-800 rounded-lg p-4">
      <div className="flex items-center gap-2 mb-4">
        <DollarSign className="w-4 h-4 text-emerald-400" />
        <span className="text-xs text-zinc-500 uppercase tracking-wider">Earnings</span>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="text-xs text-zinc-500 mb-1">Total</div>
          <div className="text-xl font-bold text-white">
            ${(earningsData.total_usd || 0).toFixed(4)}
          </div>
        </div>
        <div>
          <div className="text-xs text-zinc-500 mb-1 flex items-center gap-1">
            <TrendingUp className="w-3 h-3" />
            Today
          </div>
          <div className="text-xl font-bold text-emerald-400">
            ${(earningsData.today_usd || 0).toFixed(4)}
          </div>
        </div>
        <div>
          <div className="text-xs text-zinc-500 mb-1 flex items-center gap-1">
            <Clock className="w-3 h-3" />
            This Week
          </div>
          <div className="text-lg font-semibold text-white">
            ${(earningsData.week_usd || 0).toFixed(4)}
          </div>
        </div>
        <div>
          <div className="text-xs text-zinc-500 mb-1 flex items-center gap-1">
            <Calendar className="w-3 h-3" />
            This Month
          </div>
          <div className="text-lg font-semibold text-white">
            ${(earningsData.month_usd || 0).toFixed(4)}
          </div>
        </div>
      </div>
    </div>
  );
};

