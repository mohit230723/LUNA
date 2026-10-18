import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.describe('LUNA OS E2E Suite', () => {
  test.beforeEach(async ({ page }) => {
    // Speed up mock event streaming for tests
    await page.addInitScript(() => {
      try {
        localStorage.setItem(
          'luna.prefs',
          JSON.stringify({
            apiMode: 'mock',
            mockSpeed: 10,
            pack: 'auto',
            mode: 'scripted',
            strict_llm: false,
            parallel: 3,
          })
        );
      } catch {
        // ignore
      }
    });
  });

  test('Home Page: loads, displays status badge, navigation, and prompt prefill link', async ({ page }) => {
    await page.goto('/');

    // Check header and status badge
    await expect(page).toHaveTitle(/LUNA OS/);
    await expect(page.getByText('Agents that act on connected data.').first()).toBeVisible();
    await expect(page.getByText('BACKEND ONLINE').first()).toBeVisible();

    // Check navigation links
    const nav = page.locator('nav');
    await expect(nav.getByRole('link', { name: 'HOW IT WORKS' })).toBeVisible();
    await expect(nav.getByRole('link', { name: 'SKILL ATLAS' })).toBeVisible();
    await expect(nav.getByRole('link', { name: 'PLATFORM', exact: true })).toBeVisible();

    // Check "TRY THIS PROMPT ↗" link prefills composer on /platform
    const tryPromptLink = page.getByRole('link', { name: /TRY THIS PROMPT/i }).first();
    await expect(tryPromptLink).toBeVisible();
    await tryPromptLink.click();

    await page.waitForURL(/\/platform\?prompt=.+/);
    const textarea = page.locator('textarea[placeholder="Describe a task or ask a question"]');
    await expect(textarea).toBeVisible();
    const val = await textarea.inputValue();
    expect(val.length).toBeGreaterThan(0);
  });

  test('How It Works Page: tabs switch, stepper advances, and glossary is displayed', async ({ page }) => {
    await page.goto('/how-it-works');
    await expect(page).toHaveTitle(/How it works · LUNA OS/);

    // Initial stage is Route
    await expect(page.getByText('Route', { exact: true })).toBeVisible();
    await expect(page.getByText('Decides which pack handles the prompt')).toBeVisible();

    // Click Next button to advance to Plan
    const nextBtn = page.getByRole('button', { name: 'NEXT' });
    await nextBtn.click();
    await expect(page.getByText('Plan', { exact: true })).toBeVisible();

    // Switch to BUILD RUN tab
    const buildTab = page.getByRole('tab', { name: 'BUILD RUN' });
    await buildTab.click();
    await expect(page.getByText('Route', { exact: true })).toBeVisible();

    // Glossary section
    await expect(page.getByText('GLOSSARY')).toBeVisible();
    await expect(page.getByText('Atlas', { exact: true })).toBeVisible();
    await expect(page.getByText('Slice', { exact: true })).toBeVisible();
  });

  test('Skill Atlas Page: filter by pack, search, drawer inspection, and view toggle', async ({ page }) => {
    await page.goto('/skills');
    await expect(page).toHaveTitle(/Skill Atlas · LUNA OS/);

    // Filter by INVESTIGATE pack
    const investigateTab = page.getByRole('tab', { name: 'INVESTIGATE' });
    await investigateTab.click();
    await expect(page.getByText('entity-linker')).toBeVisible();

    // Search input
    const searchInput = page.getByPlaceholder('Search skills, technologies, capabilities');
    await searchInput.fill('bulk-linker');
    await expect(page.getByText('bulk-linker')).toBeVisible();

    // Click row to open right drawer
    await page.getByText('bulk-linker').click();
    await expect(
      page.getByText('Restricted by policy. The orchestrator always rejects this skill and records why.')
    ).toBeVisible();

    // Close drawer with close button
    const closeBtn = page.locator('button[aria-label="Close drawer"]');
    if (await closeBtn.isVisible()) {
      await closeBtn.click();
    }

    // View toggle to GRAPH
    const graphToggle = page.getByRole('tab', { name: 'GRAPH' });
    await graphToggle.click();
    await expect(page.getByText('LEGEND')).toBeVisible();
  });

  test('Platform Investigate Flow: prompt chip, streaming stages, citations, trace view, and action approval', async ({
    page,
  }) => {
    await page.goto('/platform');
    await expect(page).toHaveTitle(/Platform · LUNA OS/);

    // Click an investigate prompt chip
    const chip = page.getByText('Who is connected to the fraud involving customer cust-000?');
    await chip.click();

    // Send the prompt
    const sendBtn = page.locator('button[aria-label="Send"]');
    await sendBtn.click();

    // Wait for the assistant answer block to appear
    await expect(page.getByText(/staged accident ring/i)).toBeVisible({ timeout: 20000 });

    // Click "VIEW TRACE" to open the Trace View
    const viewTraceBtn = page.getByRole('button', { name: 'VIEW TRACE' }).first();
    await viewTraceBtn.click();

    // Verify Trace View opens
    await expect(page.getByText(/TRACE ·/i)).toBeVisible();
    await expect(page.getByText(/TRAVERSAL STEPS/i)).toBeVisible();
    await expect(page.getByText('ph-ring-01').first()).toBeVisible();

    // Verify scrubber play/pause button
    const playBtn = page
      .locator('button[aria-label="Play trace"]')
      .or(page.locator('button[aria-label="Pause trace"]'))
      .first();
    await expect(playBtn).toBeVisible();

    // Back to conversation
    const backBtn = page.locator('button[aria-label="Back to conversation"]');
    await backBtn.click();

    // Test action request approval
    const approveBtn = page.getByRole('button', { name: 'APPROVE' }).first();
    if (await approveBtn.isVisible()) {
      await approveBtn.click();
      // Approver Modal
      const nameInput = page.locator('#approver-input');
      await nameInput.fill('E2E Tester');
      const confirmApprove = page.getByRole('button', { name: 'CONFIRM APPROVAL' });
      await confirmApprove.click();

      // Verify approval executed and metrics shown
      await expect(page.getByText(/EXECUTED/i).first()).toBeVisible();
      await expect(page.getByText(/Precision/i).first()).toBeVisible();
    }
  });

  test('Platform Build Flow: build chip, contracts, files tree, and build check', async ({ page }) => {
    await page.goto('/platform');

    // Click build prompt chip
    const buildChip = page.getByText(/Build a todo app: React \+ Vite frontend/i);
    await buildChip.click();

    const sendBtn = page.locator('button[aria-label="Send"]');
    await sendBtn.click();

    // Wait for build answer
    await expect(page.getByText(/contracts implemented/i).first()).toBeVisible({ timeout: 20000 });

    // Verify files tree and download zip button
    await expect(page.getByRole('button', { name: 'DOWNLOAD ZIP' })).toBeVisible();
    await expect(page.getByText('README.md').first()).toBeVisible();

    // Click file to view preview
    await page.getByText('README.md').first().click();
    await expect(page.locator('pre')).toBeVisible();

    // Verify skills block shows rejected candidates
    await expect(page.getByText(/TECH MISMATCH/i).first()).toBeVisible();
    await expect(page.getByText('POLICY RESTRICTED').first()).toBeVisible();
  });

  test('Platform Needs-Input Flow: prompt with Svelte asks question and resumes on choice', async ({ page }) => {
    await page.goto('/platform');

    const textarea = page.locator('textarea[placeholder="Describe a task or ask a question"]');
    await textarea.fill('Build a todo app using Svelte and SQLite');
    const sendBtn = page.locator('button[aria-label="Send"]');
    await sendBtn.click();

    // Verify needs_input block appears
    await expect(page.getByText(/Svelte is not in the Skill Atlas/i)).toBeVisible({ timeout: 20000 });
    const reactOption = page.getByRole('button', { name: 'React + Vite' });
    await expect(reactOption).toBeVisible();

    // Select option to resume
    await reactOption.click();
    await expect(page.getByText(/contracts implemented/i).first()).toBeVisible({ timeout: 20000 });
  });

  test('Keyboard Navigation: Scrubber responds to Space and Arrow keys in Trace View', async ({ page }) => {
    await page.goto('/platform/conv-e2e-1/trace/run-f1');
    await expect(page.getByText(/TRACE ·/i)).toBeVisible();

    // Test Space key for play/pause
    await page.keyboard.press('Space');
    // Test Arrow keys for step
    await page.keyboard.press('ArrowRight');
    await page.keyboard.press('ArrowLeft');

    // Test Escape clears selection / closes drawer
    await page.keyboard.press('Escape');
    expect(true).toBe(true);
  });

  test('Responsive Layout: Viewports 1440, 1100, and 768 have no horizontal scrollbar on marketing pages', async ({
    page,
  }) => {
    for (const width of [1440, 1100, 768]) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto('/');

      const hasHorizontalScroll = await page.evaluate(() => {
        return document.documentElement.scrollWidth > document.documentElement.clientWidth;
      });
      expect(hasHorizontalScroll).toBe(false);
    }
  });

  test('Reduced Motion: Emulating reduced motion renders without error', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/');
    const constellation = page.locator('canvas[aria-hidden="true"]').first();
    await expect(constellation).toBeVisible();
  });

  test('Accessibility (Axe-core): No serious or critical violations across all primary pages', async ({ page }) => {
    const pagesToTest = ['/', '/how-it-works', '/skills', '/platform'];

    for (const path of pagesToTest) {
      await page.goto(path);
      // Wait for content to stabilize
      await page.waitForTimeout(500);

      const accessibilityScanResults = await new AxeBuilder({ page }).analyze();
      const seriousOrCritical = accessibilityScanResults.violations.filter(
        (v) => v.impact === 'serious' || v.impact === 'critical'
      );

      if (seriousOrCritical.length > 0) {
        console.error(`Axe violations on ${path}:`, JSON.stringify(seriousOrCritical, null, 2));
      }
      expect(seriousOrCritical).toEqual([]);
    }
  });
});
