// HPC status polling: fetches `/api/hpc/status` every 30s and exposes the
// current connection state ('off' | 'on' | 'error').
//
// Extracted from App.tsx to isolate the HPC feature surface.

import { useState, useEffect } from 'react';
import { apiGet, ApiError } from '../api/client';
import { safeValidateHpcStatus } from '../api/validators';
import { logError } from '../state/logging';
import type { HPCStatus } from '../components/layout/TopBar';

export interface UseHPCArgs {
  hpcEnabled: boolean;
  hpcBackend: string;
  hpcPartition: string;
}

export interface UseHPCResult {
  hpcStatus: HPCStatus;
}

export function useHPC({ hpcEnabled, hpcBackend, hpcPartition }: UseHPCArgs): UseHPCResult {
  const [hpcStatus, setHpcStatus] = useState<HPCStatus>('off');

  useEffect(() => {
    if (!hpcEnabled) {
      setHpcStatus('off');
      return;
    }

    const checkHpcStatus = async () => {
      try {
        const raw = await apiGet<unknown>('/api/hpc/status');
        const result = safeValidateHpcStatus(raw);
        if (result.ok) {
          const { status, connected } = result.value;
          setHpcStatus(status || (connected ? 'on' : 'off'));
        } else {
          setHpcStatus('off');
        }
      } catch (err) {
        if (err instanceof ApiError) {
          setHpcStatus('off');
        } else {
          logError('hpc.status.poll', err);
          setHpcStatus('off');
        }
      }
    };

    checkHpcStatus();
    // Poll every 30 seconds
    const interval = setInterval(checkHpcStatus, 30000);
    return () => clearInterval(interval);
  }, [hpcEnabled, hpcBackend, hpcPartition]);

  return { hpcStatus };
}
