import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Chip,
  IconButton,
  Tooltip,
  CircularProgress,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  LinearProgress,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  Visibility as ViewIcon,
  Cancel as CancelIcon,
} from '@mui/icons-material';
import axios from 'axios';
import { formatDate } from '@/utils/formatters';

const API_URL = '';

interface Execution {
  id: string;
  session_id: string;
  status: string;
  progress_percentage: number;
  files_synced: number;
  total_files: number;
  files_failed: number;
  files_skipped: number;
  bytes_transferred: number;
  queued_at: string;
  started_at?: string;
  completed_at?: string;
  duration_seconds?: number;
  current_file?: string;
  current_operation?: string;
  error_message?: string;
  is_dry_run: boolean;
  force_overwrite: boolean;
}

interface ExecutionHistoryProps {
  sessionId: string;
}

const ExecutionHistory: React.FC<ExecutionHistoryProps> = ({ sessionId }) => {
  const [executions, setExecutions] = useState<Execution[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedExecution, setSelectedExecution] = useState<Execution | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);

  const loadExecutions = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.get<Execution[]>(`${API_URL}/api/v1/executions/`, {
        params: { session_id: sessionId, limit: 50 }
      });
      setExecutions(response.data);
    } catch (err: any) {
      console.error('Failed to load executions:', err);
      setError(err.response?.data?.detail || 'Failed to load executions');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadExecutions();

    // Set up polling for real-time updates (every 5 seconds)
    const intervalId = setInterval(() => {
      loadExecutions();
    }, 5000);

    // Cleanup interval on unmount
    return () => clearInterval(intervalId);
  }, [sessionId]); // Removed 'executions' from dependency array to prevent infinite loop

  const handleViewDetails = (execution: Execution) => {
    setSelectedExecution(execution);
    setDetailsOpen(true);
  };

  const handleCancelExecution = async (execution: Execution) => {
    try {
      await axios.post(`${API_URL}/api/v1/executions/${execution.id}/cancel`);
      alert('Execution cancelled successfully!');
      await loadExecutions();
    } catch (err: any) {
      console.error('Cancel failed:', err);
      alert(`Failed to cancel execution!\n${err.response?.data?.detail || err.message}`);
    }
  };

  const getStatusColor = (status: string): 'default' | 'primary' | 'success' | 'error' | 'warning' => {
    switch (status.toLowerCase()) {
      case 'completed':
        return 'success';
      case 'running':
        return 'primary';
      case 'failed':
        return 'error';
      case 'cancelled':
        return 'warning';
      case 'queued':
        return 'default';
      default:
        return 'default';
    }
  };

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
  };

  const formatDuration = (seconds?: number): string => {
    if (!seconds) return 'N/A';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
      return `${hours}h ${minutes}m ${secs}s`;
    } else if (minutes > 0) {
      return `${minutes}m ${secs}s`;
    } else {
      return `${secs}s`;
    }
  };

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h6">Execution History</Typography>
        <IconButton onClick={loadExecutions} disabled={loading} size="small">
          <RefreshIcon />
        </IconButton>
      </Box>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Loading */}
      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
          <CircularProgress />
        </Box>
      )}

      {/* Executions Table */}
      {!loading && executions.length > 0 && (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Status</TableCell>
                <TableCell>Started</TableCell>
                <TableCell>Duration</TableCell>
                <TableCell align="right">Files</TableCell>
                <TableCell align="right">Transferred</TableCell>
                <TableCell>Options</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {executions.map((execution) => (
                <TableRow key={execution.id} hover>
                  <TableCell>
                    <Box>
                      <Chip
                        label={execution.status}
                        color={getStatusColor(execution.status)}
                        size="small"
                      />
                      {execution.status === 'RUNNING' && (
                        <Box sx={{ mt: 0.5 }}>
                          <LinearProgress
                            variant="determinate"
                            value={execution.progress_percentage}
                            sx={{ height: 4, borderRadius: 2 }}
                          />
                          <Typography variant="caption" color="text.secondary">
                            {execution.progress_percentage.toFixed(1)}%
                          </Typography>
                        </Box>
                      )}
                      {execution.current_file && execution.status === 'RUNNING' && (
                        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                          {execution.current_file}
                        </Typography>
                      )}
                    </Box>
                  </TableCell>
                  <TableCell>
                    {execution.started_at ? formatDate(execution.started_at) : 'Not started'}
                  </TableCell>
                  <TableCell>{formatDuration(execution.duration_seconds)}</TableCell>
                  <TableCell align="right">
                    <Box>
                      <Typography variant="body2">
                        {execution.files_synced} / {execution.total_files}
                      </Typography>
                      {execution.files_failed > 0 && (
                        <Typography variant="caption" color="error">
                          {execution.files_failed} failed
                        </Typography>
                      )}
                    </Box>
                  </TableCell>
                  <TableCell align="right">{formatBytes(execution.bytes_transferred)}</TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', gap: 0.5 }}>
                      {execution.is_dry_run && (
                        <Chip label="Dry Run" size="small" variant="outlined" />
                      )}
                      {execution.force_overwrite && (
                        <Chip label="Force" size="small" color="warning" variant="outlined" />
                      )}
                    </Box>
                  </TableCell>
                  <TableCell align="right">
                    <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'flex-end' }}>
                      <Tooltip title="View Details">
                        <IconButton
                          size="small"
                          onClick={() => handleViewDetails(execution)}
                        >
                          <ViewIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      {(execution.status === 'RUNNING' || execution.status === 'QUEUED') && (
                        <Tooltip title="Cancel">
                          <IconButton
                            size="small"
                            color="error"
                            onClick={() => handleCancelExecution(execution)}
                          >
                            <CancelIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      )}
                    </Box>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* No Executions */}
      {!loading && executions.length === 0 && (
        <Box sx={{ textAlign: 'center', py: 4 }}>
          <Typography variant="body2" color="text.secondary">
            No executions found for this session
          </Typography>
        </Box>
      )}

      {/* Execution Details Dialog */}
      <Dialog open={detailsOpen} onClose={() => setDetailsOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>Execution Details</DialogTitle>
        <DialogContent>
          {selectedExecution && (
            <Box sx={{ mt: 1 }}>
              <Table size="small">
                <TableBody>
                  <TableRow>
                    <TableCell><strong>Status</strong></TableCell>
                    <TableCell>
                      <Chip
                        label={selectedExecution.status}
                        color={getStatusColor(selectedExecution.status)}
                        size="small"
                      />
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell><strong>Queued At</strong></TableCell>
                    <TableCell>{formatDate(selectedExecution.queued_at)}</TableCell>
                  </TableRow>
                  {selectedExecution.started_at && (
                    <TableRow>
                      <TableCell><strong>Started At</strong></TableCell>
                      <TableCell>{formatDate(selectedExecution.started_at)}</TableCell>
                    </TableRow>
                  )}
                  {selectedExecution.completed_at && (
                    <TableRow>
                      <TableCell><strong>Completed At</strong></TableCell>
                      <TableCell>{formatDate(selectedExecution.completed_at)}</TableCell>
                    </TableRow>
                  )}
                  <TableRow>
                    <TableCell><strong>Duration</strong></TableCell>
                    <TableCell>{formatDuration(selectedExecution.duration_seconds)}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell><strong>Progress</strong></TableCell>
                    <TableCell>{selectedExecution.progress_percentage.toFixed(1)}%</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell><strong>Files Synced</strong></TableCell>
                    <TableCell>{selectedExecution.files_synced} / {selectedExecution.total_files}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell><strong>Files Failed</strong></TableCell>
                    <TableCell>{selectedExecution.files_failed}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell><strong>Files Skipped</strong></TableCell>
                    <TableCell>{selectedExecution.files_skipped}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell><strong>Bytes Transferred</strong></TableCell>
                    <TableCell>{formatBytes(selectedExecution.bytes_transferred)}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell><strong>Dry Run</strong></TableCell>
                    <TableCell>{selectedExecution.is_dry_run ? 'Yes' : 'No'}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell><strong>Force Overwrite</strong></TableCell>
                    <TableCell>{selectedExecution.force_overwrite ? 'Yes' : 'No'}</TableCell>
                  </TableRow>
                  {selectedExecution.current_file && (
                    <TableRow>
                      <TableCell><strong>Current File</strong></TableCell>
                      <TableCell>{selectedExecution.current_file}</TableCell>
                    </TableRow>
                  )}
                  {selectedExecution.error_message && (
                    <TableRow>
                      <TableCell><strong>Error</strong></TableCell>
                      <TableCell>
                        <Typography variant="body2" color="error">
                          {selectedExecution.error_message}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDetailsOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default ExecutionHistory;

