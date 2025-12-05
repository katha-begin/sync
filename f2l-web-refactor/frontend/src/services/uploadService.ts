import { api } from './api';
import {
  LocalStructure,
  CreateUploadTaskRequest,
  UploadTask,
  UploadTaskDetails,
  UploadTaskStatus,
  UploadHistoryResponse,
} from '@/types/upload';

class UploadService {
  private readonly basePath = '/uploads';

  // Structure Management - Scan local endpoint for shot files
  async getLocalStructure(
    endpointId: string,
    episode?: string,
    sequence?: string,
    department?: string
  ): Promise<LocalStructure> {
    const params: Record<string, any> = {};
    if (episode) params.episode = episode;
    if (sequence) params.sequence = sequence;
    if (department) params.department = department;

    return api.get<LocalStructure>(`${this.basePath}/structure/${endpointId}`, params);
  }

  // Trigger a scan of local structure
  async scanLocalStructure(endpointId: string, forceRefresh: boolean = false): Promise<any> {
    return api.post(`${this.basePath}/structure/${endpointId}/scan`, null, {
      params: { force_refresh: forceRefresh }
    });
  }

  // Task Management
  async createTask(request: CreateUploadTaskRequest): Promise<any> {
    return api.post<any>(`${this.basePath}/tasks`, request);
  }

  async listTasks(
    status?: UploadTaskStatus,
    limit: number = 50,
    offset: number = 0
  ): Promise<{ tasks: UploadTask[]; total: number; limit: number; offset: number }> {
    const params: Record<string, any> = { limit, offset };
    if (status) {
      params.status = status;
    }
    return api.get(`${this.basePath}/tasks`, params);
  }

  async getTaskDetails(taskId: string): Promise<UploadTaskDetails> {
    return api.get<UploadTaskDetails>(`${this.basePath}/tasks/${taskId}`);
  }

  async executeTask(taskId: string): Promise<any> {
    return api.post(`${this.basePath}/tasks/${taskId}/execute`);
  }

  async cancelTask(taskId: string): Promise<any> {
    return api.post(`${this.basePath}/tasks/${taskId}/cancel`);
  }

  async retrySkippedItems(taskId: string, overwrite: boolean = true): Promise<any> {
    return api.post(`${this.basePath}/tasks/${taskId}/retry`, null, {
      params: { overwrite }
    });
  }

  async deleteTask(taskId: string): Promise<any> {
    return api.delete(`${this.basePath}/tasks/${taskId}`);
  }

  // History
  async getHistory(
    options: {
      episode?: string;
      sequence?: string;
      shot?: string;
      status?: string;
      startDate?: string;
      endDate?: string;
      limit?: number;
      offset?: number;
    } = {}
  ): Promise<UploadHistoryResponse> {
    const params: Record<string, any> = {
      limit: options.limit || 100,
      offset: options.offset || 0,
    };
    
    if (options.episode) params.episode = options.episode;
    if (options.sequence) params.sequence = options.sequence;
    if (options.shot) params.shot = options.shot;
    if (options.status) params.status = options.status;
    if (options.startDate) params.start_date = options.startDate;
    if (options.endDate) params.end_date = options.endDate;
    
    return api.get<UploadHistoryResponse>(`${this.basePath}/history`, params);
  }
}

export const uploadService = new UploadService();
export default uploadService;

