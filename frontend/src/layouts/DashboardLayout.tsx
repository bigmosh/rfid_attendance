import { NavLink, Outlet, useLocation } from "react-router-dom";

const pageTitles: Record<string, string> = {
  "/": "Overview",
  "/attendance": "Attendance",
  "/students": "Students",
  "/devices": "Devices",
};

export function DashboardLayout() {
  const location = useLocation();
  const pageTitle = location.pathname.startsWith("/students/")
    ? "Student Details"
    : (pageTitles[location.pathname] ?? "Dashboard");
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">RF</span><span>RFID Attendance<br />System</span></div>
        <nav>
          <NavLink to="/" end>Overview</NavLink>
          <NavLink to="/attendance">Attendance</NavLink>
          <NavLink to="/students">Students</NavLink>
          <NavLink to="/devices">Devices</NavLink>
        </nav>
        <div className="sidebar-foot">Savonia UAS · IoT Thesis</div>
      </aside>
      <main className="main-content">
        <header><p className="eyebrow">RFID ATTENDANCE SYSTEM</p><h1>{pageTitle}</h1></header>
        <Outlet />
      </main>
    </div>
  );
}
