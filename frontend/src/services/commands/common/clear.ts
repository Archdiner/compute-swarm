import { Command } from '../types';
import { ParsedCommand } from '../../commandParser';
import { TerminalContextType } from '../../context';

export const clearCommand: Command = {
  name: 'clear',
  aliases: ['cls'],
  description: 'Clear the terminal',
  usage: 'clear',
  requiresMode: null,
  requiresWallet: false,
  async execute(parsed: ParsedCommand, context: TerminalContextType): Promise<{ output: string }> {
    // Return special marker that terminal component will handle
    return { output: '\x1b[2J\x1b[H' }; // ANSI clear screen
  },
  help: () => {
    return 'Clears the terminal screen.';
  },
};

