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
  Alert,
  CircularProgress,
  Box,
  InputAdornment,
  IconButton,
} from '@mui/material';
import { FolderOpen as FolderOpenIcon } from '@mui/icons-material';
import axios from 'axios';
import DirectoryBrowser from '../browse/DirectoryBrowser';

// Use relative URL - nginx will proxy to backend
const API_URL = '';

interface EndpointDialogProps {
  open: boolean;
  endpoint: any | null;
  onClose: () => void;
  onSave: () => void;
}

interface FormData {
  name: string;
  endpoint_type: string;
  host: string;
  port: number;
  username: string;
  password: string;
  remote_path: string;
  local_path: string;
}

interface FormErrors {
  [key: string]: string;
}

const EndpointDialog: React.FC<EndpointDialogProps> = ({ open, endpoint, onClose, onSave }) => {
  const [formData, setFormData] = useState<FormData>({
    name: '',
    endpoint_type: 'ftp',
    host: '',
    port: 21,
    username: '',
    password: '',
    remote_path: '/',
    local_path: '',
  });

  const [errors, setErrors] = useState<FormErrors>({});
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [browserOpen, setBrowserOpen] = useState(false);
  const [browserField, setBrowserField] = useState<'remote_path' | 'local_path'>('remote_path');

  // Reset form when endpoint changes
  useEffect(() => {
    if (endpoint) {
      setFormData({
        name: endpoint.name || '',
        endpoint_type: endpoint.endpoint_type || 'ftp',
        host: endpoint.host || '',
        port: endpoint.port || 21,
        username: endpoint.username || '',
        password: '********', // Show placeholder for existing password
        remote_path: endpoint.remote_path || '/',
        local_path: endpoint.local_path || '',
      });
    } else {
      setFormData({
        name: '',
        endpoint_type: 'ftp',
        host: '',
        port: 21,
        username: '',
        password: '',
        remote_path: '/',
        local_path: '',
      });
    }
    setErrors({});
    setTestResult(null);
  }, [endpoint, open]);

  const handleChange = (field: keyof FormData, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    // Clear error for this field
    if (errors[field]) {
      setErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });
    }
  };

  const validate = (): boolean => {
    const newErrors: FormErrors = {};

    if (!formData.name.trim()) {
      newErrors.name = 'Name is required';
    }

    // Validate based on endpoint type
    if (formData.endpoint_type === 'local') {
      // For LOCAL endpoints, only local_path is required
      if (!formData.local_path.trim()) {
        newErrors.local_path = 'Local path is required';
      }
    } else {
      // For FTP/SFTP endpoints, validate connection fields
      if (!formData.host.trim()) {
        newErrors.host = 'Host is required';
      }

      if (formData.port < 1 || formData.port > 65535) {
        newErrors.port = 'Port must be between 1 and 65535';
      }

      if (!formData.username.trim()) {
        newErrors.username = 'Username is required';
      }

      if (!endpoint && !formData.password.trim()) {
        // Password required only for new endpoints
        newErrors.password = 'Password is required';
      }

      if (!formData.local_path.trim()) {
        newErrors.local_path = 'Local path is required';
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSave = async () => {
    if (!validate()) {
      return;
    }

    setSaving(true);
    setTestResult(null);

    try {
      // Prepare data based on endpoint type
      let dataToSend: any = {
        name: formData.name,
        endpoint_type: formData.endpoint_type,
      };

      if (formData.endpoint_type === 'local') {
        // For LOCAL endpoints, only send name, type, and local_path
        dataToSend.local_path = formData.local_path;
      } else {
        // For FTP/SFTP endpoints, send all connection fields
        dataToSend.host = formData.host;
        dataToSend.port = formData.port;
        dataToSend.username = formData.username;
        dataToSend.remote_path = formData.remote_path;
        dataToSend.local_path = formData.local_path;

        // Handle password for FTP/SFTP
        if (endpoint?.id) {
          // Update existing endpoint - only send password if changed
          if (formData.password !== '********') {
            dataToSend.password = formData.password;
          }
        } else {
          // Create new endpoint - password is required
          dataToSend.password = formData.password;
        }
      }

      if (endpoint?.id) {
        // Update existing endpoint
        await axios.put(`${API_URL}/api/v1/endpoints/${endpoint.id}`, dataToSend);
      } else {
        // Create new endpoint
        await axios.post(`${API_URL}/api/v1/endpoints/`, dataToSend);
      }
      onSave();
      onClose();
    } catch (err: any) {
      console.error('Save failed:', err);
      setTestResult({
        success: false,
        message: err.response?.data?.detail || err.message || 'Failed to save endpoint',
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>{endpoint ? 'Edit Endpoint' : 'Create New Endpoint'}</DialogTitle>
      <DialogContent>
        <Box sx={{ mt: 2 }}>
          <Grid container spacing={2}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Name"
                value={formData.name}
                onChange={(e) => handleChange('name', e.target.value)}
                error={!!errors.name}
                helperText={errors.name}
                required
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                select
                label="Type"
                value={formData.endpoint_type}
                onChange={(e) => handleChange('endpoint_type', e.target.value)}
                required
              >
                <MenuItem value="ftp">FTP</MenuItem>
                <MenuItem value="sftp">SFTP</MenuItem>
                <MenuItem value="local">Local</MenuItem>
              </TextField>
            </Grid>

            {/* Show FTP/SFTP fields only when endpoint type is NOT local */}
            {formData.endpoint_type !== 'local' && (
              <>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Port"
                    type="number"
                    value={formData.port}
                    onChange={(e) => handleChange('port', parseInt(e.target.value) || 21)}
                    error={!!errors.port}
                    helperText={errors.port}
                    required
                  />
                </Grid>

                <Grid item xs={12}>
                  <TextField
                    fullWidth
                    label="Host"
                    value={formData.host}
                    onChange={(e) => handleChange('host', e.target.value)}
                    error={!!errors.host}
                    helperText={errors.host}
                    required
                  />
                </Grid>

                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Username"
                    value={formData.username}
                    onChange={(e) => handleChange('username', e.target.value)}
                    error={!!errors.username}
                    helperText={errors.username}
                    required
                  />
                </Grid>

                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Password"
                    type="password"
                    value={formData.password}
                    onChange={(e) => handleChange('password', e.target.value)}
                    error={!!errors.password}
                    helperText={endpoint ? "Leave as **** to keep existing password, or type new password" : errors.password}
                    required={!endpoint}
                    placeholder={endpoint ? "********" : ""}
                  />
                </Grid>

                <Grid item xs={12}>
                  <TextField
                    fullWidth
                    label="Remote Path"
                    value={formData.remote_path}
                    onChange={(e) => handleChange('remote_path', e.target.value)}
                    helperText="Path on the FTP server"
                    InputProps={{
                      endAdornment: (
                        <InputAdornment position="end">
                          <IconButton
                            onClick={() => {
                              setBrowserField('remote_path');
                              setBrowserOpen(true);
                            }}
                            edge="end"
                            title="Browse remote directory"
                          >
                            <FolderOpenIcon />
                          </IconButton>
                        </InputAdornment>
                      ),
                    }}
                  />
                </Grid>
              </>
            )}

            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Local Path"
                value={formData.local_path}
                onChange={(e) => handleChange('local_path', e.target.value)}
                error={!!errors.local_path}
                helperText={errors.local_path || 'Local directory path for sync (on server)'}
                required
                InputProps={{
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton
                        onClick={() => {
                          setBrowserField('local_path');
                          setBrowserOpen(true);
                        }}
                        edge="end"
                        title="Browse local directory"
                      >
                        <FolderOpenIcon />
                      </IconButton>
                    </InputAdornment>
                  ),
                }}
              />
            </Grid>
          </Grid>

          {testResult && (
            <Alert severity={testResult.success ? 'success' : 'error'} sx={{ mt: 2 }}>
              {testResult.message}
            </Alert>
          )}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={saving}>
          Cancel
        </Button>
        <Button onClick={handleSave} variant="contained" disabled={saving}>
          {saving ? <CircularProgress size={20} /> : 'Save'}
        </Button>
      </DialogActions>

      {/* Directory Browser Dialog */}
      {browserOpen && (
        <DirectoryBrowser
          open={browserOpen}
          onClose={() => setBrowserOpen(false)}
          onSelect={(path) => {
            handleChange(browserField, path);
            setBrowserOpen(false);
          }}
          // For local path browsing, always use endpointConfig with LOCAL type
          // For remote path browsing, use endpointId if available (editing), otherwise use endpointConfig (creating)
          endpointId={browserField === 'remote_path' ? endpoint?.id : undefined}
          endpointConfig={
            browserField === 'local_path'
              ? {
                  // For local path browsing, use LOCAL endpoint type
                  // Backend will prepend /mnt to the path
                  endpoint_type: 'local',
                  local_path: '/',
                  host: '',
                  port: 0,
                  username: '',
                  password: '',
                  remote_path: '',
                }
              : (!endpoint ? formData : undefined) // For remote path when creating new endpoint
          }
          initialPath={
            browserField === 'remote_path'
              ? formData.remote_path
              : (formData.local_path || '/')
          }
          title={browserField === 'remote_path' ? 'Browse Remote Directory' : 'Browse Local Directory'}
        />
      )}
    </Dialog>
  );
};

export default EndpointDialog;

