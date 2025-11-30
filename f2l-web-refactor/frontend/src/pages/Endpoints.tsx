import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Button,
  TextField,
  InputAdornment,
  Chip,
  IconButton,
  Tooltip,
  CircularProgress,
  Alert,
} from '@mui/material';
import {
  Add as AddIcon,
  Search as SearchIcon,
  Refresh as RefreshIcon,
  PowerSettingsNew as ConnectIcon,
  PowerOff as DisconnectIcon,
  RestartAlt as RestartIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';
import axios from 'axios';
import DataTable from '@/components/common/DataTable';
import EndpointDialog from '@/components/endpoints/EndpointDialog';
import { TableColumn } from '@/types';
import { ENDPOINT_TYPE_LABELS } from '@/utils/constants';
import { formatDate } from '@/utils/formatters';

// Use relative URL - nginx will proxy to backend
const API_URL = '';

const Endpoints: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedEndpoints, setSelectedEndpoints] = useState<string[]>([]);
  const [endpoints, setEndpoints] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [openDialog, setOpenDialog] = useState(false);
  const [selectedEndpoint, setSelectedEndpoint] = useState<any | null>(null);

  // Load endpoints from API
  const loadEndpoints = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.get(`${API_URL}/api/v1/endpoints/`);
      setEndpoints(response.data);
    } catch (err: any) {
      console.error('Failed to load endpoints:', err);
      setError(err.response?.data?.detail || 'Failed to load endpoints');
    } finally {
      setLoading(false);
    }
  };

  // Connect endpoint
  const handleConnect = async (endpoint: any) => {
    try {
      const response = await axios.post(`${API_URL}/api/v1/endpoints/${endpoint.id}/connect`);
      if (response.data.success) {
        alert(`Connected successfully!\n${response.data.message || ''}`);
      } else {
        alert(`Connection failed!\n${response.data.message || ''}`);
      }
      await loadEndpoints(); // Reload to get updated status
    } catch (err: any) {
      console.error('Connect failed:', err);
      alert(`Connection failed!\n${err.response?.data?.detail || err.message}`);
    }
  };

  // Disconnect endpoint
  const handleDisconnect = async (endpoint: any) => {
    try {
      const response = await axios.post(`${API_URL}/api/v1/endpoints/${endpoint.id}/disconnect`);
      if (response.data.success) {
        alert(`Disconnected successfully!\n${response.data.message || ''}`);
      }
      await loadEndpoints(); // Reload to get updated status
    } catch (err: any) {
      console.error('Disconnect failed:', err);
      alert(`Disconnect failed!\n${err.response?.data?.detail || err.message}`);
    }
  };

  // Restart endpoint connection
  const handleRestart = async (endpoint: any) => {
    try {
      const response = await axios.post(`${API_URL}/api/v1/endpoints/${endpoint.id}/restart`);
      if (response.data.success) {
        alert(`Restarted successfully!\n${response.data.message || ''}`);
      } else {
        alert(`Restart failed!\n${response.data.message || ''}`);
      }
      await loadEndpoints(); // Reload to get updated status
    } catch (err: any) {
      console.error('Restart failed:', err);
      alert(`Restart failed!\n${err.response?.data?.detail || err.message}`);
    }
  };

  // Delete endpoint
  const handleDeleteEndpoint = async (endpoint: any) => {
    if (!confirm(`Are you sure you want to delete endpoint "${endpoint.name}"?`)) {
      return;
    }
    try {
      await axios.delete(`${API_URL}/api/v1/endpoints/${endpoint.id}`);
      alert('Endpoint deleted successfully');
      await loadEndpoints();
    } catch (err: any) {
      console.error('Delete failed:', err);
      alert(`Failed to delete endpoint!\n${err.response?.data?.detail || err.message}`);
    }
  };

  // Load endpoints on mount
  useEffect(() => {
    loadEndpoints();
  }, []);

  const columns: TableColumn[] = [
    {
      id: 'name',
      label: 'Name',
      sortable: true,
      minWidth: 180,
    },
    {
      id: 'endpoint_type',
      label: 'Type',
      sortable: true,
      minWidth: 100,
      render: (value) => (
        <Chip
          label={ENDPOINT_TYPE_LABELS[value as keyof typeof ENDPOINT_TYPE_LABELS] || value}
          size="small"
          variant="outlined"
        />
      ),
    },
    {
      id: 'connection_info',
      label: 'Connection',
      minWidth: 180,
      render: (_, row) => {
        if (row.endpoint_type === 's3') {
          return `${row.s3_bucket} (${row.s3_region})`;
        }
        if (row.endpoint_type === 'local') {
          return 'Server: /mnt';
        }
        return `${row.host}:${row.port}`;
      },
    },
    {
      id: 'remote_path',
      label: 'Source Path',
      minWidth: 150,
      render: (value) => value || '-',
    },
    {
      id: 'local_path',
      label: 'Destination Path',
      minWidth: 150,
      render: (value) => value || '-',
    },
    {
      id: 'connection_status',
      label: 'Status',
      type: 'status',
      sortable: true,
      minWidth: 130,
      render: (value, row) => {
        // Determine status based on connection_status
        let label = 'Not Connected';
        let color: 'success' | 'error' | 'warning' | 'default' = 'default';

        if (value === 'connected') {
          label = 'Connected';
          color = 'success';
        } else if (value === 'error') {
          label = 'Error';
          color = 'error';
        } else if (value === 'disconnected') {
          label = 'Disconnected';
          color = 'error';  // Changed from 'default' to 'error' (red)
        } else if (value === 'restarting') {
          label = 'Restarting...';
          color = 'warning';
        } else if (value === 'not_tested') {
          label = 'Not Tested';
          color = 'warning';  // Changed from 'default' to 'warning' (yellow)
        }

        return (
          <Tooltip title={row.last_test_message || label}>
            <Chip
              label={label}
              color={color}
              size="small"
            />
          </Tooltip>
        );
      },
    },
    {
      id: 'updated_at',
      label: 'Last Updated',
      type: 'datetime',
      sortable: true,
      minWidth: 150,
      render: (value) => formatDate(value, 'PPp'),
    },
  ];

  const handleEditEndpoint = (endpoint: any) => {
    setSelectedEndpoint(endpoint);
    setOpenDialog(true);
  };

  const actions = [
    {
      label: 'Connect',
      icon: <ConnectIcon />,
      onClick: handleConnect,
    },
    {
      label: 'Disconnect',
      icon: <DisconnectIcon />,
      onClick: handleDisconnect,
    },
    {
      label: 'Restart',
      icon: <RestartIcon />,
      onClick: handleRestart,
    },
    {
      label: 'Edit',
      icon: <EditIcon />,
      onClick: handleEditEndpoint,
    },
    {
      label: 'Delete',
      icon: <DeleteIcon />,
      onClick: handleDeleteEndpoint,
    },
  ];

  const filteredEndpoints = endpoints.filter(endpoint =>
    endpoint.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    endpoint.endpoint_type.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (endpoint.host && endpoint.host.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const handleCreateEndpoint = () => {
    setSelectedEndpoint(null);
    setOpenDialog(true);
  };

  const handleRefresh = () => {
    loadEndpoints();
  };

  const handleDialogClose = () => {
    setOpenDialog(false);
    setSelectedEndpoint(null);
  };

  const handleDialogSave = () => {
    loadEndpoints(); // Reload the list after save
  };

  const handleBulkAction = (action: string) => {
    console.log(`Bulk ${action} for endpoints:`, selectedEndpoints);
  };

  return (
    <Box>
      {/* Page header */}
      <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 600, mb: 1 }}>
            Endpoints
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Manage your FTP, SFTP, S3, and local storage endpoints
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Tooltip title="Refresh">
            <IconButton onClick={handleRefresh} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleCreateEndpoint}
            disabled={loading}
          >
            Add Endpoint
          </Button>
        </Box>
      </Box>

      {/* Error message */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Loading indicator */}
      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}>
          <CircularProgress />
        </Box>
      )}

      {/* Search and filters */}
      <Box sx={{ mb: 3, display: 'flex', gap: 2, alignItems: 'center' }}>
        <TextField
          placeholder="Search endpoints..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon />
              </InputAdornment>
            ),
          }}
          sx={{ minWidth: 300 }}
        />
        
        {selectedEndpoints.length > 0 && (
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              variant="outlined"
              size="small"
              onClick={() => handleBulkAction('activate')}
            >
              Activate ({selectedEndpoints.length})
            </Button>
            <Button
              variant="outlined"
              size="small"
              onClick={() => handleBulkAction('deactivate')}
            >
              Deactivate ({selectedEndpoints.length})
            </Button>
            <Button
              variant="outlined"
              color="error"
              size="small"
              onClick={() => handleBulkAction('delete')}
            >
              Delete ({selectedEndpoints.length})
            </Button>
          </Box>
        )}
      </Box>

      {/* Data table */}
      <DataTable
        columns={columns}
        data={filteredEndpoints}
        selectable
        selectedRows={selectedEndpoints}
        onSelectionChange={setSelectedEndpoints}
        onRowClick={(row) => console.log('Row clicked:', row)}
        actions={actions}
        emptyMessage="No endpoints found. Create your first endpoint to get started."
      />

      {/* Endpoint Dialog */}
      <EndpointDialog
        open={openDialog}
        endpoint={selectedEndpoint}
        onClose={handleDialogClose}
        onSave={handleDialogSave}
      />
    </Box>
  );
};

export default Endpoints;
