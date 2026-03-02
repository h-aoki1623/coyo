import Constants from 'expo-constants';
import { getOrCreateDeviceId } from '@/services/device-id';
import type { ApiResponse } from '@/types/api';

const API_BASE_URL = Constants.expoConfig?.extra?.apiBaseUrl ?? 'http://localhost:8000';

async function getHeaders(): Promise<Record<string, string>> {
  const deviceId = await getOrCreateDeviceId();
  return {
    'Content-Type': 'application/json',
    'X-Device-Id': deviceId,
  };
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

  async delete(path: string): Promise<void> {
    const headers = await getHeaders();
    await fetch(`${API_BASE_URL}${path}`, {
      method: 'DELETE',
      headers,
    });
  },

  async postStream(path: string, formData: FormData): Promise<Response> {
    const deviceId = await getOrCreateDeviceId();
    return fetch(`${API_BASE_URL}${path}`, {
      method: 'POST',
      headers: { 'X-Device-Id': deviceId },
      body: formData,
    });
  },
};
