import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { User, LoginRequest, LoginResponse } from '@/types';
import { STORAGE_KEYS } from '@/utils/constants';

interface AuthState {
  // State
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => void;
  refreshToken: () => Promise<void>;
  updateUser: (user: Partial<User>) => void;
  clearError: () => void;
  setLoading: (loading: boolean) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      // Initial state
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      // Login action
      login: async (credentials: LoginRequest) => {
        set({ isLoading: true, error: null });

        try {
          // TODO: Replace with actual API call
          const mockResponse: LoginResponse = {
            access_token: 'mock-jwt-token',
            token_type: 'Bearer',
            expires_in: 3600,
            user: {
              id: '1',
              username: credentials.username,
              email: `${credentials.username}@example.com`,
              full_name: 'Mock User',
              is_active: true,
              is_admin: false,
              created_at: new Date().toISOString(),
            },
          };

          // Simulate API delay
          await new Promise(resolve => setTimeout(resolve, 1000));

          // Mock authentication logic
          if (credentials.username === 'admin' && credentials.password === 'admin') {
            mockResponse.user.is_admin = true;
          } else if (credentials.password !== 'password') {
            throw new Error('Invalid credentials');
          }

          set({
            user: mockResponse.user,
            token: mockResponse.access_token,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          });

          // Store token in localStorage for API requests
          localStorage.setItem('access_token', mockResponse.access_token);
        } catch (error) {
          set({
            user: null,
            token: null,
            isAuthenticated: false,
            isLoading: false,
            error: error instanceof Error ? error.message : 'Login failed',
          });
        }
      },

      // Logout action
      logout: () => {
        set({
          user: null,
          token: null,
          isAuthenticated: false,
          error: null,
        });

        // Clear token from localStorage
        localStorage.removeItem('access_token');
      },

      // Refresh token action
      refreshToken: async () => {
        const { token } = get();
        if (!token) return;

        set({ isLoading: true });

        try {
          // TODO: Replace with actual API call
          // For now, just validate the existing token
          await new Promise(resolve => setTimeout(resolve, 500));

          // Mock token refresh - in real app, this would call the API
          set({ isLoading: false });
        } catch (error) {
          // Token refresh failed, logout user
          get().logout();
          set({
            isLoading: false,
            error: 'Session expired. Please login again.',
          });
        }
      },

      // Update user action
      updateUser: (userData: Partial<User>) => {
        const { user } = get();
        if (user) {
          set({
            user: { ...user, ...userData },
          });
        }
      },

      // Clear error action
      clearError: () => {
        set({ error: null });
      },

      // Set loading action
      setLoading: (loading: boolean) => {
        set({ isLoading: loading });
      },
    }),
    {
      name: STORAGE_KEYS.AUTH_TOKEN,
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);

// Selectors for easier access
export const useAuth = () => {
  const store = useAuthStore();
  return {
    user: store.user,
    isAuthenticated: store.isAuthenticated,
    isLoading: store.isLoading,
    error: store.error,
    login: store.login,
    logout: store.logout,
    refreshToken: store.refreshToken,
    updateUser: store.updateUser,
    clearError: store.clearError,
  };
};

export const useAuthActions = () => {
  const store = useAuthStore();
  return {
    login: store.login,
    logout: store.logout,
    refreshToken: store.refreshToken,
    updateUser: store.updateUser,
    clearError: store.clearError,
    setLoading: store.setLoading,
  };
};

// Helper functions
export const isTokenExpired = (token: string): boolean => {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    const currentTime = Date.now() / 1000;
    return payload.exp < currentTime;
  } catch {
    return true;
  }
};

export const getTokenExpirationTime = (token: string): Date | null => {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return new Date(payload.exp * 1000);
  } catch {
    return null;
  }
};

// Auto-refresh token before expiration
let refreshTimer: number | null = null;

export const startTokenRefreshTimer = () => {
  const { token, refreshToken } = useAuthStore.getState();
  
  if (!token) return;

  const expirationTime = getTokenExpirationTime(token);
  if (!expirationTime) return;

  // Refresh token 5 minutes before expiration
  const refreshTime = expirationTime.getTime() - Date.now() - 5 * 60 * 1000;
  
  if (refreshTime > 0) {
    refreshTimer = setTimeout(() => {
      refreshToken();
      startTokenRefreshTimer(); // Restart timer after refresh
    }, refreshTime);
  }
};

export const stopTokenRefreshTimer = () => {
  if (refreshTimer) {
    clearTimeout(refreshTimer);
    refreshTimer = null;
  }
};

// Initialize token refresh timer on store creation
useAuthStore.subscribe((state) => {
  if (state.isAuthenticated && state.token) {
    startTokenRefreshTimer();
  } else {
    stopTokenRefreshTimer();
  }
});
