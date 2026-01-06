import { Command } from '../types';
import { ParsedCommand } from '../../commandParser';
import { TerminalContextType } from '../../context';
import { getAllCommands } from '../index';
import { OutputFormatter } from '../../outputFormatter';

export const helpCommand: Command = {
  name: 'help',
  aliases: ['h', '?'],
  description: 'Show help information',
  usage: 'help [command]',
  requiresMode: null,
  requiresWallet: false,
  async execute(parsed: ParsedCommand, context: TerminalContextType): Promise<{ output: string; error?: string }> {
    const { args } = parsed;
    
    if (args.length > 0) {
      // Show help for specific command
      const commandName = args[0].toLowerCase();
      const { getCommand } = await import('../index');
      const cmd = getCommand(commandName);
      
      if (!cmd) {
        return {
          output: OutputFormatter.error(`Command "${commandName}" not found. Use "help" to see all commands.`),
        };
      }
      
      let help = `\n${OutputFormatter.colorize(cmd.name, 'cyan')} - ${cmd.description}\n\n`;
      help += `Usage: ${cmd.usage}\n`;
      if (cmd.aliases && cmd.aliases.length > 0) {
        help += `Aliases: ${cmd.aliases.join(', ')}\n`;
      }
      if (cmd.requiresMode) {
        help += `Mode: ${cmd.requiresMode}\n`;
      }
      if (cmd.requiresWallet) {
        help += `Requires wallet connection\n`;
      }
      help += `\n${cmd.help()}\n`;
      
      return { output: help };
    }
    
    // Show all commands
    const commands = getAllCommands(context.mode);
    const buyerCommands = commands.filter(c => c.requiresMode === 'buyer');
    const sellerCommands = commands.filter(c => c.requiresMode === 'seller');
    const commonCommands = commands.filter(c => c.requiresMode === null);
    
    let output = `\n${OutputFormatter.colorize('ComputeSwarm Terminal', 'cyan')} - Available Commands\n`;
    output += `${'='.repeat(50)}\n\n`;
    
    if (commonCommands.length > 0) {
      output += `${OutputFormatter.colorize('Common Commands:', 'yellow')}\n`;
      commonCommands.forEach(cmd => {
        output += `  ${OutputFormatter.colorize(cmd.name.padEnd(20), 'cyan')} ${cmd.description}\n`;
      });
      output += '\n';
    }
    
    if (buyerCommands.length > 0) {
      output += `${OutputFormatter.colorize('Buyer Commands:', 'yellow')}\n`;
      buyerCommands.forEach(cmd => {
        output += `  ${OutputFormatter.colorize(cmd.name.padEnd(20), 'cyan')} ${cmd.description}\n`;
      });
      output += '\n';
    }
    
    if (sellerCommands.length > 0) {
      output += `${OutputFormatter.colorize('Seller Commands:', 'yellow')}\n`;
      sellerCommands.forEach(cmd => {
        output += `  ${OutputFormatter.colorize(cmd.name.padEnd(20), 'cyan')} ${cmd.description}\n`;
      });
      output += '\n';
    }
    
    output += `Use ${OutputFormatter.colorize('help <command>', 'cyan')} for detailed help on a specific command.\n`;
    
    return { output };
  },
  help: () => {
    return 'Shows available commands or detailed help for a specific command.';
  },
};

