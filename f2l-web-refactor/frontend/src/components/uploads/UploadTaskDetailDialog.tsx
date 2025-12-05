import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  CircularProgress,
  Tooltip,
  IconButton,
  Collapse,
} from '@mui/material';
import {
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
  HourglassEmpty as PendingIcon,
  SkipNext as SkippedIcon,
  CloudUpload as UploadingIcon,
  ExpandMore as ExpandIcon,
  ExpandLess as CollapseIcon,
  ContentCopy as CopyIcon,
} from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import { uploadService } from '@/services/uploadService';
import { formatBytes, formatDate } from '@/utils/formatters';
import { UPLOAD_TASK_STATUS_LABELS, UPLOAD_TASK_STATUS_COLORS } from '@/types/upload';

interface UploadTaskDetailDialogProps {
  open: boolean;
  taskId: string | null;
  onClose: () => void;
}

const statusIcons: Record<string, React.ReactNode> = {
  pending: <PendingIcon color="action" fontSize="small" />,
  uploading: <UploadingIcon color="info" fontSize="small" />,
  completed: <SuccessIcon color="success" fontSize="small" />,
  failed: <ErrorIcon color="error" fontSize="small" />,
  skipped: <SkippedIcon color="warning" fontSize="small" />,
};

const UploadTaskDetailDialog: React.FC<UploadTaskDetailDialogProps> = ({ open, taskId, onClose }) => {
  const [expandedRows, setExpandedRows] = React.useState<Set<string>>(new Set());

  const { data: task, isLoading } = useQuery({
    queryKey: ['upload-task-detail', taskId],
    queryFn: () => uploadService.getTask(taskId!),
    enabled: open && !!taskId,
    refetchInterval: (query) => query.state.data?.status === 'running' ? 2000 : false,
  });

  const toggleRow = (id: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  if (!open) return null;

  return (
    <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Typography variant="h6">Upload Task Details</Typography>
          {task && (
            <Chip
              label={UPLOAD_TASK_STATUS_LABELS[task.status]}
              sx={{ bgcolor: UPLOAD_TASK_STATUS_COLORS[task.status], color: 'white' }}
            />
          )}
        </Box>
      </DialogTitle>

      <DialogContent dividers>
        {isLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
            <CircularProgress />
          </Box>
        ) : task ? (
          <Box>
            {/* Task Summary */}
            <Paper sx={{ p: 2, mb: 2 }}>
              <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
                {task.name}
              </Typography>
              <Box sx={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                <Box>
                  <Typography variant="caption" color="text.secondary">Progress</Typography>
                  <Typography>{task.completed_items}/{task.total_items} completed</Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">Failed</Typography>
                  <Typography color="error.main">{task.failed_items}</Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">Skipped</Typography>
                  <Typography color="warning.main">{task.skipped_items}</Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">Size</Typography>
                  <Typography>{formatBytes(task.uploaded_size)} / {formatBytes(task.total_size)}</Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">Created</Typography>
                  <Typography>{task.created_at ? formatDate(task.created_at) : '-'}</Typography>
                </Box>
              </Box>
            </Paper>

            {/* Items Table */}
            <Typography variant="subtitle2" gutterBottom>
              Files ({task.items?.length || 0})
            </Typography>
            <TableContainer component={Paper} sx={{ maxHeight: 400 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell width={40}></TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Episode</TableCell>
                    <TableCell>Sequence</TableCell>
                    <TableCell>Shot</TableCell>
                    <TableCell>Department</TableCell>
                    <TableCell>Filename</TableCell>
                    <TableCell align="right">Size</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {task.items?.map((item: any) => (
                    <React.Fragment key={item.id}>
                      <TableRow
                        hover
                        sx={{ cursor: 'pointer', '& > *': { borderBottom: expandedRows.has(item.id) ? 0 : undefined } }}
                        onClick={() => toggleRow(item.id)}
                      >
                        <TableCell>
                          <IconButton size="small">
                            {expandedRows.has(item.id) ? <CollapseIcon /> : <ExpandIcon />}
                          </IconButton>
                        </TableCell>
                        <TableCell>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                            {statusIcons[item.status]}
                            <Typography variant="body2">{item.status}</Typography>
                          </Box>
                        </TableCell>
                        <TableCell>{item.episode}</TableCell>
                        <TableCell>{item.sequence}</TableCell>
                        <TableCell>{item.shot}</TableCell>
                        <TableCell>{item.department}</TableCell>
                        <TableCell>
                          <Tooltip title={item.filename}>
                            <Typography variant="body2" noWrap sx={{ maxWidth: 200 }}>{item.filename}</Typography>
                          </Tooltip>
                        </TableCell>
                        <TableCell align="right">{formatBytes(item.file_size)}</TableCell>
                      </TableRow>
                      {/* Expanded Details */}
                      <TableRow>
                        <TableCell colSpan={8} sx={{ py: 0 }}>
                          <Collapse in={expandedRows.has(item.id)} timeout="auto" unmountOnExit>
                            <Box sx={{ p: 2, bgcolor: 'grey.50' }}>
                              <Box sx={{ mb: 1 }}>
                                <Typography variant="caption" color="text.secondary">Source Path:</Typography>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                  <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem', wordBreak: 'break-all' }}>
                                    {item.source_path}
                                  </Typography>
                                  <IconButton size="small" onClick={() => copyToClipboard(item.source_path)}>
                                    <CopyIcon fontSize="small" />
                                  </IconButton>
                                </Box>
                              </Box>
                              <Box sx={{ mb: 1 }}>
                                <Typography variant="caption" color="text.secondary">Target Path:</Typography>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                  <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem', wordBreak: 'break-all' }}>
                                    {item.target_path}
                                  </Typography>
                                  <IconButton size="small" onClick={() => copyToClipboard(item.target_path)}>
                                    <CopyIcon fontSize="small" />
                                  </IconButton>
                                </Box>
                              </Box>
                              {item.error_message && (
                                <Box>
                                  <Typography variant="caption" color="error">Error:</Typography>
                                  <Typography variant="body2" color="error.main">{item.error_message}</Typography>
                                </Box>
                              )}
                              {item.target_exists && (
                                <Chip label="Target file exists" size="small" color="warning" sx={{ mt: 1 }} />
                              )}
                            </Box>
                          </Collapse>
                        </TableCell>
                      </TableRow>
                    </React.Fragment>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        ) : (
          <Typography color="text.secondary">Task not found</Typography>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
};

export default UploadTaskDetailDialog;

