---
name: UI Styling
description: Give a React site a consistent visual design with TailwindCSS design tokens, accessible colour and responsive layouts.
capabilities: [style_ui]
technologies: [TailwindCSS, React]
requires: [project-scaffold]
checklist:
  - id: tokens
    text: Colours, fonts, spacing and radii come from named theme tokens; no stray hex values in components.
  - id: contrast
    text: Body text meets WCAG AA contrast (4.5:1, 3:1 for large text) in every theme, including focus rings.
  - id: mobile
    text: Layouts, type sizes and tap targets (at least 44px) work at 375px with no overflow.
---
You own the look and feel. The pages task may be running in parallel, so style through
shared tokens and components rather than rewriting page structure.

## Set up Tailwind
- Install `tailwindcss` with the Vite plugin (`@tailwindcss/vite` for v4, or
  `tailwindcss postcss autoprefixer` with `npx tailwindcss init -p` for v3).
- Point `content` (v3) at `./index.html` and `./src/**/*.{ts,tsx}` so classes are not purged.
- Put `@import "tailwindcss";` (v4) or the three `@tailwind` directives (v3) at the top of
  `src/index.css`, and delete leftover Vite demo CSS.

## Design tokens
- Define the palette as CSS variables in `:root` (for example `--color-bg`, `--color-fg`,
  `--color-muted`, `--color-accent`, `--color-border`) and map them in the Tailwind theme so
  components use `bg-bg`, `text-fg`, `text-accent` instead of raw hex values.
- Choose at most one accent colour plus neutrals. Pick one font pairing (a heading and a body
  font, or one variable font) and load it with `font-display: swap`.
- Use a consistent spacing and type scale: Tailwind defaults are fine; do not invent
  one-off pixel values. Set `max-w-prose` or about 65ch for long text.
- If dark mode is wanted, redefine the same variables under `.dark` or
  `@media (prefers-color-scheme: dark)`; never duplicate component classes per theme.

## Components and states
- Create small styled primitives in `src/components/ui/` (`Button.tsx`, `Card.tsx`,
  `Container.tsx`) and use them across pages.
- Every interactive element gets hover, `focus-visible` (a 2px ring with offset), active and
  disabled styles. Respect `prefers-reduced-motion` with `motion-safe:` on transitions.
- Keep transitions under 200ms and avoid layout shift on hover.

## Responsive and contrast checks
- Design at 375px first, then `md:` (768px) and `lg:` (1024px) refinements.
- Tap targets are at least 44x44px; body text at least 16px on mobile.
- Check foreground/background pairs with a contrast checker and record the ratios for the
  main text, muted text and the accent on buttons in your submission.
- Run `npm run build` and confirm the CSS bundle contains the classes you used.
