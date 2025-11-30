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
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { endpointService } from '@/services/endpointService';
import { shotService } from '@/services/shotService';
import { ROUTES } from '@/utils/constants';

interface CreateTaskDialogProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

const DEPARTMENTS = ['anim', 'lighting'];

const CreateTaskDialog: React.FC<CreateTaskDialogProps> = ({ open, onClose, onSuccess }) => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const [taskName, setTaskName] = useState('');
  const [notes, setNotes] = useState('');
  const [selectedEndpoint, setSelectedEndpoint] = useState('');
  const [selectedEpisodes, setSelectedEpisodes] = useState<string[]>([]);
  const [selectedSequences, setSelectedSequences] = useState<string[]>([]);
  const [selectedShots, setSelectedShots] = useState<string[]>([]);
  const [selectedDepartments, setSelectedDepartments] = useState<string[]>(['anim', 'lighting']);
  const [error, setError] = useState<string | null>(null);

  const { data: endpointsData } = useQuery({
    queryKey: ['endpoints'],
    queryFn: () => endpointService.getEndpoints(),
    enabled: open,
  });

  // Handle both paginated response and plain array
  const endpoints = Array.isArray(endpointsData)
    ? endpointsData
    : (endpointsData?.items || []);

  const { data: structure, isLoading: structureLoading, refetch: refetchStructure } = useQuery({
    queryKey: ['shot-structure', selectedEndpoint],
    queryFn: () => shotService.getStructure(selectedEndpoint, []),
    enabled: !!selectedEndpoint && open,
  });

  // Trigger scan if structure is empty or cache is invalid
  useEffect(() => {
    const triggerScanIfNeeded = async () => {
      if (selectedEndpoint && structure && !structureLoading) {
        // Check if structure is empty or cache is invalid
        const isEmpty = structure.episodes.length === 0;
        const cacheInvalid = structure.cache_valid === false;

        if (isEmpty || cacheInvalid) {
          try {
            // Trigger scan
            await shotService.scanStructure(selectedEndpoint, false);
            // Refetch structure after scan
            refetchStructure();
          } catch (err) {
            console.error('Failed to scan structure:', err);
            setError('Failed to scan endpoint structure. Please try again.');
          }
        }
      }
    };

    triggerScanIfNeeded();
  }, [selectedEndpoint, structure, structureLoading, refetchStructure]);

  useEffect(() => {
    if (!open) {
      setTaskName('');
      setNotes('');
      setSelectedEndpoint('');
      setSelectedEpisodes([]);
      setSelectedSequences([]);
      setSelectedShots([]);
      setSelectedDepartments(['anim', 'lighting']);
      setError(null);
    }
  }, [open]);

  const availableSequences = structure?.sequences.filter((seq: any) =>
    selectedEpisodes.length === 0 || selectedEpisodes.includes(seq.episode)
  ) || [];

  const availableShots = structure?.shots.filter((shot: any) => {
    const episodeMatch = selectedEpisodes.length === 0 || selectedEpisodes.includes(shot.episode);
    const sequenceMatch = selectedSequences.length === 0 || selectedSequences.includes(shot.sequence);
    return episodeMatch && sequenceMatch;
  }) || [];

  const createTaskMutation = useMutation({
    mutationFn: async () => {
      const shots = selectedShots.map(shotKey => {
        const [episode, sequence, shot] = shotKey.split('|');
        return { episode, sequence, shot };
      });

      return shotService.createTask({
        endpoint_id: selectedEndpoint,
        task_name: taskName,
        shots,
        departments: selectedDepartments,
        notes: notes || undefined,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['download-tasks'] });
      onSuccess();
      navigate(ROUTES.DOWNLOAD_TASKS);
    },
    onError: (err: any) => {
      setError(err.message || 'Failed to create task');
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
      <DialogTitle>Create Download Task</DialogTitle>
      <DialogContent>
        <Box sx={{ mt: 2 }}>
          <Grid container spacing={2}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Task Name"
                value={taskName}
                onChange={(e) => setTaskName(e.target.value)}
                placeholder="e.g., Episode 01 Animation Download"
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
                helperText={`${endpoints.length} endpoints available`}
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
                  <Typography sx={{ ml: 2 }}>Loading structure...</Typography>
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
                      {structure.episodes.map((ep: string) => (
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
              </>
            )}

            <Grid item xs={12}>
              <TextField
                fullWidth
                multiline
                rows={3}
                label="Notes (Optional)"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Add any notes about this download task..."
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

export default CreateTaskDialog;
