import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Button,
  TextField,
  InputAdornment,
  Chip,
  IconButton,
  CircularProgress,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
} from '@mui/material';
import {
  Add as AddIcon,
  Search as SearchIcon,
  Refresh as RefreshIcon,
  PlayArrow as StartIcon,
  Stop as StopIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  History as HistoryIcon,
} from '@mui/icons-material';
import DataTable from '@/components/common/DataTable';
import SessionDialog from '@/components/sessions/SessionDialog';
import ExecutionHistory from '@/components/sessions/ExecutionHistory';
import { TableColumn } from '@/types';
import { formatDate } from '@/utils/formatters';
import sessionService, { SyncSession } from '@/services/sessionService';

const Sessions: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSessions, setSelectedSessions] = useState<string[]>([]);
  const [sessions, setSessions] = useState<SyncSession[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [openDialog, setOpenDialog] = useState(false);
  const [selectedSession, setSelectedSession] = useState<SyncSession | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [sessionToDelete, setSessionToDelete] = useState<SyncSession | null>(null);
  const [historyDialogOpen, setHistoryDialogOpen] = useState(false);
  const [historySessionId, setHistorySessionId] = useState<string | null>(null);

  // Load sessions from API
  const loadSessions = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await sessionService.getSessions();
      // Ensure data is an array
      setSessions(Array.isArray(data) ? data : []);
    } catch (err: any) {
      console.error('Failed to load sessions:', err);
      setError(err.response?.data?.detail || 'Failed to load sessions');
      setSessions([]); // Set empty array on error
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSessions();
  }, []);

  // Start session
  const handleStart = async (session: SyncSession) => {
    try {
      const result = await sessionService.startSession(session.id, false, session.force_overwrite);
      alert(`Session started successfully!\n${result.message || ''}`);
      await loadSessions(); // Reload to get updated status
    } catch (err: any) {
      console.error('Start failed:', err);
      alert(`Failed to start session!\n${err.response?.data?.detail || err.message}`);
    }
  };

  // Stop session
  const handleStop = async (session: SyncSession) => {
    try {
      const result = await sessionService.stopSession(session.id);
      alert(`Session stopped successfully!\n${result.message || ''}`);
      await loadSessions(); // Reload to get updated status
    } catch (err: any) {
      console.error('Stop failed:', err);
      alert(`Failed to stop session!\n${err.response?.data?.detail || err.message}`);
    }
  };

  // Edit session
  const handleEdit = (session: SyncSession) => {
    setSelectedSession(session);
    setOpenDialog(true);
  };

  // Delete session
  const handleDelete = (session: SyncSession) => {
    setSessionToDelete(session);
    setDeleteDialogOpen(true);
  };

  const confirmDelete = async () => {
    if (!sessionToDelete) return;

    try {
      await sessionService.deleteSession(sessionToDelete.id);
      alert('Session deleted successfully!');
      setDeleteDialogOpen(false);
      setSessionToDelete(null);
      await loadSessions();
    } catch (err: any) {
      console.error('Delete failed:', err);
      alert(`Failed to delete session!\n${err.response?.data?.detail || err.message}`);
    }
  };

  // Add new session
  const handleAdd = () => {
    setSelectedSession(null);
    setOpenDialog(true);
  };

  // View execution history
  const handleViewHistory = (session: SyncSession) => {
    setHistorySessionId(session.id);
    setHistoryDialogOpen(true);
  };

  // Filter sessions based on search query
  const filteredSessions = (Array.isArray(sessions) ? sessions : []).filter((session) =>
    session.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    session.notes?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Define table columns
  const columns: TableColumn[] = [
    {
      id: 'name',
      label: 'Name',
      minWidth: 200,
      render: (_value: any, row: any) => (
        <Box>
          <Typography variant="body2" fontWeight="medium">
            {row.name}
          </Typography>
          {row.notes && (
            <Typography variant="caption" color="text.secondary">
              {row.notes}
            </Typography>
          )}
        </Box>
      ),
    },
    {
      id: 'sync_direction',
      label: 'Direction',
      minWidth: 150,
      render: (value: any) => {
        const directionLabels: Record<string, string> = {
          'source_to_dest': 'Source → Destination',
          'dest_to_source': 'Destination → Source',
          'bidirectional': 'Bidirectional',
        };
        return directionLabels[value] || value;
      },
    },
    {
      id: 'source_path',
      label: 'Source Path',
      minWidth: 150,
    },
    {
      id: 'destination_path',
      label: 'Destination Path',
      minWidth: 150,
    },
    {
      id: 'is_active',
      label: 'Status',
      minWidth: 100,
      render: (value: any) => (
        <Chip
          label={value ? 'Active' : 'Inactive'}
          color={value ? 'success' : 'default'}
          size="small"
        />
      ),
    },
    {
      id: 'force_overwrite',
      label: 'Force Overwrite',
      minWidth: 120,
      render: (value: any) => (
        <Chip
          label={value ? 'Yes' : 'No'}
          color={value ? 'warning' : 'default'}
          size="small"
          variant="outlined"
        />
      ),
    },
    {
      id: 'schedule_enabled',
      label: 'Schedule',
      minWidth: 150,
      render: (_value: any, row: any) => {
        if (!row.schedule_enabled) {
          return <Chip label="Manual" size="small" variant="outlined" />;
        }
        const scheduleText = `Every ${row.schedule_interval} ${row.schedule_unit}`;
        return (
          <Chip
            label={scheduleText}
            color="info"
            size="small"
            icon={row.auto_start_enabled ? <StartIcon fontSize="small" /> : undefined}
          />
        );
      },
    },
    {
      id: 'last_run_at',
      label: 'Last Run',
      minWidth: 150,
      render: (value: any) => value ? formatDate(value) : 'Never',
    },
  ];

  // Actions for the 3-dot menu
  const actions = [
    {
      label: 'View History',
      icon: <HistoryIcon />,
      onClick: handleViewHistory,
    },
    {
      label: 'Start',
      icon: <StartIcon />,
      onClick: handleStart,
    },
    {
      label: 'Stop',
      icon: <StopIcon />,
      onClick: handleStop,
    },
    {
      label: 'Edit',
      icon: <EditIcon />,
      onClick: handleEdit,
    },
    {
      label: 'Delete',
      icon: <DeleteIcon />,
      onClick: handleDelete,
    },
  ];

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h4" component="h1">
          Sync Sessions
        </Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleAdd}
          >
            Create Session
          </Button>
          <IconButton onClick={loadSessions} disabled={loading}>
            <RefreshIcon />
          </IconButton>
        </Box>
      </Box>

      {/* Search */}
      <Box sx={{ mb: 2 }}>
        <TextField
          fullWidth
          placeholder="Search sessions..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon />
              </InputAdornment>
            ),
          }}
        />
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

      {/* Data Table */}
      {!loading && (
        <DataTable
          columns={columns}
          data={filteredSessions}
          selectedRows={selectedSessions}
          onSelectionChange={setSelectedSessions}
          actions={actions}
        />
      )}

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)}>
        <DialogTitle>Confirm Delete</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete session "{sessionToDelete?.name}"? This action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
          <Button onClick={confirmDelete} color="error" variant="contained">
            Delete
          </Button>
        </DialogActions>
      </Dialog>

      {/* Session Form Dialog */}
      <SessionDialog
        open={openDialog}
        session={selectedSession}
        onClose={() => setOpenDialog(false)}
        onSave={loadSessions}
      />

      {/* Execution History Dialog */}
      <Dialog
        open={historyDialogOpen}
        onClose={() => setHistoryDialogOpen(false)}
        maxWidth="lg"
        fullWidth
      >
        <DialogTitle>Execution History</DialogTitle>
        <DialogContent>
          {historySessionId && <ExecutionHistory sessionId={historySessionId} />}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setHistoryDialogOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Sessions;

