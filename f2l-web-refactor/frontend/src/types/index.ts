// Re-export all types for easy importing
export * from './api';
export * from './endpoint';
export * from './session';
export * from './execution';
export * from './shot';
// Export upload types except ShotSelection (already exported from shot.ts)
export type {
  LocalFile,
  LocalDepartment,
  LocalShot,
  LocalSequence,
  LocalEpisode,
  LocalStructure,
  LocalStructureHierarchical,
  UploadQueueItem,
  CreateUploadTaskRequest,
  UploadItemRequest,
  UploadVersionStrategy,
  UploadConflictStrategy,
  UploadTaskStatus,
  UploadItemStatus,
  UploadTask,
  UploadTaskItem,
  UploadTaskDetails,
  UploadHistoryItem,
  UploadHistoryResponse,
} from './upload';
export {
  UPLOAD_TASK_STATUS_LABELS,
  UPLOAD_ITEM_STATUS_LABELS,
  UPLOAD_TASK_STATUS_COLORS,
  UPLOAD_ITEM_STATUS_COLORS,
  UPLOAD_CONFLICT_STRATEGY_LABELS,
  formatBytes,
  calculateProgress,
} from './upload';

// Common UI Types
export interface SelectOption<T = string> {
  value: T;
  label: string;
  disabled?: boolean;
}

export interface TableColumn<T = any> {
  id: string;
  label: string;
  minWidth?: number;
  align?: 'left' | 'center' | 'right';
  format?: (value: any, row: T) => string | React.ReactNode;
  render?: (value: any, row: T) => React.ReactNode;
  type?: 'string' | 'number' | 'date' | 'datetime' | 'boolean' | 'status' | 'actions';
  sortable?: boolean;
}

export interface FormField {
  name: string;
  label: string;
  type: 'text' | 'password' | 'email' | 'number' | 'select' | 'multiselect' | 'checkbox' | 'textarea' | 'file';
  required?: boolean;
  placeholder?: string;
  helperText?: string;
  options?: SelectOption[];
  validation?: Record<string, any>;
}

// Theme Types
export type ThemeMode = 'light' | 'dark' | 'system';

export interface ThemeConfig {
  mode: ThemeMode;
  primaryColor: string;
  secondaryColor: string;
  fontSize: 'small' | 'medium' | 'large';
  borderRadius: number;
}

// Navigation Types
export interface NavigationItem {
  id: string;
  label: string;
  path: string;
  icon?: React.ComponentType;
  badge?: string | number;
  children?: NavigationItem[];
  disabled?: boolean;
  external?: boolean;
}

// Notification Types
export type NotificationType = 'success' | 'error' | 'warning' | 'info';

export interface Notification {
  id: string;
  type: NotificationType;
  title: string;
  message?: string;
  duration?: number;
  persistent?: boolean;
  read?: boolean;
  actions?: Array<{
    label: string;
    action: () => void;
    onClick?: () => void;
    closeOnClick?: boolean;
    icon?: React.ReactNode;
  }>;
}

// Dashboard Types
export interface DashboardStats {
  total_endpoints: number;
  active_endpoints: number;
  total_sessions: number;
  active_sessions: number;
  running_executions: number;
  completed_executions_today: number;
  failed_executions_today: number;
  total_files_transferred_today: number;
  total_bytes_transferred_today: number;
}

export interface ChartDataPoint {
  name: string;
  value: number;
  timestamp?: string;
}

export interface TimeSeriesData {
  timestamp: string;
  value: number;
  label?: string;
}

// Settings Types
export interface AppSettings {
  id: string;
  key: string;
  value: string;
  description?: string;
  category: string;
  type: 'string' | 'number' | 'boolean' | 'json';
  is_public: boolean;
  created_at: string;
  updated_at: string;
}

export interface UpdateSettingsRequest {
  settings: Array<{
    key: string;
    value: string;
  }>;
}

// Health Check Types
export interface HealthCheck {
  status: 'healthy' | 'unhealthy' | 'degraded';
  timestamp: string;
  checks: Record<string, {
    status: 'healthy' | 'unhealthy';
    message?: string;
    duration_ms?: number;
  }>;
  system_metrics?: {
    cpu_percent: number;
    memory_percent: number;
    disk_percent: number;
    uptime_seconds: number;
  };
}

// Log Types
export interface LogEntry {
  id: string;
  level: 'debug' | 'info' | 'warning' | 'error' | 'critical';
  message: string;
  timestamp: string;
  logger_name?: string;
  module?: string;
  function?: string;
  line_number?: number;
  execution_id?: string;
  session_id?: string;
  endpoint_id?: string;
  user_id?: string;
  extra_data?: Record<string, any>;
}

export interface LogFilters {
  level?: string[];
  date_from?: string;
  date_to?: string;
  search?: string;
  logger_name?: string;
  execution_id?: string;
  session_id?: string;
  endpoint_id?: string;
}

// User Types (for future authentication)
export interface User {
  id: string;
  username: string;
  email: string;
  full_name?: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
  last_login_at?: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}
