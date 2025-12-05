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
  Typography,
  Alert,
  CircularProgress,
  Box,
  FormControl,
  InputLabel,
  Select,
  Chip,
  Radio,
  RadioGroup,
  FormControlLabel,
  FormLabel,
  Divider,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { endpointService } from '@/services/endpointService';
import { uploadService } from '@/services/uploadService';
import { ROUTES } from '@/utils/constants';
import {
  UploadConflictStrategy,
  UPLOAD_CONFLICT_STRATEGY_LABELS,
} from '@/types/upload';

interface CreateUploadTaskDialogProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

// Department options for comp output upload
const DEPARTMENTS = ['comp'];

const CreateUploadTaskDialog: React.FC<CreateUploadTaskDialogProps> = ({ open, onClose, onSuccess }) => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  // Form state - mirrors CreateTaskDialog for download (single endpoint)
  const [taskName, setTaskName] = useState('');
  const [notes, setNotes] = useState('');
  const [selectedEndpoint, setSelectedEndpoint] = useState('');
  const [selectedEpisodes, setSelectedEpisodes] = useState<string[]>([]);
  const [selectedSequences, setSelectedSequences] = useState<string[]>([]);
  const [selectedShots, setSelectedShots] = useState<string[]>([]);
  const [selectedDepartments, setSelectedDepartments] = useState<string[]>(['comp']);
  const [conflictStrategy, setConflictStrategy] = useState<UploadConflictStrategy>('skip');
  const [error, setError] = useState<string | null>(null);

  // Fetch endpoints - same as download dialog
  const { data: endpointsData } = useQuery({
    queryKey: ['endpoints'],
    queryFn: () => endpointService.getEndpoints(),
    enabled: open,
  });

  // Handle both paginated response and plain array
  const endpoints = Array.isArray(endpointsData)
    ? endpointsData
    : (endpointsData?.items || []);

  // Fetch LOCAL structure from endpoint (reverse of download which fetches FTP structure)
  const { data: structure, isLoading: structureLoading, refetch: refetchStructure } = useQuery({
    queryKey: ['upload-local-structure', selectedEndpoint],
    queryFn: () => uploadService.getLocalStructure(selectedEndpoint),
    enabled: !!selectedEndpoint && open,
  });

  // Trigger scan if structure is empty
  useEffect(() => {
    const triggerScanIfNeeded = async () => {
      if (selectedEndpoint && structure && !structureLoading) {
        const isEmpty = !structure.episodes || structure.episodes.length === 0;
        if (isEmpty) {
          try {
            await uploadService.scanLocalStructure(selectedEndpoint, false);
            refetchStructure();
          } catch (err) {
            console.error('Failed to scan local structure:', err);
            setError('Failed to scan local structure. Please try again.');
          }
        }
      }
    };
    triggerScanIfNeeded();
  }, [selectedEndpoint, structure, structureLoading, refetchStructure]);

  // Reset form when dialog closes
  useEffect(() => {
    if (!open) {
      setTaskName('');
      setNotes('');
      setSelectedEndpoint('');
      setSelectedEpisodes([]);
      setSelectedSequences([]);
      setSelectedShots([]);
      setSelectedDepartments(['comp']);
      setConflictStrategy('skip');
      setError(null);
    }
  }, [open]);

  // Filter sequences based on selected episodes
  const availableSequences = structure?.sequences?.filter((seq: any) =>
    selectedEpisodes.length === 0 || selectedEpisodes.includes(seq.episode)
  ) || [];

  // Filter shots based on selected episodes and sequences
  const availableShots = structure?.shots?.filter((shot: any) => {
    const episodeMatch = selectedEpisodes.length === 0 || selectedEpisodes.includes(shot.episode);
    const sequenceMatch = selectedSequences.length === 0 || selectedSequences.includes(shot.sequence);
    return episodeMatch && sequenceMatch;
  }) || [];

  // Create task mutation
  const createTaskMutation = useMutation({
    mutationFn: async () => {
      const shots = selectedShots.map(shotKey => {
        const [episode, sequence, shot] = shotKey.split('|');
        return { episode, sequence, shot };
      });

      return uploadService.createTask({
        endpoint_id: selectedEndpoint,
        task_name: taskName,
        shots,
        departments: selectedDepartments,
        conflict_strategy: conflictStrategy,
        notes: notes || undefined,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['upload-tasks'] });
      onSuccess();
      navigate(ROUTES.SHOT_UPLOAD);
    },
    onError: (err: any) => {
      setError(err.message || 'Failed to create upload task');
    },
  });

  const handleCreate = () => {
    if (!taskName.trim()) {
      setError('Please enter a task name');
      return;
    }
    if (!selectedEndpoint) {
      setError('Please select an endpoint');
      return;
    }
    if (selectedShots.length === 0) {
      setError('Please select at least one shot');
      return;
    }
    createTaskMutation.mutate();
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>Create Upload Task</DialogTitle>
      <DialogContent>
        <Box sx={{ mt: 2 }}>
          <Grid container spacing={2}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Task Name"
                value={taskName}
                onChange={(e) => setTaskName(e.target.value)}
                placeholder="e.g., Episode 01 Comp Upload"
                required
              />
            </Grid>

            <Grid item xs={12}>
              <TextField
                fullWidth
                select
                label="Endpoint"
                value={selectedEndpoint}
                onChange={(e) => setSelectedEndpoint(e.target.value)}
                helperText={`${endpoints.length} endpoints available - Select endpoint to upload comp files from local to FTP`}
                required
              >
                {endpoints.length > 0 ? (
                  endpoints.map((endpoint: any) => (
                    <MenuItem key={endpoint.id} value={endpoint.id}>
                      {endpoint.name} ({endpoint.endpoint_type?.toUpperCase()})
                    </MenuItem>
                  ))
                ) : (
                  <MenuItem disabled>No endpoints available</MenuItem>
                )}
              </TextField>
            </Grid>

            {selectedEndpoint && structureLoading && (
              <Grid item xs={12}>
                <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
                  <CircularProgress size={24} />
                  <Typography sx={{ ml: 2 }}>Loading local structure...</Typography>
                </Box>
              </Grid>
            )}

            {selectedEndpoint && !structureLoading && structure && (
              <>
                <Grid item xs={12} sm={6}>
                  <FormControl fullWidth>
                    <InputLabel>Episodes</InputLabel>
                    <Select
                      multiple
                      value={selectedEpisodes}
                      onChange={(e) => setSelectedEpisodes(e.target.value as string[])}
                      renderValue={(selected) => (
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                          {selected.map((value) => (
                            <Chip key={value} label={value} size="small" />
                          ))}
                        </Box>
                      )}
                    >
                      {(structure.episodes || []).map((ep: string) => (
                        <MenuItem key={ep} value={ep}>{ep}</MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>

                <Grid item xs={12} sm={6}>
                  <FormControl fullWidth>
                    <InputLabel>Sequences</InputLabel>
                    <Select
                      multiple
                      value={selectedSequences}
                      onChange={(e) => setSelectedSequences(e.target.value as string[])}
                      renderValue={(selected) => (
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                          {selected.map((value) => (
                            <Chip key={value} label={value} size="small" />
                          ))}
                        </Box>
                      )}
                    >
                      {availableSequences.map((seq: any) => (
                        <MenuItem key={`${seq.episode}|${seq.sequence}`} value={seq.sequence}>
                          {seq.sequence}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>

                <Grid item xs={12}>
                  <FormControl fullWidth>
                    <InputLabel>Shots</InputLabel>
                    <Select
                      multiple
                      value={selectedShots}
                      onChange={(e) => setSelectedShots(e.target.value as string[])}
                      renderValue={(selected) => (
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                          {selected.map((value) => {
                            const [, , shot] = value.split('|');
                            return <Chip key={value} label={shot} size="small" />;
                          })}
                        </Box>
                      )}
                    >
                      {availableShots.map((shot: any) => {
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

                <Grid item xs={12}>
                  <FormControl fullWidth>
                    <InputLabel>Departments</InputLabel>
                    <Select
                      multiple
                      value={selectedDepartments}
                      onChange={(e) => setSelectedDepartments(e.target.value as string[])}
                      renderValue={(selected) => (
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                          {selected.map((value) => (
                            <Chip key={value} label={value} size="small" />
                          ))}
                        </Box>
                      )}
                    >
                      {DEPARTMENTS.map((dept) => (
                        <MenuItem key={dept} value={dept}>{dept}</MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>

                {/* Conflict Strategy Section */}
                <Grid item xs={12}>
                  <Divider sx={{ my: 2 }} />
                  <Typography variant="subtitle2" gutterBottom fontWeight="bold">
                    File Conflict Handling
                  </Typography>
                </Grid>

                <Grid item xs={12}>
                  <FormControl component="fieldset">
                    <FormLabel component="legend">What to do with existing files on FTP?</FormLabel>
                    <RadioGroup
                      value={conflictStrategy}
                      onChange={(e) => setConflictStrategy(e.target.value as UploadConflictStrategy)}
                    >
                      <FormControlLabel
                        value="skip"
                        control={<Radio />}
                        label={
                          <Box>
                            <Typography variant="body2" fontWeight="bold">
                              {UPLOAD_CONFLICT_STRATEGY_LABELS.skip}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              Skip files that already exist on FTP (Recommended - Fast & Safe)
                            </Typography>
                          </Box>
                        }
                      />
                      <FormControlLabel
                        value="overwrite"
                        control={<Radio />}
                        label={
                          <Box>
                            <Typography variant="body2" fontWeight="bold">
                              {UPLOAD_CONFLICT_STRATEGY_LABELS.overwrite}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              Overwrite all existing files on FTP without checking
                            </Typography>
                          </Box>
                        }
                      />
                    </RadioGroup>
                  </FormControl>
                </Grid>
              </>
            )}

            <Grid item xs={12}>
              <Divider sx={{ my: 2 }} />
            </Grid>

            <Grid item xs={12}>
              <TextField
                fullWidth
                multiline
                rows={3}
                label="Notes (Optional)"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Add any notes about this upload task..."
              />
            </Grid>
          </Grid>

          {error && (
            <Alert severity="error" sx={{ mt: 2 }} onClose={() => setError(null)}>
              {error}
            </Alert>
          )}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          onClick={handleCreate}
          variant="contained"
          disabled={createTaskMutation.isPending}
        >
          {createTaskMutation.isPending ? 'Creating...' : 'Create Task'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default CreateUploadTaskDialog;

