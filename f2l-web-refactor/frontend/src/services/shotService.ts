import { api } from './api';
import {
  ShotStructure,
  ScanResult,
  ShotComparison,
  CompareRequest,
  CreateTaskRequest,
  DownloadTask,
  TaskDetails,
  TaskSummary,
  TaskStatus,
} from '@/types/shot';

class ShotService {
  private readonly basePath = '/shots';

  // Structure Management
  async getStructure(
    endpointId: string,
    episodes?: string[],
    sequences?: string[]
  ): Promise<ShotStructure> {
    const params: Record<string, any> = {};
    if (episodes && episodes.length > 0) {
      params.episodes = episodes;
    }
    if (sequences && sequences.length > 0) {
      params.sequences = sequences;
    }
    return api.get<ShotStructure>(`${this.basePath}/structure/${endpointId}`, params);
  }

  async scanStructure(
    endpointId: string,
    forceRefresh: boolean = false
  ): Promise<ScanResult> {
    return api.post<ScanResult>(
      `${this.basePath}/structure/${endpointId}/scan`,
      {},
      { params: { force_refresh: forceRefresh } }
    );
  }

  // Comparison
  async compareShots(request: CompareRequest): Promise<ShotComparison[]> {
    return api.post<ShotComparison[]>(`${this.basePath}/compare`, request);
  }

  // Task Management
  async createTask(request: CreateTaskRequest): Promise<any> {
    return api.post<any>(`${this.basePath}/tasks`, request);
  }

  async listTasks(
    endpointId?: string,
    status?: TaskStatus,
    limit: number = 50,
    offset: number = 0
  ): Promise<TaskSummary[]> {
    const params: Record<string, any> = { limit, offset };
    if (endpointId) {
      params.endpoint_id = endpointId;
    }
    if (status) {
      params.status_filter = status;
    }
    return api.get<TaskSummary[]>(`${this.basePath}/tasks`, params);
  }

  async getTaskDetails(taskId: string): Promise<TaskDetails> {
    return api.get<TaskDetails>(`${this.basePath}/tasks/${taskId}`);
  }

  async getTaskStatus(taskId: string): Promise<DownloadTask> {
    return api.get<DownloadTask>(`${this.basePath}/tasks/${taskId}/status`);
  }

  async executeTask(taskId: string): Promise<any> {
    return api.post<any>(`${this.basePath}/tasks/${taskId}/execute`, {});
  }

  async cancelTask(taskId: string): Promise<any> {
    return api.post<any>(`${this.basePath}/tasks/${taskId}/cancel`, {});
  }

  async deleteTask(taskId: string): Promise<any> {
    return api.delete<any>(`${this.basePath}/tasks/${taskId}`);
  }
}

export const shotService = new ShotService();
export default shotService;

