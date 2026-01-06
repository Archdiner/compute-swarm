import { Command } from '../types';
import { ParsedCommand } from '../../commandParser';
import { TerminalContextType } from '../../context';
import { apiClient } from '../../../services/api';
import { OutputFormatter } from '../../outputFormatter';

export const registerCommand: Command = {
  name: 'register',
  aliases: ['reg'],
  description: 'Register GPU node',
  usage: 'register [--price <amount>]',
  requiresMode: 'seller',
  requiresWallet: true,
  async execute(parsed: ParsedCommand, context: TerminalContextType): Promise<{ output: string; error?: string }> {
    if (!context.walletAddress) {
      return {
        output: '',
        error: OutputFormatter.error('Wallet not connected. Use "wallet connect" first.'),
      };
    }

    // This will need to detect GPU via API or browser APIs
    // For now, return a placeholder
    return {
      output: OutputFormatter.info('Node registration requires GPU detection. This will be handled by the UI.'),
      exitCode: 4, // Special code to trigger registration
    };
  },
  help: () => {
    return 'Registers your GPU node with the marketplace. Automatically detects GPU type and capabilities.';
  },
};

