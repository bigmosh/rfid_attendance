import type { AttendanceRecord } from "../types/api";

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" }).format(new Date(value));
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
              <td>{formatDate(record.event_time)}</td>
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
