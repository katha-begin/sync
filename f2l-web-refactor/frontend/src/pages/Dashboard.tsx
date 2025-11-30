import React from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  LinearProgress,
  Chip,
  IconButton,
  useTheme,
} from '@mui/material';
import {
  Storage as EndpointsIcon,
  Sync as SessionsIcon,
  PlayArrow as ExecutionsIcon,
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
  Schedule as ScheduledIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';

// Mock data - in real app, this would come from API
const mockStats = {
  endpoints: {
    total: 12,
    active: 10,
    inactive: 2,
  },
  sessions: {
    total: 25,
    active: 18,
    scheduled: 7,
  },
  executions: {
    total: 156,
    running: 3,
    completed: 145,
    failed: 8,
  },
  recentExecutions: [
    {
      id: '1',
      sessionName: 'Production Backup',
      status: 'completed',
      progress: 100,
      startTime: '2024-01-15T10:30:00Z',
      duration: '2m 45s',
    },
    {
      id: '2',
      sessionName: 'Media Sync',
      status: 'running',
      progress: 65,
      startTime: '2024-01-15T11:15:00Z',
      duration: '1m 23s',
    },
    {
      id: '3',
      sessionName: 'Config Backup',
      status: 'failed',
      progress: 45,
      startTime: '2024-01-15T09:45:00Z',
      duration: '45s',
    },
  ],
};

const Dashboard: React.FC = () => {
  const theme = useTheme();

  const StatCard: React.FC<{
    title: string;
    value: number;
    icon: React.ReactNode;
    color: string;
    subtitle?: string;
  }> = ({ title, value, icon, color, subtitle }) => (
    <Card sx={{ height: '100%' }}>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 48,
              height: 48,
              borderRadius: 2,
              backgroundColor: `${color}20`,
              color: color,
              mr: 2,
            }}
          >
            {icon}
          </Box>
          <Box sx={{ flexGrow: 1 }}>
            <Typography variant="h4" sx={{ fontWeight: 600, color: color }}>
              {value}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {title}
            </Typography>
            {subtitle && (
              <Typography variant="caption" color="text.secondary">
                {subtitle}
              </Typography>
            )}
          </Box>
        </Box>
      </CardContent>
    </Card>
  );

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return theme.palette.success.main;
      case 'running':
        return theme.palette.info.main;
      case 'failed':
        return theme.palette.error.main;
      default:
        return theme.palette.grey[500];
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <SuccessIcon />;
      case 'running':
        return <ExecutionsIcon />;
      case 'failed':
        return <ErrorIcon />;
      default:
        return <ScheduledIcon />;
    }
  };

  return (
    <Box>
      {/* Page header */}
      <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 600, mb: 1 }}>
            Dashboard
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Overview of your sync operations and system status
          </Typography>
        </Box>
        <IconButton
          onClick={() => window.location.reload()}
          sx={{
            backgroundColor: theme.palette.primary.main,
            color: theme.palette.primary.contrastText,
            '&:hover': {
              backgroundColor: theme.palette.primary.dark,
            },
          }}
        >
          <RefreshIcon />
        </IconButton>
      </Box>

      {/* Statistics cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Total Endpoints"
            value={mockStats.endpoints.total}
            icon={<EndpointsIcon />}
            color={theme.palette.primary.main}
            subtitle={`${mockStats.endpoints.active} active, ${mockStats.endpoints.inactive} inactive`}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Sync Sessions"
            value={mockStats.sessions.total}
            icon={<SessionsIcon />}
            color={theme.palette.secondary.main}
            subtitle={`${mockStats.sessions.scheduled} scheduled`}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Total Executions"
            value={mockStats.executions.total}
            icon={<ExecutionsIcon />}
            color={theme.palette.info.main}
            subtitle={`${mockStats.executions.running} running`}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Success Rate"
            value={Math.round((mockStats.executions.completed / mockStats.executions.total) * 100)}
            icon={<SuccessIcon />}
            color={theme.palette.success.main}
            subtitle={`${mockStats.executions.failed} failed`}
          />
        </Grid>
      </Grid>

      {/* Recent executions */}
      <Grid container spacing={3}>
        <Grid item xs={12} lg={8}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 3, fontWeight: 600 }}>
                Recent Executions
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {mockStats.recentExecutions.map((execution) => (
                  <Box
                    key={execution.id}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      p: 2,
                      border: `1px solid ${theme.palette.divider}`,
                      borderRadius: 2,
                      '&:hover': {
                        backgroundColor: theme.palette.action.hover,
                      },
                    }}
                  >
                    <Box
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        width: 40,
                        height: 40,
                        borderRadius: 1,
                        backgroundColor: `${getStatusColor(execution.status)}20`,
                        color: getStatusColor(execution.status),
                        mr: 2,
                      }}
                    >
                      {getStatusIcon(execution.status)}
                    </Box>
                    <Box sx={{ flexGrow: 1 }}>
                      <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                        {execution.sessionName}
                      </Typography>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mt: 0.5 }}>
                        <Chip
                          label={execution.status}
                          size="small"
                          sx={{
                            backgroundColor: `${getStatusColor(execution.status)}20`,
                            color: getStatusColor(execution.status),
                            fontWeight: 500,
                          }}
                        />
                        <Typography variant="caption" color="text.secondary">
                          Duration: {execution.duration}
                        </Typography>
                      </Box>
                      {execution.status === 'running' && (
                        <Box sx={{ mt: 1 }}>
                          <LinearProgress
                            variant="determinate"
                            value={execution.progress}
                            sx={{ height: 6, borderRadius: 3 }}
                          />
                          <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5 }}>
                            {execution.progress}% complete
                          </Typography>
                        </Box>
                      )}
                    </Box>
                  </Box>
                ))}
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} lg={4}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 3, fontWeight: 600 }}>
                System Status
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="body2">API Status</Typography>
                  <Chip label="Online" color="success" size="small" />
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="body2">Database</Typography>
                  <Chip label="Connected" color="success" size="small" />
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="body2">Task Queue</Typography>
                  <Chip label="Running" color="info" size="small" />
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="body2">Storage</Typography>
                  <Chip label="85% Used" color="warning" size="small" />
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Dashboard;
