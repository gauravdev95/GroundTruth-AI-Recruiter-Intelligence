/**
 * Client-side pre-flight for the resume drop zone.
 *
 * This is a courtesy, not a control. The server sniffs the file's magic bytes
 * and enforces the size ceiling itself (`domains/resume/parsing.py`), and it is
 * the only opinion that counts — this exists so a student who drops a 40 MB
 * screenshot learns why in a moment rather than after a 40 MB upload.
 *
 * Consequently these checks are deliberately weak where the server's are
 * strong: an extension check cannot tell a real PDF from a renamed one, and it
 * does not try to.
 */

/** Matches `StorageSettings.resume_max_bytes`. Kept in sync by hand; the
 * server rejects anything past it regardless of what this says. */
export const MAX_RESUME_BYTES = 10 * 1024 * 1024;

export const RESUME_ACCEPT = ".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document";

/** The caption under the drop zone. One string so the copy and the rule it
 * describes cannot drift. */
export const RESUME_HINT = "PDF, DOCX (Max 10MB)";

export const LEGACY_DOC_MESSAGE = "Legacy .doc isn't supported — save as PDF or DOCX";

export interface FileRejection {
  reason: string;
}

export function validateResumeFile(file: File): FileRejection | null {
  const name = file.name.toLowerCase();

  // Checked before the general extension test so the student gets the specific
  // remedy — "re-save as PDF" — instead of being told .doc is simply wrong.
  // `python-docx` reads OOXML only, so accepting these would mean a wait
  // ending in a worker failure.
  if (name.endsWith(".doc")) {
    return { reason: LEGACY_DOC_MESSAGE };
  }

  if (!name.endsWith(".pdf") && !name.endsWith(".docx")) {
    return { reason: "That file type isn't supported. Upload a PDF or DOCX." };
  }

  if (file.size > MAX_RESUME_BYTES) {
    return { reason: "That file is larger than 10 MB. Upload a smaller one." };
  }

  if (file.size === 0) {
    return { reason: "That file is empty." };
  }

  return null;
}
