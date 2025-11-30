import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  LinearProgress,
  CircularProgress,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { shotService } from '@/services/shotService';
import {
  TASK_STATUS_LABELS,
  TASK_STATUS_COLORS,
  ITEM_STATUS_LABELS,
} from '@/types/shot';
import { formatBytes } from '@/utils/formatters';

interface TaskDetailsDialogProps {
  open: boolean;
  onClose: () => void;
  taskId: string;
}

const TaskDetailsDialog: React.FC<TaskDetailsDialogProps> = ({
  open,
  onClose,
  taskId,
}) => {
  const { data: details, isLoading } = useQuery({
    queryKey: ['task-details', taskId],
    queryFn: () => shotService.getTaskDetails(taskId),
    enabled: open,
    refetchInterval: (query) => {
      // Refresh every 2 seconds if task is running
      return query.state.data?.task.status === 'running' ? 2000 : false;
    },
  });

  if (isLoading || !details) {
    return (
      <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
        <DialogContent>
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
            <CircularProgress />
          </Box>
        </DialogContent>
      </Dialog>
    );
  }

  const { task, items } = details;

  return (
    <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
      <DialogTitle>
        Task Details: {task.name}
      </DialogTitle>
      <DialogContent>
        {/* Task Summary */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            Summary
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 2 }}>
            <Chip
              label={`Status: ${TASK_STATUS_LABELS[task.status]}`}
              sx={{
                backgroundColor: TASK_STATUS_COLORS[task.status],
                color: 'white',
                fontWeight: 500,
              }}
            />
            <Chip label={`Total Items: ${task.total_items}`} />
            <Chip label={`Completed: ${task.completed_items}`} color="success" />
            <Chip label={`Failed: ${task.failed_items}`} color="error" />
          </Box>

          <Box sx={{ mb: 2 }}>
            <Typography variant="body2" gutterBottom>
              Progress: {task.progress_percent}%
            </Typography>
            <LinearProgress variant="determinate" value={task.progress_percent} />
          </Box>

          <Typography variant="body2">
            <strong>Total Size:</strong> {formatBytes(task.total_size)}
          </Typography>
          <Typography variant="body2">
            <strong>Downloaded:</strong> {formatBytes(task.downloaded_size)}
          </Typography>
          {task.created_at && (
            <Typography variant="body2">
              <strong>Created:</strong> {new Date(task.created_at).toLocaleString()}
            </Typography>
          )}
          {task.started_at && (
            <Typography variant="body2">
              <strong>Started:</strong> {new Date(task.started_at).toLocaleString()}
            </Typography>
          )}
          {task.completed_at && (
            <Typography variant="body2">
              <strong>Completed:</strong> {new Date(task.completed_at).toLocaleString()}
            </Typography>
          )}
          {task.notes && (
            <Typography variant="body2">
              <strong>Notes:</strong> {task.notes}
            </Typography>
          )}
        </Box>

        {/* Items Table */}
        <Typography variant="h6" gutterBottom>
          Items ({items.length})
        </Typography>
        <TableContainer sx={{ maxHeight: 400 }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell>Episode</TableCell>
                <TableCell>Sequence</TableCell>
                <TableCell>Shot</TableCell>
                <TableCell>Department</TableCell>
                <TableCell>FTP Version</TableCell>
                <TableCell>Status</TableCell>
                <TableCell align="right">Files</TableCell>
                <TableCell align="right">Size</TableCell>
                <TableCell>Error</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.id}>
                  <TableCell>{item.episode}</TableCell>
                  <TableCell>{item.sequence}</TableCell>
                  <TableCell>{item.shot}</TableCell>
                  <TableCell sx={{ textTransform: 'capitalize' }}>
                    {item.department}
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" fontFamily="monospace">
                      {item.ftp_version || '-'}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={ITEM_STATUS_LABELS[item.status]}
                      size="small"
                      color={
                        item.status === 'completed' ? 'success' :
                        item.status === 'failed' ? 'error' :
                        item.status === 'downloading' ? 'primary' :
                        'default'
                      }
                    />
                  </TableCell>
                  <TableCell align="right">{item.file_count}</TableCell>
                  <TableCell align="right">{formatBytes(item.total_size)}</TableCell>
                  <TableCell>
                    {item.error_message && (
                      <Typography variant="caption" color="error">
                        {item.error_message}
                      </Typography>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
};

export default TaskDetailsDialog;

