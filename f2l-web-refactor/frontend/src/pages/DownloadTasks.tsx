import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  IconButton,
  Chip,
  LinearProgress,
  Tooltip,
} from '@mui/material';
import {
  PlayArrow as PlayIcon,
  Stop as StopIcon,
  Delete as DeleteIcon,
  Refresh as RefreshIcon,
  Visibility as ViewIcon,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import { shotService } from '@/services/shotService';
import { TaskSummary, TASK_STATUS_LABELS, TASK_STATUS_COLORS } from '@/types/shot';
import TaskDetailsDialog from '@/components/shots/TaskDetailsDialog';

const DownloadTasks: React.FC = () => {
  const queryClient = useQueryClient();
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [detailsDialogOpen, setDetailsDialogOpen] = useState(false);

  // Fetch tasks
  const { data: tasks = [], isLoading, refetch } = useQuery({
    queryKey: ['download-tasks'],
    queryFn: () => shotService.listTasks(),
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  // Execute task mutation
  const executeMutation = useMutation({
    mutationFn: (taskId: string) => shotService.executeTask(taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['download-tasks'] });
    },
  });

  // Cancel task mutation
  const cancelMutation = useMutation({
    mutationFn: (taskId: string) => shotService.cancelTask(taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['download-tasks'] });
    },
  });

  // Delete task mutation
  const deleteMutation = useMutation({
    mutationFn: (taskId: string) => shotService.deleteTask(taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['download-tasks'] });
    },
  });

  const handleViewDetails = (taskId: string) => {
    setSelectedTaskId(taskId);
    setDetailsDialogOpen(true);
  };

  const handleExecute = (taskId: string) => {
    if (confirm('Start downloading this task?')) {
      executeMutation.mutate(taskId);
    }
  };

  const handleCancel = (taskId: string) => {
    if (confirm('Cancel this running task?')) {
      cancelMutation.mutate(taskId);
    }
  };

  const handleDelete = (taskId: string) => {
    if (confirm('Delete this task? This cannot be undone.')) {
      deleteMutation.mutate(taskId);
    }
  };

  const columns: GridColDef<TaskSummary>[] = [
    {
      field: 'name',
      headerName: 'Task Name',
      flex: 1,
      minWidth: 200,
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 130,
      renderCell: (params: GridRenderCellParams<TaskSummary>) => (
        <Chip
          label={TASK_STATUS_LABELS[params.row.status]}
          size="small"
          sx={{
            backgroundColor: TASK_STATUS_COLORS[params.row.status],
            color: 'white',
            fontWeight: 500,
          }}
        />
      ),
    },
    {
      field: 'progress',
      headerName: 'Progress',
      width: 200,
      renderCell: (params: GridRenderCellParams<TaskSummary>) => (
        <Box sx={{ width: '100%' }}>
          <LinearProgress
            variant="determinate"
            value={params.row.progress_percent}
            sx={{ mb: 0.5 }}
          />
          <Typography variant="caption">
            {params.row.completed_items}/{params.row.total_items} items ({params.row.progress_percent}%)
          </Typography>
        </Box>
      ),
    },
    {
      field: 'total_items',
      headerName: 'Items',
      width: 80,
      align: 'right',
    },
    {
      field: 'failed_items',
      headerName: 'Failed',
      width: 80,
      align: 'right',
      renderCell: (params: GridRenderCellParams<TaskSummary>) => (
        <Typography
          variant="body2"
          color={params.row.failed_items > 0 ? 'error' : 'text.secondary'}
        >
          {params.row.failed_items}
        </Typography>
      ),
    },
    {
      field: 'created_at',
      headerName: 'Created',
      width: 180,
      valueFormatter: (params) => {
        if (!params.value) return '-';
        return new Date(params.value).toLocaleString();
      },
    },
    {
      field: 'created_by',
      headerName: 'Created By',
      width: 120,
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 180,
      sortable: false,
      renderCell: (params: GridRenderCellParams<TaskSummary>) => (
        <Box>
          <Tooltip title="View Details">
            <IconButton
              size="small"
              onClick={() => handleViewDetails(params.row.task_id)}
            >
              <ViewIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          {params.row.status === 'pending' && (
            <Tooltip title="Start Download">
              <IconButton
                size="small"
                color="primary"
                onClick={() => handleExecute(params.row.task_id)}
              >
                <PlayIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          {params.row.status === 'running' && (
            <Tooltip title="Cancel">
              <IconButton
                size="small"
                color="warning"
                onClick={() => handleCancel(params.row.task_id)}
              >
                <StopIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          {(params.row.status === 'completed' || params.row.status === 'failed' || params.row.status === 'cancelled') && (
            <Tooltip title="Delete">
              <IconButton
                size="small"
                color="error"
                onClick={() => handleDelete(params.row.task_id)}
              >
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
        </Box>
      ),
    },
  ];

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <div>
          <Typography variant="h4" gutterBottom>
            Download Tasks
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Manage and monitor shot download tasks
          </Typography>
        </div>
        <Button
          variant="outlined"
          startIcon={<RefreshIcon />}
          onClick={() => refetch()}
        >
          Refresh
        </Button>
      </Box>

      <Paper sx={{ height: 600, width: '100%' }}>
        <DataGrid
          rows={tasks}
          columns={columns}
          loading={isLoading}
          getRowId={(row) => row.task_id}
          pageSizeOptions={[10, 25, 50]}
          initialState={{
            pagination: { paginationModel: { pageSize: 25 } },
          }}
          disableRowSelectionOnClick
        />
      </Paper>

      {/* Task Details Dialog */}
      {selectedTaskId && (
        <TaskDetailsDialog
          open={detailsDialogOpen}
          onClose={() => setDetailsDialogOpen(false)}
          taskId={selectedTaskId}
        />
      )}
    </Box>
  );
};

export default DownloadTasks;

