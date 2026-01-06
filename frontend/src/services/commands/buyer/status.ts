import { Command } from '../types';
import { ParsedCommand } from '../../commandParser';
import { TerminalContextType } from '../../context';
import { apiClient } from '../../../services/api';
import { OutputFormatter } from '../../outputFormatter';

export const statusCommand: Command = {
  name: 'status',
  aliases: ['st'],
  description: 'Get job status',
  usage: 'status <job_id>',
  requiresMode: 'buyer',
  requiresWallet: false,
  async execute(parsed: ParsedCommand, context: TerminalContextType): Promise<{ output: string; error?: string }> {
    const { args } = parsed;
    
    if (args.length === 0) {
      return {
        output: '',
        error: OutputFormatter.error('Job ID required. Usage: status <job_id>'),
      };
    }

    const jobId = args[0];

    try {
      const job = await apiClient.getJobStatus(jobId);
      
      let output = `\n${OutputFormatter.colorize('Job Status', 'cyan')}\n`;
      output += `${'='.repeat(50)}\n\n`;
      
      output += `Job ID: ${OutputFormatter.colorize(job.job_id || jobId, 'cyan')}\n`;
      
      const status = job.status || 'PENDING';
      const statusColor = status === 'COMPLETED' ? 'green' : 
                         status === 'EXECUTING' ? 'yellow' : 
                         status === 'FAILED' ? 'red' : 'gray';
      output += `Status: ${OutputFormatter.colorize(status, statusColor)}\n`;
      
      if (job.created_at) {
        output += `Created: ${new Date(job.created_at).toLocaleString()}\n`;
      }
      
      if (job.started_at) {
        output += `Started: ${new Date(job.started_at).toLocaleString()}\n`;
      }
      
      if (job.completed_at) {
        output += `Completed: ${new Date(job.completed_at).toLocaleString()}\n`;
      }
      
      if (job.execution_duration_seconds) {
        output += `Duration: ${OutputFormatter.formatDuration(job.execution_duration_seconds)}\n`;
      }
      
      if (job.total_cost_usd) {
        output += `Cost: ${OutputFormatter.colorize(OutputFormatter.formatCurrency(job.total_cost_usd), 'green')}\n`;
      }
      
      if (job.result_output) {
        output += `\n${OutputFormatter.colorize('Output:', 'yellow')}\n`;
        output += job.result_output.slice(0, 500);
        if (job.result_output.length > 500) {
          output += '\n... (truncated)';
        }
      }
      
      if (job.result_error) {
        output += `\n${OutputFormatter.colorize('Error:', 'red')}\n`;
        output += job.result_error;
      }
      
      return { output };
    } catch (error: any) {
      return {
        output: '',
        error: OutputFormatter.error(`Failed to get job status: ${error.message || 'Unknown error'}`),
      };
    }
  },
  help: () => {
    return 'Shows detailed status information for a specific job.';
  },
};

