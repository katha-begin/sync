// Shot Upload Types

export interface LocalFile {
  filename: string;
  path: string;
  version?: string;
  size: number;
  modified?: string;
}

export interface LocalDepartment {
  name: string;
  path: string;
  output_path: string;
  files: LocalFile[];
}

export interface LocalShot {
  name: string;
  path: string;
  departments: LocalDepartment[];
}

export interface LocalSequence {
  name: string;
  path: string;
  shots: LocalShot[];
}

export interface LocalEpisode {
  name: string;
  path: string;
  sequences: LocalSequence[];
}

export interface LocalStructure {
  endpoint_id: string;
  endpoint_name: string;
  root_path: string;
  episodes: LocalEpisode[];
}

// Upload item for the queue
export interface UploadQueueItem {
  id: string;  // Unique client-side ID
  episode: string;
  sequence: string;
  shot: string;
  department: string;
  filename: string;
  source_path: string;
  target_path?: string;
  relative_path?: string;
  version?: string;
  size: number;
  selected: boolean;
}

// Request types
export interface UploadItemRequest {
  episode: string;
  sequence: string;
  shot: string;
  department: string;
  filename: string;
  source_path: string;
  version?: string;
  size: number;
}

export interface CreateUploadTaskRequest {
  endpoint_id: string;  // Single endpoint with both local_path and remote_path
  task_name: string;
  items: UploadItemRequest[];
  version_strategy?: UploadVersionStrategy;
  specific_version?: string;
  conflict_strategy?: UploadConflictStrategy;
  notes?: string;
}

// Version and conflict strategies for upload
export type UploadVersionStrategy = 'latest' | 'specific' | 'custom';
export type UploadConflictStrategy = 'skip' | 'overwrite';

// Upload task types
export type UploadTaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
export type UploadItemStatus = 'pending' | 'uploading' | 'completed' | 'failed' | 'skipped';

export interface UploadTask {
  id: string;
  name: string;
  endpoint_id: string;  // Single endpoint with both local_path and remote_path
  status: UploadTaskStatus;
  version_strategy?: UploadVersionStrategy;
  conflict_strategy?: UploadConflictStrategy;
  total_items: number;
  completed_items: number;
  failed_items: number;
  skipped_items: number;
  total_size: number;
  uploaded_size: number;
  created_at?: string;
  started_at?: string;
  completed_at?: string;
  created_by?: string;
  notes?: string;
}

export interface UploadTaskItem {
  id: string;
  episode: string;
  sequence: string;
  shot: string;
  department: string;
  filename: string;
  version?: string;
  source_path: string;
  target_path: string;
  status: UploadItemStatus;
  file_size: number;
  uploaded_size: number;
  target_exists: boolean;
  error_message?: string;
}

export interface UploadTaskDetails extends UploadTask {
  items: UploadTaskItem[];
}

// Upload history types
export interface UploadHistoryItem {
  id: string;
  task_id?: string;
  task_name: string;
  episode: string;
  sequence: string;
  shot: string;
  department: string;
  filename: string;
  version?: string;
  file_size: number;
  source_path: string;
  target_path: string;
  source_endpoint_name: string;
  target_endpoint_name: string;
  status: string;
  error_message?: string;
  uploaded_at?: string;
  uploaded_by?: string;
}

export interface UploadHistoryResponse {
  history: UploadHistoryItem[];
  total: number;
  limit: number;
  offset: number;
}

// Status labels
export const UPLOAD_TASK_STATUS_LABELS: Record<UploadTaskStatus, string> = {
  pending: 'Pending',
  running: 'Uploading',
  completed: 'Completed',
  failed: 'Failed',
  cancelled: 'Cancelled',
};

export const UPLOAD_ITEM_STATUS_LABELS: Record<UploadItemStatus, string> = {
  pending: 'Pending',
  uploading: 'Uploading',
  completed: 'Completed',
  failed: 'Failed',
  skipped: 'Skipped',
};

// Status colors
export const UPLOAD_TASK_STATUS_COLORS: Record<UploadTaskStatus, string> = {
  pending: '#9e9e9e',
  running: '#2196f3',
  completed: '#4caf50',
  failed: '#f44336',
  cancelled: '#ff9800',
};

export const UPLOAD_ITEM_STATUS_COLORS: Record<UploadItemStatus, string> = {
  pending: '#9e9e9e',
  uploading: '#2196f3',
  completed: '#4caf50',
  failed: '#f44336',
  skipped: '#ff9800',
};

// Conflict Strategy labels for upload
export const UPLOAD_CONFLICT_STRATEGY_LABELS: Record<UploadConflictStrategy, string> = {
  skip: 'Skip Existing',
  overwrite: 'Overwrite All',
};

// Helper to format bytes
export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Helper to calculate progress percentage
export function calculateProgress(uploaded: number, total: number): number {
  if (total === 0) return 0;
  return Math.round((uploaded / total) * 100);
}

