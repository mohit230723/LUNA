import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ALLOWED_HEXES = new Set([
  '#101010', // Obsidian
  '#080808', // Carbon
  '#f3f3f3', // Chalk
  '#9c9c9c', // Smoke
  '#c1c1c1', // Ash
  '#212121', // Graphite
  '#474747', // Iron
  '#ffffff', // Signal White
  '#6f6759', // Compass Gold
  '#3b3d45', // Card Slate
  '#1a1a1a', // Badge bg
  '#98ff38', // Pulse Green
]);

export function lintContent(filePath, content) {
  const errors = [];
  const lines = content.split('\n');

  // Check 1: Shadows & Blur
  if (/(box-shadow|text-shadow|filter:\s*blur)/i.test(content)) {
    lines.forEach((line, idx) => {
      if (/(box-shadow|text-shadow|filter:\s*blur)/i.test(line)) {
        errors.push({ file: filePath, line: idx + 1, rule: 'no-shadow-or-blur', message: `Prohibited shadow or blur: "${line.trim()}"` });
      }
    });
  }

  // Check 2: Font weights above 400
  lines.forEach((line, idx) => {
    const fwMatch = line.match(/font-weight:\s*([5-9]00|bold|bolder)/i);
    if (fwMatch) {
      errors.push({ file: filePath, line: idx + 1, rule: 'weight-400-only', message: `Font-weight must not exceed 400: "${line.trim()}"` });
    }
  });

  // Check 3: Border radius above 8px unless pill (9999px) or icon (99px)
  lines.forEach((line, idx) => {
    const brMatch = line.match(/border-radius:\s*([^;]+)/i);
    if (brMatch) {
      const val = brMatch[1].trim();
      const numMatch = val.match(/^(\d+)px$/);
      if (numMatch) {
        const px = parseInt(numMatch[1], 10);
        if (px > 8 && px !== 99 && px !== 9999) {
          errors.push({ file: filePath, line: idx + 1, rule: 'radius-limit', message: `Border radius ${px}px exceeds 8px without being 99px or 9999px: "${line.trim()}"` });
        }
      }
    }
  });

  // Check 4: Unallowed hex colors
  lines.forEach((line, idx) => {
    const hexMatches = line.matchAll(/#([0-9a-fA-F]{3,8})\b/g);
    for (const match of hexMatches) {
      const hex = match[0].toLowerCase();
      // Expand 3-digit hex if needed
      let fullHex = hex;
      if (hex.length === 4) {
        fullHex = `#${hex[1]}${hex[1]}${hex[2]}${hex[2]}${hex[3]}${hex[3]}`;
      }
      if (!ALLOWED_HEXES.has(fullHex)) {
        errors.push({ file: filePath, line: idx + 1, rule: 'allowed-colors-only', message: `Disallowed hex color "${hex}" in line: "${line.trim()}"` });
      }
    }
  });

  // Check 5: Compass Gold used as text color
  lines.forEach((line, idx) => {
    if (/(^|\s)color:\s*(var\(--color-compass-gold\)|#6f6759)/i.test(line)) {
      errors.push({ file: filePath, line: idx + 1, rule: 'compass-gold-icon-only', message: `Compass gold must only be used for icon strokes/borders, never text color: "${line.trim()}"` });
    }
  });

  // Check 6: Pulse green used outside status-dot / live / marker contexts
  let currentSelector = '';
  lines.forEach((line, idx) => {
    if (line.includes('{')) {
      currentSelector = line.split('{')[0].trim();
    }
    if (line.includes('}')) {
      currentSelector = '';
    }
    if (/(--color-pulse-green|#98ff38)/i.test(line)) {
      const isAllowedContext =
        /(status|dot|pulse|live|marker|indicator)/i.test(line) ||
        /(status|dot|pulse|live|marker|indicator)/i.test(currentSelector) ||
        /(status|dot|pulse|live|marker|indicator)/i.test(filePath);
      if (!isAllowedContext) {
        errors.push({ file: filePath, line: idx + 1, rule: 'pulse-green-live-only', message: `Pulse green is only allowed for live/active status dots and markers: "${line.trim()}"` });
      }
    }
  });

  // Check 7: No <img> in marketing pages
  if (filePath.includes('pages/Home.tsx') || filePath.includes('pages/HowItWorks.tsx')) {
    if (/<img\s/i.test(content)) {
      errors.push({ file: filePath, line: 1, rule: 'no-marketing-images', message: 'No <img> elements allowed on marketing pages (vector/dot-matrix only)' });
    }
  }

  return errors;
}

export function runLint(rootDir) {
  const srcDir = path.join(rootDir, 'src');
  if (!fs.existsSync(srcDir)) return [];

  const allErrors = [];

  function walk(dir) {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (entry.name !== 'test' && entry.name !== 'node_modules') {
          walk(fullPath);
        }
      } else if (/\.(css|tsx|ts)$/.test(entry.name)) {
        const content = fs.readFileSync(fullPath, 'utf8');
        const errors = lintContent(fullPath, content);
        allErrors.push(...errors);
      }
    }
  }

  walk(srcDir);
  return allErrors;
}

// Direct execution from CLI
const __filename = fileURLToPath(import.meta.url);
if (process.argv[1] === __filename) {
  const rootDir = path.resolve(path.dirname(__filename), '..');
  const errors = runLint(rootDir);
  if (errors.length > 0) {
    console.error(`\n❌ Design Lint Failed with ${errors.length} error(s):\n`);
    errors.forEach((err) => {
      console.error(`  ${err.file}:${err.line} [${err.rule}] ${err.message}`);
    });
    process.exit(1);
  } else {
    console.log('✅ Design Lint Passed: 0 violations of Hyperstudio visual rules.');
  }
}
