import React, { useState } from 'react';
import type { ForgeConnectInfo } from '../../api/contract';
import './forge.css';

interface SnippetProps {
  title: string;
  copyLabel: string;
  code: string;
  hint?: string;
}

const Snippet: React.FC<SnippetProps> = ({ title, copyLabel, code, hint }) => {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };
  return (
    <div className="forge-snippet">
      <div className="forge-snippet-head">
        <span>{title}</span>
        <button type="button" className="forge-btn" aria-label={copyLabel} onClick={copy}>
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      {hint && <p className="forge-muted">{hint}</p>}
      <pre className="forge-code">
        <code>{code}</code>
      </pre>
      <span className="visually-hidden" role="status">
        {copied ? `${title} snippet copied` : ''}
      </span>
    </div>
  );
};

export const ConnectCard: React.FC<{ info: ForgeConnectInfo }> = ({ info }) => {
  const { snippets, token_required } = info;
  return (
    <section className="forge-panel" aria-labelledby="forge-connect-title">
      <h2 id="forge-connect-title" className="forge-panel-title">
        Connect an agent
      </h2>
      <p className="forge-muted">
        MCP endpoint <code className="forge-file">{info.mcp_url}</code>
        {token_required && ' (bearer token required; replace <token> with your LUNA token)'}
      </p>
      <Snippet
        title="Claude Code"
        copyLabel="Copy Claude Code command"
        code={token_required ? snippets.claude_code_token : snippets.claude_code}
      />
      <Snippet
        title="Antigravity"
        copyLabel="Copy Antigravity config"
        hint="Agent panel → MCP menu → Manage MCP Servers → View raw config"
        code={token_required ? snippets.antigravity_token : snippets.antigravity}
      />
    </section>
  );
};

export default ConnectCard;
