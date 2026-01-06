import { Command } from '../types';
import { ParsedCommand } from '../../commandParser';
import { TerminalContextType } from '../../context';
import { apiClient } from '../../../services/api';
import { OutputFormatter } from '../../outputFormatter';

export const statsCommand: Command = {
  name: 'stats',
  aliases: ['marketplace', 'market'],
  description: 'Show marketplace statistics',
  usage: 'stats',
  requiresMode: 'buyer',
  requiresWallet: false,
  async execute(parsed: ParsedCommand, context: TerminalContextType): Promise<{ output: string; error?: string }> {
    try {
      const data = await apiClient.getStats();
      
      let output = `\n${OutputFormatter.colorize('Marketplace Statistics', 'cyan')}\n`;
      output += `${'='.repeat(50)}\n\n`;
      
      output += `${OutputFormatter.colorize('Active Nodes:', 'yellow')} ${data.nodes?.total_active || 0}\n\n`;
      
      if (data.nodes?.by_gpu_type) {
        output += `${OutputFormatter.colorize('GPUs Available:', 'yellow')}\n`;
        Object.entries(data.nodes.by_gpu_type).forEach(([type, info]: [string, any]) => {
          const typeUpper = type.toUpperCase();
          output += `  ${OutputFormatter.colorize(typeUpper, 'cyan')}: ${info.count || 0} nodes `;
          output += `(${OutputFormatter.colorize(`$${info.min_price?.toFixed(2)}-$${info.max_price?.toFixed(2)}/hr`, 'green')})\n`;
        });
        output += '\n';
      }
      
      if (data.jobs) {
        output += `${OutputFormatter.colorize('Job Queue:', 'yellow')}\n`;
        output += `  Pending: ${data.jobs.pending || 0}\n`;
        output += `  Executing: ${OutputFormatter.colorize(String(data.jobs.executing || 0), 'yellow')}\n`;
        output += `  Completed: ${OutputFormatter.colorize(String(data.jobs.completed || 0), 'green')}\n`;
        output += `  Failed: ${OutputFormatter.colorize(String(data.jobs.failed || 0), 'red')}\n`;
      }
      
      return { output };
    } catch (error: any) {
      return {
        output: '',
        error: OutputFormatter.error(`Failed to fetch stats: ${error.message || 'Unknown error'}`),
      };
    }
  },
  help: () => {
    return 'Shows marketplace statistics including active nodes, available GPUs, and job queue status.';
  },
};

