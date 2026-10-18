import React from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import styles from './Markdown.module.css';

export interface MarkdownProps {
  content: string;
  onCidClick?: (cid: string) => void;
  className?: string;
}

export const Markdown: React.FC<MarkdownProps> = ({
  content,
  onCidClick,
  className = '',
}) => {
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
            const codeString = String(children).trim();
            // If the code is a customer ID (e.g. cust-000) and onCidClick is provided, render as clickable chip
            if (onCidClick && /^cust-[a-zA-Z0-9_-]+$/.test(codeString)) {
              return (
                <button
                  type="button"
                  className={styles.cidChip}
                  onClick={() => onCidClick(codeString)}
                  title={`Focus node ${codeString} in trace`}
                >
                  {codeString}
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
        {content}
      </ReactMarkdown>
    </div>
  );
};
