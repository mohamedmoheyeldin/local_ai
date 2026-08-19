import { expect, test } from '@playwright/test'

test('clean chat shell and settings remain usable', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('How can I help')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Settings' })).toBeVisible()
  await page.getByRole('button', { name: 'Settings' }).click()
  await expect(page.getByRole('dialog', { name: 'Settings' })).toBeVisible()
  const dialog = page.getByRole('dialog', { name: 'Settings' })
  await expect(dialog.getByRole('tab', { name: /Model & runtime/ })).toBeVisible()
  const viewport = page.viewportSize()
  await expect.poll(async () => {
    const box = await dialog.boundingBox()
    return Boolean(box && box.width >= viewport.width - 2 && box.height >= viewport.height - 2)
  }).toBe(true)
  await dialog.getByRole('tab', { name: /MCP servers/ }).click()
  await expect(page.getByRole('button', { name: 'New MCP server' })).toBeVisible()
  await expect(page.getByText('Local, permission-controlled connections')).toBeVisible()
  const gmail = dialog.getByRole('button', { name: /Add Gmail account/ })
  await expect(gmail).toBeVisible()
  await gmail.click()
  await expect(dialog.getByRole('textbox', { name: 'Account name' })).toBeVisible()
  await expect(dialog.getByRole('button', { name: 'Save account' })).toBeDisabled()
})

test('chat sidebar and mobile drawer fit the viewport', async ({ page }) => {
  await page.goto('/')
  const viewport = page.viewportSize()
  if (viewport.width >= 768) {
    const sidebar = page.getByRole('complementary', { name: 'Chat history' })
    await expect(sidebar).toBeVisible()
    await expect(sidebar.getByRole('button', { name: 'New chat' })).toBeVisible()
    await sidebar.getByRole('button', { name: 'Hide chat sidebar' }).click()
    await expect(sidebar).toBeHidden()
    await page.getByRole('button', { name: 'Show chat sidebar' }).click()
    await expect(sidebar).toBeVisible()
  } else {
    await page.getByRole('button', { name: 'Open chats' }).click()
    const dialog = page.getByRole('dialog', { name: 'Chats' })
    await expect(dialog).toBeVisible()
    await expect.poll(async () => {
      const box = await dialog.boundingBox()
      return Boolean(box && box.x >= 0 && box.x + box.width <= viewport.width + 1)
    }).toBe(true)
    const drawer = await dialog.boundingBox()
    expect(drawer.x).toBeGreaterThanOrEqual(0)
    expect(drawer.x + drawer.width).toBeLessThanOrEqual(viewport.width)
    await dialog.getByRole('button', { name: 'Close' }).click()
  }
  const composerInput = page.getByLabel('Message Local AI')
  await expect(composerInput).toBeVisible()
  await expect.poll(() => composerInput.evaluate(element => {
    const inputStyle = getComputedStyle(element)
    const composerStyle = getComputedStyle(element.closest('.composer'))
    return [inputStyle.borderWidth, inputStyle.boxShadow, composerStyle.borderWidth]
  })).toEqual(['0px', 'none', '0px'])
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

test('chat shows automatic web research before local generation', async ({ page }) => {
  await page.route('**/api/runtime', route => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ state: 'ready', healthy: true, managed: false, endpoint: 'http://127.0.0.1:8180', model: { display_name: 'Test model' } }),
  }))
  let releaseResearch
  const researchGate = new Promise(resolve => { releaseResearch = resolve })
  await page.route('**/api/chat/stream', async route => {
    await researchGate
    await route.fulfill({
      contentType: 'application/x-ndjson',
      body: `${JSON.stringify({ type: 'token', content: 'Current answer with a source.' })}\n${JSON.stringify({ type: 'done', usage: {} })}\n`,
    })
  })
  await page.goto('/')
  await page.getByLabel('Message Local AI').fill('What changed today?')
  await page.getByRole('button', { name: 'Send message' }).click()
  await expect(page.getByText('Searching the web for current information…')).toBeVisible()
  releaseResearch()
  await expect(page.getByText('Current answer with a source.')).toBeVisible()
  await expect(page.getByText('Chats stay local. Web research shares only the current question with public search providers.')).toHaveCount(1)
})

test('local file and command tools show exact approval before execution', async ({ page }) => {
  await page.route('**/api/runtime', route => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ state: 'ready', healthy: true, endpoint: 'http://127.0.0.1:8180', model: { display_name: 'Test model' } }),
  }))
  let chatCalls = 0
  await page.route('**/api/chat/stream', route => {
    chatCalls += 1
    const body = chatCalls === 1
      ? `${JSON.stringify({ type: 'approval', local: true, server_name: 'Local workspace', tool_name: 'local_write_file', arguments: { path: 'hello.txt', content: 'Hello' } })}\n`
      : `${JSON.stringify({ type: 'token', content: 'Created hello.txt successfully.' })}\n${JSON.stringify({ type: 'done', usage: {} })}\n`
    return route.fulfill({ contentType: 'application/x-ndjson', body })
  })
  await page.route('**/api/local-tools/call', async route => {
    const request = route.request().postDataJSON()
    expect(request.approved).toBe(true)
    expect(request.arguments).toEqual({ path: 'hello.txt', content: 'Hello' })
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ result: { path: 'hello.txt', created: true } }) })
  })
  await page.goto('/')
  await page.getByLabel('Message Local AI').fill('Create hello.txt')
  await page.getByRole('button', { name: 'Send message' }).click()
  await expect(page.getByText('Allow Local workspace to run local_write_file?')).toBeVisible()
  await expect(page.getByText('This can change files or run a command on this computer.')).toBeVisible()
  await expect(page.locator('.tool-approval code')).toContainText('hello.txt')
  await page.getByRole('button', { name: 'Allow once' }).click()
  await expect(page.getByText('Created hello.txt successfully.')).toBeVisible()
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
  await dialog.getByRole('tab', { name: /Workspaces/ }).click()
  await expect(dialog.getByRole('heading', { name: 'Approved workspaces' })).toBeVisible()
  await expect(dialog.getByText('The selected folder is available to Local AI for repository context, file changes, and approved commands. Every local action still requires Allow once in chat.')).toBeVisible()
  await expect(dialog.getByRole('textbox', { name: 'Workspace name' })).toHaveAttribute('placeholder', 'My project')
  await expect(dialog.getByRole('textbox', { name: 'Project folder' })).toHaveAttribute('placeholder', /Projects[\\/]my-project$/)
  await dialog.getByRole('tab', { name: /Activity/ }).click()
  await expect(dialog.getByRole('heading', { name: 'Tool activity' })).toBeVisible()
  await dialog.getByRole('tab', { name: /Performance/ }).click()
  await expect(dialog.getByRole('heading', { name: 'Host & performance' })).toBeVisible()
  await expect(dialog.getByRole('button', { name: 'Apply best settings for this computer' })).toBeVisible()
  await expect(dialog.getByText('Average speed')).toBeVisible()
  await expect(dialog.getByRole('heading', { name: 'Performance presets' })).toBeVisible()
  await expect(dialog.getByRole('button', { name: /Long context/ })).toContainText('Uses more RAM or VRAM')
  await expect(dialog.getByRole('heading', { name: 'Custom performance' })).toBeVisible()
  const contextSlider = dialog.getByRole('slider', { name: 'Context window' })
  await expect(contextSlider).toBeVisible()
  await contextSlider.press('ArrowRight')
  await expect(dialog.getByRole('button', { name: 'Save custom performance' })).toBeEnabled()
  await expect(dialog.getByText('Impact estimates are directional.')).toBeVisible()
  await dialog.getByRole('tab', { name: /Backup/ }).click()
  await expect(dialog.getByText('Optional—use any length. A longer unique passphrase provides stronger protection.')).toBeVisible()
  await expect(dialog.getByRole('button', { name: 'Download encrypted backup' })).toBeEnabled()
  const box = await dialog.boundingBox()
  const viewport = page.viewportSize()
  expect(box.width).toBeLessThanOrEqual(viewport.width)
  expect(box.height).toBeLessThanOrEqual(viewport.height)
})
