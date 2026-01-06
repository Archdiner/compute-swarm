import React from 'react';
import { Terminal } from './Terminal';

interface BuyerInterfaceProps {
  onWalletConnect?: () => void;
  onWalletDisconnect?: () => void;
  onCommand?: (command: string) => void;
}

export const BuyerInterface: React.FC<BuyerInterfaceProps> = ({
  onWalletConnect,
  onWalletDisconnect,
  onCommand,
}) => {
  return (
    <div className="w-full h-full flex flex-col">
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-white mb-2">Buyer Mode - Guided Terminal</h2>
        <p className="text-sm text-zinc-500">
          Submit jobs, monitor status, and manage your compute tasks.
        </p>
      </div>
      <div className="flex-1 min-h-0 border border-zinc-800 rounded-lg overflow-hidden bg-[#121214]">
        <Terminal
          onWalletConnect={onWalletConnect}
          onWalletDisconnect={onWalletDisconnect}
          onCommand={onCommand}
        />
      </div>
    </div>
  );
};

