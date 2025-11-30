import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { ThemeMode, Notification } from '@/types';
import { STORAGE_KEYS, APP_CONFIG } from '@/utils/constants';

interface UIState {
  // Theme
  themeMode: ThemeMode;
  
  // Layout
  sidebarCollapsed: boolean;
  sidebarOpen: boolean; // For mobile
  
  // Loading states
  globalLoading: boolean;
  loadingStates: Record<string, boolean>;
  
  // Notifications
  notifications: Notification[];
  
  // Modals and dialogs
  modals: Record<string, boolean>;
  
  // Table settings
  tableSettings: Record<string, {
    pageSize: number;
    sortBy?: string;
    sortOrder?: 'asc' | 'desc';
    filters?: Record<string, any>;
    hiddenColumns?: string[];
  }>;
  
  // Recent searches
  recentSearches: Record<string, string[]>;
  
  // Actions
  setThemeMode: (mode: ThemeMode) => void;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  setGlobalLoading: (loading: boolean) => void;
  setLoading: (key: string, loading: boolean) => void;
  addNotification: (notification: Omit<Notification, 'id'>) => void;
  removeNotification: (id: string) => void;
  clearNotifications: () => void;
  openModal: (modalId: string) => void;
  closeModal: (modalId: string) => void;
  toggleModal: (modalId: string) => void;
  updateTableSettings: (tableId: string, settings: Partial<UIState['tableSettings'][string]>) => void;
  addRecentSearch: (category: string, search: string) => void;
  clearRecentSearches: (category?: string) => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set, get) => ({
      // Initial state
      themeMode: APP_CONFIG.DEFAULT_THEME,
      sidebarCollapsed: false,
      sidebarOpen: false,
      globalLoading: false,
      loadingStates: {},
      notifications: [],
      modals: {},
      tableSettings: {},
      recentSearches: {},

      // Theme actions
      setThemeMode: (mode: ThemeMode) => {
        set({ themeMode: mode });
      },

      // Sidebar actions
      toggleSidebar: () => {
        set(state => ({ sidebarCollapsed: !state.sidebarCollapsed }));
      },

      setSidebarOpen: (open: boolean) => {
        set({ sidebarOpen: open });
      },

      // Loading actions
      setGlobalLoading: (loading: boolean) => {
        set({ globalLoading: loading });
      },

      setLoading: (key: string, loading: boolean) => {
        set(state => ({
          loadingStates: {
            ...state.loadingStates,
            [key]: loading,
          },
        }));
      },

      // Notification actions
      addNotification: (notification: Omit<Notification, 'id'>) => {
        const id = Date.now().toString();
        const newNotification: Notification = {
          ...notification,
          id,
          duration: notification.duration ?? 5000,
        };

        set(state => ({
          notifications: [...state.notifications, newNotification],
        }));

        // Auto-remove notification after duration (unless persistent)
        if (!newNotification.persistent && newNotification.duration && newNotification.duration > 0) {
          setTimeout(() => {
            get().removeNotification(id);
          }, newNotification.duration);
        }
      },

      removeNotification: (id: string) => {
        set(state => ({
          notifications: state.notifications.filter(n => n.id !== id),
        }));
      },

      clearNotifications: () => {
        set({ notifications: [] });
      },

      // Modal actions
      openModal: (modalId: string) => {
        set(state => ({
          modals: { ...state.modals, [modalId]: true },
        }));
      },

      closeModal: (modalId: string) => {
        set(state => ({
          modals: { ...state.modals, [modalId]: false },
        }));
      },

      toggleModal: (modalId: string) => {
        set(state => ({
          modals: { ...state.modals, [modalId]: !state.modals[modalId] },
        }));
      },

      // Table settings actions
      updateTableSettings: (tableId: string, settings: Partial<UIState['tableSettings'][string]>) => {
        set(state => ({
          tableSettings: {
            ...state.tableSettings,
            [tableId]: {
              ...state.tableSettings[tableId],
              ...settings,
            },
          },
        }));
      },

      // Recent searches actions
      addRecentSearch: (category: string, search: string) => {
        if (!search.trim()) return;

        set(state => {
          const existing = state.recentSearches[category] || [];
          const filtered = existing.filter(s => s !== search);
          const updated = [search, ...filtered].slice(0, 10); // Keep last 10

          return {
            recentSearches: {
              ...state.recentSearches,
              [category]: updated,
            },
          };
        });
      },

      clearRecentSearches: (category?: string) => {
        set(state => {
          if (category) {
            const { [category]: _, ...rest } = state.recentSearches;
            return { recentSearches: rest };
          } else {
            return { recentSearches: {} };
          }
        });
      },
    }),
    {
      name: STORAGE_KEYS.USER_PREFERENCES,
      partialize: (state) => ({
        themeMode: state.themeMode,
        sidebarCollapsed: state.sidebarCollapsed,
        tableSettings: state.tableSettings,
        recentSearches: state.recentSearches,
      }),
    }
  )
);

// Selectors for easier access
export const useTheme = () => {
  const themeMode = useUIStore(state => state.themeMode);
  const setThemeMode = useUIStore(state => state.setThemeMode);
  return { themeMode, setThemeMode };
};

export const useSidebar = () => {
  const sidebarCollapsed = useUIStore(state => state.sidebarCollapsed);
  const sidebarOpen = useUIStore(state => state.sidebarOpen);
  const toggleSidebar = useUIStore(state => state.toggleSidebar);
  const setSidebarOpen = useUIStore(state => state.setSidebarOpen);
  
  return {
    sidebarCollapsed,
    sidebarOpen,
    toggleSidebar,
    setSidebarOpen,
  };
};

export const useLoading = () => {
  const globalLoading = useUIStore(state => state.globalLoading);
  const loadingStates = useUIStore(state => state.loadingStates);
  const setGlobalLoading = useUIStore(state => state.setGlobalLoading);
  const setLoading = useUIStore(state => state.setLoading);
  
  return {
    globalLoading,
    loadingStates,
    setGlobalLoading,
    setLoading,
    isLoading: (key: string) => loadingStates[key] || false,
  };
};

export const useNotifications = () => {
  const notifications = useUIStore(state => state.notifications);
  const addNotification = useUIStore(state => state.addNotification);
  const removeNotification = useUIStore(state => state.removeNotification);
  const clearNotifications = useUIStore(state => state.clearNotifications);
  
  return {
    notifications,
    addNotification,
    removeNotification,
    clearNotifications,
  };
};

export const useModals = () => {
  const modals = useUIStore(state => state.modals);
  const openModal = useUIStore(state => state.openModal);
  const closeModal = useUIStore(state => state.closeModal);
  const toggleModal = useUIStore(state => state.toggleModal);
  
  return {
    modals,
    openModal,
    closeModal,
    toggleModal,
    isModalOpen: (modalId: string) => modals[modalId] || false,
  };
};

export const useTableSettings = () => {
  const tableSettings = useUIStore(state => state.tableSettings);
  const updateTableSettings = useUIStore(state => state.updateTableSettings);
  
  return {
    tableSettings,
    updateTableSettings,
    getTableSettings: (tableId: string) => tableSettings[tableId] || { pageSize: 25 },
  };
};

export const useRecentSearches = () => {
  const recentSearches = useUIStore(state => state.recentSearches);
  const addRecentSearch = useUIStore(state => state.addRecentSearch);
  const clearRecentSearches = useUIStore(state => state.clearRecentSearches);
  
  return {
    recentSearches,
    addRecentSearch,
    clearRecentSearches,
    getRecentSearches: (category: string) => recentSearches[category] || [],
  };
};

// Utility functions for notifications
export const showSuccessNotification = (title: string, message?: string) => {
  useUIStore.getState().addNotification({
    type: 'success',
    title,
    message,
  });
};

export const showErrorNotification = (title: string, message?: string) => {
  useUIStore.getState().addNotification({
    type: 'error',
    title,
    message,
    persistent: true,
  });
};

export const showWarningNotification = (title: string, message?: string) => {
  useUIStore.getState().addNotification({
    type: 'warning',
    title,
    message,
  });
};

export const showInfoNotification = (title: string, message?: string) => {
  useUIStore.getState().addNotification({
    type: 'info',
    title,
    message,
  });
};
