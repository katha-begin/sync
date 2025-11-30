import React, { useState } from 'react';
import {
  Box,
  Typography,
  Button,
  CircularProgress,
  Alert,
  IconButton,
} from '@mui/material';
import {
  Add as AddIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import shotService from '@/services/shotService';
import CreateTaskDialog from '@/components/shots/CreateTaskDialog';
import DataTable from '@/components/common/DataTable';
import { TableColumn } from '@/types';
import { formatDate } from '@/utils/formatters';

const ShotDownload: React.FC = () => {
  const [createTaskDialogOpen, setCreateTaskDialogOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: tasks = [], isLoading, refetch } = useQuery({
    queryKey: ['download-tasks'],
    queryFn: () => shotService.listTasks(),
  });

  const columns: TableColumn[] = [
    { id: 'name', label: 'Task Name', minWidth: 200 },
    { id: 'status', label: 'Status', minWidth: 120 },
    { id: 'total_items', label: 'Items', minWidth: 80, align: 'right' },
    { id: 'total_size', label: 'Size', minWidth: 100, align: 'right' },
    { id: 'created_at', label: 'Created', minWidth: 150, render: (value) => formatDate(value as string) },
  ];

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h4" component="h1">Shot Download</Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreateTaskDialogOpen(true)}>
            Create Download Task
          </Button>
          <IconButton onClick={() => refetch()} disabled={isLoading}><RefreshIcon /></IconButton>
        </Box>
      </Box>
      <Typography variant="body2" color="text.secondary" gutterBottom sx={{ mb: 3 }}>
        Create download tasks to sync shots from FTP endpoints to local storage.
      </Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>}
      {isLoading && <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}><CircularProgress /></Box>}
      {!isLoading && <DataTable columns={columns} data={tasks} selectedRows={[]} onSelectionChange={() => {}} actions={[]} />}
      <CreateTaskDialog open={createTaskDialogOpen} onClose={() => setCreateTaskDialogOpen(false)} onSuccess={() => { refetch(); setCreateTaskDialogOpen(false); }} />
    </Box>
  );
};

export default ShotDownload;
