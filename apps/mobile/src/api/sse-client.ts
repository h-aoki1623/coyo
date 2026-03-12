import { fetch } from 'expo/fetch';
import Constants from 'expo-constants';

import { getAuthToken } from '@/services/token-provider';
import type { TurnEvent } from '@/types/api';

const API_BASE_URL = Constants.expoConfig?.extra?.apiBaseUrl ?? 'http://localhost:8000';

// Maximum buffer size (1 MB) to prevent memory exhaustion from malformed streams
const MAX_BUFFER_SIZE = 1024 * 1024;

// Parse a single SSE line into its field type and value
function parseSSELine(line: string): { event?: string; data?: string } {
  if (line.startsWith(':')) return {}; // SSE comment (keep-alive)
  if (line.startsWith('event: ')) return { event: line.slice(7) };
  if (line.startsWith('data: ')) return { data: line.slice(6) };
  return {};
}

/**
 * Parse complete SSE event blocks from a buffer and return parsed events
 * along with the remaining incomplete buffer.
 */
export function parseSSEBuffer(buffer: string): { events: TurnEvent[]; remaining: string } {
  const events: TurnEvent[] = [];
  // Normalize \r\n and \r to \n (per SSE spec)
  const normalized = buffer.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
  // Split on double-newline (SSE event boundary)
  const blocks = normalized.split('\n\n');
  // Last element may be incomplete — keep it as remaining buffer
  const remaining = blocks.pop() ?? '';

  for (const block of blocks) {
    const trimmed = block.trim();
    if (trimmed === '') continue;

    let currentEvent = '';
    for (const line of trimmed.split('\n')) {
      const parsed = parseSSELine(line.trim());
      if (parsed.event) {
        currentEvent = parsed.event;
      }
      if (parsed.data && currentEvent) {
        try {
          const data = JSON.parse(parsed.data);
          events.push({ type: currentEvent, data } as TurnEvent);
        } catch {
          if (__DEV__) {
            console.warn(`[SSE] Skipping malformed JSON for event "${currentEvent}":`, parsed.data);
          }
        }
      }
    }
  }

  return { events, remaining };
}

/**
 * Parse a complete SSE response body into an array of TurnEvent objects.
 */
export function parseSSEResponse(body: string): TurnEvent[] {
  // Ensure the body ends with a double-newline so parseSSEBuffer
  // treats the entire content as complete events.
  const normalized = body.endsWith('\n\n') ? body : body + '\n\n';
  const { events } = parseSSEBuffer(normalized);
  return events;
}

/**
 * Send audio and receive turn events from the backend SSE endpoint.
 *
 * Uses expo/fetch which supports ReadableStream on response bodies,
 * enabling incremental SSE event delivery. Events are yielded as soon
 * as they arrive from the backend (e.g. stt_result after STT completes)
 * rather than waiting for the entire response to finish.
 */
export async function* streamTurnEvents(
  conversationId: string,
  audioFormData: FormData,
  signal?: AbortSignal,
): AsyncGenerator<TurnEvent> {
  const url = `${API_BASE_URL}/api/conversations/${encodeURIComponent(conversationId)}/turns`;

  // Build auth headers (Firebase auth token)
  const headers: Record<string, string> = {
    'Accept': 'text/event-stream',
  };
  const token = await getAuthToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    method: 'POST',
    headers,
    body: audioFormData,
    signal,
  });

  if (!response.ok) {
    const bodyText = await response.text().catch(() => '');
    let body: Record<string, unknown> | null = null;
    try { body = JSON.parse(bodyText); } catch { /* not JSON */ }
    const message = (body as Record<string, Record<string, string>> | null)?.error?.message
      ?? (body as Record<string, string> | null)?.detail
      ?? `Stream request failed (HTTP ${response.status})`;
    if (__DEV__) {
      const truncated = bodyText.length > 200 ? bodyText.slice(0, 200) + '...' : bodyText;
      console.warn(`[SSE] Stream error HTTP ${response.status}: ${truncated}`);
    }
    yield {
      type: 'error',
      data: { code: 'STREAM_ERROR', message },
    };
    return;
  }

  // Use ReadableStream for incremental reading (expo/fetch supports this)
  if (!response.body) {
    // Fallback: read full body if stream is not available
    const bodyText = await response.text();
    const events = parseSSEResponse(bodyText);
    for (const event of events) {
      yield event;
    }
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      if (signal?.aborted) break;

      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      if (buffer.length > MAX_BUFFER_SIZE) {
        yield {
          type: 'error',
          data: { code: 'BUFFER_OVERFLOW', message: 'Stream buffer exceeded maximum size' },
        };
        return;
      }

      const { events, remaining } = parseSSEBuffer(buffer);
      buffer = remaining;

      for (const event of events) {
        yield event;
      }
    }

    // Process any remaining data in the buffer after stream ends
    if (buffer.trim()) {
      const { events } = parseSSEBuffer(buffer + '\n\n');
      for (const event of events) {
        yield event;
      }
    }
  } finally {
    reader.releaseLock();
  }
}
