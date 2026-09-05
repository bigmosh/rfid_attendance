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
