import Constants from 'expo-constants';

import { getAuthToken } from '@/services/token-provider';
import type { ApiResponse } from '@/types/api';

const API_BASE_URL = Constants.expoConfig?.extra?.apiBaseUrl ?? 'http://localhost:8000';

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

export const apiClient = {
  async get<T>(path: string): Promise<ApiResponse<T>> {
    const headers = await getHeaders();
    const response = await fetch(`${API_BASE_URL}${path}`, { headers });
    return handleResponse<T>(response);
  },

  async post<T>(path: string, body?: unknown): Promise<ApiResponse<T>> {
    const headers = await getHeaders();
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: 'POST',
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
    return handleResponse<T>(response);
  },

  async delete<T = void>(path: string): Promise<ApiResponse<T>> {
    const headers = await getHeaders();
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: 'DELETE',
      headers,
    });
    return handleResponse<T>(response);
  },

  async postStream(path: string, formData: FormData): Promise<Response> {
    const headers = await getAuthHeaders();
    return fetch(`${API_BASE_URL}${path}`, {
      method: 'POST',
      headers,
      body: formData,
    });
  },
};
