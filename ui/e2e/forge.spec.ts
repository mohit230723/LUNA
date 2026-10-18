import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.describe('Platform forge tabs', () => {
  test.beforeEach(async ({ page }) => {
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

  test('Agents tab is the default and shows the DAG and task cards', async ({ page }) => {
    await page.goto('/platform?mock=1');
    await expect(page.getByRole('tab', { name: 'Agents' })).toHaveAttribute('aria-selected', 'true');
    await expect(page.locator('.forge-dag').first()).toBeVisible();
    const card = page.getByRole('article').filter({ hasText: 'react-vite-pages' }).first();
    await expect(card).toBeVisible();
  });

  test('Skills tab lists 7 skills and approves the pending one', async ({ page }) => {
    await page.goto('/platform?mock=1');
    await page.getByRole('tab', { name: 'Skills' }).click();
    const table = page.getByRole('table', { name: 'Skills' });
    await expect(table.locator('tbody tr')).toHaveCount(7);
    const queue = page.getByRole('region', { name: 'Review queue' });
    await expect(queue.getByText('SEO Audit')).toBeVisible();
    await queue.getByRole('button', { name: 'Approve SEO Audit' }).click();
    await expect(queue.getByText('No skills awaiting review.')).toBeVisible();
    await expect(table.locator('tbody tr', { hasText: 'SEO Audit' })).toContainText('approved');
  });

  test('Agents and Skills tabs have no axe violations', async ({ page }) => {
    await page.goto('/platform?mock=1');
    await expect(page.getByRole('article').first()).toBeVisible();
    const agents = await new AxeBuilder({ page }).analyze();
    expect(agents.violations).toEqual([]);

    await page.getByRole('tab', { name: 'Skills' }).click();
    await expect(page.getByRole('table', { name: 'Skills' })).toBeVisible();
    const skills = await new AxeBuilder({ page }).analyze();
    expect(skills.violations).toEqual([]);
  });

  test('no horizontal scroll at 375px on either tab', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/platform?mock=1');
    await expect(page.getByRole('article').first()).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375);

    await page.getByRole('tab', { name: 'Skills' }).click();
    await expect(page.getByRole('table', { name: 'Skills' })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375);
  });
});
