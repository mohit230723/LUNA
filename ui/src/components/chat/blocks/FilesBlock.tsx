import React, { useState } from 'react';
import { Folder, FileText, ChevronRight, ChevronDown } from 'lucide-react';
import { GhostButton } from '../../ui/GhostButton';
import { Badge } from '../../ui/Badge';
import type { FileNode, ViolationInfo } from '../../../api/contract';
import styles from './blocks.module.css';

export interface FilesBlockProps {
  tree: FileNode[];
  zipUrl: string;
  contractsImplemented: number;
  contractsTotal: number;
  openViolations: ViolationInfo[];
  previewContent?: { path: string; content: string; truncated: boolean };
  onSelectFile?: (path: string) => void;
}

const FileTreeItem: React.FC<{
  node: FileNode;
  level: number;
  onSelectFile?: (path: string) => void;
}> = ({ node, level, onSelectFile }) => {
  const [isOpen, setIsOpen] = useState(true);

  if (node.kind === 'dir') {
    return (
      <div style={{ paddingLeft: level * 16 }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '4px 0',
            cursor: 'pointer',
            color: 'var(--color-chalk)',
            fontSize: '13px',
          }}
          onClick={() => setIsOpen(!isOpen)}
        >
          {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          <Folder size={14} strokeWidth={1.5} />
          <span>{node.path.split('/').pop() || node.path}</span>
        </div>
        {isOpen && node.children && (
          <div>
            {node.children.map((child) => (
              <FileTreeItem
                key={child.path}
                node={child}
                level={level + 1}
                onSelectFile={onSelectFile}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div
      style={{
        paddingLeft: (level + 1) * 16,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingTop: 3,
        paddingBottom: 3,
        cursor: 'pointer',
        fontSize: '13px',
      }}
      onClick={() => onSelectFile && onSelectFile(node.path)}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--color-ash)' }}>
        <FileText size={14} strokeWidth={1.5} />
        <span>{node.path.split('/').pop() || node.path}</span>
      </div>
      {node.bytes !== undefined && (
        <span className={styles.monoMeta}>{node.bytes} B</span>
      )}
    </div>
  );
};

export const FilesBlock: React.FC<FilesBlockProps> = ({
  tree,
  zipUrl,
  contractsImplemented,
  contractsTotal,
  openViolations,
  previewContent,
  onSelectFile,
}) => {
  return (
    <div className={styles.blockCard}>
      <div className={styles.blockHeader}>
        <div>
          <h4 className={styles.blockTitle}>GENERATED ARTIFACTS</h4>
          <span className={styles.monoMeta}>
            {openViolations.length === 0
              ? `${contractsImplemented} of ${contractsTotal} contracts implemented`
              : `${contractsImplemented} of ${contractsTotal} implemented, ${openViolations.length} open`}
          </span>
        </div>
        <a href={zipUrl} download>
          <GhostButton>DOWNLOAD ZIP</GhostButton>
        </a>
      </div>

      {openViolations.length > 0 && (
        <div style={{ padding: '8px 12px', backgroundColor: 'var(--color-obsidian)', borderRadius: 4 }}>
          <span className={styles.monoMeta} style={{ display: 'block', marginBottom: 4 }}>
            OPEN VIOLATIONS
          </span>
          {openViolations.map((v) => (
            <div key={v.id} style={{ fontSize: '12px', color: 'var(--color-chalk)' }}>
              x [{v.kind}] {v.detail}
            </div>
          ))}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: previewContent ? '260px 1fr' : '1fr', gap: 16 }}>
        <div
          style={{
            backgroundColor: 'var(--color-obsidian)',
            border: '1px solid var(--color-graphite)',
            borderRadius: 'var(--radius-card)',
            padding: '12px',
            maxHeight: '320px',
            overflowY: 'auto',
          }}
        >
          {tree.map((node) => (
            <FileTreeItem
              key={node.path}
              node={node}
              level={0}
              onSelectFile={onSelectFile}
            />
          ))}
        </div>

        {previewContent && (
          <div
            style={{
              backgroundColor: 'var(--color-obsidian)',
              border: '1px solid var(--color-graphite)',
              borderRadius: 'var(--radius-card)',
              padding: '12px',
              display: 'flex',
              flexDirection: 'column',
              maxHeight: '320px',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                borderBottom: '1px solid var(--color-graphite)',
                paddingBottom: 6,
                marginBottom: 8,
              }}
            >
              <span className={styles.monoMeta}>{previewContent.path}</span>
              {previewContent.truncated && <Badge size="compact">TRUNCATED</Badge>}
            </div>
            <pre
              style={{
                margin: 0,
                fontFamily: 'var(--font-mono)',
                fontSize: '11px',
                color: 'var(--color-ash)',
                overflow: 'auto',
                whiteSpace: 'pre-wrap',
                flex: 1,
              }}
            >
              {previewContent.content}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
};
