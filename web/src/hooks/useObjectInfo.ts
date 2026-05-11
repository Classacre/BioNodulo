import { useState, useEffect, useCallback } from 'react';
import type { ObjectInfo } from '../types';

export function useObjectInfo() {
  const [objectInfo, setObjectInfo] = useState<ObjectInfo>({});
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch('/api/object_info');
      if (r.ok) {
        const data = await r.json();
        setObjectInfo(data);
      }
    } catch {
      // Will be empty initially without backend
    }
    setLoading(false);
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return { objectInfo, loading, refresh };
}
