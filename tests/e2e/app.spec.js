import { expect, test } from '@playwright/test'

test('clean chat shell and settings remain usable', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('How can I help')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Settings' })).toBeVisible()
  await page.getByRole('button', { name: 'Settings' }).click()
  await expect(page.getByRole('dialog', { name: 'Settings' })).toBeVisible()
  await expect(page.getByRole('button', { name: /Model & runtime/ })).toBeVisible()
  await page.getByRole('button', { name: /MCP servers/ }).click()
  await expect(page.getByRole('button', { name: 'New MCP server' })).toBeVisible()
  await expect(page.getByText('Local, permission-controlled connections')).toBeVisible()
})

test('chat drawer and composer fit the viewport', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Chats' }).click()
  const dialog = page.getByRole('dialog', { name: 'Conversations' })
  await expect(dialog).toBeVisible()
  const viewport = page.viewportSize()
  await expect.poll(async () => {
    const box = await dialog.boundingBox()
    return Boolean(box && box.x >= 0 && box.x + box.width <= viewport.width + 1)
  }).toBe(true)
  const drawer = await dialog.boundingBox()
  expect(drawer.x).toBeGreaterThanOrEqual(0)
  expect(drawer.x + drawer.width).toBeLessThanOrEqual(viewport.width)
  await dialog.getByRole('button', { name: 'Close' }).click()
  await expect(page.getByLabel('Message Local AI')).toBeVisible()
})

test('files can be attached, indexed, shown, and removed', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Add files or folders' }).click()
  await expect(page.getByText('Folder', { exact: true })).toBeVisible()
  await page.keyboard.press('Escape')
  const picker = page.locator('input[type="file"]:not([webkitdirectory])')
  await picker.setInputFiles({
    name: 'project-notes.md',
    mimeType: 'text/markdown',
    buffer: Buffer.from('The launch checklist owner is Riverstone.'),
  })
  await expect(page.getByText('1 file indexed')).toBeVisible()
  await expect(page.getByText('project-notes.md', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Remove project-notes.md' }).click()
  await expect(page.getByText('project-notes.md', { exact: true })).toHaveCount(0)
})

test('light and dark themes are available and persist', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Theme' }).click()
  await page.getByText('Dark', { exact: true }).click()
  await expect.poll(() => page.evaluate(() => localStorage.getItem('local-ai-color-mode'))).toBe('night')
  await page.reload()
  await expect.poll(() => page.evaluate(() => localStorage.getItem('local-ai-color-mode'))).toBe('night')
  await page.getByRole('button', { name: 'Theme' }).click()
  await page.getByText('Light', { exact: true }).click()
  await expect.poll(() => page.evaluate(() => localStorage.getItem('local-ai-color-mode'))).toBe('day')
})

test('advanced local settings are accessible and responsive', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Settings' }).click()
  const dialog = page.getByRole('dialog', { name: 'Settings' })
  await dialog.getByRole('button', { name: /Workspaces/ }).click()
  await expect(dialog.getByRole('heading', { name: 'Approved workspaces' })).toBeVisible()
  await dialog.getByRole('button', { name: /Activity/ }).click()
  await expect(dialog.getByRole('heading', { name: 'MCP activity' })).toBeVisible()
  await dialog.getByRole('button', { name: /Performance/ }).click()
  await expect(dialog.getByRole('heading', { name: 'Host & performance' })).toBeVisible()
  await expect(dialog.getByRole('button', { name: 'Apply best settings for this computer' })).toBeVisible()
  await expect(dialog.getByText('Average speed')).toBeVisible()
  await dialog.getByRole('button', { name: /Backup/ }).click()
  await expect(dialog.getByRole('button', { name: 'Download encrypted backup' })).toBeVisible()
  const box = await dialog.boundingBox()
  const viewport = page.viewportSize()
  expect(box.width).toBeLessThanOrEqual(viewport.width)
  expect(box.height).toBeLessThanOrEqual(viewport.height)
})
