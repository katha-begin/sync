// Session Types
export type SyncDirection = 'source_to_destination' | 'destination_to_source' | 'bidirectional';

export interface SyncSession {
  id: string;
  name: string;
  description?: string;
  
  // Endpoint configuration
  source_endpoint_id: string;
  destination_endpoint_id: string;
  source_path: string;
  destination_path: string;
  
  // Sync configuration
  sync_direction: SyncDirection;
  delete_extra_files: boolean;
  preserve_timestamps: boolean;
  follow_symlinks: boolean;
  
  // Filtering
  include_patterns?: string[];
  exclude_patterns?: string[];
  max_file_size?: number;
  min_file_size?: number;
  
  // Performance settings
  parallel_transfers: boolean;
  max_parallel_transfers?: number;
  transfer_chunk_size?: number;
  
  // Scheduling
  schedule_enabled: boolean;
  schedule_cron?: string;
  schedule_timezone?: string;
  next_run_at?: string;
  
  // Status and metadata
  is_active: boolean;
  created_at: string;
  updated_at: string;
  last_executed_at?: string;
  last_execution_status?: 'completed' | 'failed' | 'cancelled';
  
  // Related data (populated in responses)
  source_endpoint?: {
    id: string;
    name: string;
    endpoint_type: string;
  };
  destination_endpoint?: {
    id: string;
    name: string;
    endpoint_type: string;
  };
}

export interface CreateSessionRequest {
  name: string;
  description?: string;
  source_endpoint_id: string;
  destination_endpoint_id: string;
  source_path: string;
  destination_path: string;
  sync_direction: SyncDirection;
  delete_extra_files?: boolean;
  preserve_timestamps?: boolean;
  follow_symlinks?: boolean;
  include_patterns?: string[];
  exclude_patterns?: string[];
  max_file_size?: number;
  min_file_size?: number;
  parallel_transfers?: boolean;
  max_parallel_transfers?: number;
  transfer_chunk_size?: number;
  schedule_enabled?: boolean;
  schedule_cron?: string;
  schedule_timezone?: string;
  is_active?: boolean;
}

export interface UpdateSessionRequest extends Partial<CreateSessionRequest> {
  id: string;
}

export interface SessionStatistics {
  session_id: string;
  total_executions: number;
  successful_executions: number;
  failed_executions: number;
  cancelled_executions: number;
  total_files_transferred: number;
  total_bytes_transferred: number;
  average_execution_duration?: number;
  last_execution_at?: string;
  next_scheduled_run?: string;
}

// Multi-Session Types
export interface MultiSessionConfig {
  id: string;
  name: string;
  description?: string;
  session_ids: string[];
  execution_mode: 'parallel' | 'sequential';
  continue_on_error: boolean;
  schedule_enabled: boolean;
  schedule_cron?: string;
  schedule_timezone?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  
  // Related data
  sessions?: SyncSession[];
}

export interface CreateMultiSessionRequest {
  name: string;
  description?: string;
  session_ids: string[];
  execution_mode: 'parallel' | 'sequential';
  continue_on_error?: boolean;
  schedule_enabled?: boolean;
  schedule_cron?: string;
  schedule_timezone?: string;
  is_active?: boolean;
}

// Schedule Types
export interface ScheduleUpdate {
  schedule_enabled: boolean;
  schedule_cron?: string;
  schedule_timezone?: string;
}

export interface ScheduledSession {
  session_id: string;
  session_name: string;
  schedule_cron: string;
  schedule_timezone: string;
  next_run_at: string;
  last_run_at?: string;
  last_run_status?: 'completed' | 'failed' | 'cancelled';
  is_active: boolean;
}

// Sync Analysis Types
export interface SyncAnalysisRequest {
  session_id: string;
  dry_run?: boolean;
}

export interface SyncOperation {
  operation: 'download' | 'upload' | 'delete' | 'skip';
  source_path: string;
  destination_path: string;
  file_size?: number;
  reason: string;
  estimated_duration?: number;
}

export interface SyncAnalysis {
  session_id: string;
  operations: SyncOperation[];
  summary: {
    total_operations: number;
    downloads: number;
    uploads: number;
    deletes: number;
    skipped: number;
    total_size: number;
    estimated_duration: number;
  };
  analyzed_at: string;
}
