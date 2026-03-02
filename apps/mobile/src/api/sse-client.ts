import Constants from 'expo-constants';
import { getOrCreateDeviceId } from '@/services/device-id';
import type { TurnEvent } from '@/types/api';

const API_BASE_URL = Constants.expoConfig?.extra?.apiBaseUrl ?? 'http://localhost:8000';

// Parse a single SSE line into its field type and value
function parseSSELine(line: string): { event?: string; data?: string } {
  if (line.startsWith('event: ')) return { event: line.slice(7) };
  if (line.startsWith('data: ')) return { data: line.slice(6) };
  return {};
}

/**
 * Parse a complete SSE response body into an array of TurnEvent objects.
 */
export function parseSSEResponse(body: string): TurnEvent[] {
  const events: TurnEvent[] = [];
  const lines = body.split('\n');
  let currentEvent = '';

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed === '') {
      // Empty line signals end of an SSE event block
      currentEvent = '';
      continue;
    }

    const parsed = parseSSELine(trimmed);
    if (parsed.event) {
      currentEvent = parsed.event;
    }
    if (parsed.data && currentEvent) {
      try {
        const data = JSON.parse(parsed.data);
        events.push({ type: currentEvent, data } as TurnEvent);
      } catch {
        // Skip malformed JSON lines
      }
    }
  }

  return events;
}

/**
 * Send audio and receive turn events from the backend SSE endpoint.
 *
 * React Native does not support ReadableStream on fetch responses,
 * and XHR onprogress/responseText is unreliable for incremental streaming.
 * This implementation waits for the full SSE response, then yields all
 * parsed events. The UI will update once the backend completes processing.
 *
 * TODO: Add true streaming support via a native SSE module or polyfill
 * for real-time event delivery (ai_response_chunk, tts_audio_url, etc.).
 */
export async function* streamTurnEvents(
  conversationId: string,
  audioFormData: FormData,
): AsyncGenerator<TurnEvent> {
  const deviceId = await getOrCreateDeviceId();
  const url = `${API_BASE_URL}/api/conversations/${conversationId}/turns`;

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'X-Device-Id': deviceId,
      'Accept': 'text/event-stream',
    },
    body: audioFormData,
  });

  if (!response.ok) {
    const bodyText = await response.text().catch(() => '');
    let body: Record<string, unknown> | null = null;
    try { body = JSON.parse(bodyText); } catch { /* not JSON */ }
    const message = (body as Record<string, Record<string, string>> | null)?.error?.message
      ?? (body as Record<string, string> | null)?.detail
      ?? `Stream request failed (HTTP ${response.status})`;
    if (__DEV__) {
      console.warn(`[SSE] Stream error HTTP ${response.status}: ${bodyText}`);
    }
    yield {
      type: 'error',
      data: { code: 'STREAM_ERROR', message },
    };
    return;
  }

  // Read the full response body (all SSE events at once)
  const bodyText = await response.text();

  if (__DEV__) {
    console.log(`[SSE] Received ${bodyText.length} bytes: ${bodyText.substring(0, 200)}`);
  }

  // Parse and yield all SSE events
  const events = parseSSEResponse(bodyText);
  for (const event of events) {
    yield event;
  }
}
