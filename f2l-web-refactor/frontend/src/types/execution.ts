// Execution Types
export type ExecutionStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface SyncExecution {
  id: string;
  session_id: string;
  status: ExecutionStatus;
  
  // Execution details
  started_at: string;
  completed_at?: string;
  duration?: number;
  
  // Progress tracking
  files_scanned: number;
  files_transferred: number;
  files_skipped: number;
  files_failed: number;
  bytes_transferred: number;
  progress_percent: number;
  current_file?: string;
  
  // Results
  operations_completed: number;
  operations_failed: number;
  error_message?: string;
  
  // Configuration snapshot
  dry_run: boolean;
  sync_direction: string;
  source_path: string;
  destination_path: string;
  
  // Metadata
  created_at: string;
  updated_at: string;
  
  // Related data
  session?: {
    id: string;
    name: string;
  };
}

export interface ExecutionProgress {
  execution_id: string;
  status: ExecutionStatus;
  progress_percent: number;
  files_scanned: number;
  files_transferred: number;
  files_skipped: number;
  files_failed: number;
  bytes_transferred: number;
  current_file?: string;
  estimated_time_remaining?: number;
  transfer_rate?: number; // bytes per second
  updated_at: string;
}

export interface ExecutionStatistics {
  execution_id: string;
  session_id: string;
  total_operations: number;
  successful_operations: number;
  failed_operations: number;
  total_files: number;
  total_size: number;
  transfer_rate: number;
  duration: number;
  efficiency_score: number; // 0-100
}

export interface ExecutionLog {
  id: string;
  execution_id: string;
  level: 'debug' | 'info' | 'warning' | 'error';
  message: string;
  details?: Record<string, any>;
  timestamp: string;
  file_path?: string;
  operation?: string;
}

export interface StartExecutionRequest {
  session_id: string;
  dry_run?: boolean;
  force?: boolean;
}

export interface StartExecutionResponse {
  execution_id: string;
  status: ExecutionStatus;
  message: string;
}

export interface CancelExecutionRequest {
  execution_id: string;
  reason?: string;
}

// Execution Filters and Queries
export interface ExecutionFilters {
  session_id?: string;
  status?: ExecutionStatus[];
  date_from?: string;
  date_to?: string;
  duration_min?: number;
  duration_max?: number;
  has_errors?: boolean;
}

export interface ExecutionSummary {
  total_executions: number;
  successful_executions: number;
  failed_executions: number;
  cancelled_executions: number;
  total_files_transferred: number;
  total_bytes_transferred: number;
  average_duration: number;
  success_rate: number;
  last_24h_executions: number;
  last_7d_executions: number;
}

// Real-time Execution Updates
export interface ExecutionUpdate {
  execution_id: string;
  type: 'status_change' | 'progress_update' | 'file_update' | 'error' | 'completion';
  data: {
    status?: ExecutionStatus;
    progress_percent?: number;
    current_file?: string;
    files_transferred?: number;
    bytes_transferred?: number;
    error_message?: string;
    transfer_rate?: number;
  };
  timestamp: string;
}

// Batch Operations
export interface BatchExecutionRequest {
  session_ids: string[];
  execution_mode: 'parallel' | 'sequential';
  dry_run?: boolean;
  continue_on_error?: boolean;
}

export interface BatchExecutionResponse {
  batch_id: string;
  execution_ids: string[];
  status: 'started' | 'failed';
  message: string;
}
