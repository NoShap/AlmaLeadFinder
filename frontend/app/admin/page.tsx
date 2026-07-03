"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ApiError,
  Lead,
  clearToken,
  downloadResume,
  fetchLeads,
  getStoredToken,
  markReachedOut,
} from "@/lib/api";

export default function AdminDashboardPage() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyLeadId, setBusyLeadId] = useState<string | null>(null);

  const handleAuthFailure = useCallback(() => {
    clearToken();
    router.push("/admin/login");
  }, [router]);

  useEffect(() => {
    const stored = getStoredToken();
    if (!stored) {
      router.push("/admin/login");
      return;
    }
    setToken(stored);
    fetchLeads(stored)
      .then((body) => setLeads(body.items))
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          handleAuthFailure();
        } else {
          setError("Could not load leads. Is the API running?");
        }
      })
      .finally(() => setLoading(false));
  }, [router, handleAuthFailure]);

  async function handleMarkReachedOut(lead: Lead) {
    if (!token) return;
    setBusyLeadId(lead.id);
    setError(null);
    try {
      const updated = await markReachedOut(token, lead.id);
      setLeads((current) => current.map((l) => (l.id === updated.id ? updated : l)));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        handleAuthFailure();
      } else {
        setError(err instanceof ApiError ? err.message : "Update failed. Please retry.");
      }
    } finally {
      setBusyLeadId(null);
    }
  }

  async function handleDownload(lead: Lead) {
    if (!token) return;
    setError(null);
    try {
      await downloadResume(token, lead);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        handleAuthFailure();
      } else {
        setError("Could not download the resume.");
      }
    }
  }

  if (loading) {
    return <div className="empty">Loading leads…</div>;
  }

  return (
    <div className="card">
      <div className="toolbar">
        <div>
          <h1>Leads</h1>
          <p className="subtitle" style={{ margin: 0 }}>
            {leads.length} lead{leads.length === 1 ? "" : "s"}
          </p>
        </div>
        <button
          className="link"
          onClick={() => {
            clearToken();
            router.push("/admin/login");
          }}
        >
          Sign out
        </button>
      </div>

      {error && <div className="form-error">{error}</div>}

      {leads.length === 0 ? (
        <div className="empty">No leads yet — submissions from the public form appear here.</div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Resume</th>
                <th>Submitted</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {leads.map((lead) => (
                <tr key={lead.id}>
                  <td>
                    {lead.first_name} {lead.last_name}
                  </td>
                  <td>
                    <a href={`mailto:${lead.email}`}>{lead.email}</a>
                  </td>
                  <td>
                    <button
                      className="link truncate"
                      title={lead.resume_filename}
                      onClick={() => handleDownload(lead)}
                    >
                      {lead.resume_filename}
                    </button>
                  </td>
                  <td className="nowrap">
                    {new Date(lead.created_at).toLocaleString(undefined, {
                      dateStyle: "short",
                      timeStyle: "short",
                    })}
                  </td>
                  <td className="nowrap">
                    {lead.state === "PENDING" ? (
                      <span className="badge pending">PENDING</span>
                    ) : (
                      <span className="badge reached-out">REACHED OUT</span>
                    )}
                  </td>
                  <td className="nowrap">
                    {lead.state === "PENDING" && (
                      <button
                        className="secondary"
                        disabled={busyLeadId === lead.id}
                        onClick={() => handleMarkReachedOut(lead)}
                      >
                        {busyLeadId === lead.id ? "Saving…" : "Mark reached out"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
