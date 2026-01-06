import { Command } from '../types';
import { ParsedCommand } from '../../commandParser';
import { TerminalContextType } from '../../context';
import { apiClient } from '../../../services/api';
import { OutputFormatter } from '../../outputFormatter';

export const listCommand: Command = {
  name: 'list',
  aliases: ['ls', 'jobs'],
  description: 'List your jobs',
  usage: 'list [--status <status>]',
  requiresMode: 'buyer',
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
      const data = await apiClient.listBuyerJobs(context.walletAddress, statusFilter);
      const jobs = data.jobs || [];

      if (jobs.length === 0) {
        return {
          output: OutputFormatter.info('No jobs found.'),
        };
      }

      const columns = [
        { header: 'Job ID', width: 12 },
        { header: 'Status', width: 12 },
        { header: 'Cost', width: 12 },
        { header: 'Created', width: 20 },
      ];

      const rows = jobs.map((job: any) => {
        const status = job.status || 'PENDING';
        const statusColor = status === 'COMPLETED' ? 'green' : 
                           status === 'EXECUTING' ? 'yellow' : 
                           status === 'FAILED' ? 'red' : 'gray';
        
        return {
          'Job ID': OutputFormatter.colorize(job.job_id?.slice(0, 8) || 'N/A', 'cyan'),
          'Status': OutputFormatter.colorize(status, statusColor),
          'Cost': job.total_cost_usd ? OutputFormatter.formatCurrency(job.total_cost_usd) : '-',
          'Created': job.created_at ? new Date(job.created_at).toLocaleString() : '-',
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
    return 'Lists all your jobs. Use --status <status> to filter by status (PENDING, EXECUTING, COMPLETED, FAILED).';
  },
};

