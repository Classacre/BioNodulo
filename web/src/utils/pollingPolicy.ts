export const SYSTEM_STATS_POLL_VISIBLE_MS = 15_000;
export const SYSTEM_STATS_POLL_HIDDEN_MS = 120_000;

export const CLOUD_RUN_POLL_VISIBLE_MS = 10_000;
export const CLOUD_RUN_POLL_HIDDEN_MS = 60_000;

export const COLLAB_PRESENCE_POLL_VISIBLE_MS = 30_000;
export const COLLAB_PRESENCE_POLL_HIDDEN_MS = 120_000;

export const CLOUD_CREDITS_POLL_VISIBLE_MS = 300_000;
export const CLOUD_CREDITS_POLL_HIDDEN_MS = 600_000;

interface VisibilityLike {
  hidden?: boolean;
}

export function isBrowserDocumentHidden(doc: VisibilityLike | null | undefined = globalThis.document): boolean {
  return doc?.hidden === true;
}

export function pollingDelay(
  visibleMs: number,
  hiddenMs: number,
  doc: VisibilityLike | null | undefined = globalThis.document,
): number {
  return isBrowserDocumentHidden(doc) ? hiddenMs : visibleMs;
}

type PollCallback = () => void | Promise<void>;

export function startVisibilityAwarePolling(
  callback: PollCallback,
  visibleMs: number,
  hiddenMs: number,
  doc: (Document & VisibilityLike) | null | undefined = globalThis.document,
): () => void {
  let stopped = false;
  let running = false;
  let timeout: ReturnType<typeof setTimeout> | null = null;

  const clearScheduled = () => {
    if (timeout !== null) {
      clearTimeout(timeout);
      timeout = null;
    }
  };

  const schedule = () => {
    if (stopped) return;
    clearScheduled();
    timeout = setTimeout(run, pollingDelay(visibleMs, hiddenMs, doc));
  };

  const run = async () => {
    if (stopped || running) return;
    running = true;
    try {
      await callback();
    } finally {
      running = false;
      schedule();
    }
  };

  const handleVisibilityChange = () => {
    if (isBrowserDocumentHidden(doc)) {
      schedule();
    } else {
      clearScheduled();
      void run();
    }
  };

  doc?.addEventListener?.('visibilitychange', handleVisibilityChange);
  void run();

  return () => {
    stopped = true;
    clearScheduled();
    doc?.removeEventListener?.('visibilitychange', handleVisibilityChange);
  };
}
