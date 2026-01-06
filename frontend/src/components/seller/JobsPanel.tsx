import React, { useEffect, useState } from 'react';
import { apiClient } from '../../services/api';
import { Activity, CheckCircle, XCircle, Clock } from 'lucide-react';

interface JobsPanelProps {
  sellerAddress: string;
}

export const JobsPanel: React.FC<JobsPanelProps> = ({ sellerAddress }) => {
  const [jobs, setJobs] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadJobs = async () => {
      try {
        const data = await apiClient.listSellerJobs(sellerAddress);
        setJobs(data);
      } catch (error) {
        console.error('Failed to load jobs:', error);
      } finally {
        setLoading(false);
      }
    };

    if (sellerAddress) {
      loadJobs();
      const interval = setInterval(loadJobs, 5000);
      return () => clearInterval(interval);
    }
  }, [sellerAddress]);

  if (loading) {
    return (
      <div className="bg-zinc-900/40 border border-zinc-800 rounded-lg p-4">
        <div className="text-zinc-500 text-sm">Loading jobs...</div>
      </div>
    );
  }

  const jobList = jobs?.jobs || [];
  const active = jobList.filter((j: any) => j.status === 'EXECUTING' || j.status === 'CLAIMED').length;
  const completed = jobList.filter((j: any) => j.status === 'COMPLETED').length;
  const failed = jobList.filter((j: any) => j.status === 'FAILED').length;

  return (
    <div className="bg-zinc-900/40 border border-zinc-800 rounded-lg p-4">
      <div className="flex items-center gap-2 mb-4">
        <Activity className="w-4 h-4 text-blue-400" />
        <span className="text-xs text-zinc-500 uppercase tracking-wider">Jobs</span>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="text-xs text-zinc-500 mb-1 flex items-center gap-1">
            <Clock className="w-3 h-3" />
            Active
          </div>
          <div className="text-xl font-bold text-yellow-400">{active}</div>
        </div>
        <div>
          <div className="text-xs text-zinc-500 mb-1 flex items-center gap-1">
            <CheckCircle className="w-3 h-3" />
            Completed
          </div>
          <div className="text-xl font-bold text-emerald-400">{completed}</div>
        </div>
        <div>
          <div className="text-xs text-zinc-500 mb-1 flex items-center gap-1">
            <XCircle className="w-3 h-3" />
            Failed
          </div>
          <div className="text-lg font-semibold text-red-400">{failed}</div>
        </div>
        <div>
          <div className="text-xs text-zinc-500 mb-1">Total</div>
          <div className="text-lg font-semibold text-white">{jobList.length}</div>
        </div>
      </div>
    </div>
  );
};

