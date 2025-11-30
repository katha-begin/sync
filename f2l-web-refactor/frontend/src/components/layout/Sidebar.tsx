import React from 'react';
import {
  Box,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Typography,
  Divider,
  IconButton,
  Tooltip,
  useTheme,
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  Storage as EndpointsIcon,
  Sync as SessionsIcon,
  PlaylistPlay as MultiSessionIcon,
  History as ExecutionsIcon,
  Description as LogsIcon,
  Settings as SettingsIcon,
  ChevronLeft as CollapseIcon,
  ChevronRight as ExpandIcon,
  Movie as ShotIcon,
  CloudDownload as DownloadIcon,
} from '@mui/icons-material';
import { useLocation, useNavigate } from 'react-router-dom';
import { useSidebar } from '@/stores/uiStore';
import { ROUTES } from '@/utils/constants';

interface SidebarProps {
  width: number;
  collapsed: boolean;
  open: boolean;
  onClose: () => void;
  isMobile: boolean;
}

interface NavigationItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  path: string;
  badge?: number;
}

const navigationItems: NavigationItem[] = [
  {
    id: 'dashboard',
    label: 'Dashboard',
    icon: <DashboardIcon />,
    path: ROUTES.DASHBOARD,
  },
  {
    id: 'endpoints',
    label: 'Endpoints',
    icon: <EndpointsIcon />,
    path: ROUTES.ENDPOINTS,
  },
  {
    id: 'sessions',
    label: 'Sessions',
    icon: <SessionsIcon />,
    path: ROUTES.SESSIONS,
  },
  {
    id: 'multi-sessions',
    label: 'Multi-Sessions',
    icon: <MultiSessionIcon />,
    path: ROUTES.MULTI_SESSIONS,
  },
  {
    id: 'shot-download',
    label: 'Shot Download',
    icon: <ShotIcon />,
    path: ROUTES.SHOT_DOWNLOAD,
  },
  {
    id: 'download-tasks',
    label: 'Download Tasks',
    icon: <DownloadIcon />,
    path: ROUTES.DOWNLOAD_TASKS,
  },
  {
    id: 'executions',
    label: 'Executions',
    icon: <ExecutionsIcon />,
    path: ROUTES.EXECUTIONS,
  },
  {
    id: 'logs',
    label: 'Logs',
    icon: <LogsIcon />,
    path: ROUTES.LOGS,
  },
];

const Sidebar: React.FC<SidebarProps> = ({
  width,
  collapsed,
  open,
  onClose,
  isMobile,
}) => {
  const theme = useTheme();
  const location = useLocation();
  const navigate = useNavigate();
  const { toggleSidebar } = useSidebar();

  const handleNavigate = (path: string) => {
    navigate(path);
    if (isMobile) {
      onClose();
    }
  };

  const isActive = (path: string) => {
    return location.pathname === path;
  };

  const sidebarContent = (
    <Box
      sx={{
        width: width,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: theme.palette.background.paper,
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: theme.spacing(2),
          minHeight: 64,
          borderBottom: `1px solid ${theme.palette.divider}`,
        }}
      >
        {!collapsed && (
          <Typography
            variant="h6"
            sx={{
              fontWeight: 600,
              color: theme.palette.primary.main,
              flexGrow: 1,
            }}
          >
            F2L Sync
          </Typography>
        )}
        
        {!isMobile && (
          <Tooltip title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
            <IconButton
              onClick={toggleSidebar}
              size="small"
              sx={{
                color: theme.palette.text.secondary,
              }}
            >
              {collapsed ? <ExpandIcon /> : <CollapseIcon />}
            </IconButton>
          </Tooltip>
        )}
      </Box>

      {/* Navigation */}
      <Box sx={{ flexGrow: 1, overflow: 'auto' }}>
        <List sx={{ padding: theme.spacing(1, 0) }}>
          {navigationItems.map((item) => (
            <ListItem key={item.id} disablePadding>
              <Tooltip
                title={collapsed ? item.label : ''}
                placement="right"
                disableHoverListener={!collapsed}
              >
                <ListItemButton
                  onClick={() => handleNavigate(item.path)}
                  selected={isActive(item.path)}
                  sx={{
                    margin: theme.spacing(0.5, 1),
                    borderRadius: theme.shape.borderRadius,
                    minHeight: 48,
                    justifyContent: collapsed ? 'center' : 'flex-start',
                    '&.Mui-selected': {
                      backgroundColor: theme.palette.primary.main,
                      color: theme.palette.primary.contrastText,
                      '&:hover': {
                        backgroundColor: theme.palette.primary.dark,
                      },
                      '& .MuiListItemIcon-root': {
                        color: theme.palette.primary.contrastText,
                      },
                    },
                    '&:hover': {
                      backgroundColor: theme.palette.action.hover,
                    },
                  }}
                >
                  <ListItemIcon
                    sx={{
                      minWidth: collapsed ? 0 : 40,
                      justifyContent: 'center',
                      color: isActive(item.path)
                        ? theme.palette.primary.contrastText
                        : theme.palette.text.secondary,
                    }}
                  >
                    {item.icon}
                  </ListItemIcon>
                  
                  {!collapsed && (
                    <ListItemText
                      primary={item.label}
                      sx={{
                        '& .MuiListItemText-primary': {
                          fontSize: '0.875rem',
                          fontWeight: isActive(item.path) ? 600 : 400,
                        },
                      }}
                    />
                  )}
                  
                  {!collapsed && item.badge && (
                    <Box
                      sx={{
                        backgroundColor: theme.palette.error.main,
                        color: theme.palette.error.contrastText,
                        borderRadius: '50%',
                        minWidth: 20,
                        height: 20,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                      }}
                    >
                      {item.badge}
                    </Box>
                  )}
                </ListItemButton>
              </Tooltip>
            </ListItem>
          ))}
        </List>

        <Divider sx={{ margin: theme.spacing(1, 2) }} />

        {/* Settings */}
        <List sx={{ padding: theme.spacing(1, 0) }}>
          <ListItem disablePadding>
            <Tooltip
              title={collapsed ? 'Settings' : ''}
              placement="right"
              disableHoverListener={!collapsed}
            >
              <ListItemButton
                onClick={() => handleNavigate(ROUTES.SETTINGS)}
                selected={isActive(ROUTES.SETTINGS)}
                sx={{
                  margin: theme.spacing(0.5, 1),
                  borderRadius: theme.shape.borderRadius,
                  minHeight: 48,
                  justifyContent: collapsed ? 'center' : 'flex-start',
                  '&.Mui-selected': {
                    backgroundColor: theme.palette.primary.main,
                    color: theme.palette.primary.contrastText,
                    '&:hover': {
                      backgroundColor: theme.palette.primary.dark,
                    },
                    '& .MuiListItemIcon-root': {
                      color: theme.palette.primary.contrastText,
                    },
                  },
                  '&:hover': {
                    backgroundColor: theme.palette.action.hover,
                  },
                }}
              >
                <ListItemIcon
                  sx={{
                    minWidth: collapsed ? 0 : 40,
                    justifyContent: 'center',
                    color: isActive(ROUTES.SETTINGS)
                      ? theme.palette.primary.contrastText
                      : theme.palette.text.secondary,
                  }}
                >
                  <SettingsIcon />
                </ListItemIcon>
                
                {!collapsed && (
                  <ListItemText
                    primary="Settings"
                    sx={{
                      '& .MuiListItemText-primary': {
                        fontSize: '0.875rem',
                        fontWeight: isActive(ROUTES.SETTINGS) ? 600 : 400,
                      },
                    }}
                  />
                )}
              </ListItemButton>
            </Tooltip>
          </ListItem>
        </List>
      </Box>
    </Box>
  );

  if (isMobile) {
    return (
      <Drawer
        variant="temporary"
        open={open}
        onClose={onClose}
        ModalProps={{
          keepMounted: true, // Better open performance on mobile
        }}
        sx={{
          '& .MuiDrawer-paper': {
            width: width,
            boxSizing: 'border-box',
          },
        }}
      >
        {sidebarContent}
      </Drawer>
    );
  }

  return (
    <Drawer
      variant="permanent"
      sx={{
        width: width,
        flexShrink: 0,
        '& .MuiDrawer-paper': {
          width: width,
          boxSizing: 'border-box',
          transition: theme.transitions.create('width', {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.enteringScreen,
          }),
        },
      }}
    >
      {sidebarContent}
    </Drawer>
  );
};

export default Sidebar;
