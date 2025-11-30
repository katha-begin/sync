import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  MenuItem,
  Grid,
  FormControlLabel,
  Checkbox,
  Typography,
  Alert,
  CircularProgress,
  IconButton,
  InputAdornment,
} from '@mui/material';
import { Folder as FolderIcon } from '@mui/icons-material';
import axios from 'axios';
import { SyncSession, CreateSessionRequest } from '@/services/sessionService';
import DirectoryBrowser from '@/components/browse/DirectoryBrowser';

const API_URL = '';

interface Endpoint {
  id: string;
  name: string;
  endpoint_type: string;
  host?: string;
  port?: number;
  remote_path?: string;  // For FTP/SFTP endpoints
  local_path?: string;   // For LOCAL endpoints
}

interface SessionDialogProps {
  open: boolean;
  session: SyncSession | null;
  onClose: () => void;
  onSave: () => void;
}

const SessionDialog: React.FC<SessionDialogProps> = ({ open, session, onClose, onSave }) => {
  const [formData, setFormData] = useState<CreateSessionRequest>({
    name: '',
    source_endpoint_id: '',
    destination_endpoint_id: '',
    sync_direction: 'source_to_dest',
    notes: '',
    source_path: '/',
    destination_path: '/',
    // Phase 5: folder_filter, file_filter, exclude_patterns will be added
    force_overwrite: false,
    // Phase 5: delete_extra_files, preserve_timestamps, verify_checksums, max_parallel_transfers will be added
    schedule_enabled: false,
    schedule_interval: undefined,
    schedule_unit: 'minutes',
    auto_start_enabled: false,
  });

  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [sourceBrowserOpen, setSourceBrowserOpen] = useState(false);
  const [destBrowserOpen, setDestBrowserOpen] = useState(false);

  // Load endpoints
  useEffect(() => {
    if (open) {
      loadEndpoints();
    }
  }, [open]);

  // Populate form when editing
  useEffect(() => {
    if (session) {
      setFormData({
        name: session.name,
        source_endpoint_id: session.source_endpoint_id,
        destination_endpoint_id: session.destination_endpoint_id,
        sync_direction: session.sync_direction,
        notes: session.notes || '',
        source_path: session.source_path,
        destination_path: session.destination_path,
        force_overwrite: session.force_overwrite,
        schedule_enabled: session.schedule_enabled,
        schedule_interval: session.schedule_interval,
        schedule_unit: session.schedule_unit || 'minutes',
        auto_start_enabled: session.auto_start_enabled || false,
      });
    } else {
      // Reset form for new session
      setFormData({
        name: '',
        source_endpoint_id: '',
        destination_endpoint_id: '',
        sync_direction: 'source_to_dest',
        notes: '',
        source_path: '/',
        destination_path: '/',
        // Phase 5: folder_filter, file_filter, exclude_patterns will be added
        force_overwrite: false,
        // Phase 5: delete_extra_files, preserve_timestamps, verify_checksums, max_parallel_transfers will be added
        schedule_enabled: false,
        schedule_interval: undefined,
        schedule_unit: 'minutes',
        auto_start_enabled: false,
      });
    }
    setErrors({});
    setError(null);
  }, [session, open]);

  const loadEndpoints = async () => {
    try {
      // Get ALL endpoints (active and inactive) including LOCAL endpoints
      const response = await axios.get<Endpoint[]>(`${API_URL}/api/v1/endpoints/`, {
        params: {
          active_only: false,
          limit: 100
        }
      });
      console.log('🔍 Loaded endpoints:', response.data);
      console.log('🔍 Endpoint types:', response.data.map(e => `${e.name} (${e.endpoint_type})`));
      setEndpoints(response.data);
    } catch (err: any) {
      console.error('Failed to load endpoints:', err);
      setError('Failed to load endpoints');
    }
  };

  const handleChange = (field: keyof CreateSessionRequest, value: any) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    // Clear error for this field
    if (errors[field]) {
      setErrors((prev) => {
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });
    }
  };

  // Auto-fill source path when source endpoint is selected
  const handleSourceEndpointChange = (endpointId: string) => {
    handleChange('source_endpoint_id', endpointId);

    // Auto-fill source_path with root path since base path is in endpoint config
    // User will browse from the endpoint's base path
    handleChange('source_path', '/');
  };

  // Auto-fill destination path when destination endpoint is selected
  const handleDestinationEndpointChange = (endpointId: string) => {
    handleChange('destination_endpoint_id', endpointId);

    // Auto-fill destination_path with root path since base path is in endpoint config
    // User will browse from the endpoint's base path
    handleChange('destination_path', '/');
  };

  /**
   * Strip the endpoint's base path from the selected path to get the relative path.
   * This ensures users don't have to manually remove the base path every time they browse.
   *
   * Example:
   * - Endpoint base path: /os10148/SWA or igloo_swa_v/SWA
   * - Selected path: /os10148/SWA/_temp/rich or igloo_swa_v/SWA/_temp/rich
   * - Result: _temp/rich
   */
  const stripBasePath = (fullPath: string, basePath: string): string => {
    if (!basePath || basePath === '/') {
      return fullPath;
    }

    // Normalize paths by removing leading/trailing slashes
    const normalizedFull = fullPath.replace(/^\/+|\/+$/g, '');
    const normalizedBase = basePath.replace(/^\/+|\/+$/g, '');

    // If the full path starts with the base path, strip it
    if (normalizedFull.startsWith(normalizedBase)) {
      const relativePath = normalizedFull.substring(normalizedBase.length);
      // Remove leading slash from relative path
      return relativePath.replace(/^\/+/, '') || '/';
    }

    // If no match, return the full path as-is
    return fullPath;
  };

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.name.trim()) {
      newErrors.name = 'Name is required';
    }

    if (!formData.source_endpoint_id) {
      newErrors.source_endpoint_id = 'Source endpoint is required';
    }

    if (!formData.destination_endpoint_id) {
      newErrors.destination_endpoint_id = 'Destination endpoint is required';
    }

    if (!formData.source_path || !formData.source_path.trim()) {
      newErrors.source_path = 'Source path is required';
    }

    if (!formData.destination_path || !formData.destination_path.trim()) {
      newErrors.destination_path = 'Destination path is required';
    }

    // Validate schedule fields if scheduling is enabled
    if (formData.schedule_enabled) {
      if (!formData.schedule_interval || formData.schedule_interval < 1) {
        newErrors.schedule_interval = 'Schedule interval must be at least 1';
      }
      if (!formData.schedule_unit) {
        newErrors.schedule_unit = 'Schedule unit is required';
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSave = async () => {
    if (!validate()) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      if (session) {
        // Update existing session
        await axios.put(`${API_URL}/api/v1/sessions/${session.id}`, formData);
      } else {
        // Create new session
        await axios.post(`${API_URL}/api/v1/sessions/`, formData);
      }

      onSave();
      onClose();
    } catch (err: any) {
      console.error('Failed to save session:', err);
      setError(err.response?.data?.detail || 'Failed to save session');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>{session ? 'Edit Session' : 'Create New Session'}</DialogTitle>
      <DialogContent>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <Grid container spacing={2} sx={{ mt: 1 }}>
          {/* Basic Information */}
          <Grid item xs={12}>
            <Typography variant="subtitle2" color="primary" gutterBottom>
              Basic Information
            </Typography>
          </Grid>

          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Session Name"
              value={formData.name}
              onChange={(e) => handleChange('name', e.target.value)}
              error={!!errors.name}
              helperText={errors.name}
              required
            />
          </Grid>

          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Notes"
              value={formData.notes}
              onChange={(e) => handleChange('notes', e.target.value)}
              multiline
              rows={2}
            />
          </Grid>

          {/* Endpoints */}
          <Grid item xs={12}>
            <Typography variant="subtitle2" color="primary" gutterBottom sx={{ mt: 2 }}>
              Endpoints
            </Typography>
          </Grid>

          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              select
              label="Source Endpoint (Step 1)"
              value={formData.source_endpoint_id}
              onChange={(e) => handleSourceEndpointChange(e.target.value)}
              error={!!errors.source_endpoint_id}
              helperText={errors.source_endpoint_id || `${endpoints.length} endpoints available`}
              required
            >
              {Array.isArray(endpoints) && endpoints.length > 0 ? (
                endpoints.map((endpoint) => (
                  <MenuItem key={endpoint.id} value={endpoint.id}>
                    {endpoint.name} ({endpoint.endpoint_type?.toUpperCase()})
                  </MenuItem>
                ))
              ) : (
                <MenuItem disabled>No endpoints available</MenuItem>
              )}
            </TextField>
          </Grid>

          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              select
              label="Destination Endpoint (Step 3)"
              value={formData.destination_endpoint_id}
              onChange={(e) => handleDestinationEndpointChange(e.target.value)}
              error={!!errors.destination_endpoint_id}
              helperText={errors.destination_endpoint_id || `${endpoints.length} endpoints available`}
              required
            >
              {Array.isArray(endpoints) && endpoints.length > 0 ? (
                endpoints.map((endpoint) => (
                  <MenuItem key={endpoint.id} value={endpoint.id}>
                    {endpoint.name} ({endpoint.endpoint_type?.toUpperCase()})
                  </MenuItem>
                ))
              ) : (
                <MenuItem disabled>No endpoints available</MenuItem>
              )}
            </TextField>
          </Grid>

          <Grid item xs={12}>
            <TextField
              fullWidth
              select
              label="Sync Direction"
              value={formData.sync_direction}
              onChange={(e) => handleChange('sync_direction', e.target.value)}
            >
              <MenuItem value="source_to_dest">Source → Destination</MenuItem>
              <MenuItem value="dest_to_source">Destination → Source</MenuItem>
              <MenuItem value="bidirectional">Bidirectional</MenuItem>
            </TextField>
          </Grid>

          {/* Paths */}
          <Grid item xs={12}>
            <Typography variant="subtitle2" color="primary" gutterBottom sx={{ mt: 2 }}>
              Paths
            </Typography>
          </Grid>

          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="Source Path (Step 2)"
              value={formData.source_path}
              onChange={(e) => handleChange('source_path', e.target.value)}
              error={!!errors.source_path}
              helperText={errors.source_path || 'Select path within source endpoint'}
              required
              disabled={!formData.source_endpoint_id}
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      onClick={() => setSourceBrowserOpen(true)}
                      disabled={!formData.source_endpoint_id}
                      edge="end"
                      title="Browse directories"
                    >
                      <FolderIcon />
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />
          </Grid>

          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="Destination Path (Step 4)"
              value={formData.destination_path}
              onChange={(e) => handleChange('destination_path', e.target.value)}
              error={!!errors.destination_path}
              helperText={errors.destination_path || 'Select path within destination endpoint'}
              required
              disabled={!formData.destination_endpoint_id}
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      onClick={() => setDestBrowserOpen(true)}
                      disabled={!formData.destination_endpoint_id}
                      edge="end"
                      title="Browse directories"
                    >
                      <FolderIcon />
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />
          </Grid>

          {/* Sync Options */}
          <Grid item xs={12}>
            <Typography variant="subtitle2" color="primary" gutterBottom sx={{ mt: 2 }}>
              Sync Options
            </Typography>
          </Grid>

          <Grid item xs={12}>
            <FormControlLabel
              control={
                <Checkbox
                  checked={formData.force_overwrite}
                  onChange={(e) => handleChange('force_overwrite', e.target.checked)}
                />
              }
              label={
                <span>
                  Force Overwrite{' '}
                  <span style={{ fontSize: '0.85em', color: '#999' }}>
                    (sync all files, default is smart sync)
                  </span>
                </span>
              }
            />
          </Grid>

          {/* Scheduling Section */}
          <Grid item xs={12}>
            <FormControlLabel
              control={
                <Checkbox
                  checked={formData.schedule_enabled}
                  onChange={(e) => handleChange('schedule_enabled', e.target.checked)}
                />
              }
              label="Enable Scheduling"
            />
          </Grid>

          {formData.schedule_enabled && (
            <>
              <Grid item xs={6}>
                <TextField
                  fullWidth
                  type="number"
                  label="Schedule Interval"
                  value={formData.schedule_interval || ''}
                  onChange={(e) => handleChange('schedule_interval', parseInt(e.target.value) || undefined)}
                  error={!!errors.schedule_interval}
                  helperText={errors.schedule_interval || 'How often to run'}
                  inputProps={{ min: 1 }}
                />
              </Grid>

              <Grid item xs={6}>
                <TextField
                  fullWidth
                  select
                  label="Schedule Unit"
                  value={formData.schedule_unit || 'minutes'}
                  onChange={(e) => handleChange('schedule_unit', e.target.value)}
                  error={!!errors.schedule_unit}
                  helperText={errors.schedule_unit}
                >
                  <MenuItem value="minutes">Minutes</MenuItem>
                  <MenuItem value="hours">Hours</MenuItem>
                  <MenuItem value="days">Days</MenuItem>
                </TextField>
              </Grid>

              <Grid item xs={12}>
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={formData.auto_start_enabled}
                      onChange={(e) => handleChange('auto_start_enabled', e.target.checked)}
                    />
                  }
                  label="Auto-start on app launch"
                />
              </Grid>
            </>
          )}
        </Grid>
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose} disabled={loading}>
          Cancel
        </Button>
        <Button onClick={handleSave} variant="contained" disabled={loading}>
          {loading ? <CircularProgress size={24} /> : session ? 'Update' : 'Create'}
        </Button>
      </DialogActions>

      {/* Directory Browser for Source Path */}
      <DirectoryBrowser
        open={sourceBrowserOpen}
        onClose={() => setSourceBrowserOpen(false)}
        onSelect={(path) => {
          // Strip the endpoint's base path to get the relative path
          const sourceEndpoint = endpoints.find(e => e.id === formData.source_endpoint_id);
          if (sourceEndpoint) {
            const basePath = sourceEndpoint.endpoint_type === 'local'
              ? (sourceEndpoint.local_path || '/')
              : (sourceEndpoint.remote_path || '/');
            const relativePath = stripBasePath(path, basePath);
            handleChange('source_path', relativePath);
          } else {
            handleChange('source_path', path);
          }
          setSourceBrowserOpen(false);
        }}
        endpointId={formData.source_endpoint_id}
        initialPath={formData.source_path}
        title="Browse Source Directory"
      />

      {/* Directory Browser for Destination Path */}
      <DirectoryBrowser
        open={destBrowserOpen}
        onClose={() => setDestBrowserOpen(false)}
        onSelect={(path) => {
          // Strip the endpoint's base path to get the relative path
          const destEndpoint = endpoints.find(e => e.id === formData.destination_endpoint_id);
          if (destEndpoint) {
            const basePath = destEndpoint.endpoint_type === 'local'
              ? (destEndpoint.local_path || '/')
              : (destEndpoint.remote_path || '/');
            const relativePath = stripBasePath(path, basePath);
            handleChange('destination_path', relativePath);
          } else {
            handleChange('destination_path', path);
          }
          setDestBrowserOpen(false);
        }}
        endpointId={formData.destination_endpoint_id}
        initialPath={formData.destination_path}
        title="Browse Destination Directory"
      />
    </Dialog>
  );
};

export default SessionDialog;

