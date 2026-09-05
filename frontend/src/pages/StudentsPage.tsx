import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { createStudent, listStudents } from "../api/client";
import type { StudentListResponse, StudentStatus } from "../types/api";

function cardLabel(status: "active" | "disabled" | null): string {
  if (status === "active") return "Registered";
  if (status === "disabled") return "Disabled";
  return "Not registered";
}

export function StudentsPage() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<"" | StudentStatus>("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<StudentListResponse>();
  const [error, setError] = useState<string>();
  const [showForm, setShowForm] = useState(false);
  const [studentNumber, setStudentNumber] = useState("");
  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState<string>();

  const loadStudents = async (targetPage = page) => {
    try {
      const result = await listStudents({ page: targetPage, page_size: 20, search, status });
      setData(result);
      setError(undefined);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load students.");
    }
  };

  useEffect(() => { setPage(1); }, [search, status]);
  useEffect(() => { void loadStudents(); }, [page, search, status]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(undefined);
    try {
      const student = await createStudent({ student_number: studentNumber, name });
      setStudentNumber("");
      setName("");
      setShowForm(false);
      setSuccess(`${student.name} was added successfully.`);
      setPage(1);
      await loadStudents(1);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Unable to add student.");
    } finally {
      setSubmitting(false);
    }
  };

  return <section className="panel students-panel">
    <div className="panel-heading action-heading">
      <div><h2>Students</h2><p>Manage student records and their RFID card status.</p></div>
      <button onClick={() => { setShowForm(true); setSuccess(undefined); }}>+ Add Student</button>
    </div>
    <div className="filters">
      <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search students or number" />
      <select value={status} onChange={(event) => setStatus(event.target.value as "" | StudentStatus)} aria-label="Student status">
        <option value="">Status: All</option><option value="active">Active</option><option value="inactive">Inactive</option>
      </select>
    </div>
    {success ? <div className="success-state">{success}</div> : null}
    {error ? <div className="error-state"><h2>Unable to complete student action.</h2><p>{error}</p></div> : !data ? <div className="loading">Loading students…</div> : data.items.length === 0 ? <div className="empty-state">No students found.</div> : <>
      <div className="table-wrap"><table><thead><tr><th>Name</th><th>Student Number</th><th>RFID Card</th><th>Status</th></tr></thead><tbody>
        {data.items.map((student) => <tr key={student.id} className="clickable-row"><td><Link to={`/students/${student.id}`}>{student.name}</Link></td><td>{student.student_number}</td><td>{cardLabel(student.rfid_card_status)}</td><td><span className={`status ${student.status}`}>{student.status}</span></td></tr>)}
      </tbody></table></div>
      <div className="pagination"><button disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button><span>Page {data.page} of {Math.max(data.pages, 1)}</span><button disabled={data.pages === 0 || page >= data.pages} onClick={() => setPage(page + 1)}>Next</button></div>
    </>}
    {showForm ? <div className="modal-backdrop" role="presentation"><form className="modal" onSubmit={submit}><div className="panel-heading"><div><h2>Add Student</h2><p>Create a student record before manual RFID assignment.</p></div></div><label>Student Number<input required maxLength={64} value={studentNumber} onChange={(event) => setStudentNumber(event.target.value)} /></label><label>Full Name<input required maxLength={255} value={name} onChange={(event) => setName(event.target.value)} /></label><div className="form-actions"><button type="button" className="secondary" onClick={() => setShowForm(false)}>Cancel</button><button type="submit" disabled={submitting}>{submitting ? "Adding…" : "Add Student"}</button></div></form></div> : null}
  </section>;
}
