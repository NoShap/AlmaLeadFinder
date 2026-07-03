export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type LeadState = "PENDING" | "REACHED_OUT";

export interface Lead {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  resume_filename: string;
  state: LeadState;
  created_at: string;
  updated_at: string;
  reached_out_at: string | null;
}

export interface LeadList {
  items: Lead[];
  total: number;
}

interface ApiFieldError {
  loc: (string | number)[];
  msg: string;
}

/** Error carrying per-field messages so forms can render errors inline. */
export class ApiError extends Error {
  status: number;
  fieldErrors: Record<string, string>;

  constructor(status: number, message: string, fieldErrors: Record<string, string> = {}) {
    super(message);
    this.status = status;
    this.fieldErrors = fieldErrors;
  }
}

async function throwApiError(response: Response): Promise<never> {
  let message = `Request failed (${response.status})`;
  const fieldErrors: Record<string, string> = {};
  try {
    const body = await response.json();
    if (typeof body.detail === "string") {
      message = body.detail;
    } else if (Array.isArray(body.detail)) {
      for (const err of body.detail as ApiFieldError[]) {
        const field = String(err.loc[err.loc.length - 1]);
        fieldErrors[field] = err.msg;
      }
      message = "Please fix the highlighted fields.";
    }
  } catch {
    // non-JSON error body; keep the generic message
  }
  throw new ApiError(response.status, message, fieldErrors);
}

export async function submitLead(form: FormData): Promise<Lead> {
  const response = await fetch(`${API_URL}/api/leads`, { method: "POST", body: form });
  if (!response.ok) await throwApiError(response);
  return response.json();
}

export async function login(email: string, password: string): Promise<string> {
  const response = await fetch(`${API_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) await throwApiError(response);
  const body = await response.json();
  return body.access_token as string;
}

export async function loginWithGoogle(credential: string): Promise<string> {
  const response = await fetch(`${API_URL}/api/auth/google`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ credential }),
  });
  if (!response.ok) await throwApiError(response);
  const body = await response.json();
  return body.access_token as string;
}

function authHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}

export async function fetchLeads(token: string): Promise<LeadList> {
  const response = await fetch(`${API_URL}/api/leads?limit=200`, {
    headers: authHeaders(token),
    cache: "no-store",
  });
  if (!response.ok) await throwApiError(response);
  return response.json();
}

export async function markReachedOut(token: string, leadId: string): Promise<Lead> {
  const response = await fetch(`${API_URL}/api/leads/${leadId}`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ state: "REACHED_OUT" }),
  });
  if (!response.ok) await throwApiError(response);
  return response.json();
}

export async function downloadResume(token: string, lead: Lead): Promise<void> {
  const response = await fetch(`${API_URL}/api/leads/${lead.id}/resume`, {
    headers: authHeaders(token),
  });
  if (!response.ok) await throwApiError(response);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = lead.resume_filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

// Token lives in a cookie (not localStorage) so Next.js middleware can gate /admin
// routes server-side. Not HttpOnly because the client attaches it as a Bearer header;
// the API re-validates signature, expiry, and allowlist on every request regardless.
const TOKEN_KEY = "alma_admin_token";
const TOKEN_MAX_AGE_SECONDS = 8 * 60 * 60;

export function getStoredToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${TOKEN_KEY}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

export function storeToken(token: string): void {
  document.cookie = `${TOKEN_KEY}=${encodeURIComponent(token)}; path=/; max-age=${TOKEN_MAX_AGE_SECONDS}; samesite=lax`;
}

export function clearToken(): void {
  document.cookie = `${TOKEN_KEY}=; path=/; max-age=0`;
}
