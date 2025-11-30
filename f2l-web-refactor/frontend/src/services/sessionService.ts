import axios from 'axios';

// Use relative URL - nginx will proxy to backend
const API_URL = '';

export interface SyncSession {
  id: string;
  name: string;
  source_endpoint_id: string;
  destination_endpoint_id: string;
  sync_direction: string;
  is_active: boolean;
  notes?: string;

  // Sync configuration
  source_path: string;
  destination_path: string;
  // Phase 5: folder_filter, file_filter, exclude_patterns will be added

  // Sync options
  force_overwrite: boolean;
  // Phase 5: delete_extra_files, preserve_timestamps, verify_checksums, max_parallel_transfers will be added

  // Scheduling
  schedule_enabled: boolean;
  schedule_interval?: number;
  schedule_unit?: string;
  auto_start_enabled: boolean;

  // Status
  is_running: boolean;
  last_run_at?: string;
  last_run_status?: string;

  // Timestamps
  created_at: string;
  updated_at: string;
}

export interface CreateSessionRequest {
  name: string;
  source_endpoint_id: string;
  destination_endpoint_id: string;
  sync_direction: string;
  notes?: string;
  source_path?: string;
  destination_path?: string;
  // Phase 5: folder_filter, file_filter, exclude_patterns will be added
  force_overwrite?: boolean;
  // Phase 5: delete_extra_files, preserve_timestamps, verify_checksums, max_parallel_transfers will be added
  schedule_enabled?: boolean;
  schedule_interval?: number;
  schedule_unit?: string;
  auto_start_enabled?: boolean;
}

export interface UpdateSessionRequest extends Partial<CreateSessionRequest> {
  is_active?: boolean;
}

class SessionService {
  private readonly basePath = `${API_URL}/api/v1/sessions/`;

  // CRUD Operations
  async getSessions(): Promise<SyncSession[]> {
    const response = await axios.get<SyncSession[]>(this.basePath, {
      params: { active_only: false }  // Get all sessions, not just active ones
    });
    return response.data;
  }

  async getSession(id: string): Promise<SyncSession> {
    const response = await axios.get<SyncSession>(`${this.basePath}${id}`);
    return response.data;
  }

  async createSession(data: CreateSessionRequest): Promise<SyncSession> {
    const response = await axios.post<SyncSession>(this.basePath, data);
    return response.data;
  }

  async updateSession(id: string, data: UpdateSessionRequest): Promise<SyncSession> {
    const response = await axios.put<SyncSession>(`${this.basePath}${id}`, data);
    return response.data;
  }

  async deleteSession(id: string): Promise<void> {
    await axios.delete(`${this.basePath}${id}`);
  }

  // Session Actions
  async startSession(id: string, dryRun: boolean = false, forceOverwrite: boolean = false): Promise<any> {
    const response = await axios.post(`${this.basePath}${id}/start`, null, {
      params: { dry_run: dryRun, force_overwrite: forceOverwrite }
    });
    return response.data;
  }

  async stopSession(id: string): Promise<any> {
    const response = await axios.post(`${this.basePath}${id}/stop`);
    return response.data;
  }

}

export const sessionService = new SessionService();
export default sessionService;
