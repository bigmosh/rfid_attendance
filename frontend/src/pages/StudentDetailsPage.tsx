import { FormEvent, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  assignCard,
  getStudent,
  getStudentAttendance,
  replaceCard,
  unassignCard,
  updateCardStatus,
  updateStudent,
} from "../api/client";
import { AttendanceTable } from "../components/AttendanceTable";
import type { AttendanceListResponse, StudentDetail } from "../types/api";

function formatCreatedAt(value: string): string {
  return new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export function StudentDetailsPage() {
  const studentId = Number(useParams().studentId);
  const [student, setStudent] = useState<StudentDetail>();
  const [attendance, setAttendance] = useState<AttendanceListResponse>();
  const [name, setName] = useState("");
  const [studentNumber, setStudentNumber] = useState("");
  const [uid, setUid] = useState("");
  const [error, setError] = useState<string>();
  const [message, setMessage] = useState<string>();
  const [saving, setSaving] = useState(false);

  const load = async () => {
    if (!Number.isInteger(studentId) || studentId < 1) { setError("Student not found."); return; }
    try {
      const [studentResult, attendanceResult] = await Promise.all([
        getStudent(studentId), getStudentAttendance(studentId, { page: 1, page_size: 10 }),
      ]);
      setStudent(studentResult);
      setName(studentResult.name);
      setStudentNumber(studentResult.student_number);
      setAttendance(attendanceResult);
      setError(undefined);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load student.");
    }
  };

  useEffect(() => { void load(); }, [studentId]);

  const perform = async (action: () => Promise<unknown>, successMessage: string) => {
    setSaving(true);
    setError(undefined);
    try {
      await action();
      setMessage(successMessage);
      setUid("");
      await load();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Unable to complete this action.");
    } finally {
      setSaving(false);
    }
  };

  const saveStudent = (event: FormEvent) => {
    event.preventDefault();
    void perform(() => updateStudent(studentId, { name, student_number: studentNumber }), "Student information saved.");
  };
  const changeStudentStatus = () => {
    if (!student) return;
    const next = student.status === "active" ? "inactive" : "active";
    const label = next === "inactive" ? "Deactivate this student? Their attendance history will remain, but future scans will be rejected." : "Reactivate this student?";
    if (window.confirm(label)) void perform(() => updateStudent(studentId, { status: next }), `Student ${next === "active" ? "reactivated" : "deactivated"}.`);
  };
  const submitCard = (event: FormEvent) => {
    event.preventDefault();
    if (!student) return;
    if (student.rfid_card && !window.confirm("Replace this RFID card? The previous card will be disabled and its attendance history preserved.")) return;
    void perform(
      () => student.rfid_card ? replaceCard(studentId, uid) : assignCard(studentId, uid),
      student.rfid_card ? "RFID card replaced. The prior card was disabled." : "RFID card assigned.",
    );
  };

  if (error && !student) return <div className="error-state"><h2>Unable to load student.</h2><p>{error}</p><Link to="/students">Back to students</Link></div>;
  if (!student || !attendance) return <div className="loading">Loading student details…</div>;
  const card = student.rfid_card;
  return <>
    <Link className="back-link" to="/students">← Students</Link>
    {error ? <div className="error-state"><h2>Unable to complete student action.</h2><p>{error}</p></div> : null}
    {message ? <div className="success-state">{message}</div> : null}
    <section className="detail-hero"><div><p className="eyebrow">STUDENT</p><h2>{student.name}</h2><p>{student.student_number} <span className={`status ${student.status}`}>{student.status}</span></p></div><button className="secondary" disabled={saving} onClick={changeStudentStatus}>{student.status === "active" ? "Deactivate Student" : "Reactivate Student"}</button></section>
    <div className="detail-grid">
      <section className="panel"><div className="panel-heading"><div><h2>Student Information</h2><p>Edit the stored student record.</p></div></div><form className="stacked-form" onSubmit={saveStudent}><label>Full Name<input required value={name} onChange={(event) => setName(event.target.value)} /></label><label>Student Number<input required value={studentNumber} onChange={(event) => setStudentNumber(event.target.value)} /></label><p className="meta">Created {formatCreatedAt(student.created_at)}</p><button disabled={saving} type="submit">{saving ? "Saving…" : "Save Student"}</button></form></section>
      <section className="panel"><div className="panel-heading"><div><h2>RFID Card</h2><p>Manual registration only. Physical enrollment is planned for Stage 3.</p></div></div>{card ? <><dl className="detail-list"><div><dt>UID</dt><dd>{card.uid}</dd></div><div><dt>Status</dt><dd><span className={`status ${card.status}`}>{card.status}</span></dd></div></dl><div className="card-actions">{card.status === "active" ? <><button className="secondary" disabled={saving} onClick={() => { if (window.confirm("Disable this RFID card? Future scans will be rejected.")) void perform(() => updateCardStatus(studentId, "disabled"), "RFID card disabled."); }}>Disable Card</button><button className="danger" disabled={saving} onClick={() => { if (window.confirm("Unassign this RFID card? It will be disabled and its attendance history preserved.")) void perform(() => unassignCard(studentId), "RFID card unassigned and disabled."); }}>Unassign Card</button></> : <button disabled={saving} onClick={() => void perform(() => updateCardStatus(studentId, "active"), "RFID card reactivated.")}>Reactivate Card</button>}</div></> : <div className="empty-state">No RFID card registered.</div>}<form className="stacked-form card-form" onSubmit={submitCard}><label>{card ? "Replace RFID Card UID" : "Assign RFID Card UID"}<input required placeholder="77-48-28-61-92" value={uid} onChange={(event) => setUid(event.target.value)} /></label><button disabled={saving} type="submit">{card ? "Replace Card" : "Assign Card"}</button></form></section>
    </div>
    <section className="panel attendance-history"><div className="panel-heading"><div><h2>Attendance History</h2><p>Most recent attendance records for this student.</p></div></div><AttendanceTable records={attendance.items} /></section>
  </>;
}
