"use client";

import { FormEvent, useRef, useState } from "react";
import { ApiError, submitLead } from "@/lib/api";

export default function LeadFormPage() {
  const formRef = useRef<HTMLFormElement>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setFormError(null);
    setFieldErrors({});
    try {
      await submitLead(new FormData(event.currentTarget));
      setSubmitted(true);
    } catch (error) {
      if (error instanceof ApiError) {
        setFormError(error.message);
        setFieldErrors(error.fieldErrors);
      } else {
        setFormError("Something went wrong. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (submitted) {
    return (
      <div className="card narrow success-panel">
        <div className="check">✅</div>
        <h1>Thanks — we got it!</h1>
        <p className="subtitle">
          Check your inbox for a confirmation. One of our attorneys will review your
          background and reach out shortly.
        </p>
        <button
          className="secondary"
          onClick={() => {
            formRef.current?.reset();
            setSubmitted(false);
          }}
        >
          Submit another
        </button>
      </div>
    );
  }

  return (
    <div className="card narrow">
      <h1>Get an assessment</h1>
      <p className="subtitle">
        Tell us about yourself and share your resume — an Alma attorney will review your
        background and reach out.
      </p>

      {formError && <div className="form-error">{formError}</div>}

      <form ref={formRef} onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="first_name">First name</label>
          <input id="first_name" name="first_name" type="text" required maxLength={255} />
          {fieldErrors.first_name && (
            <div className="field-error">{fieldErrors.first_name}</div>
          )}
        </div>

        <div className="field">
          <label htmlFor="last_name">Last name</label>
          <input id="last_name" name="last_name" type="text" required maxLength={255} />
          {fieldErrors.last_name && (
            <div className="field-error">{fieldErrors.last_name}</div>
          )}
        </div>

        <div className="field">
          <label htmlFor="email">Email</label>
          <input id="email" name="email" type="email" required />
          {fieldErrors.email && <div className="field-error">{fieldErrors.email}</div>}
        </div>

        <div className="field">
          <label htmlFor="resume">Resume / CV</label>
          <input id="resume" name="resume" type="file" accept=".pdf,.doc,.docx" required />
          <div className="hint">PDF or Word document, up to 5 MB.</div>
          {fieldErrors.resume && <div className="field-error">{fieldErrors.resume}</div>}
        </div>

        <button type="submit" disabled={submitting}>
          {submitting ? "Submitting…" : "Submit"}
        </button>
      </form>
    </div>
  );
}
