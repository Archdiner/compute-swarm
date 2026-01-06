import { Command } from '../types';
import { ParsedCommand } from '../../commandParser';
import { TerminalContextType } from '../../context';
import { apiClient } from '../../../services/api';
import { OutputFormatter } from '../../outputFormatter';

export const submitCommand: Command = {
  name: 'submit',
  aliases: ['sub'],
  description: 'Submit a job',
  usage: 'submit [--template <name>] [--file <path>] [--price <amount>] [--timeout <seconds>]',
  requiresMode: 'buyer',
  requiresWallet: true,
  async execute(parsed: ParsedCommand, context: TerminalContextType): Promise<{ output: string; error?: string }> {
    if (!context.walletAddress) {
      return {
        output: '',
        error: OutputFormatter.error('Wallet not connected. Use "wallet connect" first.'),
      };
    }

    // This is a placeholder - actual implementation will handle interactive prompts
    // For now, return a message indicating this needs to be handled by the UI
    return {
      output: OutputFormatter.info('Job submission requires interactive input. This will be handled by the UI.'),
      exitCode: 3, // Special code to trigger interactive submission
    };
  },
  help: () => {
    return 'Submit a compute job:\n' +
           '  --template <name>  - Use a template (pytorch, huggingface, etc.)\n' +
           '  --file <path>      - Submit from a file\n' +
           '  --price <amount>   - Max price per hour (default: $10.00)\n' +
           '  --timeout <sec>    - Timeout in seconds (default: 3600)';
  },
};

