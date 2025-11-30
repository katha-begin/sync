// API Configuration
export const API_CONFIG = {
  BASE_URL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  VERSION: import.meta.env.VITE_API_VERSION || 'v1',
  TIMEOUT: 30000,
  RETRY_ATTEMPTS: 3,
  RETRY_DELAY: 1000,
} as const;

// WebSocket Configuration
export const WS_CONFIG = {
  URL: import.meta.env.VITE_WS_URL || 'http://localhost:8000',
  RECONNECT_ATTEMPTS: 5,
  RECONNECT_DELAY: 3000,
  HEARTBEAT_INTERVAL: 30000,
} as const;

// Application Configuration
export const APP_CONFIG = {
  NAME: import.meta.env.VITE_APP_NAME || 'F2L Sync',
  VERSION: import.meta.env.VITE_APP_VERSION || '2.0.0',
  DESCRIPTION: import.meta.env.VITE_APP_DESCRIPTION || 'File-to-Local Sync Management System',
  DEFAULT_THEME: (import.meta.env.VITE_DEFAULT_THEME as 'light' | 'dark') || 'light',
  ENABLE_DARK_MODE: import.meta.env.VITE_ENABLE_DARK_MODE === 'true',
} as const;

// Pagination Defaults
export const PAGINATION = {
  DEFAULT_PAGE_SIZE: 25,
  PAGE_SIZE_OPTIONS: [10, 25, 50, 100],
  MAX_PAGE_SIZE: 1000,
} as const;

// File Size Limits
export const FILE_LIMITS = {
  MAX_UPLOAD_SIZE: 100 * 1024 * 1024, // 100MB
  MAX_IMPORT_SIZE: 10 * 1024 * 1024,  // 10MB
  CHUNK_SIZE: 1024 * 1024,            // 1MB
} as const;

// Endpoint Types
export const ENDPOINT_TYPES = {
  FTP: 'ftp',
  SFTP: 'sftp',
  S3: 's3',
  LOCAL: 'local',
} as const;

export const ENDPOINT_TYPE_LABELS = {
  [ENDPOINT_TYPES.FTP]: 'FTP',
  [ENDPOINT_TYPES.SFTP]: 'SFTP',
  [ENDPOINT_TYPES.S3]: 'Amazon S3',
  [ENDPOINT_TYPES.LOCAL]: 'Local',
} as const;

// Sync Directions
export const SYNC_DIRECTIONS = {
  SOURCE_TO_DESTINATION: 'source_to_destination',
  DESTINATION_TO_SOURCE: 'destination_to_source',
  BIDIRECTIONAL: 'bidirectional',
} as const;

export const SYNC_DIRECTION_LABELS = {
  [SYNC_DIRECTIONS.SOURCE_TO_DESTINATION]: 'Source → Destination',
  [SYNC_DIRECTIONS.DESTINATION_TO_SOURCE]: 'Destination → Source',
  [SYNC_DIRECTIONS.BIDIRECTIONAL]: 'Bidirectional',
} as const;

// Execution Statuses
export const EXECUTION_STATUSES = {
  PENDING: 'pending',
  RUNNING: 'running',
  COMPLETED: 'completed',
  FAILED: 'failed',
  CANCELLED: 'cancelled',
} as const;

export const EXECUTION_STATUS_LABELS = {
  [EXECUTION_STATUSES.PENDING]: 'Pending',
  [EXECUTION_STATUSES.RUNNING]: 'Running',
  [EXECUTION_STATUSES.COMPLETED]: 'Completed',
  [EXECUTION_STATUSES.FAILED]: 'Failed',
  [EXECUTION_STATUSES.CANCELLED]: 'Cancelled',
} as const;

// Log Levels
export const LOG_LEVELS = {
  DEBUG: 'debug',
  INFO: 'info',
  WARNING: 'warning',
  ERROR: 'error',
  CRITICAL: 'critical',
} as const;

export const LOG_LEVEL_LABELS = {
  [LOG_LEVELS.DEBUG]: 'Debug',
  [LOG_LEVELS.INFO]: 'Info',
  [LOG_LEVELS.WARNING]: 'Warning',
  [LOG_LEVELS.ERROR]: 'Error',
  [LOG_LEVELS.CRITICAL]: 'Critical',
} as const;

// Colors for status indicators
export const STATUS_COLORS = {
  SUCCESS: '#4caf50',
  ERROR: '#f44336',
  WARNING: '#ff9800',
  INFO: '#2196f3',
  PENDING: '#9e9e9e',
  RUNNING: '#2196f3',
} as const;

// Default Port Numbers
export const DEFAULT_PORTS = {
  FTP: 21,
  SFTP: 22,
  HTTP: 80,
  HTTPS: 443,
} as const;

// Common File Patterns
export const FILE_PATTERNS = {
  ALL: '*',
  IMAGES: '*.{jpg,jpeg,png,gif,bmp,svg}',
  DOCUMENTS: '*.{pdf,doc,docx,txt,rtf}',
  VIDEOS: '*.{mp4,avi,mkv,mov,wmv}',
  AUDIO: '*.{mp3,wav,flac,aac}',
  ARCHIVES: '*.{zip,rar,7z,tar,gz}',
} as const;

// Cron Presets
export const CRON_PRESETS = {
  EVERY_MINUTE: '* * * * *',
  EVERY_5_MINUTES: '*/5 * * * *',
  EVERY_15_MINUTES: '*/15 * * * *',
  EVERY_30_MINUTES: '*/30 * * * *',
  HOURLY: '0 * * * *',
  DAILY_MIDNIGHT: '0 0 * * *',
  DAILY_2AM: '0 2 * * *',
  WEEKLY_SUNDAY: '0 0 * * 0',
  MONTHLY: '0 0 1 * *',
} as const;

export const CRON_PRESET_LABELS = {
  [CRON_PRESETS.EVERY_MINUTE]: 'Every minute',
  [CRON_PRESETS.EVERY_5_MINUTES]: 'Every 5 minutes',
  [CRON_PRESETS.EVERY_15_MINUTES]: 'Every 15 minutes',
  [CRON_PRESETS.EVERY_30_MINUTES]: 'Every 30 minutes',
  [CRON_PRESETS.HOURLY]: 'Every hour',
  [CRON_PRESETS.DAILY_MIDNIGHT]: 'Daily at midnight',
  [CRON_PRESETS.DAILY_2AM]: 'Daily at 2:00 AM',
  [CRON_PRESETS.WEEKLY_SUNDAY]: 'Weekly on Sunday',
  [CRON_PRESETS.MONTHLY]: 'Monthly on 1st',
} as const;

// Time Zones (common ones)
export const TIMEZONES = [
  'UTC',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'Europe/London',
  'Europe/Paris',
  'Europe/Berlin',
  'Asia/Tokyo',
  'Asia/Shanghai',
  'Australia/Sydney',
] as const;

// Refresh Intervals (in milliseconds)
export const REFRESH_INTERVALS = {
  FAST: 1000,      // 1 second
  NORMAL: 5000,    // 5 seconds
  SLOW: 30000,     // 30 seconds
  VERY_SLOW: 60000, // 1 minute
} as const;

// Local Storage Keys
export const STORAGE_KEYS = {
  AUTH_TOKEN: 'f2l_auth_token',
  USER_PREFERENCES: 'f2l_user_preferences',
  THEME_MODE: 'f2l_theme_mode',
  SIDEBAR_COLLAPSED: 'f2l_sidebar_collapsed',
  TABLE_SETTINGS: 'f2l_table_settings',
  RECENT_SEARCHES: 'f2l_recent_searches',
} as const;

// Navigation Routes
export const ROUTES = {
  HOME: '/',
  DASHBOARD: '/dashboard',
  ENDPOINTS: '/endpoints',
  SESSIONS: '/sessions',
  MULTI_SESSIONS: '/multi-sessions',
  EXECUTIONS: '/executions',
  LOGS: '/logs',
  SETTINGS: '/settings',
  LOGIN: '/login',
  PROFILE: '/profile',
  SHOT_DOWNLOAD: '/shot-download',
  DOWNLOAD_TASKS: '/download-tasks',
} as const;

// Form Validation Rules
export const VALIDATION_RULES = {
  REQUIRED: { required: 'This field is required' },
  EMAIL: {
    pattern: {
      value: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
      message: 'Please enter a valid email address',
    },
  },
  PORT: {
    min: { value: 1, message: 'Port must be between 1 and 65535' },
    max: { value: 65535, message: 'Port must be between 1 and 65535' },
  },
  PASSWORD: {
    minLength: { value: 8, message: 'Password must be at least 8 characters' },
  },
  URL: {
    pattern: {
      value: /^https?:\/\/.+/,
      message: 'Please enter a valid URL',
    },
  },
} as const;

// Chart Colors
export const CHART_COLORS = [
  '#1976d2', // Primary blue
  '#388e3c', // Green
  '#f57c00', // Orange
  '#d32f2f', // Red
  '#7b1fa2', // Purple
  '#0288d1', // Light blue
  '#689f38', // Light green
  '#fbc02d', // Yellow
  '#e64a19', // Deep orange
  '#5d4037', // Brown
] as const;

// Feature Flags
export const FEATURES = {
  ANALYTICS: import.meta.env.VITE_ENABLE_ANALYTICS === 'true',
  ERROR_REPORTING: import.meta.env.VITE_ENABLE_ERROR_REPORTING === 'true',
  SERVICE_WORKER: import.meta.env.VITE_ENABLE_SERVICE_WORKER === 'true',
  CACHE: import.meta.env.VITE_CACHE_ENABLED !== 'false',
  CSP: import.meta.env.VITE_ENABLE_CSP === 'true',
} as const;
