import { useCallback, useEffect, useRef } from 'react';
import useReactWebSocket, { ReadyState } from 'react-use-websocket';

export function useWebSocket(url: string) {
  const handlers = useRef<Set<(data: unknown) => void>>(new Set());
  const {
    sendJsonMessage,
    lastJsonMessage,
    readyState,
  } = useReactWebSocket(url, {
    share: true,
    shouldReconnect: event => ![4401, 4403].includes(event.code),
    reconnectInterval: 3000,
    retryOnError: true,
  });

  useEffect(() => {
    if (lastJsonMessage === null) return;
    handlers.current.forEach(handler => handler(lastJsonMessage));
  }, [lastJsonMessage]);

  const send = useCallback((data: unknown) => {
    sendJsonMessage(data);
  }, [sendJsonMessage]);

  const onMessage = useCallback((handler: (data: unknown) => void) => {
    handlers.current.add(handler);
    return () => {
      handlers.current.delete(handler);
    };
  }, []);

  return {
    connected: readyState === ReadyState.OPEN,
    send,
    onMessage,
  };
}
