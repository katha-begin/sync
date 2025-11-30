# Nginx Configuration

This directory contains nginx configurations for different environments.

## Configuration Files

### `nginx.dev.conf` (Development - NO CACHE)
- **Currently Active**
- No caching for any files
- All responses include `Cache-Control: no-cache`
- Best for active development to see changes immediately
- Requires hard refresh (Ctrl+Shift+R) to clear browser cache

### `nginx.conf` (Production - 30 MIN MAX CACHE)
- Maximum 30 minutes cache for static files
- No cache for HTML files (always fresh)
- 30 min cache for JS/CSS files
- 30 min cache for images and fonts
- Better performance for production

## Switching Between Configurations

### To Use Development Config (No Cache)
Edit `docker-compose.yml` line 184:
```yaml
- ./nginx/nginx.dev.conf:/etc/nginx/nginx.conf:ro
```

### To Use Production Config (30 Min Cache)
Edit `docker-compose.yml` line 184:
```yaml
- ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
```

After changing, restart nginx:
```bash
docker-compose restart nginx
```

Or redeploy:
```bash
.\deploy.ps1
```

## Cache Settings Summary

| File Type | Development | Production |
|-----------|-------------|------------|
| HTML      | No cache    | No cache   |
| JS/CSS    | No cache    | 30 minutes |
| Images    | No cache    | 30 minutes |
| Fonts     | No cache    | 30 minutes |

## Clearing Browser Cache

Even with no-cache headers, browsers may still cache files. Always use:
- **Hard Refresh**: `Ctrl + Shift + R` (Windows/Linux) or `Cmd + Shift + R` (Mac)
- **Clear Cache**: Browser Settings → Clear browsing data → Cached images and files

