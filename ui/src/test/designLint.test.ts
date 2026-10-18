import { describe, it, expect } from 'vitest';
import { lintContent } from '../../scripts/design-lint.mjs';

describe('design-lint', () => {
  it('passes on valid Hyperstudio CSS', () => {
    const validCss = `
      .card {
        background-color: var(--color-obsidian);
        border: 1px solid #212121;
        border-radius: 8px;
        color: #f3f3f3;
        font-weight: 400;
      }
      .pill-button {
        border-radius: 9999px;
        background-color: #ffffff;
      }
      .status-dot {
        width: 6px;
        height: 6px;
        background-color: #98ff38;
      }
    `;
    const errors = lintContent('src/components/card.css', validCss);
    expect(errors).toHaveLength(0);
  });

  it('fails when box-shadow or text-shadow is used', () => {
    const invalidCss = `
      .card {
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
      }
    `;
    const errors = lintContent('src/components/card.css', invalidCss);
    expect(errors.some((e: any) => e.rule === 'no-shadow-or-blur')).toBe(true);
  });

  it('fails when font-weight is bold or greater than 400', () => {
    const invalidCss = `
      h1 {
        font-weight: bold;
      }
      .heading {
        font-weight: 600;
      }
    `;
    const errors = lintContent('src/components/heading.css', invalidCss);
    expect(errors.filter((e: any) => e.rule === 'weight-400-only')).toHaveLength(2);
  });

  it('fails when border-radius exceeds 8px without being 99px or 9999px', () => {
    const invalidCss = `
      .box {
        border-radius: 16px;
      }
    `;
    const errors = lintContent('src/components/box.css', invalidCss);
    expect(errors.some((e: any) => e.rule === 'radius-limit')).toBe(true);
  });

  it('fails on disallowed hex colors', () => {
    const invalidCss = `
      .alert {
        color: #ff0000;
        background-color: #00ff00;
      }
    `;
    const errors = lintContent('src/components/alert.css', invalidCss);
    expect(errors.filter((e: any) => e.rule === 'allowed-colors-only')).toHaveLength(2);
  });

  it('fails when Compass Gold is used for text color', () => {
    const invalidCss = `
      .gold-text {
        color: var(--color-compass-gold);
      }
    `;
    const errors = lintContent('src/components/text.css', invalidCss);
    expect(errors.some((e: any) => e.rule === 'compass-gold-icon-only')).toBe(true);
  });

  it('fails when img tags appear in marketing pages', () => {
    const invalidTsx = `
      export function Home() {
        return <div><img src="/photo.jpg" alt="hero" /></div>;
      }
    `;
    const errors = lintContent('src/pages/Home.tsx', invalidTsx);
    expect(errors.some((e: any) => e.rule === 'no-marketing-images')).toBe(true);
  });
});
