import React from 'react';
import {
  Box,
  CssBaseline,
  ThemeProvider,
  useMediaQuery,
} from '@mui/material';
import { getTheme } from '@/styles/theme';
import { useTheme, useSidebar } from '@/stores/uiStore';
import Sidebar from './Sidebar';
import Header from './Header';
import NotificationContainer from '../common/NotificationContainer';

interface AppLayoutProps {
  children: React.ReactNode;
}

const SIDEBAR_WIDTH = 280;
const SIDEBAR_COLLAPSED_WIDTH = 64;

const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  const { themeMode } = useTheme();
  const { sidebarCollapsed, sidebarOpen, setSidebarOpen } = useSidebar();
  const theme = getTheme(themeMode);
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  const handleSidebarToggle = () => {
    if (isMobile) {
      setSidebarOpen(!sidebarOpen);
    }
  };

  const sidebarWidth = isMobile 
    ? SIDEBAR_WIDTH 
    : sidebarCollapsed 
      ? SIDEBAR_COLLAPSED_WIDTH 
      : SIDEBAR_WIDTH;

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ display: 'flex', minHeight: '100vh' }}>
        {/* Sidebar */}
        <Sidebar
          width={sidebarWidth}
          collapsed={sidebarCollapsed}
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          isMobile={isMobile}
        />

        {/* Main content area */}
        <Box
          component="main"
          sx={{
            flexGrow: 1,
            display: 'flex',
            flexDirection: 'column',
            minHeight: '100vh',
            marginLeft: isMobile ? 0 : `${sidebarWidth}px`,
            transition: theme.transitions.create(['margin-left'], {
              easing: theme.transitions.easing.sharp,
              duration: theme.transitions.duration.leavingScreen,
            }),
          }}
        >
          {/* Header */}
          <Header onMenuClick={handleSidebarToggle} />

          {/* Page content */}
          <Box
            sx={{
              flexGrow: 1,
              padding: theme.spacing(3),
              backgroundColor: theme.palette.background.default,
              minHeight: 'calc(100vh - 64px)', // Subtract header height
            }}
          >
            {children}
          </Box>
        </Box>

        {/* Notifications */}
        <NotificationContainer />
      </Box>
    </ThemeProvider>
  );
};

export default AppLayout;
