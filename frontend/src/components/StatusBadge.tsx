import React from 'react';

interface StatusBadgeProps {
  status: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const styles: Record<string, string> = {
    PENDING: 'text-zinc-500 bg-zinc-500/5 border-zinc-500/10',
    CLAIMED: 'text-blue-400 bg-blue-400/5 border-blue-400/20',
    EXECUTING: 'text-amber-400 bg-amber-400/5 border-amber-400/20',
    RUNNING: 'text-amber-400 bg-amber-400/5 border-amber-400/20',
    COMPLETED: 'text-emerald-400 bg-emerald-400/5 border-emerald-400/20',
    FAILED: 'text-rose-400 bg-rose-400/5 border-rose-400/20',
    CANCELLED: 'text-zinc-400 bg-zinc-400/5 border-zinc-400/10',
  };

  const styleClass = styles[status.toUpperCase()] || styles.PENDING;

  return (
    <div className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-mono border ${styleClass}`}>
      {(status === 'EXECUTING' || status === 'RUNNING') && (
        <div className="w-1 h-1 rounded-full bg-amber-400 animate-pulse" />
      )}
      {status}
    </div>
  );
};

