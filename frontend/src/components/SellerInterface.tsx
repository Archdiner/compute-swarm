import React from 'react';
import { Terminal } from './Terminal';
import { EarningsPanel } from './seller/EarningsPanel';
import { JobsPanel } from './seller/JobsPanel';
import { NodeStatusPanel } from './seller/NodeStatusPanel';
import { useTerminalContext } from '../services/context';

interface SellerInterfaceProps {
  onWalletConnect?: () => void;
  onWalletDisconnect?: () => void;
  onCommand?: (command: string) => void;
}

export const SellerInterface: React.FC<SellerInterfaceProps> = ({
  onWalletConnect,
  onWalletDisconnect,
  onCommand,
}) => {
  const { walletAddress } = useTerminalContext();

  return (
    <div className="w-full h-full flex flex-col gap-4">
      <div className="mb-2">
        <h2 className="text-lg font-semibold text-white mb-2">Seller Mode - Dashboard & Terminal</h2>
        <p className="text-sm text-zinc-500">
          Monitor earnings, manage nodes, and execute seller commands.
        </p>
      </div>

      {/* Dashboard Panels */}
      {walletAddress && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <EarningsPanel sellerAddress={walletAddress} />
          <JobsPanel sellerAddress={walletAddress} />
          <NodeStatusPanel sellerAddress={walletAddress} />
        </div>
      )}

      {/* Terminal */}
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

