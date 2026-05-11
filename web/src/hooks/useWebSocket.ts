import { useEffect, useRef, useCallback, useState } from 'react';

const RECONNECT_DELAY = 3000;

export function useWebSocket(url: string) {
  const ws = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const handlers = useRef<Set<(data: unknown) => void>>(new Set());
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const shouldReconnect = useRef(true);

  const connect = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) return;
    try {
      ws.current = new WebSocket(url);
      ws.current.onopen = () => setConnected(true);
      ws.current.onclose = () => {
        setConnected(false);
        if (shouldReconnect.current) {
          reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY);
        }
      };
      ws.current.onerror = () => {
        ws.current?.close();
      };
      ws.current.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          handlers.current.forEach(h => h(data));
        } catch { /* non-JSON */ }
      };
    } catch { /* ignore */ }
  }, [url]);

  const disconnect = useCallback(() => {
    shouldReconnect.current = false;
    if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    ws.current?.close();
  }, []);

  const send = useCallback((data: unknown) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(data));
    }
  }, []);

  const onMessage = useCallback((handler: (data: unknown) => void) => {
    handlers.current.add(handler);
    return () => { handlers.current.delete(handler); };
  }, []);

  useEffect(() => {
    shouldReconnect.current = true;
    connect();
    return disconnect;
  }, [connect, disconnect]);

  return { connected, send, onMessage };
}
