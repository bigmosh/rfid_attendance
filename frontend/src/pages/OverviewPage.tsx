import { useEffect, useState } from "react";
import { getAttendance, getDashboardSummary } from "../api/client";
import { AttendanceTable } from "../components/AttendanceTable";
import type { AttendanceListResponse, DashboardSummary } from "../types/api";

const cards: Array<[keyof DashboardSummary, string]> = [
  ["total_students", "Total Students"],
  ["attendance_today", "Attendance Today"],
  ["registered_devices", "Registered Devices"],
  ["active_rfid_cards", "Active RFID Cards"],
];

export function OverviewPage() {
  const [summary, setSummary] = useState<DashboardSummary>();
  const [attendance, setAttendance] = useState<AttendanceListResponse>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const [nextSummary, nextAttendance] = await Promise.all([
          getDashboardSummary(),
          getAttendance({ page: 1, page_size: 8 }),
        ]);
        if (active) { setSummary(nextSummary); setAttendance(nextAttendance); setError(undefined); }
      } catch (loadError) {
        if (active) setError(loadError instanceof Error ? loadError.message : "Unable to load attendance data.");
      }
    };
    void load();
    const timer = window.setInterval(load, 8000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);

  if (error) return <div className="error-state"><h2>Unable to load attendance data.</h2><p>{error}</p></div>;
  if (!summary || !attendance) return <div className="loading">Loading dashboard data…</div>;
  return <>
    <section className="summary-grid">
      {cards.map(([key, label]) => <article className="summary-card" key={key}><p>{label}</p><strong>{summary[key]}</strong></article>)}
    </section>
    <section className="panel"><div className="panel-heading"><div><h2>Recent Attendance</h2><p>Automatically refreshed every 8 seconds.</p></div></div><AttendanceTable records={attendance.items} /></section>
  </>;
}
