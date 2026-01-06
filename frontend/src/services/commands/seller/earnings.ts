import { Command } from '../types';
import { ParsedCommand } from '../../commandParser';
import { TerminalContextType } from '../../context';
import { apiClient } from '../../../services/api';
import { OutputFormatter } from '../../outputFormatter';

export const earningsCommand: Command = {
  name: 'earnings',
  aliases: ['earn', 'money'],
  description: 'Show earnings summary',
  usage: 'earnings [--days <n>]',
  requiresMode: 'seller',
  requiresWallet: true,
  async execute(parsed: ParsedCommand, context: TerminalContextType): Promise<{ output: string; error?: string }> {
    if (!context.walletAddress) {
      return {
        output: '',
        error: OutputFormatter.error('Wallet not connected. Use "wallet connect" first.'),
      };
    }

    try {
      const days = parsed.flags.days ? parseInt(parsed.flags.days as string) : 30;
      const data = await apiClient.getSellerEarnings(context.walletAddress, days);
      
      const earnings = data.earnings || {};
      const jobs = data.jobs || {};
      
      let output = `\n${OutputFormatter.colorize('Earnings Summary', 'cyan')}\n`;
      output += `${'='.repeat(50)}\n\n`;
      
      output += `Total: ${OutputFormatter.colorize(OutputFormatter.formatCurrency(earnings.total_usd || 0), 'green')}\n`;
      output += `Today: ${OutputFormatter.colorize(OutputFormatter.formatCurrency(earnings.today_usd || 0), 'green')}\n`;
      output += `This Week: ${OutputFormatter.colorize(OutputFormatter.formatCurrency(earnings.week_usd || 0), 'green')}\n`;
      output += `This Month: ${OutputFormatter.colorize(OutputFormatter.formatCurrency(earnings.month_usd || 0), 'green')}\n\n`;
      
      output += `${OutputFormatter.colorize('Job Statistics:', 'yellow')}\n`;
      output += `  Completed: ${jobs.total_completed || 0}\n`;
      output += `  Total Compute Hours: ${(jobs.total_compute_hours || 0).toFixed(2)}\n`;
      if (jobs.avg_earnings_per_job) {
        output += `  Avg per Job: ${OutputFormatter.formatCurrency(jobs.avg_earnings_per_job)}\n`;
      }
      
      return { output };
    } catch (error: any) {
      return {
        output: '',
        error: OutputFormatter.error(`Failed to fetch earnings: ${error.message || 'Unknown error'}`),
      };
    }
  },
  help: () => {
    return 'Shows your earnings summary. Use --days <n> to specify the period (default: 30 days).';
  },
};

