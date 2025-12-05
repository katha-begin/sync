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
  ListItemText,
  ListItemIcon,
  IconButton,
  Tooltip,
  FormControlLabel,
  Radio,
  RadioGroup,
  FormLabel,
  Grid,
  Chip,
  Switch,
} from '@mui/material';
import {
  Add as AddIcon,
  Remove as RemoveIcon,
  VideoFile as FileIcon,
  ClearAll as ClearAllIcon,
  SelectAll as SelectAllIcon,
  Deselect as DeselectIcon,
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

  // Episode/Sequence/Shot/Department filter state
  const [selectedEpisodes, setSelectedEpisodes] = useState<string[]>([]);
  const [selectedSequences, setSelectedSequences] = useState<string[]>([]);
  const [selectedShots, setSelectedShots] = useState<string[]>([]);
  const [selectedDepartments, setSelectedDepartments] = useState<string[]>([]);

  // Latest version only toggle
  const [latestOnly, setLatestOnly] = useState(true);

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
  const { data: structure, isLoading: structureLoading, error: structureError } = useQuery({
    queryKey: ['upload-local-structure', selectedEndpoint],
    queryFn: () => uploadService.getLocalStructure(selectedEndpoint),
    enabled: !!selectedEndpoint && open,
  });

  // Compute available episode names from structure
  const availableEpisodeNames = useMemo(() => {
    if (!structure?.episodes) return [];
    return structure.episodes.map((ep: LocalEpisode) => ep.name);
  }, [structure]);

  // Compute available sequences based on selected episodes
  const availableSequences = useMemo(() => {
    if (!structure?.episodes || selectedEpisodes.length === 0) return [];
    const sequences: { episode: string; sequence: string }[] = [];
    structure.episodes
      .filter((ep: LocalEpisode) => selectedEpisodes.includes(ep.name))
      .forEach((ep: LocalEpisode) => {
        ep.sequences?.forEach((seq: LocalSequence) => {
          sequences.push({ episode: ep.name, sequence: seq.name });
        });
      });
    return sequences;
  }, [structure, selectedEpisodes]);

  // Compute available shots based on selected sequences
  const availableShots = useMemo(() => {
    if (!structure?.episodes || selectedSequences.length === 0) return [];
    const shots: { episode: string; sequence: string; shot: string }[] = [];
    structure.episodes
      .filter((ep: LocalEpisode) => selectedEpisodes.includes(ep.name))
      .forEach((ep: LocalEpisode) => {
        ep.sequences
          ?.filter((seq: LocalSequence) => selectedSequences.includes(seq.name))
          .forEach((seq: LocalSequence) => {
            seq.shots?.forEach((shot: LocalShot) => {
              shots.push({ episode: ep.name, sequence: seq.name, shot: shot.name });
            });
          });
      });
    return shots;
  }, [structure, selectedEpisodes, selectedSequences]);

  // Compute available departments based on selected shots
  const availableDepartments = useMemo(() => {
    if (!structure?.episodes || selectedShots.length === 0) return [];
    const selectedShotSet = new Set(selectedShots);
    const departmentSet = new Set<string>();

    structure.episodes
      .filter((ep: LocalEpisode) => selectedEpisodes.includes(ep.name))
      .forEach((ep: LocalEpisode) => {
        ep.sequences
          ?.filter((seq: LocalSequence) => selectedSequences.includes(seq.name))
          .forEach((seq: LocalSequence) => {
            seq.shots
              ?.filter((shot: LocalShot) => selectedShotSet.has(`${ep.name}|${seq.name}|${shot.name}`))
              .forEach((shot: LocalShot) => {
                shot.departments?.forEach((dept) => {
                  departmentSet.add(dept.name);
                });
              });
          });
      });
    return Array.from(departmentSet).sort();
  }, [structure, selectedEpisodes, selectedSequences, selectedShots]);

  // Flatten structure into a list of files for display
  interface FlatFile {
    id: string;
    episode: string;
    sequence: string;
    shot: string;
    department: string;
    filename: string;
    path: string;
    version: string;
    size: number;
    isLatest: boolean;
  }

  const availableFiles = useMemo((): FlatFile[] => {
    if (!structure?.episodes || selectedShots.length === 0) return [];

    const selectedShotSet = new Set(selectedShots);
    const filterByDepartment = selectedDepartments.length > 0;
    const files: FlatFile[] = [];

    // Collect all files
    structure.episodes
      .filter((ep: LocalEpisode) => selectedEpisodes.includes(ep.name))
      .forEach((ep: LocalEpisode) => {
        ep.sequences
          ?.filter((seq: LocalSequence) => selectedSequences.includes(seq.name))
          .forEach((seq: LocalSequence) => {
            seq.shots
              ?.filter((shot: LocalShot) => selectedShotSet.has(`${ep.name}|${seq.name}|${shot.name}`))
              .forEach((shot: LocalShot) => {
                shot.departments
                  ?.filter((dept) => !filterByDepartment || selectedDepartments.includes(dept.name))
                  .forEach((dept) => {
                    dept.files?.forEach((file: LocalFile) => {
                      files.push({
                        id: `${ep.name}-${seq.name}-${shot.name}-${dept.name}-${file.filename}`,
                        episode: ep.name,
                        sequence: seq.name,
                        shot: shot.name,
                        department: dept.name,
                        filename: file.filename,
                        path: file.path,
                        version: file.version || '',
                        size: file.size,
                        isLatest: false, // Will be set below
                      });
                    });
                  });
              });
          });
      });

    // Determine latest version per shot+department
    const latestVersionMap = new Map<string, string>();
    files.forEach((f) => {
      const key = `${f.episode}|${f.sequence}|${f.shot}|${f.department}`;
      const currentLatest = latestVersionMap.get(key);
      if (!currentLatest || f.version > currentLatest) {
        latestVersionMap.set(key, f.version);
      }
    });

    // Mark latest files
    files.forEach((f) => {
      const key = `${f.episode}|${f.sequence}|${f.shot}|${f.department}`;
      f.isLatest = f.version === latestVersionMap.get(key);
    });

    // Sort by episode, sequence, shot, department, version (desc)
    files.sort((a, b) => {
      if (a.episode !== b.episode) return a.episode.localeCompare(b.episode);
      if (a.sequence !== b.sequence) return a.sequence.localeCompare(b.sequence);
      if (a.shot !== b.shot) return a.shot.localeCompare(b.shot);
      if (a.department !== b.department) return a.department.localeCompare(b.department);
      return b.version.localeCompare(a.version); // Latest first
    });

    return files;
  }, [structure, selectedEpisodes, selectedSequences, selectedShots, selectedDepartments]);

  // Filter by latestOnly toggle
  const displayedFiles = useMemo(() => {
    if (latestOnly) {
      return availableFiles.filter((f) => f.isLatest);
    }
    return availableFiles;
  }, [availableFiles, latestOnly]);

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
    setSelectedEpisodes([]);
    setSelectedSequences([]);
    setSelectedShots([]);
    setSelectedDepartments([]);
    setUploadQueue([]);
    setLatestOnly(true);
    setError(null);
  };

  // Handle close
  const handleClose = () => {
    resetForm();
    onClose();
  };

  // Check if file is in queue
  const isInQueue = (file: FlatFile) => {
    return uploadQueue.some(
      (item) =>
        item.episode === file.episode &&
        item.sequence === file.sequence &&
        item.shot === file.shot &&
        item.department === file.department &&
        item.filename === file.filename
    );
  };

  // Add file to queue
  const addFileToQueue = (file: FlatFile) => {
    if (!isInQueue(file)) {
      const newItem: UploadQueueItem = {
        id: generateId(),
        episode: file.episode,
        sequence: file.sequence,
        shot: file.shot,
        department: file.department,
        filename: file.filename,
        source_path: file.path,
        version: file.version,
        size: file.size,
        selected: true,
      };
      setUploadQueue((prev) => [...prev, newItem]);
    }
  };

  // Remove file from queue by matching fields
  const removeFileFromQueue = (file: FlatFile) => {
    setUploadQueue((prev) =>
      prev.filter(
        (item) =>
          !(item.episode === file.episode &&
            item.sequence === file.sequence &&
            item.shot === file.shot &&
            item.department === file.department &&
            item.filename === file.filename)
      )
    );
  };

  // Remove from queue by ID
  const removeFromQueue = (id: string) => {
    setUploadQueue((prev) => prev.filter((item) => item.id !== id));
  };

  // Clear queue
  const clearQueue = () => {
    setUploadQueue([]);
  };

  // Select all visible files
  const selectAll = () => {
    displayedFiles.forEach((file) => {
      if (!isInQueue(file)) {
        addFileToQueue(file);
      }
    });
  };

  // Deselect all visible files
  const deselectAll = () => {
    displayedFiles.forEach((file) => {
      removeFileFromQueue(file);
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

          {/* Episode/Sequence/Shot Filters - Show after endpoint is selected */}
          {selectedEndpoint && structureLoading && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
              <CircularProgress size={20} />
              <Typography variant="body2" color="text.secondary">
                Loading structure from local path...
              </Typography>
            </Box>
          )}

          {selectedEndpoint && structureError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              Failed to load structure: {(structureError as Error)?.message || 'Unknown error'}.
              Please ensure the endpoint's local_path is correctly configured and accessible.
            </Alert>
          )}

          {selectedEndpoint && !structureLoading && structure && (
            <Grid container spacing={2} sx={{ mb: 2 }}>
              <Grid item xs={12} sm={3}>
                <FormControl fullWidth size="small">
                  <InputLabel>Episodes</InputLabel>
                  <Select
                    multiple
                    value={selectedEpisodes}
                    onChange={(e) => {
                      setSelectedEpisodes(e.target.value as string[]);
                      setSelectedSequences([]);
                      setSelectedShots([]);
                      setSelectedDepartments([]);
                    }}
                    label="Episodes"
                    renderValue={(selected) => (
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                        {selected.map((value) => (
                          <Chip key={value} label={value} size="small" />
                        ))}
                      </Box>
                    )}
                  >
                    {availableEpisodeNames.map((ep: string) => (
                      <MenuItem key={ep} value={ep}>{ep}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>

              <Grid item xs={12} sm={3}>
                <FormControl fullWidth size="small" disabled={selectedEpisodes.length === 0}>
                  <InputLabel>Sequences</InputLabel>
                  <Select
                    multiple
                    value={selectedSequences}
                    onChange={(e) => {
                      setSelectedSequences(e.target.value as string[]);
                      setSelectedShots([]);
                      setSelectedDepartments([]);
                    }}
                    label="Sequences"
                    renderValue={(selected) => (
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                        {selected.map((value) => (
                          <Chip key={value} label={value} size="small" />
                        ))}
                      </Box>
                    )}
                  >
                    {availableSequences.map((seq) => (
                      <MenuItem key={`${seq.episode}|${seq.sequence}`} value={seq.sequence}>
                        {seq.sequence}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>

              <Grid item xs={12} sm={3}>
                <FormControl fullWidth size="small" disabled={selectedSequences.length === 0}>
                  <InputLabel>Shots</InputLabel>
                  <Select
                    multiple
                    value={selectedShots}
                    onChange={(e) => {
                      setSelectedShots(e.target.value as string[]);
                      setSelectedDepartments([]);
                    }}
                    label="Shots"
                    renderValue={(selected) => (
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                        {selected.map((value) => {
                          const [, , shot] = value.split('|');
                          return <Chip key={value} label={shot} size="small" />;
                        })}
                      </Box>
                    )}
                  >
                    {availableShots.map((shot) => {
                      const key = `${shot.episode}|${shot.sequence}|${shot.shot}`;
                      return (
                        <MenuItem key={key} value={key}>
                          {shot.episode} / {shot.sequence} / {shot.shot}
                        </MenuItem>
                      );
                    })}
                  </Select>
                </FormControl>
              </Grid>

              <Grid item xs={12} sm={3}>
                <FormControl fullWidth size="small" disabled={selectedShots.length === 0}>
                  <InputLabel>Departments</InputLabel>
                  <Select
                    multiple
                    value={selectedDepartments}
                    onChange={(e) => setSelectedDepartments(e.target.value as string[])}
                    label="Departments"
                    renderValue={(selected) => (
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                        {selected.map((value) => (
                          <Chip key={value} label={value} size="small" />
                        ))}
                      </Box>
                    )}
                  >
                    {availableDepartments.map((dept) => (
                      <MenuItem key={dept} value={dept}>{dept}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
            </Grid>
          )}

          {selectedEndpoint && structureLoading && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
              <CircularProgress size={20} />
              <Typography variant="body2">Loading structure...</Typography>
            </Box>
          )}

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
          {/* Left Panel - Available Files (Flat List) */}
          <Paper variant="outlined" sx={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <Box sx={{ p: 1, bgcolor: 'grey.100', borderBottom: 1, borderColor: 'divider' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Typography variant="subtitle2">Available Files ({displayedFiles.length})</Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <FormControlLabel
                    control={
                      <Switch
                        size="small"
                        checked={latestOnly}
                        onChange={(e) => setLatestOnly(e.target.checked)}
                      />
                    }
                    label={<Typography variant="caption">Latest Only</Typography>}
                    sx={{ mr: 1 }}
                  />
                  <Tooltip title="Select All">
                    <IconButton size="small" onClick={selectAll} disabled={displayedFiles.length === 0}>
                      <SelectAllIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Deselect All">
                    <IconButton size="small" onClick={deselectAll} disabled={displayedFiles.length === 0}>
                      <DeselectIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </Box>
              </Box>
            </Box>
            <Box sx={{ flex: 1, overflow: 'auto' }}>
              {!selectedEndpoint ? (
                <Box sx={{ p: 2, textAlign: 'center', color: 'text.secondary' }}>
                  Select an endpoint to browse files
                </Box>
              ) : selectedShots.length === 0 ? (
                <Box sx={{ p: 2, textAlign: 'center', color: 'text.secondary' }}>
                  Select Episode → Sequence → Shot to browse files
                </Box>
              ) : displayedFiles.length === 0 ? (
                <Box sx={{ p: 2, textAlign: 'center', color: 'text.secondary' }}>
                  No files found for selected filters
                </Box>
              ) : (
                <List dense disablePadding>
                  {displayedFiles.map((file) => {
                    const inQueue = isInQueue(file);
                    return (
                      <ListItem
                        key={file.id}
                        sx={{
                          bgcolor: inQueue ? 'action.selected' : 'inherit',
                          '&:hover': { bgcolor: inQueue ? 'action.selected' : 'action.hover' },
                        }}
                        secondaryAction={
                          <IconButton
                            size="small"
                            onClick={() => inQueue ? removeFileFromQueue(file) : addFileToQueue(file)}
                            color={inQueue ? 'error' : 'default'}
                          >
                            {inQueue ? <RemoveIcon fontSize="small" /> : <AddIcon fontSize="small" />}
                          </IconButton>
                        }
                      >
                        <ListItemIcon sx={{ minWidth: 32 }}>
                          <FileIcon fontSize="small" color={inQueue ? 'primary' : 'action'} />
                        </ListItemIcon>
                        <ListItemText
                          primary={
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                              <Typography variant="body2" noWrap sx={{ maxWidth: 280 }}>
                                {file.filename}
                              </Typography>
                              {!file.isLatest && !latestOnly && (
                                <Chip label="older" size="small" variant="outlined" sx={{ height: 16, fontSize: '0.65rem' }} />
                              )}
                            </Box>
                          }
                          secondary={`${file.department} | ${file.version || 'N/A'} | ${formatBytes(file.size)} | ${file.shot}`}
                        />
                      </ListItem>
                    );
                  })}
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

