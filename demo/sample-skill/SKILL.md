---
name: Accessible Landing Page
description: Build a landing page that meets WCAG AA basics - semantic structure, keyboard access, contrast and alt text.
capabilities: [implement_frontend]
technologies: [React, TypeScript]
checklist:
  - id: landmarks
    text: Page uses header, main and footer landmarks and one h1.
  - id: keyboard
    text: Every interactive element is reachable and visible when focused.
  - id: contrast
    text: Text and controls meet a 4.5:1 contrast ratio.
---
Build the page with semantic HTML first, then add styling.

## Structure
- One `h1`, headings in order, no skipped levels.
- Wrap the page in `header`, `main` and `footer`.

## Interaction
- Use real `button` and `a` elements, never clickable `div`s.
- Show a visible focus ring on every control.

## Media
- Every image has meaningful `alt` text, or `alt=""` when decorative.
