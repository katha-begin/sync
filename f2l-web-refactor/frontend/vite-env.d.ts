/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string
  readonly VITE_API_TIMEOUT: string
  readonly VITE_WS_URL: string
  readonly VITE_APP_NAME: string
  readonly VITE_APP_VERSION: string
  readonly VITE_APP_DESCRIPTION: string
  readonly VITE_APP_AUTHOR: string
  readonly VITE_APP_HOMEPAGE: string
  readonly VITE_ENABLE_DEVTOOLS: string
  readonly VITE_LOG_LEVEL: string
  readonly VITE_SENTRY_DSN: string
  readonly VITE_ANALYTICS_ID: string
  readonly VITE_FEATURE_FLAGS: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}