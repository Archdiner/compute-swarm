export interface TableColumn {
  header: string;
  width?: number;
  align?: 'left' | 'right' | 'center';
}

export interface TableRow {
  [key: string]: string | number | null | undefined;
}

export class OutputFormatter {
  static colorize(text: string, color: 'green' | 'red' | 'yellow' | 'blue' | 'cyan' | 'white' | 'gray'): string {
    const colors = {
      green: '\x1b[32m',
      red: '\x1b[31m',
      yellow: '\x1b[33m',
      blue: '\x1b[34m',
      cyan: '\x1b[36m',
      white: '\x1b[37m',
      gray: '\x1b[90m',
      reset: '\x1b[0m',
    };
    return `${colors[color]}${text}${colors.reset}`;
  }

  static success(text: string): string {
    return this.colorize(`✓ ${text}`, 'green');
  }

  static error(text: string): string {
    return this.colorize(`✗ ${text}`, 'red');
  }

  static warning(text: string): string {
    return this.colorize(`⚠ ${text}`, 'yellow');
  }

  static info(text: string): string {
    return this.colorize(`ℹ ${text}`, 'blue');
  }

  static table(columns: TableColumn[], rows: TableRow[]): string {
    if (rows.length === 0) {
      return 'No data';
    }

    // Calculate column widths
    const widths = columns.map(col => {
      const headerWidth = col.header.length;
      const maxDataWidth = Math.max(
        ...rows.map(row => {
          const value = row[col.header]?.toString() || '';
          return value.length;
        })
      );
      return Math.max(headerWidth, maxDataWidth, col.width || 0);
    });

    // Build table
    let output = '';

    // Top border
    output += '┌' + widths.map(w => '─'.repeat(w + 2)).join('┬') + '┐\n';

    // Header
    output += '│ ' + columns.map((col, i) => {
      const header = col.header;
      const padding = widths[i] - header.length;
      return header + ' '.repeat(padding) + ' ';
    }).join('│ ') + '│\n';

    // Separator
    output += '├' + widths.map(w => '─'.repeat(w + 2)).join('┼') + '┤\n';

    // Rows
    rows.forEach(row => {
      output += '│ ' + columns.map((col, i) => {
        const value = row[col.header]?.toString() || '';
        const padding = widths[i] - value.length;
        const aligned = col.align === 'right' 
          ? ' '.repeat(padding) + value
          : value + ' '.repeat(padding);
        return aligned + ' ';
      }).join('│ ') + '│\n';
    });

    // Bottom border
    output += '└' + widths.map(w => '─'.repeat(w + 2)).join('┴') + '┘';

    return output;
  }

  static progressBar(current: number, total: number, width: number = 20): string {
    const percentage = Math.min(100, Math.max(0, (current / total) * 100));
    const filled = Math.floor((percentage / 100) * width);
    const empty = width - filled;
    return `[${'█'.repeat(filled)}${'░'.repeat(empty)}] ${percentage.toFixed(0)}%`;
  }

  static formatDuration(seconds: number): string {
    if (seconds < 60) {
      return `${seconds}s`;
    } else if (seconds < 3600) {
      const mins = Math.floor(seconds / 60);
      const secs = seconds % 60;
      return `${mins}m ${secs}s`;
    } else {
      const hours = Math.floor(seconds / 3600);
      const mins = Math.floor((seconds % 3600) / 60);
      return `${hours}h ${mins}m`;
    }
  }

  static formatCurrency(amount: number, currency: string = 'USD'): string {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency,
      minimumFractionDigits: 4,
      maximumFractionDigits: 4,
    }).format(amount);
  }

  static formatAddress(address: string): string {
    if (address.length <= 10) return address;
    return `${address.slice(0, 6)}...${address.slice(-4)}`;
  }
}

