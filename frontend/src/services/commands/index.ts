import { Command, CommandRegistry } from './types';
import * as buyerCommands from './buyer';
import * as sellerCommands from './seller';
import * as commonCommands from './common';

const registry: CommandRegistry = {};

// Register buyer commands
Object.values(buyerCommands).forEach(cmd => {
  if (cmd && typeof cmd === 'object' && 'name' in cmd) {
    registry[cmd.name] = cmd as Command;
    if (cmd.aliases) {
      cmd.aliases.forEach(alias => {
        registry[alias] = cmd as Command;
      });
    }
  }
});

// Register seller commands
Object.values(sellerCommands).forEach(cmd => {
  if (cmd && typeof cmd === 'object' && 'name' in cmd) {
    registry[cmd.name] = cmd as Command;
    if (cmd.aliases) {
      cmd.aliases.forEach(alias => {
        registry[alias] = cmd as Command;
      });
    }
  }
});

// Register common commands
Object.values(commonCommands).forEach(cmd => {
  if (cmd && typeof cmd === 'object' && 'name' in cmd) {
    registry[cmd.name] = cmd as Command;
    if (cmd.aliases) {
      cmd.aliases.forEach(alias => {
        registry[alias] = cmd as Command;
      });
    }
  }
});

export function getCommand(name: string): Command | undefined {
  return registry[name.toLowerCase()];
}

export function getAllCommands(mode?: 'buyer' | 'seller'): Command[] {
  return Object.values(registry).filter(cmd => {
    if (!mode) return true;
    if (cmd.requiresMode === null) return true; // Common commands
    return cmd.requiresMode === mode;
  });
}

export { registry };

