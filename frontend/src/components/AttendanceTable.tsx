import type { AttendanceRecord } from "../types/api";

function formatAttendanceDate(value: string): string {
  // attendance_date is already the backend-authoritative APP_TIMEZONE date.
  // Use UTC formatting so a browser timezone cannot shift the date value.
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeZone: "UTC",
  }).format(new Date(`${value}T12:00:00Z`));
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

export function AttendanceTable({ records }: { records: AttendanceRecord[] }) {
  if (!records.length) {
    return <div className="empty-state">No attendance records match the current filters.</div>;
  }
  return (
    <div className="table-wrap">
      <table>
        <thead><tr><th>Student</th><th>Student Number</th><th>Date</th><th>Time</th><th>Device</th><th>Status</th></tr></thead>
        <tbody>
          {records.map((record) => (
            <tr key={record.id}>
              <td>{record.student.name}</td>
              <td>{record.student.student_number}</td>
              <td>{formatAttendanceDate(record.attendance_date)}</td>
              <td>{formatTime(record.event_time)}</td>
              <td>{record.device.name}</td>
              <td><span className="status">{record.status}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
