import { TerminalContextType } from '../context';
import { ParsedCommand } from '../commandParser';

export interface CommandResult {
  output: string;
  error?: string;
  exitCode?: number;
}

export interface Command {
  name: string;
  aliases?: string[];
  description: string;
  usage: string;
  requiresWallet?: boolean;
  requiresMode?: 'buyer' | 'seller' | null;
  execute: (parsed: ParsedCommand, context: TerminalContextType) => Promise<CommandResult>;
  help: () => string;
}

export interface CommandRegistry {
  [key: string]: Command;
}

