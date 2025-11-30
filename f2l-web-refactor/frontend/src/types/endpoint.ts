// Endpoint Types
export type EndpointType = 'ftp' | 'sftp' | 's3' | 'local';

export interface Endpoint {
  id: string;
  name: string;
  endpoint_type: EndpointType;
  host?: string;
  port?: number;
  username?: string;
  password?: string; // Only for creation/update, not returned in responses
  base_path?: string;
  
  // S3 specific
  bucket_name?: string;
  region?: string;
  access_key?: string;
  secret_key?: string; // Only for creation/update
  
  // Connection settings
  timeout?: number;
  max_connections?: number;
  passive_mode?: boolean; // FTP specific
  
  // Status and metadata
  is_active: boolean;
  created_at: string;
  updated_at: string;
  last_tested_at?: string;
  last_test_status?: 'success' | 'failed';
  last_test_message?: string;
}

export interface CreateEndpointRequest {
  name: string;
  endpoint_type: EndpointType;
  host?: string;
  port?: number;
  username?: string;
  password?: string;
  base_path?: string;
  
  // S3 specific
  bucket_name?: string;
  region?: string;
  access_key?: string;
  secret_key?: string;
  
  // Connection settings
  timeout?: number;
  max_connections?: number;
  passive_mode?: boolean;
  
  is_active?: boolean;
}

export interface UpdateEndpointRequest extends Partial<CreateEndpointRequest> {
  id: string;
}

export interface EndpointConnectionTest {
  status: 'success' | 'failed';
  message: string;
  duration_ms?: number;
  tested_at: string;
}

export interface EndpointStatistics {
  endpoint_id: string;
  total_sessions: number;
  total_executions: number;
  successful_executions: number;
  failed_executions: number;
  total_files_transferred: number;
  total_bytes_transferred: number;
  last_execution_at?: string;
  average_execution_duration?: number;
}

// Directory Browsing Types
export interface DirectoryItem {
  name: string;
  path: string;
  size?: number;
  modified_time?: string;
  is_directory: boolean;
  permissions?: string;
  owner?: string;
  group?: string;
}

export interface DirectoryListing {
  path: string;
  items: DirectoryItem[];
  total_items: number;
  total_size?: number;
  parent_path?: string;
}

export interface BrowseDirectoryParams {
  path: string;
  max_depth?: number;
  include_hidden?: boolean;
  file_pattern?: string;
  sort_by?: 'name' | 'size' | 'modified_time';
  sort_order?: 'asc' | 'desc';
}

export interface FileMetadata {
  path: string;
  name: string;
  size: number;
  modified_time: string;
  checksum?: string;
  mime_type?: string;
  is_directory: boolean;
}

export interface CompareFilesRequest {
  source_endpoint_id: string;
  destination_endpoint_id: string;
  source_path: string;
  destination_path: string;
}

export interface FileComparison {
  source_file?: FileMetadata;
  destination_file?: FileMetadata;
  status: 'identical' | 'different' | 'source_only' | 'destination_only' | 'error';
  differences?: string[];
  recommendation?: 'sync_to_destination' | 'sync_to_source' | 'no_action' | 'conflict';
}
