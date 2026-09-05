import { Route, Routes } from "react-router-dom";
import { DashboardLayout } from "./layouts/DashboardLayout";
import { AttendancePage } from "./pages/AttendancePage";
import { OverviewPage } from "./pages/OverviewPage";
import { PlaceholderPage } from "./pages/PlaceholderPage";
import { StudentDetailsPage } from "./pages/StudentDetailsPage";
import { StudentsPage } from "./pages/StudentsPage";

export default function App() {
  return <Routes><Route element={<DashboardLayout />}><Route path="/" element={<OverviewPage />} /><Route path="/attendance" element={<AttendancePage />} /><Route path="/students" element={<StudentsPage />} /><Route path="/students/:studentId" element={<StudentDetailsPage />} /><Route path="/devices" element={<PlaceholderPage title="Device" />} /></Route></Routes>;
}
