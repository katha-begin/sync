import { format, formatDistanceToNow, parseISO, isValid } from 'date-fns';

// File size formatting
export const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B';

  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
};

// Alias for formatFileSize
export const formatBytes = formatFileSize;

// Transfer rate formatting
export const formatTransferRate = (bytesPerSecond: number): string => {
  return `${formatFileSize(bytesPerSecond)}/s`;
};

// Duration formatting
export const formatDuration = (seconds: number): string => {
  if (seconds < 60) {
    return `${Math.round(seconds)}s`;
  } else if (seconds < 3600) {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.round(seconds % 60);
    return remainingSeconds > 0 ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`;
  } else {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
  }
};

// Date formatting
export const formatDate = (date: string | Date, formatString: string = 'PPp'): string => {
  try {
    const dateObj = typeof date === 'string' ? parseISO(date) : date;
    if (!isValid(dateObj)) return 'Invalid date';
    return format(dateObj, formatString);
  } catch {
    return 'Invalid date';
  }
};

export const formatRelativeTime = (date: string | Date): string => {
  try {
    const dateObj = typeof date === 'string' ? parseISO(date) : date;
    if (!isValid(dateObj)) return 'Invalid date';
    return formatDistanceToNow(dateObj, { addSuffix: true });
  } catch {
    return 'Invalid date';
  }
};

// Progress formatting
export const formatProgress = (current: number, total: number): string => {
  if (total === 0) return '0%';
  const percentage = Math.round((current / total) * 100);
  return `${percentage}%`;
};

export const formatProgressWithCounts = (current: number, total: number): string => {
  const percentage = formatProgress(current, total);
  return `${percentage} (${current.toLocaleString()} / ${total.toLocaleString()})`;
};

// Number formatting
export const formatNumber = (num: number, decimals: number = 0): string => {
  return num.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
};

export const formatPercentage = (value: number, total: number, decimals: number = 1): string => {
  if (total === 0) return '0%';
  const percentage = (value / total) * 100;
  return `${percentage.toFixed(decimals)}%`;
};

// Status formatting
export const formatStatus = (status: string): string => {
  return status
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
};

// Path formatting
export const formatPath = (path: string, maxLength: number = 50): string => {
  if (path.length <= maxLength) return path;
  
  const parts = path.split('/');
  if (parts.length <= 2) return path;
  
  // Try to keep the filename and some parent directories
  let result = parts[parts.length - 1]; // filename
  let currentLength = result.length;
  
  for (let i = parts.length - 2; i >= 0; i--) {
    const part = parts[i];
    const addition = `/${part}`;
    
    if (currentLength + addition.length + 3 <= maxLength) { // +3 for "..."
      result = part + '/' + result;
      currentLength += addition.length;
    } else {
      result = '.../' + result;
      break;
    }
  }
  
  return result;
};

// Endpoint type formatting
export const formatEndpointType = (type: string): string => {
  const typeMap: Record<string, string> = {
    ftp: 'FTP',
    sftp: 'SFTP',
    s3: 'Amazon S3',
    local: 'Local',
  };
  
  return typeMap[type.toLowerCase()] || type.toUpperCase();
};

// Sync direction formatting
export const formatSyncDirection = (direction: string): string => {
  const directionMap: Record<string, string> = {
    source_to_destination: 'Source → Destination',
    destination_to_source: 'Destination → Source',
    bidirectional: 'Bidirectional',
  };
  
  return directionMap[direction] || direction;
};

// Error message formatting
export const formatErrorMessage = (error: any): string => {
  if (typeof error === 'string') return error;
  if (error?.message) return error.message;
  if (error?.detail) return error.detail;
  return 'An unknown error occurred';
};

// Cron expression formatting (basic)
export const formatCronExpression = (cron: string): string => {
  try {
    const parts = cron.split(' ');
    if (parts.length !== 5) return cron;
    
    const [minute, hour, day, month, weekday] = parts;
    
    // Handle some common patterns
    if (cron === '0 0 * * *') return 'Daily at midnight';
    if (cron === '0 2 * * *') return 'Daily at 2:00 AM';
    if (cron === '0 0 * * 0') return 'Weekly on Sunday at midnight';
    if (cron === '0 0 1 * *') return 'Monthly on the 1st at midnight';
    
    // Basic formatting
    let result = '';
    
    if (minute === '0' && hour !== '*') {
      result += `At ${hour}:00`;
    } else if (minute !== '*' && hour !== '*') {
      result += `At ${hour}:${minute.padStart(2, '0')}`;
    } else {
      result += 'Every ';
      if (minute !== '*') result += `${minute} minutes`;
      if (hour !== '*') result += ` at hour ${hour}`;
    }
    
    if (day !== '*') result += ` on day ${day}`;
    if (month !== '*') result += ` in month ${month}`;
    if (weekday !== '*') result += ` on weekday ${weekday}`;
    
    return result || cron;
  } catch {
    return cron;
  }
};

// Validation helpers
export const isValidEmail = (email: string): boolean => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
};

export const isValidUrl = (url: string): boolean => {
  try {
    new URL(url);
    return true;
  } catch {
    return false;
  }
};

export const isValidPort = (port: number): boolean => {
  return port >= 1 && port <= 65535;
};

// Text truncation
export const truncateText = (text: string, maxLength: number, suffix: string = '...'): string => {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength - suffix.length) + suffix;
};

// Capitalize first letter
export const capitalize = (text: string): string => {
  return text.charAt(0).toUpperCase() + text.slice(1);
};

// Convert camelCase to Title Case
export const camelToTitle = (text: string): string => {
  return text
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, str => str.toUpperCase())
    .trim();
};
