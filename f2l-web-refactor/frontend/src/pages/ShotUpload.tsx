import React, { useState } from 'react';
import {
  Box,
  Typography,
  Button,
  CircularProgress,
  Alert,
  IconButton,
  Tabs,
  Tab,
  Chip,
  Tooltip,
} from '@mui/material';
import {
  Add as AddIcon,
  Refresh as RefreshIcon,
  CloudUpload as UploadIcon,
  History as HistoryIcon,
  PlayArrow as PlayIcon,
  Delete as DeleteIcon,
  Cancel as CancelIcon,
  Replay as RetryIcon,
  Visibility as ViewIcon,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { uploadService } from '@/services/uploadService';
import CreateUploadTaskDialog from '@/components/uploads/CreateUploadTaskDialog';
import UploadTaskDetailDialog from '@/components/uploads/UploadTaskDetailDialog';
import DataTable from '@/components/common/DataTable';
import { TableColumn } from '@/types';
import { formatDate, formatBytes } from '@/utils/formatters';
import {
  UploadTask,
  UploadHistoryItem,
  UPLOAD_TASK_STATUS_LABELS,
  UPLOAD_TASK_STATUS_COLORS,
} from '@/types/upload';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div role="tabpanel" hidden={value !== index} {...other}>
      {value === index && <Box sx={{ pt: 2 }}>{children}</Box>}
    </div>
  );
}

const ShotUpload: React.FC = () => {
  const [tabValue, setTabValue] = useState(0);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [detailTaskId, setDetailTaskId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  // Fetch upload tasks
  const { data: tasksData, isLoading: tasksLoading, refetch: refetchTasks } = useQuery({
    queryKey: ['upload-tasks'],
    queryFn: () => uploadService.listTasks(),
  });

  // Fetch upload history
  const { data: historyData, isLoading: historyLoading, refetch: refetchHistory } = useQuery({
    queryKey: ['upload-history'],
    queryFn: () => uploadService.getHistory({ limit: 100 }),
  });

  // Mutations
  const executeMutation = useMutation({
    mutationFn: (taskId: string) => uploadService.executeTask(taskId),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['upload-tasks'] }); },
    onError: (err: any) => setError(err.message || 'Failed to execute task'),
  });

  const cancelMutation = useMutation({
    mutationFn: (taskId: string) => uploadService.cancelTask(taskId),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['upload-tasks'] }); },
    onError: (err: any) => setError(err.message || 'Failed to cancel task'),
  });

  const deleteMutation = useMutation({
    mutationFn: (taskId: string) => uploadService.deleteTask(taskId),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['upload-tasks'] }); },
    onError: (err: any) => setError(err.message || 'Failed to delete task'),
  });

  const retryMutation = useMutation({
    mutationFn: (taskId: string) => uploadService.retrySkippedItems(taskId, true),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['upload-tasks'] }); },
    onError: (err: any) => setError(err.message || 'Failed to retry task'),
  });

  const tasks = tasksData?.tasks || [];
  const history = historyData?.history || [];

  // Task columns
  const taskColumns: TableColumn<UploadTask>[] = [
    { id: 'name', label: 'Task Name', minWidth: 200 },
    {
      id: 'status', label: 'Status', minWidth: 120,
      render: (_, row) => (
        <Chip
          label={UPLOAD_TASK_STATUS_LABELS[row.status]}
          size="small"
          sx={{ bgcolor: UPLOAD_TASK_STATUS_COLORS[row.status], color: 'white' }}
        />
      ),
    },
    { id: 'total_items', label: 'Items', minWidth: 80, align: 'right' },
    {
      id: 'progress', label: 'Progress', minWidth: 120,
      render: (_, row) => `${row.completed_items}/${row.total_items} (${row.skipped_items} skipped)`,
    },
    {
      id: 'total_size', label: 'Size', minWidth: 100, align: 'right',
      render: (_, row) => formatBytes(row.total_size),
    },
    {
      id: 'created_at', label: 'Created', minWidth: 150,
      render: (value) => formatDate(value as string),
    },
    {
      id: 'actions', label: 'Actions', minWidth: 180, align: 'center',
      render: (_, row) => (
        <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'center' }}>
          <Tooltip title="View Details">
            <IconButton size="small" onClick={() => setDetailTaskId(row.id)} color="default">
              <ViewIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          {row.status === 'pending' && (
            <Tooltip title="Execute">
              <IconButton size="small" onClick={() => executeMutation.mutate(row.id)} color="primary">
                <PlayIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          {row.status === 'running' && (
            <Tooltip title="Cancel">
              <IconButton size="small" onClick={() => cancelMutation.mutate(row.id)} color="warning">
                <CancelIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          {row.status === 'completed' && row.skipped_items > 0 && (
            <Tooltip title="Retry Skipped">
              <IconButton size="small" onClick={() => retryMutation.mutate(row.id)} color="info">
                <RetryIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          {row.status !== 'running' && (
            <Tooltip title="Delete">
              <IconButton size="small" onClick={() => deleteMutation.mutate(row.id)} color="error">
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
        </Box>
      ),
    },
  ];

  // History columns
  const historyColumns: TableColumn<UploadHistoryItem>[] = [
    { id: 'task_name', label: 'Task', minWidth: 120 },
    { id: 'episode', label: 'Episode', minWidth: 80 },
    { id: 'sequence', label: 'Sequence', minWidth: 80 },
    { id: 'shot', label: 'Shot', minWidth: 80 },
    { id: 'department', label: 'Dept', minWidth: 80 },
    { id: 'filename', label: 'Filename', minWidth: 200 },
    { id: 'version', label: 'Version', minWidth: 80 },
    {
      id: 'file_size', label: 'Size', minWidth: 100, align: 'right',
      render: (_, row) => formatBytes(row.file_size),
    },
    {
      id: 'status', label: 'Status', minWidth: 100,
      render: (_, row) => (
        <Chip
          label={row.status}
          size="small"
          color={row.status === 'completed' ? 'success' : row.status === 'failed' ? 'error' : 'default'}
        />
      ),
    },
    { id: 'target_endpoint_name', label: 'Target', minWidth: 120 },
    {
      id: 'uploaded_at', label: 'Uploaded', minWidth: 150,
      render: (value) => formatDate(value as string),
    },
    {
      id: 'actions', label: 'Actions', minWidth: 80, align: 'center',
      render: (_, row) => (
        <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'center' }}>
          {row.task_id && (
            <Tooltip title="View Task Details">
              <IconButton size="small" onClick={() => setDetailTaskId(row.task_id!)} color="default">
                <ViewIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
        </Box>
      ),
    },
  ];

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <UploadIcon sx={{ fontSize: 32, color: 'primary.main' }} />
          <Typography variant="h4" component="h1">Shot Upload</Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreateDialogOpen(true)}>
            Create Upload Task
          </Button>
          <IconButton onClick={() => { refetchTasks(); refetchHistory(); }}>
            <RefreshIcon />
          </IconButton>
        </Box>
      </Box>

      <Typography variant="body2" color="text.secondary" gutterBottom sx={{ mb: 2 }}>
        Upload comp department output files from local storage to FTP/SFTP endpoints.
      </Typography>

      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>}

      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs value={tabValue} onChange={(_, v) => setTabValue(v)}>
          <Tab icon={<UploadIcon />} iconPosition="start" label={`Upload Tasks (${tasks.length})`} />
          <Tab icon={<HistoryIcon />} iconPosition="start" label="Upload History" />
        </Tabs>
      </Box>

      <TabPanel value={tabValue} index={0}>
        {tasksLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}><CircularProgress /></Box>
        ) : (
          <DataTable columns={taskColumns} data={tasks} selectedRows={[]} onSelectionChange={() => {}} actions={[]} />
        )}
      </TabPanel>

      <TabPanel value={tabValue} index={1}>
        {historyLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}><CircularProgress /></Box>
        ) : (
          <DataTable columns={historyColumns} data={history} selectedRows={[]} onSelectionChange={() => {}} actions={[]} />
        )}
      </TabPanel>

      <CreateUploadTaskDialog
        open={createDialogOpen}
        onClose={() => setCreateDialogOpen(false)}
        onSuccess={() => { refetchTasks(); setCreateDialogOpen(false); }}
      />

      <UploadTaskDetailDialog
        open={!!detailTaskId}
        taskId={detailTaskId}
        onClose={() => setDetailTaskId(null)}
      />
    </Box>
  );
};

export default ShotUpload;

