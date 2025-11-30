import { api } from './api';
import {
  Endpoint,
  CreateEndpointRequest,
  UpdateEndpointRequest,
  EndpointConnectionTest,
  EndpointStatistics,
  DirectoryListing,
  BrowseDirectoryParams,
  FileComparison,
  CompareFilesRequest,
  PaginatedResponse,
  QueryParams,
} from '@/types';

class EndpointService {
  private readonly basePath = '/endpoints';

  // CRUD Operations
  async getEndpoints(params?: QueryParams): Promise<PaginatedResponse<Endpoint>> {
    return api.get<PaginatedResponse<Endpoint>>(this.basePath, params);
  }

  async getEndpoint(id: string): Promise<Endpoint> {
    return api.get<Endpoint>(`${this.basePath}/${id}`);
  }

  async createEndpoint(data: CreateEndpointRequest): Promise<Endpoint> {
    return api.post<Endpoint>(this.basePath, data);
  }

  async updateEndpoint(data: UpdateEndpointRequest): Promise<Endpoint> {
    const { id, ...updateData } = data;
    return api.put<Endpoint>(`${this.basePath}/${id}`, updateData);
  }

  async deleteEndpoint(id: string): Promise<void> {
    return api.delete<void>(`${this.basePath}/${id}`);
  }

  // Connection Testing
  async testConnection(id: string): Promise<EndpointConnectionTest> {
    return api.post<EndpointConnectionTest>(`${this.basePath}/${id}/test`);
  }

  async testConnectionWithConfig(config: CreateEndpointRequest): Promise<EndpointConnectionTest> {
    return api.post<EndpointConnectionTest>(`${this.basePath}/test`, config);
  }

  // Statistics
  async getEndpointStatistics(id: string): Promise<EndpointStatistics> {
    return api.get<EndpointStatistics>(`${this.basePath}/${id}/statistics`);
  }

  async getAllEndpointStatistics(): Promise<EndpointStatistics[]> {
    return api.get<EndpointStatistics[]>(`${this.basePath}/statistics`);
  }

  // Directory Browsing
  async browseDirectory(id: string, params: BrowseDirectoryParams): Promise<DirectoryListing> {
    return api.get<DirectoryListing>(`${this.basePath}/${id}/browse`, {
      filters: {
        path: params.path,
        max_depth: params.max_depth,
        include_hidden: params.include_hidden,
        file_pattern: params.file_pattern,
        sort_by: params.sort_by,
        sort_order: params.sort_order,
      },
    });
  }

  async getDirectorySize(id: string, path: string): Promise<{ total_size: number; file_count: number }> {
    return api.get<{ total_size: number; file_count: number }>(
      `${this.basePath}/${id}/directory-size`,
      {
        filters: { path },
      }
    );
  }

  // File Operations
  async getFileMetadata(id: string, path: string): Promise<any> {
    return api.get(`${this.basePath}/${id}/file-metadata`, {
      filters: { path },
    });
  }

  async compareFiles(data: CompareFilesRequest): Promise<FileComparison> {
    return api.post<FileComparison>(`${this.basePath}/compare-files`, data);
  }

  async downloadFile(id: string, path: string, filename?: string): Promise<void> {
    return api.downloadFile(
      `${this.basePath}/${id}/download`,
      filename,
      {
        params: { path },
      }
    );
  }

  async uploadFile(id: string, path: string, file: File, onProgress?: (progress: number) => void): Promise<any> {
    return api.uploadFile(
      `${this.basePath}/${id}/upload?path=${encodeURIComponent(path)}`,
      file,
      onProgress
    );
  }

  // Bulk Operations
  async bulkTestConnections(ids: string[]): Promise<Record<string, EndpointConnectionTest>> {
    return api.post<Record<string, EndpointConnectionTest>>(`${this.basePath}/bulk-test`, { ids });
  }

  async bulkUpdateStatus(ids: string[], isActive: boolean): Promise<void> {
    return api.patch<void>(`${this.basePath}/bulk-update-status`, {
      ids,
      is_active: isActive,
    });
  }

  async bulkDelete(ids: string[]): Promise<void> {
    return api.delete<void>(`${this.basePath}/bulk-delete`, {
      data: { ids },
    });
  }

  // Search and Filtering
  async searchEndpoints(query: string, filters?: Record<string, any>): Promise<Endpoint[]> {
    return api.get<Endpoint[]>(`${this.basePath}/search`, {
      search: query,
      filters,
    });
  }

  async getEndpointsByType(type: string): Promise<Endpoint[]> {
    return api.get<Endpoint[]>(this.basePath, {
      filters: { endpoint_type: type },
    });
  }

  async getActiveEndpoints(): Promise<Endpoint[]> {
    return api.get<Endpoint[]>(this.basePath, {
      filters: { is_active: true },
    });
  }

  // Health and Monitoring
  async getEndpointHealth(id: string): Promise<any> {
    return api.get(`${this.basePath}/${id}/health`);
  }

  async getAllEndpointHealth(): Promise<Record<string, any>> {
    return api.get(`${this.basePath}/health`);
  }

  // Configuration Templates
  async getEndpointTemplate(type: string): Promise<Partial<CreateEndpointRequest>> {
    return api.get<Partial<CreateEndpointRequest>>(`${this.basePath}/templates/${type}`);
  }

  async validateEndpointConfig(config: CreateEndpointRequest): Promise<{ valid: boolean; errors?: string[] }> {
    return api.post<{ valid: boolean; errors?: string[] }>(`${this.basePath}/validate`, config);
  }

  // Import/Export
  async exportEndpoints(ids?: string[]): Promise<void> {
    const params = ids ? { ids: ids.join(',') } : {};
    return api.downloadFile(`${this.basePath}/export`, 'endpoints.json', { params });
  }

  async importEndpoints(file: File, onProgress?: (progress: number) => void): Promise<{ imported: number; errors: string[] }> {
    return api.uploadFile<{ imported: number; errors: string[] }>(
      `${this.basePath}/import`,
      file,
      onProgress
    );
  }
}

export const endpointService = new EndpointService();
