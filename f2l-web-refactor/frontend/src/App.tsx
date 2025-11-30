import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import AppLayout from '@/components/layout/AppLayout';
import Dashboard from '@/pages/Dashboard';
import Endpoints from '@/pages/Endpoints';
import Sessions from '@/pages/Sessions';
import ShotDownload from '@/pages/ShotDownload';
import DownloadTasks from '@/pages/DownloadTasks';
import { useAuth } from '@/stores/authStore';
import { ROUTES } from '@/utils/constants';
import LoadingSpinner from '@/components/common/LoadingSpinner';

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
  },
});

// Mock login page component
const LoginPage: React.FC = () => {
  const { login, isLoading } = useAuth();

  const handleLogin = async () => {
    await login({ username: 'admin', password: 'admin' });
  };

  return (
    <div style={{ 
      display: 'flex', 
      justifyContent: 'center', 
      alignItems: 'center', 
      minHeight: '100vh',
      flexDirection: 'column',
      gap: '20px'
    }}>
      <h1>F2L Sync Login</h1>
      <button 
        onClick={handleLogin} 
        disabled={isLoading}
        style={{
          padding: '10px 20px',
          fontSize: '16px',
          backgroundColor: '#1976d2',
          color: 'white',
          border: 'none',
          borderRadius: '4px',
          cursor: isLoading ? 'not-allowed' : 'pointer'
        }}
      >
        {isLoading ? 'Logging in...' : 'Login as Admin'}
      </button>
      <p style={{ color: '#666', fontSize: '14px' }}>
        Demo credentials: admin/admin
      </p>
    </div>
  );
};

// Placeholder components for other pages
const MultiSessions: React.FC = () => (
  <div>
    <h1>Multi-Sessions</h1>
    <p>Multi-session management page - Coming soon!</p>
  </div>
);

const Executions: React.FC = () => (
  <div>
    <h1>Executions</h1>
    <p>Execution monitoring page - Coming soon!</p>
  </div>
);

const Logs: React.FC = () => (
  <div>
    <h1>Logs</h1>
    <p>Log viewer page - Coming soon!</p>
  </div>
);

const Settings: React.FC = () => (
  <div>
    <h1>Settings</h1>
    <p>Application settings page - Coming soon!</p>
  </div>
);

// Protected route wrapper
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <LoadingSpinner fullScreen message="Loading..." />;
  }

  if (!isAuthenticated) {
    return <Navigate to={ROUTES.LOGIN} replace />;
  }

  return <>{children}</>;
};

const App: React.FC = () => {
  const { isAuthenticated } = useAuth();

  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <Routes>
          {/* Login route */}
          <Route 
            path={ROUTES.LOGIN} 
            element={
              isAuthenticated ? (
                <Navigate to={ROUTES.DASHBOARD} replace />
              ) : (
                <LoginPage />
              )
            } 
          />

          {/* Protected routes */}
          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <AppLayout>
                  <Routes>
                    {/* Redirect root to dashboard */}
                    <Route path="/" element={<Navigate to={ROUTES.DASHBOARD} replace />} />

                    {/* Main pages */}
                    <Route path={ROUTES.DASHBOARD} element={<Dashboard />} />
                    <Route path={ROUTES.ENDPOINTS} element={<Endpoints />} />
                    <Route path={ROUTES.SESSIONS} element={<Sessions />} />
                    <Route path={ROUTES.MULTI_SESSIONS} element={<MultiSessions />} />
                    <Route path={ROUTES.EXECUTIONS} element={<Executions />} />
                    <Route path={ROUTES.LOGS} element={<Logs />} />
                    <Route path={ROUTES.SETTINGS} element={<Settings />} />
                    <Route path={ROUTES.SHOT_DOWNLOAD} element={<ShotDownload />} />
                    <Route path={ROUTES.DOWNLOAD_TASKS} element={<DownloadTasks />} />

                    {/* Catch all - redirect to dashboard */}
                    <Route path="*" element={<Navigate to={ROUTES.DASHBOARD} replace />} />
                  </Routes>
                </AppLayout>
              </ProtectedRoute>
            }
          />
        </Routes>
      </Router>

      {/* React Query DevTools */}
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
};

export default App;
