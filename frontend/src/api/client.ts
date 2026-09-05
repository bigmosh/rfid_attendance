import type {
  AttendanceListResponse,
  DashboardSummary,
  RFIDCard,
  RFIDCardStatus,
  StudentCreateInput,
  StudentDetail,
  StudentListResponse,
  StudentUpdateInput,
} from "../types/api";

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message: string, public readonly status?: number, public readonly code?: string) {
    super(message);
  }
}

function errorMessage(payload: unknown, fallback: string): { message: string; code?: string } {
  if (!payload || typeof payload !== "object") return { message: fallback };
  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === "string") return { message: detail };
  if (detail && typeof detail === "object") {
    const structured = detail as { message?: unknown; code?: unknown };
    if (typeof structured.message === "string") {
      return { message: structured.message, code: typeof structured.code === "string" ? structured.code : undefined };
    }
  }
  if (Array.isArray(detail) && typeof detail[0]?.msg === "string") return { message: detail[0].msg };
  return { message: fallback };
}

async function requestJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}${path}`, options);
  } catch {
    throw new ApiError("Unable to connect to the dashboard API.");
  }
  if (!response.ok) {
    let payload: unknown;
    try { payload = await response.json(); } catch { payload = undefined; }
    const error = errorMessage(payload, `Dashboard API returned HTTP ${response.status}.`);
    throw new ApiError(error.message, response.status, error.code);
  }
  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError("Dashboard API returned an invalid response.");
  }
}

function getJson<T>(path: string): Promise<T> {
  return requestJson<T>(path);
}

function sendJson<T>(path: string, method: "POST" | "PATCH", body?: unknown): Promise<T> {
  return requestJson<T>(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
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

export function listStudents(params: Record<string, string | number | undefined>): Promise<StudentListResponse> {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") query.set(key, String(value));
  });
  const suffix = query.size ? `?${query.toString()}` : "";
  return getJson<StudentListResponse>(`/api/v1/students${suffix}`);
}

export function getStudent(studentId: number): Promise<StudentDetail> {
  return getJson<StudentDetail>(`/api/v1/students/${studentId}`);
}

export function createStudent(student: StudentCreateInput): Promise<StudentDetail> {
  return sendJson<StudentDetail>("/api/v1/students", "POST", student);
}

export function updateStudent(studentId: number, student: StudentUpdateInput): Promise<StudentDetail> {
  return sendJson<StudentDetail>(`/api/v1/students/${studentId}`, "PATCH", student);
}

export function assignCard(studentId: number, uid: string): Promise<RFIDCard> {
  return sendJson<RFIDCard>(`/api/v1/students/${studentId}/rfid-card`, "POST", { uid });
}

export function replaceCard(studentId: number, uid: string): Promise<RFIDCard> {
  return sendJson<RFIDCard>(`/api/v1/students/${studentId}/rfid-card/replace`, "POST", { uid });
}

export function updateCardStatus(studentId: number, status: RFIDCardStatus): Promise<RFIDCard> {
  return sendJson<RFIDCard>(`/api/v1/students/${studentId}/rfid-card`, "PATCH", { status });
}

export function unassignCard(studentId: number): Promise<RFIDCard> {
  return sendJson<RFIDCard>(`/api/v1/students/${studentId}/rfid-card/unassign`, "POST");
}

export function getStudentAttendance(studentId: number, params: Record<string, string | number | undefined>): Promise<AttendanceListResponse> {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") query.set(key, String(value));
  });
  const suffix = query.size ? `?${query.toString()}` : "";
  return getJson<AttendanceListResponse>(`/api/v1/students/${studentId}/attendance${suffix}`);
}
