import React from 'react';
import {
  Snackbar,
  Alert,
  AlertTitle,
  IconButton,
  Box,
  Slide,
  SlideProps,
} from '@mui/material';
import {
  Close as CloseIcon,
} from '@mui/icons-material';
import { useNotifications } from '@/stores/uiStore';
import { Notification } from '@/types';

function SlideTransition(props: SlideProps) {
  return <Slide {...props} direction="left" />;
}

const NotificationContainer: React.FC = () => {
  const { notifications, removeNotification } = useNotifications();

  const handleClose = (id: string) => {
    removeNotification(id);
  };

  return (
    <Box
      sx={{
        position: 'fixed',
        top: 80,
        right: 16,
        zIndex: 9999,
        display: 'flex',
        flexDirection: 'column',
        gap: 1,
        maxWidth: 400,
      }}
    >
      {notifications.map((notification) => (
        <NotificationItem
          key={notification.id}
          notification={notification}
          onClose={() => handleClose(notification.id)}
        />
      ))}
    </Box>
  );
};

interface NotificationItemProps {
  notification: Notification;
  onClose: () => void;
}

const NotificationItem: React.FC<NotificationItemProps> = ({
  notification,
  onClose,
}) => {
  return (
    <Snackbar
      open={true}
      autoHideDuration={notification.persistent ? null : notification.duration}
      onClose={onClose}
      TransitionComponent={SlideTransition}
      sx={{
        position: 'relative',
        transform: 'none !important',
        left: 'auto !important',
        right: 'auto !important',
        top: 'auto !important',
        bottom: 'auto !important',
      }}
    >
      <Alert
        severity={notification.type}
        variant="filled"
        onClose={onClose}
        sx={{
          width: '100%',
          minWidth: 300,
          maxWidth: 400,
          '& .MuiAlert-message': {
            width: '100%',
          },
        }}
        action={
          <IconButton
            size="small"
            aria-label="close"
            color="inherit"
            onClick={onClose}
          >
            <CloseIcon fontSize="small" />
          </IconButton>
        }
      >
        <AlertTitle sx={{ fontWeight: 600 }}>
          {notification.title}
        </AlertTitle>
        {notification.message && (
          <Box sx={{ mt: 0.5 }}>
            {notification.message}
          </Box>
        )}
        {notification.actions && (
          <Box sx={{ mt: 1, display: 'flex', gap: 1 }}>
            {notification.actions.map((action, index) => (
              <IconButton
                key={index}
                size="small"
                color="inherit"
                onClick={() => {
                  action.onClick?.();
                  if (action.closeOnClick !== false) {
                    onClose();
                  }
                }}
                sx={{
                  backgroundColor: 'rgba(255, 255, 255, 0.2)',
                  '&:hover': {
                    backgroundColor: 'rgba(255, 255, 255, 0.3)',
                  },
                }}
              >
                {action.icon}
              </IconButton>
            ))}
          </Box>
        )}
      </Alert>
    </Snackbar>
  );
};

export default NotificationContainer;
