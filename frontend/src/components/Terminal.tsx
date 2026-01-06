import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Terminal as XTerm } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import '@xterm/xterm/css/xterm.css';
import { useTerminalContext } from '../services/context';
import { parseCommand } from '../services/commandParser';
import { getCommand } from '../services/commands';
import { OutputFormatter } from '../services/outputFormatter';

interface TerminalProps {
  onWalletConnect?: () => void;
  onWalletDisconnect?: () => void;
  onCommand?: (command: string) => void;
}

export const Terminal: React.FC<TerminalProps> = ({ 
  onWalletConnect, 
  onWalletDisconnect,
  onCommand 
}) => {
  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<XTerm | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const [currentInput, setCurrentInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const context = useTerminalContext();

  useEffect(() => {
    if (!terminalRef.current) return;

    const xterm = new XTerm({
      theme: {
        background: '#121214',
        foreground: '#e1e1e3',
        cursor: '#fbbf24',
        selection: '#fbbf2440',
        black: '#000000',
        red: '#ef4444',
        green: '#10b981',
        yellow: '#fbbf24',
        blue: '#3b82f6',
        magenta: '#a855f7',
        cyan: '#06b6d4',
        white: '#e1e1e3',
        brightBlack: '#525252',
        brightRed: '#f87171',
        brightGreen: '#34d399',
        brightYellow: '#fbbf24',
        brightBlue: '#60a5fa',
        brightMagenta: '#c084fc',
        brightCyan: '#22d3ee',
        brightWhite: '#ffffff',
      },
      fontSize: 13,
      fontFamily: 'Monaco, Menlo, "Ubuntu Mono", monospace',
      cursorBlink: true,
      cursorStyle: 'block',
      lineHeight: 1.2,
      letterSpacing: 0.5,
    });

    const fitAddon = new FitAddon();
    const webLinksAddon = new WebLinksAddon();

    xterm.loadAddon(fitAddon);
    xterm.loadAddon(webLinksAddon);
    xterm.open(terminalRef.current);
    fitAddon.fit();

    xtermRef.current = xterm;
    fitAddonRef.current = fitAddon;

    // Initial welcome message
    const prompt = getPrompt();
    xterm.writeln('\x1b[36mComputeSwarm Terminal v1.0.0\x1b[0m');
    xterm.writeln('Type "help" for available commands.\n');
    xterm.write(prompt);

    // Handle input
    let inputBuffer = '';
    let historyIndex = -1;

    xterm.onData((data) => {
      if (isProcessing) return;

      const code = data.charCodeAt(0);

      // Enter key
      if (code === 13) {
        xterm.write('\r\n');
        if (inputBuffer.trim()) {
          handleCommand(inputBuffer.trim());
          context.addToHistory(inputBuffer.trim());
          inputBuffer = '';
          historyIndex = -1;
        } else {
          xterm.write(prompt);
        }
      }
      // Backspace
      else if (code === 127) {
        if (inputBuffer.length > 0) {
          inputBuffer = inputBuffer.slice(0, -1);
          xterm.write('\b \b');
        }
      }
      // Up arrow
      else if (code === 27 && data.length === 3 && data.charCodeAt(2) === 65) {
        if (context.commandHistory.length > 0) {
          historyIndex = Math.min(historyIndex + 1, context.commandHistory.length - 1);
          const historyCommand = context.commandHistory[context.commandHistory.length - 1 - historyIndex];
          // Clear current line
          xterm.write('\r' + ' '.repeat(inputBuffer.length + prompt.length) + '\r');
          inputBuffer = historyCommand;
          xterm.write(prompt + inputBuffer);
        }
      }
      // Down arrow
      else if (code === 27 && data.length === 3 && data.charCodeAt(2) === 66) {
        if (historyIndex > 0) {
          historyIndex = historyIndex - 1;
          const historyCommand = context.commandHistory[context.commandHistory.length - 1 - historyIndex];
          xterm.write('\r' + ' '.repeat(inputBuffer.length + prompt.length) + '\r');
          inputBuffer = historyCommand;
          xterm.write(prompt + inputBuffer);
        } else if (historyIndex === 0) {
          historyIndex = -1;
          xterm.write('\r' + ' '.repeat(inputBuffer.length + prompt.length) + '\r');
          inputBuffer = '';
          xterm.write(prompt);
        }
      }
      // Tab (future: autocomplete)
      else if (code === 9) {
        // Tab completion would go here
      }
      // Regular character
      else if (code >= 32) {
        inputBuffer += data;
        xterm.write(data);
      }
    });

    // Handle window resize
    const handleResize = () => {
      fitAddon.fit();
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      xterm.dispose();
    };
  }, []);

  const getPrompt = () => {
    const mode = context.mode === 'buyer' ? '\x1b[33m[buyer]\x1b[0m' : '\x1b[35m[seller]\x1b[0m';
    return `${mode} $ `;
  };

  const handleCommand = async (input: string) => {
    if (!xtermRef.current) return;

    setIsProcessing(true);
    const xterm = xtermRef.current;

    try {
      const parsed = parseCommand(input);
      
      if (!parsed.command) {
        xterm.write(getPrompt());
        setIsProcessing(false);
        return;
      }

      // Handle clear command specially
      if (parsed.command === 'clear') {
        xterm.clear();
        xterm.write(getPrompt());
        setIsProcessing(false);
        return;
      }

      const cmd = getCommand(parsed.command);
      
      if (!cmd) {
        xterm.writeln(`\x1b[31mCommand not found: ${parsed.command}\x1b[0m`);
        xterm.writeln(`Type "help" for available commands.`);
        xterm.write(getPrompt());
        setIsProcessing(false);
        return;
      }

      // Check mode requirement
      if (cmd.requiresMode && cmd.requiresMode !== context.mode) {
        xterm.writeln(`\x1b[31mCommand "${parsed.command}" requires ${cmd.requiresMode} mode.\x1b[0m`);
        xterm.write(getPrompt());
        setIsProcessing(false);
        return;
      }

      // Check wallet requirement
      if (cmd.requiresWallet && !context.walletAddress) {
        xterm.writeln(`\x1b[33mWallet not connected. Use "wallet connect" first.\x1b[0m`);
        if (onWalletConnect) {
          onWalletConnect();
        }
        xterm.write(getPrompt());
        setIsProcessing(false);
        return;
      }

      // Execute command
      const result = await cmd.execute(parsed, context);

      // Handle special exit codes
      if (result.exitCode === 1 && onWalletConnect) {
        onWalletConnect();
      } else if (result.exitCode === 2 && onWalletDisconnect) {
        onWalletDisconnect();
      } else if (result.exitCode === 3 || result.exitCode === 4) {
        // Interactive commands - handled by UI
        if (onCommand) {
          onCommand(input);
        }
      }

      // Write output
      if (result.output) {
        // Parse ANSI codes and write
        xterm.writeln(result.output);
      }

      if (result.error) {
        xterm.writeln(result.error);
      }

    } catch (error: any) {
      xterm.writeln(`\x1b[31mError: ${error.message || 'Unknown error'}\x1b[0m`);
    } finally {
      xterm.write(getPrompt());
      setIsProcessing(false);
    }
  };

  return (
    <div className="w-full h-full">
      <div ref={terminalRef} className="w-full h-full" style={{ minHeight: '400px' }} />
    </div>
  );
};

