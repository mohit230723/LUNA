import React from 'react';
import { StepName, STEP_ORDER } from '../state/pipelineReducer';
import {
  Play,
  Pause,
  SkipForward,
  RotateCcw,
  Shield,
  Activity,
  Layers,
  Sparkles,
} from 'lucide-react';

interface HeaderProps {
  runId: string;
  runStatus: string;
  currentStep: StepName;
  stepProgress: number;
  mode: 'LIVE' | 'REPLAY';
  isPlaying: boolean;
  speed: number;
  replayIndex: number;
  totalReplayEvents: number;
  onToggleMode: (mode: 'LIVE' | 'REPLAY') => void;
  onTogglePlay: () => void;
  onStepNext: () => void;
  onReset: () => void;
  onChangeSpeed: (speed: number) => void;
  onScrub: (index: number) => void;
  onStartLiveRun: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  runId,
  runStatus,
  currentStep,
  stepProgress,
  mode,
  isPlaying,
  speed,
  replayIndex,
  totalReplayEvents,
  onToggleMode,
  onTogglePlay,
  onStepNext,
  onReset,
  onChangeSpeed,
  onScrub,
  onStartLiveRun,
}) => {
  return (
    <header
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
        padding: '12px 20px',
        background: 'var(--bg-surface)',
        borderBottom: '1px solid var(--border-default)',
        zIndex: 50,
      }}
    >
      {/* Top Bar: Brand, Status, Mode, Controls */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        {/* Brand */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '36px',
              height: '36px',
              borderRadius: '8px',
              background: 'linear-gradient(135deg, #1f6feb 0%, #39c5cf 100%)',
              boxShadow: 'var(--shadow-glow-blue)',
            }}
          >
            <Shield size={20} color="#ffffff" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '16px', fontWeight: 800, letterSpacing: '0.05em' }}>
                LUNA OS
              </span>
              <span
                style={{
                  fontSize: '11px',
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--accent-cyan)',
                  padding: '1px 6px',
                  borderRadius: '4px',
                  background: 'rgba(57, 197, 207, 0.1)',
                  border: '1px solid rgba(57, 197, 207, 0.3)',
                }}
              >
                v4.0
              </span>
            </div>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              Autonomous Graph Defense & Multi-Agent Investigation
            </span>
          </div>
        </div>

        {/* Center: Run ID & Status Badge */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {runId && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '4px 10px',
                background: 'var(--bg-panel)',
                border: '1px solid var(--border-default)',
                borderRadius: '6px',
                fontSize: '12px',
                fontFamily: 'var(--font-mono)',
              }}
            >
              <span style={{ color: 'var(--text-muted)' }}>RUN:</span>
              <span style={{ color: 'var(--accent-blue)', fontWeight: 600 }}>{runId}</span>
            </div>
          )}

          <div
            className={`badge ${
              runStatus === 'RUNNING'
                ? 'badge-blue'
                : runStatus === 'AWAITING_APPROVAL'
                ? 'badge-amber'
                : runStatus === 'COMPLETED'
                ? 'badge-benign'
                : 'badge-superseded'
            }`}
          >
            <span
              style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                backgroundColor:
                  runStatus === 'RUNNING'
                    ? 'var(--accent-blue)'
                    : runStatus === 'AWAITING_APPROVAL'
                    ? 'var(--badge-amber)'
                    : runStatus === 'COMPLETED'
                    ? 'var(--verdict-benign)'
                    : 'var(--text-muted)',
              }}
              className={runStatus === 'RUNNING' || runStatus === 'AWAITING_APPROVAL' ? 'pulse' : ''}
            />
            {runStatus || 'IDLE'}
          </div>
        </div>

        {/* Right: Mode Toggle & Action Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {/* Mode Switcher */}
          <div
            style={{
              display: 'flex',
              background: 'var(--bg-panel)',
              border: '1px solid var(--border-default)',
              borderRadius: '6px',
              padding: '2px',
            }}
          >
            <button
              onClick={() => onToggleMode('LIVE')}
              style={{
                padding: '4px 10px',
                fontSize: '11px',
                fontWeight: 600,
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
                background: mode === 'LIVE' ? '#1f6feb' : 'transparent',
                color: mode === 'LIVE' ? '#fff' : 'var(--text-secondary)',
                transition: 'all 0.15s ease',
              }}
            >
              LIVE SSE
            </button>
            <button
              onClick={() => onToggleMode('REPLAY')}
              style={{
                padding: '4px 10px',
                fontSize: '11px',
                fontWeight: 600,
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
                background: mode === 'REPLAY' ? '#1f6feb' : 'transparent',
                color: mode === 'REPLAY' ? '#fff' : 'var(--text-secondary)',
                transition: 'all 0.15s ease',
              }}
            >
              REPLAY
            </button>
          </div>

          {mode === 'LIVE' ? (
            <button className="btn btn-primary" onClick={onStartLiveRun} disabled={runStatus === 'RUNNING'}>
              <Sparkles size={14} />
              Start Run
            </button>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <button
                className="btn"
                onClick={onTogglePlay}
                title={isPlaying ? 'Pause Replay' : 'Play Replay'}
                style={{ padding: '6px 10px' }}
              >
                {isPlaying ? <Pause size={14} /> : <Play size={14} />}
              </button>
              <button
                className="btn"
                onClick={onStepNext}
                title="Step forward 1 event"
                disabled={isPlaying || replayIndex >= totalReplayEvents - 1}
                style={{ padding: '6px 10px' }}
              >
                <SkipForward size={14} />
              </button>
              <button
                className="btn"
                onClick={onReset}
                title="Restart replay from step 0"
                style={{ padding: '6px 10px' }}
              >
                <RotateCcw size={14} />
              </button>

              {/* Speed Buttons */}
              <div style={{ display: 'flex', gap: '2px', marginLeft: '4px' }}>
                {[1, 2, 5].map((s) => (
                  <button
                    key={s}
                    onClick={() => onChangeSpeed(s)}
                    style={{
                      padding: '3px 6px',
                      fontSize: '10px',
                      fontFamily: 'var(--font-mono)',
                      background: speed === s ? 'var(--bg-subtle)' : 'transparent',
                      color: speed === s ? 'var(--accent-blue)' : 'var(--text-muted)',
                      border: '1px solid',
                      borderColor: speed === s ? 'var(--border-accent)' : 'transparent',
                      borderRadius: '4px',
                      cursor: 'pointer',
                    }}
                  >
                    {s}x
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Scrub Bar (in Replay Mode) */}
      {mode === 'REPLAY' && totalReplayEvents > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '11px', color: 'var(--text-muted)' }}>
          <span style={{ fontFamily: 'var(--font-mono)', minWidth: '85px' }}>
            Event {replayIndex + 1}/{totalReplayEvents}
          </span>
          <input
            type="range"
            min={0}
            max={totalReplayEvents - 1}
            value={replayIndex}
            onChange={(e) => onScrub(Number(e.target.value))}
            style={{
              flex: 1,
              height: '4px',
              accentColor: 'var(--accent-blue)',
              cursor: 'pointer',
            }}
          />
        </div>
      )}

      {/* Pipeline 9-Step Timeline */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(9, 1fr)',
          gap: '6px',
          paddingTop: '4px',
        }}
      >
        {STEP_ORDER.map((step, idx) => {
          const isActive = currentStep === step;
          const isDone = idx < stepProgress || (idx === stepProgress && runStatus === 'COMPLETED');
          return (
            <div
              key={step}
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '4px',
                padding: '6px 8px',
                borderRadius: '6px',
                background: isActive
                  ? 'rgba(88, 166, 255, 0.08)'
                  : isDone
                  ? 'rgba(63, 185, 80, 0.05)'
                  : 'var(--bg-panel)',
                border: '1px solid',
                borderColor: isActive
                  ? 'var(--accent-blue)'
                  : isDone
                  ? 'rgba(63, 185, 80, 0.3)'
                  : 'var(--border-default)',
                transition: 'all 0.2s ease',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span
                  style={{
                    fontSize: '10px',
                    fontFamily: 'var(--font-mono)',
                    color: isActive ? 'var(--accent-blue)' : isDone ? 'var(--verdict-benign)' : 'var(--text-muted)',
                    fontWeight: 700,
                  }}
                >
                  0{idx + 1}
                </span>
                {isActive && (
                  <span
                    style={{
                      width: '6px',
                      height: '6px',
                      borderRadius: '50%',
                      background: 'var(--accent-blue)',
                    }}
                    className="pulse"
                  />
                )}
              </div>
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 600,
                  textTransform: 'capitalize',
                  color: isActive ? 'var(--text-primary)' : isDone ? 'var(--text-secondary)' : 'var(--text-muted)',
                }}
              >
                {step}
              </span>
            </div>
          );
        })}
      </div>
    </header>
  );
};
