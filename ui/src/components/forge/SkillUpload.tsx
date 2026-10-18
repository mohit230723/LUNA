import React, { useState } from 'react';
import { getApi } from '../../api';
import './forge.css';

export interface SkillUploadProps {
  onChanged: () => void;
}

export const SkillUpload: React.FC<SkillUploadProps> = ({ onChanged }) => {
  const [skill, setSkill] = useState<File | null>(null);
  const [refs, setRefs] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const upload = async () => {
    if (!skill) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    setWarnings([]);
    try {
      const res = await getApi().uploadForgeSkill(skill, refs);
      setMessage(`Uploaded ${res.skill_id} (${res.status.replace('_', ' ')}).`);
      setWarnings(res.warnings);
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed.');
    } finally {
      setBusy(false);
    }
  };

  const reimport = async () => {
    setBusy(true);
    setError(null);
    setMessage(null);
    setWarnings([]);
    try {
      const res = await getApi().reimportForgeSkills();
      setMessage(`Re-imported ${res.length} skill${res.length === 1 ? '' : 's'}.`);
      setWarnings(res.flatMap((r) => r.warnings.map((w) => `${r.skill_id}: ${w}`)));
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Re-import failed.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="forge-panel" aria-labelledby="forge-upload-title">
      <h2 className="forge-panel-title" id="forge-upload-title">
        Add a skill
      </h2>
      <div className="forge-field">
        <label htmlFor="forge-upload-skill">SKILL.md file</label>
        <input
          id="forge-upload-skill"
          type="file"
          accept=".md,text/markdown"
          onChange={(e) => setSkill(e.target.files?.[0] ?? null)}
        />
      </div>
      <div className="forge-field">
        <label htmlFor="forge-upload-refs">Reference files (optional)</label>
        <input
          id="forge-upload-refs"
          type="file"
          multiple
          onChange={(e) => setRefs(Array.from(e.target.files ?? []))}
        />
      </div>
      <div className="forge-actions">
        <button type="button" className="forge-btn" disabled={!skill || busy} onClick={upload}>
          Upload skill
        </button>
        <button type="button" className="forge-btn" disabled={busy} onClick={reimport}>
          Re-import repo skills
        </button>
      </div>
      <div role="status" aria-live="polite">
        {message && <p className="forge-muted">{message}</p>}
        {warnings.length > 0 && (
          <ul className="forge-warnings" aria-label="Upload warnings">
            {warnings.map((w, i) => (
              <li key={i}>Warning: {w}</li>
            ))}
          </ul>
        )}
      </div>
      {error && (
        <p className="forge-error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
};

export default SkillUpload;
