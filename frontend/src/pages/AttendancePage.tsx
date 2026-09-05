import { useEffect, useState } from "react";
import { getAttendance } from "../api/client";
import { AttendanceTable } from "../components/AttendanceTable";
import type { AttendanceListResponse } from "../types/api";

export function AttendancePage() {
  const [search, setSearch] = useState("");
  const [date, setDate] = useState("");
  const [deviceId, setDeviceId] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<AttendanceListResponse>();
  const [error, setError] = useState<string>();

  useEffect(() => { setPage(1); }, [search, date, deviceId]);
  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const result = await getAttendance({ page, page_size: 20, search, date, device_id: deviceId });
        if (active) { setData(result); setError(undefined); }
      } catch (loadError) { if (active) setError(loadError instanceof Error ? loadError.message : "Unable to load attendance data."); }
    };
    void load();
    const timer = window.setInterval(load, 8000);
    return () => { active = false; window.clearInterval(timer); };
  }, [search, date, deviceId, page]);

  return <section className="panel">
    <div className="filters">
      <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search student or number" />
      <input value={date} onChange={(event) => setDate(event.target.value)} type="date" aria-label="Attendance date" />
      <input value={deviceId} onChange={(event) => setDeviceId(event.target.value)} placeholder="Device ID" />
    </div>
    {error ? <div className="error-state"><h2>Unable to load attendance data.</h2><p>{error}</p></div> : !data ? <div className="loading">Loading attendance records…</div> : <>
      <AttendanceTable records={data.items} />
      <div className="pagination"><button disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button><span>Page {data.page} of {Math.max(data.pages, 1)}</span><button disabled={data.pages === 0 || page >= data.pages} onClick={() => setPage(page + 1)}>Next</button></div>
    </>}
  </section>;
}
