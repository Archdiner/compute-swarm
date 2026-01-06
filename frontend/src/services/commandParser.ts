export interface ParsedCommand {
  command: string;
  args: string[];
  flags: Record<string, string | boolean>;
}

export function parseCommand(input: string): ParsedCommand {
  const trimmed = input.trim();
  if (!trimmed) {
    return { command: '', args: [], flags: {} };
  }

  const parts: string[] = [];
  let current = '';
  let inQuotes = false;
  let quoteChar = '';

  for (let i = 0; i < trimmed.length; i++) {
    const char = trimmed[i];
    
    if ((char === '"' || char === "'") && (i === 0 || trimmed[i - 1] !== '\\')) {
      if (!inQuotes) {
        inQuotes = true;
        quoteChar = char;
      } else if (char === quoteChar) {
        inQuotes = false;
        quoteChar = '';
      } else {
        current += char;
      }
    } else if (char === ' ' && !inQuotes) {
      if (current) {
        parts.push(current);
        current = '';
      }
    } else {
      current += char;
    }
  }

  if (current) {
    parts.push(current);
  }

  if (parts.length === 0) {
    return { command: '', args: [], flags: {} };
  }

  const command = parts[0];
  const args: string[] = [];
  const flags: Record<string, string | boolean> = {};

  for (let i = 1; i < parts.length; i++) {
    const part = parts[i];
    
    if (part.startsWith('--')) {
      const flagName = part.slice(2);
      const nextPart = parts[i + 1];
      
      // Check if next part is a value (not a flag)
      if (nextPart && !nextPart.startsWith('--') && i + 1 < parts.length) {
        flags[flagName] = nextPart;
        i++; // Skip the value
      } else {
        flags[flagName] = true;
      }
    } else {
      args.push(part);
    }
  }

  return { command, args, flags };
}

