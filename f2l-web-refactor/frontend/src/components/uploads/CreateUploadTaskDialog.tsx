import React, { useState, useMemo } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  MenuItem,
  Typography,
  Alert,
  CircularProgress,
  Box,
  FormControl,
  InputLabel,
  Select,
  Divider,
  Paper,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  ListItemIcon,
  IconButton,
  Tooltip,
  FormControlLabel,
  Radio,
  RadioGroup,
  FormLabel,
  Collapse,
  LinearProgress,
} from '@mui/material';
import {
  Add as AddIcon,
  Remove as RemoveIcon,
  ExpandMore as ExpandIcon,
  Folder as FolderIcon,
  VideoFile as FileIcon,
  ClearAll as ClearAllIcon,
  ChevronRight as ChevronRightIcon,
} from '@mui/icons-material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { endpointService } from '@/services/endpointService';
import { uploadService } from '@/services/uploadService';
import {
  LocalEpisode,
  LocalSequence,
  LocalShot,
  LocalFile,
  UploadQueueItem,
  CreateUploadTaskRequest,
  UploadConflictStrategy,
  UPLOAD_CONFLICT_STRATEGY_LABELS,
  formatBytes,
} from '@/types/upload';

// Simple unique ID generator (replaces uuid)
const generateId = () => `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;

interface CreateUploadTaskDialogProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

const CreateUploadTaskDialog: React.FC<CreateUploadTaskDialogProps> = ({
  open,
  onClose,
  onSuccess,
}) => {
  const queryClient = useQueryClient();

  // Form state - Single endpoint (has both local_path and remote_path)
  const [taskName, setTaskName] = useState('');
  const [notes, setNotes] = useState('');
  const [selectedEndpoint, setSelectedEndpoint] = useState('');
  const [conflictStrategy, setConflictStrategy] = useState<UploadConflictStrategy>('skip');
  const [error, setError] = useState<string | null>(null);

  // Structure navigation state
  const [expandedEpisodes, setExpandedEpisodes] = useState<Set<string>>(new Set());
  const [expandedSequences, setExpandedSequences] = useState<Set<string>>(new Set());
  const [expandedShots, setExpandedShots] = useState<Set<string>>(new Set());

  // Upload queue state
  const [uploadQueue, setUploadQueue] = useState<UploadQueueItem[]>([]);

  // Fetch endpoints
  const { data: endpointsData } = useQuery({
    queryKey: ['endpoints'],
    queryFn: () => endpointService.getEndpoints(),
    enabled: open,
  });

  const endpoints = Array.isArray(endpointsData)
    ? endpointsData
    : (endpointsData?.items || []);

  // Filter endpoints that have both local_path and remote_path configured (for upload)
  // These are typically FTP/SFTP endpoints that also have local_path set
  const uploadableEndpoints = endpoints.filter((e: any) =>
    e.local_path && e.remote_path && ['ftp', 'sftp'].includes(e.endpoint_type)
  );

  // Fetch local structure using selected endpoint's local_path
  const { data: structure, isLoading: structureLoading } = useQuery({
    queryKey: ['upload-local-structure', selectedEndpoint],
    queryFn: () => uploadService.getLocalStructure(selectedEndpoint),
    enabled: !!selectedEndpoint && open,
  });

  // Create task mutation
  const createTaskMutation = useMutation({
    mutationFn: (request: CreateUploadTaskRequest) => uploadService.createTask(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['upload-tasks'] });
      onSuccess();
      resetForm();
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || err.message || 'Failed to create task');
    },
  });

  // Reset form
  const resetForm = () => {
    setTaskName('');
    setNotes('');
    setSelectedEndpoint('');
    setConflictStrategy('skip');
    setUploadQueue([]);
    setExpandedEpisodes(new Set());
    setExpandedSequences(new Set());
    setExpandedShots(new Set());
    setError(null);
  };

  // Handle close
  const handleClose = () => {
    resetForm();
    onClose();
  };

  // Toggle episode expansion
  const toggleEpisode = (episodeName: string) => {
    setExpandedEpisodes((prev) => {
      const next = new Set(prev);
      if (next.has(episodeName)) next.delete(episodeName);
      else next.add(episodeName);
      return next;
    });
  };

  // Toggle sequence expansion
  const toggleSequence = (key: string) => {
    setExpandedSequences((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  // Toggle shot expansion
  const toggleShot = (key: string) => {
    setExpandedShots((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  // Add file to queue
  const addToQueue = (
    episode: string,
    sequence: string,
    shot: string,
    department: string,
    file: LocalFile
  ) => {
    const exists = uploadQueue.some(
      (item) =>
        item.episode === episode &&
        item.sequence === sequence &&
        item.shot === shot &&
        item.department === department &&
        item.filename === file.filename
    );

    if (!exists) {
      const newItem: UploadQueueItem = {
        id: generateId(),
        episode,
        sequence,
        shot,
        department,
        filename: file.filename,
        source_path: file.path,
        version: file.version,
        size: file.size,
        selected: true,
      };
      setUploadQueue((prev) => [...prev, newItem]);
    }
  };

  // Remove from queue
  const removeFromQueue = (id: string) => {
    setUploadQueue((prev) => prev.filter((item) => item.id !== id));
  };

  // Clear queue
  const clearQueue = () => {
    setUploadQueue([]);
  };

  // Add all files from a shot
  const addAllFromShot = (
    episode: string,
    sequence: string,
    shot: LocalShot
  ) => {
    shot.departments.forEach((dept) => {
      dept.files.forEach((file) => {
        addToQueue(episode, sequence, shot.name, dept.name, file);
      });
    });
  };

  // Calculate totals
  const totalSize = useMemo(
    () => uploadQueue.reduce((sum, item) => sum + item.size, 0),
    [uploadQueue]
  );

  // Handle submit
  const handleSubmit = () => {
    if (!taskName.trim()) {
      setError('Task name is required');
      return;
    }
    if (!selectedEndpoint) {
      setError('Please select an endpoint');
      return;
    }
    if (uploadQueue.length === 0) {
      setError('Please add at least one file to upload');
      return;
    }

    const request: CreateUploadTaskRequest = {
      endpoint_id: selectedEndpoint,
      task_name: taskName,
      items: uploadQueue.map((item) => ({
        episode: item.episode,
        sequence: item.sequence,
        shot: item.shot,
        department: item.department,
        filename: item.filename,
        source_path: item.source_path,
        version: item.version,
        size: item.size,
      })),
      conflict_strategy: conflictStrategy,
      notes: notes || undefined,
    };

    createTaskMutation.mutate(request);
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="xl" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          Create Upload Task
        </Box>
      </DialogTitle>

      <DialogContent dividers>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {/* Task Configuration */}
        <Box sx={{ mb: 3 }}>
          <TextField
            label="Task Name"
            value={taskName}
            onChange={(e) => setTaskName(e.target.value)}
            fullWidth
            required
            sx={{ mb: 2 }}
          />

          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>Endpoint</InputLabel>
            <Select
              value={selectedEndpoint}
              onChange={(e) => setSelectedEndpoint(e.target.value)}
              label="Endpoint"
            >
              {uploadableEndpoints.length === 0 ? (
                <MenuItem disabled value="">
                  No endpoints configured with both local and remote paths
                </MenuItem>
              ) : (
                uploadableEndpoints.map((ep: any) => (
                  <MenuItem key={ep.id} value={ep.id}>
                    {ep.name} ({ep.endpoint_type?.toUpperCase()})
                  </MenuItem>
                ))
              )}
            </Select>
          </FormControl>

          <FormControl component="fieldset" sx={{ mb: 2 }}>
            <FormLabel>Conflict Strategy</FormLabel>
            <RadioGroup
              row
              value={conflictStrategy}
              onChange={(e) => setConflictStrategy(e.target.value as UploadConflictStrategy)}
            >
              {Object.entries(UPLOAD_CONFLICT_STRATEGY_LABELS).map(([value, label]) => (
                <FormControlLabel
                  key={value}
                  value={value}
                  control={<Radio size="small" />}
                  label={label}
                />
              ))}
            </RadioGroup>
          </FormControl>
        </Box>

        <Divider sx={{ mb: 2 }} />

        {/* Split Panel: Left (Available) | Right (Queue) */}
        <Box sx={{ display: 'flex', gap: 2, height: 400 }}>
          {/* Left Panel - Available Files */}
          <Paper variant="outlined" sx={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <Box sx={{ p: 1, bgcolor: 'grey.100', borderBottom: 1, borderColor: 'divider' }}>
              <Typography variant="subtitle2">Available Files</Typography>
              {structureLoading && <LinearProgress sx={{ mt: 1 }} />}
            </Box>
            <Box sx={{ flex: 1, overflow: 'auto' }}>
              {!selectedEndpoint ? (
                <Box sx={{ p: 2, textAlign: 'center', color: 'text.secondary' }}>
                  Select an endpoint to browse files
                </Box>
              ) : structureLoading ? (
                <Box sx={{ p: 2, textAlign: 'center' }}>
                  <CircularProgress size={24} />
                </Box>
              ) : structure?.episodes?.length === 0 ? (
                <Box sx={{ p: 2, textAlign: 'center', color: 'text.secondary' }}>
                  No episodes found
                </Box>
              ) : (
                <List dense disablePadding>
                  {structure?.episodes?.map((episode: LocalEpisode) => (
                    <React.Fragment key={episode.name}>
                      <ListItemButton onClick={() => toggleEpisode(episode.name)} sx={{ pl: 1 }}>
                        <ListItemIcon sx={{ minWidth: 32 }}>
                          {expandedEpisodes.has(episode.name) ? <ExpandIcon /> : <ChevronRightIcon />}
                        </ListItemIcon>
                        <ListItemIcon sx={{ minWidth: 32 }}>
                          <FolderIcon color="primary" fontSize="small" />
                        </ListItemIcon>
                        <ListItemText primary={episode.name} />
                      </ListItemButton>
                      <Collapse in={expandedEpisodes.has(episode.name)}>
                        {episode.sequences?.map((seq: LocalSequence) => (
                          <React.Fragment key={`${episode.name}-${seq.name}`}>
                            <ListItemButton
                              onClick={() => toggleSequence(`${episode.name}-${seq.name}`)}
                              sx={{ pl: 4 }}
                            >
                              <ListItemIcon sx={{ minWidth: 32 }}>
                                {expandedSequences.has(`${episode.name}-${seq.name}`) ? (
                                  <ExpandIcon />
                                ) : (
                                  <ChevronRightIcon />
                                )}
                              </ListItemIcon>
                              <ListItemIcon sx={{ minWidth: 32 }}>
                                <FolderIcon color="secondary" fontSize="small" />
                              </ListItemIcon>
                              <ListItemText primary={seq.name} />
                            </ListItemButton>
                            <Collapse in={expandedSequences.has(`${episode.name}-${seq.name}`)}>
                              {seq.shots?.map((shot: LocalShot) => (
                                <React.Fragment key={`${episode.name}-${seq.name}-${shot.name}`}>
                                  <ListItemButton
                                    onClick={() =>
                                      toggleShot(`${episode.name}-${seq.name}-${shot.name}`)
                                    }
                                    sx={{ pl: 7 }}
                                  >
                                    <ListItemIcon sx={{ minWidth: 32 }}>
                                      {expandedShots.has(
                                        `${episode.name}-${seq.name}-${shot.name}`
                                      ) ? (
                                        <ExpandIcon />
                                      ) : (
                                        <ChevronRightIcon />
                                      )}
                                    </ListItemIcon>
                                    <ListItemIcon sx={{ minWidth: 32 }}>
                                      <FolderIcon fontSize="small" />
                                    </ListItemIcon>
                                    <ListItemText primary={shot.name} />
                                    <Tooltip title="Add all files from this shot">
                                      <IconButton
                                        size="small"
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          addAllFromShot(episode.name, seq.name, shot);
                                        }}
                                      >
                                        <AddIcon fontSize="small" />
                                      </IconButton>
                                    </Tooltip>
                                  </ListItemButton>
                                  <Collapse
                                    in={expandedShots.has(
                                      `${episode.name}-${seq.name}-${shot.name}`
                                    )}
                                  >
                                    {shot.departments?.map((dept) =>
                                      dept.files?.map((file) => (
                                        <ListItem
                                          key={`${episode.name}-${seq.name}-${shot.name}-${dept.name}-${file.filename}`}
                                          sx={{ pl: 10 }}
                                          secondaryAction={
                                            <IconButton
                                              size="small"
                                              onClick={() =>
                                                addToQueue(
                                                  episode.name,
                                                  seq.name,
                                                  shot.name,
                                                  dept.name,
                                                  file
                                                )
                                              }
                                            >
                                              <AddIcon fontSize="small" />
                                            </IconButton>
                                          }
                                        >
                                          <ListItemIcon sx={{ minWidth: 32 }}>
                                            <FileIcon fontSize="small" color="action" />
                                          </ListItemIcon>
                                          <ListItemText
                                            primary={file.filename}
                                            secondary={`${dept.name} | ${file.version || 'N/A'} | ${formatBytes(file.size)}`}
                                          />
                                        </ListItem>
                                      ))
                                    )}
                                  </Collapse>
                                </React.Fragment>
                              ))}
                            </Collapse>
                          </React.Fragment>
                        ))}
                      </Collapse>
                    </React.Fragment>
                  ))}
                </List>
              )}
            </Box>
          </Paper>

          {/* Right Panel - Upload Queue */}
          <Paper variant="outlined" sx={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <Box
              sx={{
                p: 1,
                bgcolor: 'primary.main',
                color: 'primary.contrastText',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <Typography variant="subtitle2">
                Upload Queue ({uploadQueue.length} files, {formatBytes(totalSize)})
              </Typography>
              <Tooltip title="Clear All">
                <IconButton size="small" onClick={clearQueue} sx={{ color: 'inherit' }}>
                  <ClearAllIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </Box>
            <Box sx={{ flex: 1, overflow: 'auto' }}>
              {uploadQueue.length === 0 ? (
                <Box sx={{ p: 2, textAlign: 'center', color: 'text.secondary' }}>
                  No files in queue. Add files from the left panel.
                </Box>
              ) : (
                <List dense disablePadding>
                  {uploadQueue.map((item) => (
                    <ListItem
                      key={item.id}
                      secondaryAction={
                        <IconButton
                          size="small"
                          onClick={() => removeFromQueue(item.id)}
                          color="error"
                        >
                          <RemoveIcon fontSize="small" />
                        </IconButton>
                      }
                    >
                      <ListItemIcon sx={{ minWidth: 32 }}>
                        <FileIcon fontSize="small" color="primary" />
                      </ListItemIcon>
                      <ListItemText
                        primary={item.filename}
                        secondary={`${item.episode}/${item.sequence}/${item.shot}/${item.department} | ${item.version || 'N/A'} | ${formatBytes(item.size)}`}
                      />
                    </ListItem>
                  ))}
                </List>
              )}
            </Box>
          </Paper>
        </Box>

        {/* Notes */}
        <TextField
          label="Notes (optional)"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          fullWidth
          multiline
          rows={2}
          sx={{ mt: 2 }}
        />
      </DialogContent>

      <DialogActions>
        <Button onClick={handleClose}>Cancel</Button>
        <Button
          variant="contained"
          onClick={handleSubmit}
          disabled={createTaskMutation.isPending || uploadQueue.length === 0}
        >
          {createTaskMutation.isPending ? <CircularProgress size={20} /> : 'Create Task'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default CreateUploadTaskDialog;

