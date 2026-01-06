import { Command } from '../types';
import { ParsedCommand } from '../../commandParser';
import { TerminalContextType } from '../../context';
import { apiClient } from '../../../services/api';
import { OutputFormatter } from '../../outputFormatter';

export const jobsCommand: Command = {
  name: 'jobs',
  aliases: ['j'],
  description: 'List seller jobs',
  usage: 'jobs [--status <status>]',
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
      const statusFilter = parsed.flags.status as string | undefined;
      const data = await apiClient.listSellerJobs(context.walletAddress, statusFilter);
      const jobs = data.jobs || [];

      if (jobs.length === 0) {
        return {
          output: OutputFormatter.info('No jobs found.'),
        };
      }

      const columns = [
        { header: 'Job ID', width: 12 },
        { header: 'Status', width: 12 },
        { header: 'Earnings', width: 12 },
        { header: 'Completed', width: 20 },
      ];

      const rows = jobs.map((job: any) => {
        const status = job.status || 'PENDING';
        const statusColor = status === 'COMPLETED' ? 'green' : 
                           status === 'EXECUTING' ? 'yellow' : 
                           status === 'FAILED' ? 'red' : 'gray';
        
        return {
          'Job ID': OutputFormatter.colorize(job.job_id?.slice(0, 8) || 'N/A', 'cyan'),
          'Status': OutputFormatter.colorize(status, statusColor),
          'Earnings': job.total_cost_usd ? OutputFormatter.formatCurrency(job.total_cost_usd) : '-',
          'Completed': job.completed_at ? new Date(job.completed_at).toLocaleString() : '-',
        };
      });

      let output = `\n${OutputFormatter.colorize('Your Jobs', 'cyan')}\n`;
      output += OutputFormatter.table(columns, rows);
      output += `\n${jobs.length} job(s) found\n`;

      return { output };
    } catch (error: any) {
      return {
        output: '',
        error: OutputFormatter.error(`Failed to list jobs: ${error.message || 'Unknown error'}`),
      };
    }
  },
  help: () => {
    return 'Lists all jobs you have executed. Use --status <status> to filter by status.';
  },
};

