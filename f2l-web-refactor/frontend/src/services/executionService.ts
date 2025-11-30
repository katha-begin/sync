import { api } from './api';
import {
  SyncExecution,
  ExecutionProgress,
  ExecutionStatistics,
  ExecutionLog,
  ExecutionFilters,
  ExecutionSummary,
  CancelExecutionRequest,
  BatchExecutionRequest,
  BatchExecutionResponse,
  PaginatedResponse,
  QueryParams,
} from '@/types';

class ExecutionService {
  private readonly basePath = '/executions';

  // CRUD Operations
  async getExecutions(params?: QueryParams & { filters?: ExecutionFilters }): Promise<PaginatedResponse<SyncExecution>> {
    return api.get<PaginatedResponse<SyncExecution>>(this.basePath, params);
  }

  async getExecution(id: string): Promise<SyncExecution> {
    return api.get<SyncExecution>(`${this.basePath}/${id}`);
  }

  async deleteExecution(id: string): Promise<void> {
    return api.delete<void>(`${this.basePath}/${id}`);
  }

  // Execution Control
  async cancelExecution(data: CancelExecutionRequest): Promise<void> {
    return api.post<void>(`${this.basePath}/${data.execution_id}/cancel`, {
      reason: data.reason,
    });
  }

  async pauseExecution(id: string): Promise<void> {
    return api.post<void>(`${this.basePath}/${id}/pause`);
  }

  async resumeExecution(id: string): Promise<void> {
    return api.post<void>(`${this.basePath}/${id}/resume`);
  }

  // Progress Monitoring
  async getExecutionProgress(id: string): Promise<ExecutionProgress> {
    return api.get<ExecutionProgress>(`${this.basePath}/${id}/progress`);
  }

  async getExecutionStatistics(id: string): Promise<ExecutionStatistics> {
    return api.get<ExecutionStatistics>(`${this.basePath}/${id}/statistics`);
  }

  async getExecutionSummary(filters?: ExecutionFilters): Promise<ExecutionSummary> {
    return api.get<ExecutionSummary>(`${this.basePath}/summary`, {
      filters,
    });
  }

  // Execution Logs
  async getExecutionLogs(id: string, params?: QueryParams): Promise<PaginatedResponse<ExecutionLog>> {
    return api.get<PaginatedResponse<ExecutionLog>>(`${this.basePath}/${id}/logs`, params);
  }

  async downloadExecutionLogs(id: string, format: 'txt' | 'json' | 'csv' = 'txt'): Promise<void> {
    return api.downloadFile(
      `${this.basePath}/${id}/logs/download`,
      `execution-${id}-logs.${format}`,
      {
        params: { format },
      }
    );
  }

  // Batch Operations
  async startBatchExecution(data: BatchExecutionRequest): Promise<BatchExecutionResponse> {
    return api.post<BatchExecutionResponse>(`${this.basePath}/batch`, data);
  }

  async getBatchExecutionStatus(batchId: string): Promise<{
    batch_id: string;
    status: 'running' | 'completed' | 'failed' | 'cancelled';
    executions: Array<{
      execution_id: string;
      session_id: string;
      status: string;
      progress_percent: number;
    }>;
  }> {
    return api.get(`${this.basePath}/batch/${batchId}/status`);
  }

  async cancelBatchExecution(batchId: string, reason?: string): Promise<void> {
    return api.post<void>(`${this.basePath}/batch/${batchId}/cancel`, { reason });
  }

  // Bulk Operations
  async bulkCancel(ids: string[], reason?: string): Promise<void> {
    return api.post<void>(`${this.basePath}/bulk-cancel`, {
      execution_ids: ids,
      reason,
    });
  }

  async bulkDelete(ids: string[]): Promise<void> {
    return api.delete<void>(`${this.basePath}/bulk-delete`, {
      data: { execution_ids: ids },
    });
  }

  async bulkRetry(ids: string[]): Promise<BatchExecutionResponse> {
    return api.post<BatchExecutionResponse>(`${this.basePath}/bulk-retry`, {
      execution_ids: ids,
    });
  }

  // Search and Filtering
  async searchExecutions(query: string, filters?: ExecutionFilters): Promise<SyncExecution[]> {
    return api.get<SyncExecution[]>(`${this.basePath}/search`, {
      search: query,
      filters,
    });
  }

  async getExecutionsBySession(sessionId: string, params?: QueryParams): Promise<PaginatedResponse<SyncExecution>> {
    return api.get<PaginatedResponse<SyncExecution>>(this.basePath, {
      ...params,
      filters: {
        ...params?.filters,
        session_id: sessionId,
      },
    });
  }

  async getRunningExecutions(): Promise<SyncExecution[]> {
    return api.get<SyncExecution[]>(this.basePath, {
      filters: { status: ['running', 'pending'] },
    });
  }

  async getRecentExecutions(limit: number = 10): Promise<SyncExecution[]> {
    return api.get<SyncExecution[]>(this.basePath, {
      size: limit,
      sort: 'created_at',
      order: 'desc',
    });
  }

  async getFailedExecutions(params?: QueryParams): Promise<PaginatedResponse<SyncExecution>> {
    return api.get<PaginatedResponse<SyncExecution>>(this.basePath, {
      ...params,
      filters: {
        ...params?.filters,
        status: ['failed'],
      },
    });
  }

  // Analytics and Reporting
  async getExecutionTrends(period: 'day' | 'week' | 'month' = 'week'): Promise<Array<{
    date: string;
    total: number;
    successful: number;
    failed: number;
    cancelled: number;
  }>> {
    return api.get(`${this.basePath}/trends`, {
      filters: { period },
    });
  }

  async getExecutionMetrics(sessionId?: string): Promise<{
    total_executions: number;
    success_rate: number;
    average_duration: number;
    total_files_transferred: number;
    total_bytes_transferred: number;
    peak_transfer_rate: number;
  }> {
    return api.get(`${this.basePath}/metrics`, {
      filters: sessionId ? { session_id: sessionId } : undefined,
    });
  }

  async getPerformanceStats(executionId: string): Promise<{
    transfer_rate_history: Array<{ timestamp: string; rate: number }>;
    file_size_distribution: Array<{ size_range: string; count: number }>;
    operation_breakdown: Array<{ operation: string; count: number; total_time: number }>;
  }> {
    return api.get(`${this.basePath}/${executionId}/performance`);
  }

  // Cleanup and Maintenance
  async cleanupOldExecutions(olderThanDays: number): Promise<{ deleted_count: number }> {
    return api.post<{ deleted_count: number }>(`${this.basePath}/cleanup`, {
      older_than_days: olderThanDays,
    });
  }

  async archiveExecution(id: string): Promise<void> {
    return api.post<void>(`${this.basePath}/${id}/archive`);
  }

  async getArchivedExecutions(params?: QueryParams): Promise<PaginatedResponse<SyncExecution>> {
    return api.get<PaginatedResponse<SyncExecution>>(`${this.basePath}/archived`, params);
  }

  // Export and Reporting
  async exportExecutions(filters?: ExecutionFilters, format: 'csv' | 'json' | 'xlsx' = 'csv'): Promise<void> {
    return api.downloadFile(
      `${this.basePath}/export`,
      `executions.${format}`,
      {
        params: { ...filters, format },
      }
    );
  }

  async generateExecutionReport(executionId: string, format: 'pdf' | 'html' = 'pdf'): Promise<void> {
    return api.downloadFile(
      `${this.basePath}/${executionId}/report`,
      `execution-${executionId}-report.${format}`,
      {
        params: { format },
      }
    );
  }

  // Real-time Updates (to be used with WebSocket)
  async subscribeToExecutionUpdates(executionId: string): Promise<void> {
    // This would typically be handled by the WebSocket service
    // but we include it here for completeness
    return api.post<void>(`${this.basePath}/${executionId}/subscribe`);
  }

  async unsubscribeFromExecutionUpdates(executionId: string): Promise<void> {
    return api.post<void>(`${this.basePath}/${executionId}/unsubscribe`);
  }
}

export const executionService = new ExecutionService();
