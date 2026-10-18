---
name: React Vite Pages
description: Build the pages, routing and components of a React + Vite + TypeScript site.
capabilities: [implement_frontend]
technologies: [React, Vite, TypeScript]
requires: [project-scaffold]
checklist:
  - id: routes
    text: Every page in the request has a route, a nav link, and a 404 route catches unknown paths.
  - id: responsive
    text: Every page is usable at 375px, 768px and 1280px widths with no horizontal scrolling.
  - id: a11y
    text: Pages use semantic landmarks, one h1 each, labelled controls, alt text, and full keyboard navigation.
---
You implement the user-facing pages on top of the scaffolded Vite + React + TypeScript project.
Read the README and `package.json` first and keep the existing conventions.

## Routing and structure
- Install `react-router-dom` (v6+) and define routes with `createBrowserRouter` in `src/main.tsx`
  or a dedicated `src/router.tsx`.
- One file per page in `src/pages/` (`Home.tsx`, `About.tsx`, `Projects.tsx`, `Contact.tsx`, ...).
  Shared pieces go in `src/components/` (`Layout.tsx`, `Header.tsx`, `Footer.tsx`).
- Wrap pages in a `Layout` with `<header>`, `<nav>`, `<main>` and `<footer>`; render children
  through `<Outlet />`. Use `NavLink` so the current page is marked with `aria-current="page"`.
- Add a `*` route rendering a `NotFound` page with a link back home.
- Update `document.title` per page (a small `useEffect` or a `usePageTitle` hook).

## Content and data
- Write real copy from the request; never leave lorem ipsum. Keep site data such as projects,
  links or menu items in typed arrays under `src/data/` so content changes do not touch JSX.
- Type props with explicit interfaces. No `any`; prefer discriminated unions for variants.
- If the plan includes a backend, read its base URL from `import.meta.env.VITE_API_URL`,
  put fetch calls in `src/api/client.ts`, and render loading, empty and error states for each.
- Forms: controlled inputs, a `<label>` for every field, inline validation messages tied with
  `aria-describedby`, and a disabled submit button while a request is in flight.

## Responsive layout and accessibility
- Mobile first: base styles target small screens, then add `min-width` breakpoints.
- Use flexbox or grid for layout; images get `max-width: 100%`, explicit width/height and
  `loading="lazy"` below the fold.
- Exactly one `<h1>` per page, headings in order, meaningful `alt` text (empty `alt=""` for
  decorative images), visible focus outlines, and a "Skip to content" link.
- The mobile nav toggle is a `<button>` with `aria-expanded` and `aria-controls`.
- If a styling task is in the plan, use plain semantic class names and leave visual design to it.

## Verify
- `npm run build` passes with no TypeScript errors.
- Click through every route in `npm run dev`, including an unknown URL, at 375px and 1280px.
- Tab through each page with the keyboard only and confirm focus order and visibility.
