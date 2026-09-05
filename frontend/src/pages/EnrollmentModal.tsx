import { useEffect, useMemo, useState } from "react";
import { cancelEnrollment, createEnrollment, getEnrollment, listDevices } from "../api/client";
import type { EnrollmentDevice, EnrollmentResponse, StudentDetail } from "../types/api";

type ModalState = "preparing" | "waiting" | "completed" | "cancelled" | "expired" | "failed";

function secondsRemaining(expiresAt?: string): number {
  if (!expiresAt) return 0;
  return Math.max(0, Math.ceil((new Date(expiresAt).getTime() - Date.now()) / 1000));
}

export function EnrollmentModal({ student, replaceExisting, onClose, onCompleted }: {
  student: StudentDetail;
  replaceExisting: boolean;
  onClose: () => void;
  onCompleted: () => Promise<void>;
}) {
  const [devices, setDevices] = useState<EnrollmentDevice[]>([]);
  const [deviceId, setDeviceId] = useState("");
  const [enrollment, setEnrollment] = useState<EnrollmentResponse>();
  const [modalState, setModalState] = useState<ModalState>("preparing");
  const [error, setError] = useState<string>();
  const [remaining, setRemaining] = useState(0);
  const activeDevices = useMemo(() => devices.filter((device) => device.status === "active"), [devices]);

  useEffect(() => {
    const loadDevices = async () => {
      try {
        const result = await listDevices();
        setDevices(result);
        const active = result.filter((device) => device.status === "active");
        if (active.length === 1) setDeviceId(active[0].device_id);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Unable to load attendance devices.");
      }
    };
    void loadDevices();
  }, []);

  useEffect(() => {
    if (!enrollment || modalState !== "waiting") return;
    const refresh = async () => {
      try {
        const next = await getEnrollment(enrollment.id);
        setEnrollment(next);
        setRemaining(secondsRemaining(next.expires_at));
        if (
          next.status === "completed"
          || next.status === "cancelled"
          || next.status === "expired"
          || next.status === "failed"
        ) {
          setModalState(next.status);
        }
      } catch (refreshError) {
        setError(refreshError instanceof Error ? refreshError.message : "Unable to check enrollment status.");
      }
    };
    void refresh();
    const poll = window.setInterval(() => void refresh(), 2000);
    return () => window.clearInterval(poll);
  }, [enrollment?.id, modalState]);

  useEffect(() => {
    if (!enrollment || modalState !== "waiting") return;
    setRemaining(secondsRemaining(enrollment.expires_at));
    const timer = window.setInterval(() => setRemaining(secondsRemaining(enrollment.expires_at)), 1000);
    return () => window.clearInterval(timer);
  }, [enrollment?.expires_at, modalState]);

  const begin = async () => {
    if (!deviceId) { setError("Select an active attendance device."); return; }
    setError(undefined);
    try {
      const result = await createEnrollment(student.id, deviceId);
      setEnrollment(result);
      setRemaining(secondsRemaining(result.expires_at));
      setModalState("waiting");
    } catch (beginError) {
      setError(beginError instanceof Error ? beginError.message : "Unable to start enrollment.");
    }
  };

  const cancel = async () => {
    if (!enrollment) { onClose(); return; }
    try {
      const result = await cancelEnrollment(enrollment.id);
      setEnrollment(result);
      if (result.status === "cancelled" || result.status === "expired") {
        setModalState(result.status);
      } else {
        setModalState("failed");
      }
    } catch (cancelError) {
      setError(cancelError instanceof Error ? cancelError.message : "Unable to cancel enrollment.");
    }
  };

  const done = async () => {
    if (modalState === "completed") await onCompleted();
    onClose();
  };

  const isTerminal = modalState === "completed" || modalState === "cancelled" || modalState === "expired" || modalState === "failed";
  return <div className="modal-backdrop" role="presentation"><section className="modal enrollment-modal" aria-label="RFID card enrollment">
    <div className="panel-heading"><div><h2>{replaceExisting ? "Replace RFID Card Using Device" : "Register RFID Card"}</h2><p>{student.name} · {student.student_number}</p></div></div>
    {error ? <div className="error-state"><p>{error}</p></div> : null}
    {modalState === "preparing" ? <><label>Attendance Device<select value={deviceId} onChange={(event) => setDeviceId(event.target.value)}><option value="">Select device</option>{activeDevices.map((device) => <option key={device.id} value={device.device_id}>{device.name}</option>)}</select></label>{activeDevices.length === 0 ? <div className="empty-state">No active attendance devices are available.</div> : null}<div className="form-actions"><button className="secondary" onClick={onClose}>Cancel</button><button disabled={!deviceId} onClick={() => void begin()}>Start Registration</button></div></> : null}
    {modalState === "waiting" ? <div className="enrollment-state"><strong>Waiting for RFID card…</strong><p>Tap the new card on the selected attendance device.</p><p className="meta">Expires in: {remaining} seconds</p><div className="form-actions"><button className="secondary" onClick={() => void cancel()}>Cancel</button></div></div> : null}
    {isTerminal ? <div className="enrollment-state"><strong>{modalState === "completed" ? "RFID Card Registered" : `Registration ${modalState}`}</strong><p>{modalState === "completed" ? "The student details will now show the registered card." : (enrollment?.failure_reason ?? "No card was registered.")}</p><div className="form-actions"><button onClick={() => void done()}>Done</button></div></div> : null}
  </section></div>;
}
