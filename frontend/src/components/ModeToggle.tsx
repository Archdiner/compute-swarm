import React from 'react';
import { Mode } from '../services/context';

interface ModeToggleProps {
  mode: Mode;
  onModeChange: (mode: Mode) => void;
}

export const ModeToggle: React.FC<ModeToggleProps> = ({ mode, onModeChange }) => {
  return (
    <div className="flex items-center gap-2">
      <button
        onClick={() => onModeChange('buyer')}
        className={`px-4 py-1.5 rounded-md text-xs font-medium transition-all ${
          mode === 'buyer'
            ? 'bg-amber-400 text-zinc-950'
            : 'bg-zinc-900/40 text-zinc-500 hover:text-zinc-300 border border-zinc-800'
        }`}
      >
        Buyer
      </button>
      <button
        onClick={() => onModeChange('seller')}
        className={`px-4 py-1.5 rounded-md text-xs font-medium transition-all ${
          mode === 'seller'
            ? 'bg-amber-400 text-zinc-950'
            : 'bg-zinc-900/40 text-zinc-500 hover:text-zinc-300 border border-zinc-800'
        }`}
      >
        Seller
      </button>
    </div>
  );
};

