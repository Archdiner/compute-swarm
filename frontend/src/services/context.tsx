import { createContext, useContext, useState, useCallback, ReactNode } from 'react';

export type Mode = 'buyer' | 'seller';

export interface TerminalContextType {
  mode: Mode;
  setMode: (mode: Mode) => void;
  commandHistory: string[];
  addToHistory: (command: string) => void;
  historyIndex: number;
  setHistoryIndex: (index: number) => void;
  walletAddress: string | null;
  setWalletAddress: (address: string | null) => void;
}

const TerminalContext = createContext<TerminalContextType | undefined>(undefined);

export function TerminalProvider({ children, walletAddress }: { children: ReactNode; walletAddress: string | null }) {
  const [mode, setMode] = useState<Mode>('buyer');
  const [commandHistory, setCommandHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState<number>(-1);

  const addToHistory = useCallback((command: string) => {
    if (command.trim()) {
      setCommandHistory(prev => {
        // Don't add duplicates if it's the same as the last command
        if (prev.length > 0 && prev[prev.length - 1] === command) {
          return prev;
        }
        return [...prev, command];
      });
      setHistoryIndex(-1);
    }
  }, []);

  return (
    <TerminalContext.Provider
      value={{
        mode,
        setMode,
        commandHistory,
        addToHistory,
        historyIndex,
        setHistoryIndex,
        walletAddress,
        setWalletAddress: () => {}, // Controlled by parent
      }}
    >
      {children}
    </TerminalContext.Provider>
  );
}

export function useTerminalContext(): TerminalContextType {
  const context = useContext(TerminalContext);
  if (!context) {
    // Return default context if not within provider (for App.tsx initial render)
    return {
      mode: 'buyer',
      setMode: () => {},
      commandHistory: [],
      addToHistory: () => {},
      historyIndex: -1,
      setHistoryIndex: () => {},
      walletAddress: null,
      setWalletAddress: () => {},
    };
  }
  return context;
}
