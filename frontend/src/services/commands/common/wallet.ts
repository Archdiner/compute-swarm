import { Command } from '../types';
import { ParsedCommand } from '../../commandParser';
import { TerminalContextType } from '../../context';
import { OutputFormatter } from '../../outputFormatter';

export const walletCommand: Command = {
  name: 'wallet',
  aliases: ['w'],
  description: 'Wallet management commands',
  usage: 'wallet [connect|disconnect|info]',
  requiresMode: null,
  requiresWallet: false,
  async execute(parsed: ParsedCommand, context: TerminalContextType): Promise<{ output: string; error?: string }> {
    const { args } = parsed;
    const subcommand = args[0]?.toLowerCase() || 'info';
    
    if (subcommand === 'connect') {
      if (context.walletAddress) {
        return {
          output: OutputFormatter.info('Wallet already connected'),
        };
      }
      // Return special marker to trigger wallet connection
      return {
        output: OutputFormatter.info('Opening wallet connection...'),
        exitCode: 1, // Special code to trigger connection
      };
    }
    
    if (subcommand === 'disconnect') {
      if (!context.walletAddress) {
        return {
          output: OutputFormatter.warning('No wallet connected'),
        };
      }
      // Return special marker to trigger wallet disconnection
      return {
        output: OutputFormatter.info('Disconnecting wallet...'),
        exitCode: 2, // Special code to trigger disconnection
      };
    }
    
    if (subcommand === 'info' || !subcommand) {
      if (!context.walletAddress) {
        return {
          output: OutputFormatter.warning('No wallet connected. Use "wallet connect" to connect.'),
        };
      }
      
      return {
        output: `\n${OutputFormatter.colorize('Wallet Information', 'cyan')}\n` +
                `${'='.repeat(40)}\n` +
                `Address: ${OutputFormatter.colorize(OutputFormatter.formatAddress(context.walletAddress), 'green')}\n` +
                `Mode: ${OutputFormatter.colorize(context.mode, 'yellow')}\n`,
      };
    }
    
    return {
      output: OutputFormatter.error(`Unknown wallet subcommand: ${subcommand}`),
    };
  },
  help: () => {
    return 'Wallet management:\n' +
           '  connect    - Connect your wallet\n' +
           '  disconnect - Disconnect your wallet\n' +
           '  info       - Show wallet information';
  },
};

