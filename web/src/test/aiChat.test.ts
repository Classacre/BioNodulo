import { describe, expect, it, vi } from 'vitest';
import { apiRequest } from '../api/client';
import { readAIChatEvents, streamAIChat, AIChatStreamError, type AIChatStep } from '../api/aiChat';

vi.mock('../api/client', () => ({ apiRequest: vi.fn() }));

function stream(chunks: string[]): Response {
  const encoder = new TextEncoder();
  return new Response(new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  }), { headers: { 'Content-Type': 'text/event-stream' } });
}

describe('assistant event stream', () => {
  it('reads split events in order and ignores heartbeats', async () => {
    const steps: AIChatStep[] = [];
    await readAIChatEvents(stream([
      ': heart', 'beat\n\n',
      'data: {"type":"tool_call","content":"","name":"scan","id":"1"}\n',
      '\ndata: {"type":"tool_result","content":"","name":"scan","id":"1","status":"completed"}\n\n',
      'data: {"type":"reply","content":"Done"}\n\n',
      'data: [DONE]\n\n',
    ]), step => steps.push(step));
    expect(steps.map(step => step.type)).toEqual(['tool_call', 'tool_result', 'reply']);
    expect(steps[1].id).toBe('1');
  });

  it('surfaces the terminal failure event before completion', async () => {
    const steps: AIChatStep[] = [];
    await readAIChatEvents(stream([
      'data: {"type":"error","content":"Provider unavailable","status":"error"}\n\n',
      'data: [DONE]\n\n',
    ]), step => steps.push(step));
    expect(steps).toEqual([expect.objectContaining({ type: 'error', content: 'Provider unavailable' })]);
  });

  it('rejects an empty or prematurely closed stream', async () => {
    await expect(readAIChatEvents(stream([]), vi.fn())).rejects.toBeInstanceOf(AIChatStreamError);
    await expect(readAIChatEvents(stream(['data: {"type":"reply","content":"partial"}\n\n']), vi.fn()))
      .rejects.toThrow('closed before completion');
  });

  it('keeps CRLF boundaries intact when split across chunks', async () => {
    const steps: AIChatStep[] = [];
    await readAIChatEvents(stream([
      'data: {"type":"reply","content":"Ready"}\r', '\n\r', '\n',
      'data: [DONE]\r', '\n\r', '\n',
    ]), step => steps.push(step));
    expect(steps).toEqual([expect.objectContaining({ type: 'reply', content: 'Ready' })]);
  });

  it('rejects completion with activity but no terminal reply or error', async () => {
    await expect(readAIChatEvents(stream([
      'data: {"type":"status","content":"Waiting"}\n\n',
      'data: [DONE]\n\n',
    ]), vi.fn())).rejects.toThrow('without a reply or error');
  });

  it('cancels the upstream reader after a malformed event', async () => {
    let cancelled = false;
    const response = new Response(new ReadableStream({
      start(controller) { controller.enqueue(new TextEncoder().encode('data: {bad json}\n\n')); },
      cancel() { cancelled = true; },
    }));
    await expect(readAIChatEvents(response, vi.fn())).rejects.toThrow('invalid activity event');
    expect(cancelled).toBe(true);
  });

  it('cancels a pending read on abort', async () => {
    let cancelled = false;
    const response = new Response(new ReadableStream({ cancel() { cancelled = true; } }));
    const controller = new AbortController();
    const pending = readAIChatEvents(response, vi.fn(), controller.signal);
    controller.abort();
    await expect(pending).rejects.toMatchObject({ name: 'AbortError' });
    expect(cancelled).toBe(true);
  });

  it('honors cancellation before reading', async () => {
    const controller = new AbortController();
    controller.abort();
    await expect(readAIChatEvents(stream(['data: [DONE]\n\n']), vi.fn(), controller.signal))
      .rejects.toMatchObject({ name: 'AbortError' });
  });
});

describe('assistant connection deadlines', () => {
  it('allows a cold connection to respond after 35 seconds', async () => {
    vi.useFakeTimers();
    try {
      vi.mocked(apiRequest).mockImplementationOnce((_path, init) => new Promise((resolve, reject) => {
        const timer = window.setTimeout(() => resolve(stream([
          'data: {"type":"reply","content":"Ready"}\n\n',
          'data: [DONE]\n\n',
        ])), 60_000);
        init.signal?.addEventListener('abort', () => {
          window.clearTimeout(timer);
          reject(new DOMException('Aborted', 'AbortError'));
        }, { once: true });
      }));
      const steps: AIChatStep[] = [];
      const pending = streamAIChat({}, step => steps.push(step));
      await vi.advanceTimersByTimeAsync(60_000);
      await expect(pending).resolves.toBeUndefined();
      expect(steps.map(step => step.content)).toEqual(['Ready']);
    } finally {
      vi.useRealTimers();
    }
  });

  it('still times out a connected stream that stops sending activity', async () => {
    vi.useFakeTimers();
    try {
      vi.mocked(apiRequest).mockResolvedValueOnce(new Response(new ReadableStream(), {
        headers: { 'Content-Type': 'text/event-stream' },
      }));
      const pending = streamAIChat({}, vi.fn());
      const assertion = expect(pending).rejects.toThrow('stopped sending activity');
      await vi.advanceTimersByTimeAsync(35_001);
      await assertion;
    } finally {
      vi.useRealTimers();
    }
  });
});
