function trimTrailingSlash(value: string): string {
  return value.endsWith('/') ? value.slice(0, -1) : value;
}

export function appBasePath(): string {
  if (typeof window === 'undefined') return '';

  const viteBase = import.meta.env.BASE_URL;
  if (viteBase && viteBase !== '/' && viteBase !== './') {
    return trimTrailingSlash(viteBase);
  }

  const path = window.location.pathname;
  if (!path || path === '/') return '';
  if (path.endsWith('/')) return trimTrailingSlash(path);

  const lastSegment = path.slice(path.lastIndexOf('/') + 1);
  if (!lastSegment.includes('.')) return path;

  const directory = path.slice(0, path.lastIndexOf('/'));
  return directory === '/' ? '' : directory;
}

export function appPath(path: string): string {
  if (path.startsWith('http://') || path.startsWith('https://')) return path;
  const cleanPath = path.replace(/^\/+/, '');
  const base = appBasePath();
  return base ? `${base}/${cleanPath}` : `/${cleanPath}`;
}

export function appWebSocketUrl(path: string, query = ''): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${window.location.host}${appPath(path)}${query}`;
}
