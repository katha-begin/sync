// Shot Download Types

export interface ShotSelection {
  episode: string;
  sequence: string;
  shot: string;
}

export interface ShotStructure {
  episodes: string[];
  sequences: Array<{
    episode: string;
    sequence: string;
  }>;
  shots: Array<{
    episode: string;
    sequence: string;
    shot: string;
  }>;
  cache_valid: boolean;
  last_scan?: string;
}

export interface ScanResult {
  status: string;
  message: string;
  total_episodes: number;
  total_sequences: number;
  total_shots: number;
  scan_duration_seconds?: number;
  last_scan?: string;
}

export interface ShotComparison {
  episode: string;
  sequence: string;
  shot: string;
  department: string;
  ftp_version?: string;
  local_version?: string;
  available_versions?: string[];  // All available versions on FTP
  latest_version?: string;  // Latest available version
  needs_update: boolean;
  status: 'up_to_date' | 'update_available' | 'new_download' | 'ftp_missing' | 'error';
  file_count: number;
  total_size: number;
  error_message?: string;
}

export interface CompareRequest {
  endpoint_id: string;
  shots: ShotSelection[];
  departments: string[];
}

export type VersionStrategy = 'latest' | 'specific' | 'all' | 'custom';
export type ConflictStrategy = 'skip' | 'overwrite' | 'compare' | 'keep_both';

export interface CreateTaskRequest {
  endpoint_id: string;
  task_name: string;
  shots: ShotSelection[];
  departments: string[];
  version_strategy?: VersionStrategy;
  specific_version?: string;
  custom_versions?: Record<string, string[]>;  // Map of "shot-department" to versions array
  conflict_strategy?: ConflictStrategy;
  notes?: string;
  created_by?: string;
}

export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
export type ItemStatus = 'pending' | 'downloading' | 'completed' | 'failed';

export interface DownloadTask {
  task_id: string;
  name: string;
  status: TaskStatus;
  version_strategy?: VersionStrategy;
  specific_version?: string;
  conflict_strategy?: ConflictStrategy;
  total_items: number;
  completed_items: number;
  failed_items: number;
  total_size: number;
  downloaded_size: number;
  progress_percent: number;
  created_at?: string;
  started_at?: string;
  completed_at?: string;
  created_by?: string;
  notes?: string;
}

export interface DownloadTaskItem {
  id: string;
  episode: string;
  sequence: string;
  shot: string;
  department: string;
  ftp_version?: string;
  local_version?: string;
  selected_version?: string;
  available_versions?: string[];
  latest_version?: string;
  status: ItemStatus;
  file_count: number;
  total_size: number;
  downloaded_size: number;
  files_skipped?: number;
  files_overwritten?: number;
  files_kept_both?: number;
  error_message?: string;
  started_at?: string;
  completed_at?: string;
}

export interface TaskDetails {
  task: DownloadTask;
  items: DownloadTaskItem[];
}

export interface TaskSummary {
  task_id: string;
  name: string;
  status: TaskStatus;
  total_items: number;
  completed_items: number;
  failed_items: number;
  progress_percent: number;
  created_at?: string;
  created_by?: string;
}

// Department options
export const DEPARTMENTS = ['anim', 'lighting'] as const;
export type Department = typeof DEPARTMENTS[number];

// Status labels
export const TASK_STATUS_LABELS: Record<TaskStatus, string> = {
  pending: 'Pending',
  running: 'Running',
  completed: 'Completed',
  failed: 'Failed',
  cancelled: 'Cancelled',
};

export const ITEM_STATUS_LABELS: Record<ItemStatus, string> = {
  pending: 'Pending',
  downloading: 'Downloading',
  completed: 'Completed',
  failed: 'Failed',
};

export const COMPARISON_STATUS_LABELS: Record<ShotComparison['status'], string> = {
  up_to_date: 'Up to Date',
  update_available: 'Update Available',
  new_download: 'New Download',
  ftp_missing: 'FTP Missing',
  error: 'Error',
};

// Status colors
export const TASK_STATUS_COLORS: Record<TaskStatus, string> = {
  pending: '#9e9e9e',
  running: '#2196f3',
  completed: '#4caf50',
  failed: '#f44336',
  cancelled: '#ff9800',
};

export const COMPARISON_STATUS_COLORS: Record<ShotComparison['status'], string> = {
  up_to_date: '#4caf50',
  update_available: '#ff9800',
  new_download: '#2196f3',
  ftp_missing: '#f44336',
  error: '#f44336',
};

// Version Strategy labels
export const VERSION_STRATEGY_LABELS: Record<VersionStrategy, string> = {
  latest: 'Latest Version',
  specific: 'Specific Version',
  all: 'All Versions',
  custom: 'Custom (Per Shot)',
};

// Conflict Strategy labels
export const CONFLICT_STRATEGY_LABELS: Record<ConflictStrategy, string> = {
  skip: 'Skip Existing',
  overwrite: 'Overwrite All',
  compare: 'Compare & Update',
  keep_both: 'Keep Both',
};
