import Constants from 'expo-constants';

import { getAuthToken } from '@/services/token-provider';
import type { ApiResponse } from '@/types/api';

const API_BASE_URL = Constants.expoConfig?.extra?.apiBaseUrl ?? 'http://localhost:8000';

/**
 * Default timeout for JSON API calls (get/post). Chosen to catch genuine
 * hangs (network dead, server wedged, etc.) without aborting slow-but-
 * legitimate requests such as a Cloud Run cold start followed by a
 * complex backend query. Callers can override via `{ timeoutMs }`.
 */
export const DEFAULT_TIMEOUT_MS = 15_000;

/**
 * Shorter default for DELETE. Side-effect operations are expected to be
 * fast — if a delete is genuinely taking this long, something is wrong
 * and we want to fail fast.
 */
export const DELETE_TIMEOUT_MS = 10_000;

/**
 * Per-call options shared by get/post/delete. Streaming endpoints
 * (`postStream`) intentionally do NOT accept a timeout — SSE is
 * long-lived by design.
 */
export interface RequestOptions {
  /** Override the default timeout (ms). Pass 0 to disable. */
  timeoutMs?: number;
}

/**
 * Build request headers with Firebase auth token.
 */
async function getHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  const token = await getAuthToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  return headers;
}

/**
 * Build auth-only headers (no Content-Type) for FormData requests.
 */
async function getAuthHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = {};

  const token = await getAuthToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  return headers;
}

/**
 * `fetch` wrapper that aborts the request after `timeoutMs` using
 * AbortController. Pass `timeoutMs = 0` to disable the timeout entirely
 * (used for streaming). On abort, `fetch` rejects with an `AbortError`
 * which the caller translates into a `TIMEOUT_ERROR` envelope.
 */
async function fetchWithTimeout(
  url: string,
  init: RequestInit,
  timeoutMs: number,
): Promise<Response> {
  if (timeoutMs <= 0) {
    return fetch(url, init);
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

async function handleResponse<T>(response: Response): Promise<ApiResponse<T>> {
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    return {
      error: body?.error ?? {
        code: 'UNKNOWN_ERROR',
        message: `Request failed with status ${response.status}`,
      },
    };
  }
  const data = await response.json();
  return { data };
}

/**
 * True when the rejection was produced by `AbortController.abort()`.
 * React Native's `fetch` surfaces aborts as a `DOMException` with
 * `name === 'AbortError'` on the runtime-provided Error polyfill.
 */
function isAbortError(err: unknown): boolean {
  return err instanceof Error && err.name === 'AbortError';
}

function timeoutErrorResponse<T>(timeoutMs: number): ApiResponse<T> {
  return {
    error: {
      code: 'TIMEOUT_ERROR',
      message: `Request timed out after ${timeoutMs}ms`,
    },
  };
}

export const apiClient = {
  async get<T>(path: string, options?: RequestOptions): Promise<ApiResponse<T>> {
    const timeoutMs = options?.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    try {
      const headers = await getHeaders();
      const response = await fetchWithTimeout(
        `${API_BASE_URL}${path}`,
        { headers },
        timeoutMs,
      );
      return handleResponse<T>(response);
    } catch (err) {
      if (isAbortError(err)) {
        return timeoutErrorResponse<T>(timeoutMs);
      }
      throw err;
    }
  },

  async post<T>(
    path: string,
    body?: unknown,
    options?: RequestOptions,
  ): Promise<ApiResponse<T>> {
    const timeoutMs = options?.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    try {
      const headers = await getHeaders();
      const response = await fetchWithTimeout(
        `${API_BASE_URL}${path}`,
        {
          method: 'POST',
          headers,
          body: body ? JSON.stringify(body) : undefined,
        },
        timeoutMs,
      );
      return handleResponse<T>(response);
    } catch (err) {
      if (isAbortError(err)) {
        return timeoutErrorResponse<T>(timeoutMs);
      }
      throw err;
    }
  },

  async delete<T = void>(
    path: string,
    options?: RequestOptions,
  ): Promise<ApiResponse<T>> {
    const timeoutMs = options?.timeoutMs ?? DELETE_TIMEOUT_MS;
    try {
      const headers = await getHeaders();
      const response = await fetchWithTimeout(
        `${API_BASE_URL}${path}`,
        {
          method: 'DELETE',
          headers,
        },
        timeoutMs,
      );
      return handleResponse<T>(response);
    } catch (err) {
      if (isAbortError(err)) {
        return timeoutErrorResponse<T>(timeoutMs);
      }
      throw err;
    }
  },

  async postStream(path: string, formData: FormData): Promise<Response> {
    // No timeout: SSE is long-lived by design. Death detection belongs at
    // the stream-consumer layer, not here.
    const headers = await getAuthHeaders();
    return fetch(`${API_BASE_URL}${path}`, {
      method: 'POST',
      headers,
      body: formData,
    });
  },
};
