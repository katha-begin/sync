import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Breadcrumbs,
  Link,
  Typography,
  CircularProgress,
  Alert,
  Box,
  Chip,
} from '@mui/material';
import {
  Folder as FolderIcon,
  InsertDriveFile as FileIcon,
  NavigateNext as NavigateNextIcon,
  Home as HomeIcon,
} from '@mui/icons-material';
import axios from 'axios';

interface FileItem {
  name: string;
  path: string;
  size: number;
  modified: string | null;
  is_file: boolean;
  is_directory: boolean;
  permissions: string | null;
}

interface DirectoryListing {
  path: string;
  items: FileItem[];
  total_items: number;
  total_files: number;
  total_directories: number;
}

interface EndpointConfig {
  endpoint_type: string;
  host?: string;
  port?: number;
  username?: string;
  password?: string;
  remote_path?: string;
  local_path?: string;
}

interface DirectoryBrowserProps {
  open: boolean;
  onClose: () => void;
  onSelect: (path: string) => void;
  endpointId?: string;  // Optional - for saved endpoints
  endpointConfig?: EndpointConfig;  // Optional - for temporary configs
  initialPath?: string;
  title?: string;
}

const DirectoryBrowser: React.FC<DirectoryBrowserProps> = ({
  open,
  onClose,
  onSelect,
  endpointId,
  endpointConfig,
  initialPath = '/',
  title = 'Browse Directory',
}) => {
  const [currentPath, setCurrentPath] = useState(initialPath);
  const [listing, setListing] = useState<DirectoryListing | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const API_URL = '';  // Relative URL

  useEffect(() => {
    if (open) {
      loadDirectory(currentPath);
    }
  }, [open, currentPath, endpointId, endpointConfig]);

  const loadDirectory = async (path: string) => {
    setLoading(true);
    setError(null);

    try {
      let response;

      if (endpointId) {
        // Use saved endpoint
        response = await axios.get<DirectoryListing>(
          `${API_URL}/api/v1/browse/${endpointId}`,
          {
            params: {
              path,
              recursive: false,
              max_depth: 1,
            },
          }
        );
      } else if (endpointConfig) {
        // Use temporary config
        response = await axios.post<DirectoryListing>(
          `${API_URL}/api/v1/browse/config`,
          endpointConfig,
          {
            params: {
              path,
              recursive: false,
              max_depth: 1,
            },
          }
        );
      } else {
        throw new Error('Either endpointId or endpointConfig must be provided');
      }

      // Debug: Log the raw response
      console.log('DirectoryBrowser: Raw API response:', response.data);
      console.log('DirectoryBrowser: First item:', response.data.items[0]);

      // Map items to ensure is_directory is set correctly
      const mappedItems = response.data.items.map(item => {
        const mapped = {
          ...item,
          is_directory: !item.is_file, // Calculate is_directory from is_file
        };
        console.log(`Item: ${item.name}, is_file: ${item.is_file}, is_directory: ${mapped.is_directory}`);
        return mapped;
      });

      setListing({
        ...response.data,
        items: mappedItems,
      });
    } catch (err: any) {
      console.error('Failed to load directory:', err);
      setError(err.response?.data?.detail || 'Failed to load directory');
    } finally {
      setLoading(false);
    }
  };

  const handleNavigate = (path: string) => {
    setCurrentPath(path);
  };

  const handleItemClick = (item: FileItem) => {
    console.log('Item clicked:', item);
    if (item.is_directory) {
      console.log('Navigating to:', item.path);
      handleNavigate(item.path);
    }
  };

  const handleSelect = () => {
    onSelect(currentPath);
    onClose();
  };

  const getPathParts = (path: string): string[] => {
    if (path === '/') return ['/'];
    const parts = path.split('/').filter(Boolean);
    return ['/', ...parts];
  };

  const getPathUpTo = (index: number): string => {
    if (index === 0) return '/';
    const parts = getPathParts(currentPath);
    return '/' + parts.slice(1, index + 1).join('/');
  };

  const formatSize = (bytes: number): string => {
    if (bytes === 0) return '-';
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(2)} ${sizes[i]}`;
  };

  const formatDate = (dateStr: string | null): string => {
    if (!dateStr) return '-';
    try {
      const date = new Date(dateStr);
      return date.toLocaleString();
    } catch {
      return '-';
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        {/* Breadcrumb Navigation */}
        <Box sx={{ mb: 2 }}>
          <Breadcrumbs separator={<NavigateNextIcon fontSize="small" />}>
            {getPathParts(currentPath).map((part, index) => {
              const path = getPathUpTo(index);
              const isLast = index === getPathParts(currentPath).length - 1;

              return isLast ? (
                <Typography key={index} color="text.primary">
                  {part === '/' ? <HomeIcon fontSize="small" /> : part}
                </Typography>
              ) : (
                <Link
                  key={index}
                  component="button"
                  variant="body1"
                  onClick={() => handleNavigate(path)}
                  sx={{ display: 'flex', alignItems: 'center' }}
                >
                  {part === '/' ? <HomeIcon fontSize="small" /> : part}
                </Link>
              );
            })}
          </Breadcrumbs>
        </Box>

        {/* Current Path Display */}
        <Box sx={{ mb: 2 }}>
          <Typography variant="body2" color="text.secondary">
            Current Path: <strong>{currentPath}</strong>
          </Typography>
          {listing && (
            <Box sx={{ mt: 1, display: 'flex', gap: 1 }}>
              <Chip
                label={`${listing.total_directories} folders`}
                size="small"
                color="primary"
                variant="outlined"
              />
              <Chip
                label={`${listing.total_files} files`}
                size="small"
                color="secondary"
                variant="outlined"
              />
            </Box>
          )}
        </Box>

        {/* Loading State */}
        {loading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
            <CircularProgress />
          </Box>
        )}

        {/* Error State */}
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {/* Directory Listing */}
        {!loading && !error && listing && (
          <List sx={{ maxHeight: 400, overflow: 'auto' }}>
            {listing.items.length === 0 ? (
              <ListItem>
                <ListItemText
                  primary="Empty directory"
                  secondary="No files or folders found"
                />
              </ListItem>
            ) : (
              listing.items
                .sort((a, b) => {
                  // Directories first, then files
                  if (a.is_directory && !b.is_directory) return -1;
                  if (!a.is_directory && b.is_directory) return 1;
                  return a.name.localeCompare(b.name);
                })
                .map((item, index) => (
                  <ListItem key={index} disablePadding>
                    <ListItemButton
                      onClick={() => item.is_directory && handleItemClick(item)}
                      disabled={!item.is_directory}
                      sx={{
                        cursor: item.is_directory ? 'pointer' : 'default',
                        '&:hover': {
                          backgroundColor: item.is_directory ? 'action.hover' : 'transparent',
                        },
                      }}
                    >
                      <ListItemIcon>
                        {item.is_directory ? (
                          <FolderIcon color="primary" />
                        ) : (
                          <FileIcon color="action" />
                        )}
                      </ListItemIcon>
                      <ListItemText
                        primary={item.name}
                        secondary={
                          <Box component="span" sx={{ display: 'flex', gap: 2 }}>
                            <span>{formatSize(item.size)}</span>
                            <span>{formatDate(item.modified)}</span>
                            {item.permissions && <span>{item.permissions}</span>}
                          </Box>
                        }
                      />
                    </ListItemButton>
                  </ListItem>
                ))
            )}
          </List>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button onClick={handleSelect} variant="contained" color="primary">
          Select This Directory
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default DirectoryBrowser;

