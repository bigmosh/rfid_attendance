import type { AttendanceListResponse, DashboardSummary } from "../types/api";

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

async function getJson<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}${path}`);
  } catch {
    throw new Error("Unable to connect to the dashboard API.");
  }
  if (!response.ok) {
    throw new Error(`Dashboard API returned HTTP ${response.status}.`);
  }
  try {
    return (await response.json()) as T;
  } catch {
    throw new Error("Dashboard API returned an invalid response.");
  }
}

export function getDashboardSummary(): Promise<DashboardSummary> {
  return getJson<DashboardSummary>("/api/v1/dashboard/summary");
}

export function getAttendance(params: Record<string, string | number | undefined>): Promise<AttendanceListResponse> {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") query.set(key, String(value));
  });
  const suffix = query.size ? `?${query.toString()}` : "";
  return getJson<AttendanceListResponse>(`/api/v1/attendance${suffix}`);
}
