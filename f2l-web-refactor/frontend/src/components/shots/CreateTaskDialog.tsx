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
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { endpointService } from '@/services/endpointService';
import { shotService } from '@/services/shotService';
import { ROUTES } from '@/utils/constants';
import {
  VersionStrategy,
  ConflictStrategy,
  VERSION_STRATEGY_LABELS,
  CONFLICT_STRATEGY_LABELS,
  ShotComparison,
} from '@/types/shot';

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
  const [versionStrategy, setVersionStrategy] = useState<VersionStrategy>('latest');
  const [specificVersion, setSpecificVersion] = useState('');
  const [customVersions, setCustomVersions] = useState<Record<string, string[]>>({});
  const [conflictStrategy, setConflictStrategy] = useState<ConflictStrategy>('skip');
  const [error, setError] = useState<string | null>(null);
  const [comparisonResults, setComparisonResults] = useState<ShotComparison[]>([]);
  const [showComparison, setShowComparison] = useState(false);

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
      setVersionStrategy('latest');
      setSpecificVersion('');
      setCustomVersions({});
      setConflictStrategy('skip');
      setError(null);
      setComparisonResults([]);
      setShowComparison(false);
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

  // Comparison mutation to get available versions
  const compareMutation = useMutation({
    mutationFn: async () => {
      const shots = selectedShots.map(shotKey => {
        const [episode, sequence, shot] = shotKey.split('|');
        return { episode, sequence, shot };
      });

      return shotService.compareShots({
        endpoint_id: selectedEndpoint,
        shots,
        departments: selectedDepartments,
      });
    },
    onSuccess: (data) => {
      setComparisonResults(data);
      setShowComparison(true);
      setError(null);
    },
    onError: (err: any) => {
      setError(err.message || 'Failed to compare shots');
    },
  });

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
        version_strategy: versionStrategy,
        specific_version: versionStrategy === 'specific' ? specificVersion : undefined,
        custom_versions: versionStrategy === 'custom' ? customVersions : undefined,
        conflict_strategy: conflictStrategy,
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

  const handleCompare = () => {
    if (!selectedEndpoint) {
      setError('Please select an endpoint');
      return;
    }
    if (selectedShots.length === 0) {
      setError('Please select at least one shot');
      return;
    }
    if (selectedDepartments.length === 0) {
      setError('Please select at least one department');
      return;
    }
    setError(null);
    compareMutation.mutate();
  };

  const handleCustomVersionToggle = (shotKey: string, version: string) => {
    setCustomVersions(prev => {
      const currentVersions = prev[shotKey] || [];
      const isSelected = currentVersions.includes(version);

      if (isSelected) {
        // Remove version
        return {
          ...prev,
          [shotKey]: currentVersions.filter(v => v !== version),
        };
      } else {
        // Add version
        return {
          ...prev,
          [shotKey]: [...currentVersions, version].sort(),
        };
      }
    });
  };

  const handleSelectAllVersions = (shotKey: string, versions: string[]) => {
    setCustomVersions(prev => ({
      ...prev,
      [shotKey]: [...versions].sort(),
    }));
  };

  const handleClearVersions = (shotKey: string) => {
    setCustomVersions(prev => ({
      ...prev,
      [shotKey]: [],
    }));
  };

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
    if (versionStrategy === 'specific' && !specificVersion.trim()) {
      setError('Please enter a version number for specific version strategy');
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

                {/* Compare Button */}
                <Grid item xs={12}>
                  <Divider sx={{ my: 2 }} />
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <Button
                      variant="contained"
                      onClick={handleCompare}
                      disabled={compareMutation.isPending || selectedShots.length === 0 || selectedDepartments.length === 0}
                    >
                      {compareMutation.isPending ? 'Comparing...' : 'Compare & Check Versions'}
                    </Button>
                    <Typography variant="caption" color="text.secondary">
                      Click to scan available versions for selected shots
                    </Typography>
                  </Box>
                </Grid>

                {/* Comparison Results Table */}
                {showComparison && comparisonResults.length > 0 && (
                  <>
                    <Grid item xs={12}>
                      <Divider sx={{ my: 2 }} />
                      <Typography variant="subtitle2" gutterBottom fontWeight="bold">
                        Available Versions ({comparisonResults.length} items)
                      </Typography>
                    </Grid>

                    <Grid item xs={12}>
                      <TableContainer component={Paper} sx={{ maxHeight: 400 }}>
                        <Table size="small" stickyHeader>
                          <TableHead>
                            <TableRow>
                              <TableCell>Shot</TableCell>
                              <TableCell>Department</TableCell>
                              <TableCell>Latest Version</TableCell>
                              <TableCell>Available Versions</TableCell>
                              <TableCell>Status</TableCell>
                            </TableRow>
                          </TableHead>
                          <TableBody>
                            {comparisonResults.map((item, index) => {
                              return (
                                <TableRow key={index}>
                                  <TableCell>
                                    <Typography variant="body2" fontFamily="monospace">
                                      {item.episode}/{item.sequence}/{item.shot}
                                    </Typography>
                                  </TableCell>
                                  <TableCell>{item.department}</TableCell>
                                  <TableCell>
                                    <Chip
                                      label={item.latest_version || 'N/A'}
                                      size="small"
                                      color="primary"
                                    />
                                  </TableCell>
                                  <TableCell>
                                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                                      {item.available_versions && item.available_versions.length > 0 ? (
                                        item.available_versions.map((v) => (
                                          <Chip key={v} label={v} size="small" variant="outlined" />
                                        ))
                                      ) : (
                                        <Typography variant="caption" color="text.secondary">None</Typography>
                                      )}
                                    </Box>
                                  </TableCell>
                                  <TableCell>
                                    <Chip
                                      label={item.status}
                                      size="small"
                                      color={item.status === 'error' ? 'error' : 'default'}
                                    />
                                  </TableCell>
                                </TableRow>
                              );
                            })}
                          </TableBody>
                        </Table>
                      </TableContainer>
                    </Grid>

                    {/* Version Strategy Section */}
                    <Grid item xs={12}>
                      <Divider sx={{ my: 2 }} />
                      <Typography variant="subtitle2" gutterBottom fontWeight="bold">
                        Version Selection Strategy
                      </Typography>
                    </Grid>

                    <Grid item xs={12}>
                      <FormControl component="fieldset">
                        <FormLabel component="legend">How to select versions?</FormLabel>
                        <RadioGroup
                          value={versionStrategy}
                          onChange={(e) => {
                            const newStrategy = e.target.value as VersionStrategy;
                            setVersionStrategy(newStrategy);
                            if (newStrategy !== 'custom') {
                              setCustomVersions({});
                            }
                          }}
                        >
                          <FormControlLabel
                            value="latest"
                            control={<Radio />}
                            label={
                              <Box>
                                <Typography variant="body2" fontWeight="bold">
                                  {VERSION_STRATEGY_LABELS.latest}
                                </Typography>
                                <Typography variant="caption" color="text.secondary">
                                  Download the newest version of each shot (Recommended)
                                </Typography>
                              </Box>
                            }
                          />
                          <FormControlLabel
                            value="specific"
                            control={<Radio />}
                            label={
                              <Box>
                                <Typography variant="body2" fontWeight="bold">
                                  {VERSION_STRATEGY_LABELS.specific}
                                </Typography>
                                <Typography variant="caption" color="text.secondary">
                                  Try to download the same version for all shots
                                </Typography>
                              </Box>
                            }
                          />
                          <FormControlLabel
                            value="custom"
                            control={<Radio />}
                            label={
                              <Box>
                                <Typography variant="body2" fontWeight="bold">
                                  {VERSION_STRATEGY_LABELS.custom}
                                </Typography>
                                <Typography variant="caption" color="text.secondary">
                                  Select version individually for each shot
                                </Typography>
                              </Box>
                            }
                          />
                        </RadioGroup>
                      </FormControl>
                    </Grid>

                    {versionStrategy === 'specific' && (
                      <Grid item xs={12}>
                        <FormControl fullWidth>
                          <InputLabel>Select Version</InputLabel>
                          <Select
                            value={specificVersion}
                            onChange={(e) => setSpecificVersion(e.target.value)}
                            label="Select Version"
                          >
                            {/* Get unique versions from all comparison results */}
                            {Array.from(new Set(
                              comparisonResults.flatMap(item => item.available_versions || [])
                            )).sort().reverse().map((version) => (
                              <MenuItem key={version} value={version}>{version}</MenuItem>
                            ))}
                          </Select>
                        </FormControl>
                      </Grid>
                    )}

                    {versionStrategy === 'custom' && (
                      <Grid item xs={12}>
                        <Typography variant="body2" color="text.secondary" gutterBottom>
                          Select version for each shot:
                        </Typography>
                        <TableContainer component={Paper} sx={{ maxHeight: 300 }}>
                          <Table size="small" stickyHeader>
                            <TableHead>
                              <TableRow>
                                <TableCell>Shot</TableCell>
                                <TableCell>Department</TableCell>
                                <TableCell>Select Versions (click to toggle)</TableCell>
                              </TableRow>
                            </TableHead>
                            <TableBody>
                              {comparisonResults.map((item, index) => {
                                const shotKey = `${item.episode}|${item.sequence}|${item.shot}|${item.department}`;
                                const selectedVersions = customVersions[shotKey] || [];
                                const hasSelection = selectedVersions.length > 0;
                                return (
                                  <TableRow key={index}>
                                    <TableCell>
                                      <Typography variant="body2" fontFamily="monospace">
                                        {item.episode}/{item.sequence}/{item.shot}
                                      </Typography>
                                    </TableCell>
                                    <TableCell>{item.department}</TableCell>
                                    <TableCell>
                                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, alignItems: 'center' }}>
                                        {item.available_versions && item.available_versions.length > 0 ? (
                                          <>
                                            {item.available_versions.map((v) => {
                                              const isSelected = selectedVersions.includes(v);
                                              const isLatest = v === item.latest_version;
                                              return (
                                                <Chip
                                                  key={v}
                                                  label={isLatest ? `${v} (latest)` : v}
                                                  size="small"
                                                  onClick={() => handleCustomVersionToggle(shotKey, v)}
                                                  color={isSelected ? 'primary' : 'default'}
                                                  variant={isSelected ? 'filled' : 'outlined'}
                                                  sx={{
                                                    cursor: 'pointer',
                                                    fontWeight: isLatest ? 'bold' : 'normal',
                                                  }}
                                                />
                                              );
                                            })}
                                            <Box sx={{ ml: 1, display: 'flex', gap: 0.5 }}>
                                              <Chip
                                                label="All"
                                                size="small"
                                                onClick={() => handleSelectAllVersions(shotKey, item.available_versions || [])}
                                                color="secondary"
                                                variant="outlined"
                                                sx={{ cursor: 'pointer', fontSize: '0.7rem' }}
                                              />
                                              {hasSelection && (
                                                <Chip
                                                  label="Clear"
                                                  size="small"
                                                  onClick={() => handleClearVersions(shotKey)}
                                                  color="error"
                                                  variant="outlined"
                                                  sx={{ cursor: 'pointer', fontSize: '0.7rem' }}
                                                />
                                              )}
                                            </Box>
                                          </>
                                        ) : (
                                          <Typography variant="body2" color="text.secondary">
                                            No versions available
                                          </Typography>
                                        )}
                                      </Box>
                                    </TableCell>
                                  </TableRow>
                                );
                              })}
                            </TableBody>
                          </Table>
                        </TableContainer>
                      </Grid>
                    )}
                  </>
                )}

                {/* Conflict Strategy Section */}
                <Grid item xs={12}>
                  <Divider sx={{ my: 2 }} />
                  <Typography variant="subtitle2" gutterBottom fontWeight="bold">
                    File Conflict Handling
                  </Typography>
                </Grid>

                <Grid item xs={12}>
                  <FormControl component="fieldset">
                    <FormLabel component="legend">What to do with existing files?</FormLabel>
                    <RadioGroup
                      value={conflictStrategy}
                      onChange={(e) => setConflictStrategy(e.target.value as ConflictStrategy)}
                    >
                      <FormControlLabel
                        value="skip"
                        control={<Radio />}
                        label={
                          <Box>
                            <Typography variant="body2" fontWeight="bold">
                              {CONFLICT_STRATEGY_LABELS.skip}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              Skip files that already exist locally (Recommended - Fast & Safe)
                            </Typography>
                          </Box>
                        }
                      />
                      <FormControlLabel
                        value="compare"
                        control={<Radio />}
                        label={
                          <Box>
                            <Typography variant="body2" fontWeight="bold">
                              {CONFLICT_STRATEGY_LABELS.compare}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              Compare file size and date, update if FTP version is newer
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
                              {CONFLICT_STRATEGY_LABELS.overwrite}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              Overwrite all existing files without checking
                            </Typography>
                          </Box>
                        }
                      />
                      <FormControlLabel
                        value="keep_both"
                        control={<Radio />}
                        label={
                          <Box>
                            <Typography variant="body2" fontWeight="bold">
                              {CONFLICT_STRATEGY_LABELS.keep_both}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              Rename existing files and download new ones
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
