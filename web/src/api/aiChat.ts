import { apiRequest } from './client';

export interface AIChatStep {
  type: 'status' | 'thinking' | 'commentary' | 'tool_call' | 'tool_result' | 'propose_changes' | 'reply_delta' | 'reply' | 'error';
  content: string;
  id?: string;
  status?: 'queued' | 'running' | 'completed' | 'error' | string;
  duration_ms?: number;
  name?: string;
  arguments?: Record<string, unknown>;
  result?: Record<string, unknown>;
  workflow?: Record<string, unknown>;
  description?: string;
}

export class AIChatStreamError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'AIChatStreamError';
  }
}

/** Reads complete SSE frames even when UTF-8, lines, or JSON span chunks. */
export async function readAIChatEvents(
  response: Response,
  onStep: (step: AIChatStep) => void,
  signal?: AbortSignal,
  onChunk?: () => void,
): Promise<void> {
  if (!response.body) throw new AIChatStreamError('The assistant returned an empty stream.');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let completed = false;
  let terminal = false;
  let pendingCR = false;
  let validCompletion = false;
  const abortReader = () => { void reader.cancel(); };
  signal?.addEventListener('abort', abortReader, { once: true });
  const appendText = (text: string) => {
    // Keep a trailing CR until the next chunk tells us whether it is CRLF.
    let normalized = '';
    for (const char of text) {
      if (pendingCR) {
        normalized += '\n';
        pendingCR = false;
        if (char === '\n') continue;
      }
      if (char === '\r') pendingCR = true;
      else normalized += char;
    }
    buffer += normalized;
    if (buffer.length > 1_000_000) throw new AIChatStreamError('The assistant sent an oversized activity event.');
  };

  const processFrame = (frame: string) => {
    const data = frame.split('\n')
      .filter(line => line.startsWith('data:'))
      .map(line => line.slice(5).trimStart())
      .join('\n');
    if (!data) return; // comments/heartbeats
    if (data === '[DONE]') {
      completed = true;
      return;
    }
    if (completed) throw new AIChatStreamError('The assistant sent data after completion.');
    let step: AIChatStep;
    try {
      step = JSON.parse(data) as AIChatStep;
    } catch {
      throw new AIChatStreamError('The assistant sent an invalid activity event.');
    }
    if (!step || typeof step !== 'object' || typeof step.type !== 'string' || typeof step.content !== 'string') {
      throw new AIChatStreamError('The assistant sent an invalid activity event.');
    }
    if (step.type === 'reply' || step.type === 'error') terminal = true;
    onStep(step);
  };

  try {
    while (true) {
      if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
      const { value, done } = await reader.read();
      if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
      if (done) break;
      onChunk?.();
      appendText(decoder.decode(value, { stream: true }));
      let boundary = buffer.indexOf('\n\n');
      while (boundary >= 0) {
        processFrame(buffer.slice(0, boundary));
        buffer = buffer.slice(boundary + 2);
        boundary = buffer.indexOf('\n\n');
      }
    }
    appendText(decoder.decode());
    if (pendingCR) buffer += '\n';
    if (buffer.trim()) processFrame(buffer);
    if (!completed) throw new AIChatStreamError('The assistant connection closed before completion.');
    if (!terminal) throw new AIChatStreamError('The assistant completed without a reply or error.');
    validCompletion = true;
  } finally {
    signal?.removeEventListener('abort', abortReader);
    if (!validCompletion) {
      try { await reader.cancel(); } catch { /* already closed */ }
    }
    reader.releaseLock();
  }
}

export async function streamAIChat(
  request: unknown,
  onStep: (step: AIChatStep) => void,
  signal?: AbortSignal,
): Promise<void> {
  const controller = new AbortController();
  let timeoutReason = '';
  const stop = () => controller.abort();
  signal?.addEventListener('abort', stop, { once: true });
  if (signal?.aborted) controller.abort();
  const totalTimer = window.setTimeout(() => {
    timeoutReason = 'The assistant exceeded the time limit.';
    controller.abort();
  }, 270_000);
  let idleTimer: number | undefined;
  const resetIdle = () => {
    window.clearTimeout(idleTimer);
    idleTimer = window.setTimeout(() => {
      timeoutReason = 'The assistant connection stopped sending activity.';
      controller.abort();
    }, 35_000);
  };
  resetIdle();
  try {
    const response = await apiRequest('/ai/chat/stream', {
      method: 'POST',
      json: request,
      headers: { Accept: 'text/event-stream' },
      signal: controller.signal,
    });
    if (!(response.headers.get('Content-Type') || '').includes('text/event-stream')) {
      throw new AIChatStreamError('The assistant did not provide a live activity stream.');
    }
    await readAIChatEvents(response, onStep, controller.signal, resetIdle);
  } catch (error) {
    if (timeoutReason) throw new AIChatStreamError(timeoutReason);
    throw error;
  } finally {
    window.clearTimeout(totalTimer);
    window.clearTimeout(idleTimer);
    signal?.removeEventListener('abort', stop);
  }
}
