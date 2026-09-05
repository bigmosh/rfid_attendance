export interface Student {
  id: number;
  student_number: string;
  name: string;
}

export interface Device {
  device_id: string;
  name: string;
}

export interface AttendanceRecord {
  id: number;
  student: Student;
  device: Device;
  event_time: string;
  server_received_at: string;
  status: "recorded";
}

export interface AttendanceListResponse {
  items: AttendanceRecord[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

export interface DashboardSummary {
  total_students: number;
  attendance_today: number;
  registered_devices: number;
  active_rfid_cards: number;
}

export type StudentStatus = "active" | "inactive";
export type RFIDCardStatus = "active" | "disabled";

export interface RFIDCard {
  id: number;
  uid: string;
  status: RFIDCardStatus;
  created_at: string;
}

export interface StudentListItem extends Student {
  status: StudentStatus;
  rfid_card_status: RFIDCardStatus | null;
}

export interface StudentDetail extends Student {
  status: StudentStatus;
  created_at: string;
  rfid_card: RFIDCard | null;
}

export interface StudentListResponse {
  items: StudentListItem[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

export interface StudentCreateInput {
  student_number: string;
  name: string;
}

export interface StudentUpdateInput {
  student_number?: string;
  name?: string;
  status?: StudentStatus;
}

export interface EnrollmentDevice {
  id: number;
  device_id: string;
  name: string;
  status: string;
  last_seen: string | null;
}

export type EnrollmentStatus = "pending" | "completed" | "cancelled" | "expired" | "failed";

export interface EnrollmentStudent extends Student {}

export interface EnrollmentResponse {
  id: number;
  status: EnrollmentStatus;
  student: EnrollmentStudent;
  device: Pick<EnrollmentDevice, "device_id" | "name">;
  created_at: string;
  expires_at: string;
  completed_at: string | null;
  failure_reason: string | null;
}
