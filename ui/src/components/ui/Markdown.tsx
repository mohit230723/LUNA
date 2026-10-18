import React from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import styles from './Markdown.module.css';

export interface MarkdownProps {
  content: string;
  onCidClick?: (cid: string) => void;
  entityNames?: Record<string, string>;
  className?: string;
}

export const Markdown: React.FC<MarkdownProps> = ({
  content,
  onCidClick,
  entityNames = {},
  className = '',
}) => {
  // Pre-process [[cid]] citations into special code syntax `cid:<cid>`
  const processedContent = content.replace(/\[\[(.*?)\]\]/g, '`cid:$1`');

  return (
    <div className={`${styles.markdown} ${className}`}>
      <ReactMarkdown
        rehypePlugins={[rehypeSanitize]}
        components={{
          h1: ({ children }) => <h1 className={styles.heading1}>{children}</h1>,
          h2: ({ children }) => <h2 className={styles.heading2}>{children}</h2>,
          h3: ({ children }) => <h3 className={styles.heading3}>{children}</h3>,
          p: ({ children }) => <p className={styles.paragraph}>{children}</p>,
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className={styles.link}
            >
              {children}
            </a>
          ),
          code: ({ className: codeClassName, children, ...props }) => {
            const raw = String(children).trim();
            if (raw.startsWith('cid:')) {
              const cid = raw.slice(4);
              const displayName = entityNames[cid] || cid;
              return (
                <button
                  type="button"
                  className={styles.cidChip}
                  onClick={() => onCidClick && onCidClick(cid)}
                  title={`Focus node ${cid} in trace`}
                >
                  {displayName}
                </button>
              );
            }

            if (onCidClick && (/^[a-z0-9_-]+:[a-z0-9_-]+/i.test(raw) || /^cust-[a-zA-Z0-9_-]+$/.test(raw))) {
              const displayName = entityNames[raw] || raw;
              return (
                <button
                  type="button"
                  className={styles.cidChip}
                  onClick={() => onCidClick(raw)}
                  title={`Focus node ${raw} in trace`}
                >
                  {displayName}
                </button>
              );
            }

            return (
              <code className={`${styles.inlineCode} ${codeClassName || ''}`} {...props}>
                {children}
              </code>
            );
          },
          pre: ({ children }) => <pre className={styles.codeBlock}>{children}</pre>,
          table: ({ children }) => <table className={styles.table}>{children}</table>,
          th: ({ children }) => <th className={styles.th}>{children}</th>,
          td: ({ children }) => <td className={styles.td}>{children}</td>,
        }}
      >
        {processedContent}
      </ReactMarkdown>
    </div>
  );
};
