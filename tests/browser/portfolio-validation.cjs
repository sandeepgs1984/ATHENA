/* Isolated real-dashboard browser gate. Requires Playwright on NODE_PATH. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');
const staticDir = path.join(root, 'src/athena/api/static');
const output = process.env.PORTFOLIO_UI_ARTIFACTS || '/tmp/athena-rv7';
const app = fs.readFileSync(path.join(root, 'src/athena/api/app.py'), 'utf8');
const parts = app.split('DASHBOARD_JS_PARTS: tuple[str, ...] = (')[1].split(')')[0];
const script = [...parts.matchAll(/"([^"]+\.js)"/g)]
    .map(match => fs.readFileSync(path.join(staticDir, 'js', match[1]), 'utf8')).join('\n');
const rows = Array.from({ length: 48 }, (_, index) => ({
    instrument_id: `fixture-${index}`, symbol: index === 0 ? 'LONG-SYMBOL-FIXTURE' : `TEST${index}`,
    qty: 137, quantity: 137, avg_price: '1234.56', last_price: '1456.78',
    investment: '169134.72', current_value: '199578.86',
    pnl: index % 2 ? '-30444.14' : '30444.14', pnl_pct: index % 2 ? '-18.00' : '18.00',
    status: index % 2 ? 'CAUTION' : 'HEALTHY', conviction: 'HIGH',
    trend_or_setup: index % 2 ? 'DOWNTREND / -' : 'UPTREND / BREAKOUT', next_action: 'WATCH',
    daily_review: { review_status: 'HOLD', guidance: 'Synthetic browser fixture only.' },
    provenance: { interpretation_version: 'portfolio-interpretation-v4' },
}));
const snapshot = { rows, summary: { holding_count: 48, total_investment: '8118466.56',
    total_current_value: '9580000.12', total_pnl: '1461533.56', total_pnl_pct: '18.00',
    last_synced_at: '2026-09-11T10:00:00Z' } };

(async () => {
    fs.mkdirSync(output, { recursive: true });
    const browser = await chromium.launch({ headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome' });
    try {
        for (const width of [390, 640, 768, 1280, 1920]) {
            const context = await browser.newContext({ viewport: { width, height: 900 }, reducedMotion: 'reduce' });
            const page = await context.newPage();
            const errors = [], unexpected = [];
            let releaseSync;
            let syncStatus = 'SUCCESS';
            const syncWait = new Promise(resolve => { releaseSync = resolve; });
            page.on('pageerror', error => errors.push(error.message));
            // No request can reach a real service, including external font/CDN hosts.
            await context.route('**/*', async route => {
                const url = new URL(route.request().url());
                if (url.origin !== 'http://portfolio.test') return route.abort();
                const pathname = url.pathname;
                let data;
                if (pathname === '/api/v1/auth/status') data = { auth_required: false };
                else if (pathname === '/health') return route.fulfill({ json: { status: 'UP' } });
                else if (pathname === '/api/v1/health') data = { cycles_enabled: false };
                else if (pathname === '/api/v1/ops/kite/status') data = { required: false };
                else if (pathname === '/api/v1/my-portfolio/holdings') data = rows;
                else if (pathname === '/api/v1/my-portfolio/imports') {
                    data = route.request().method() === 'POST'
                        ? { import_id: 'fixture', filename: 'fixture.csv', status: 'PREVIEWED',
                            total_rows: 48, accepted_rows: 48, rejected_rows: 0, rows: [], proposed_changes: [] }
                        : { imports: [] };
                }
                else if (pathname === '/api/v1/my-portfolio/notes') data = [];
                else if (pathname === '/api/v1/my-portfolio/snapshot') data = snapshot;
                else if (pathname === '/api/v1/my-portfolio/snapshot/changes') data = null;
                else if (pathname === '/api/v1/my-portfolio/snapshot/timeline') data = { entries: [] };
                else if (pathname === '/api/v1/my-portfolio/sync') data = { sync_run_id: 'fixture', status: 'RUNNING' };
                else if (pathname === '/api/v1/my-portfolio/sync/fixture') {
                    await syncWait;
                    data = { sync_run_id: 'fixture', status: syncStatus, total_holdings: 48, succeeded_holdings: 48 };
                }
                else if (['/api/v1/dashboard/session-status', '/api/v1/dashboard/advisory-freshness',
                    '/api/v1/dashboard/cycle-status', '/api/v1/market/ticker'].includes(pathname)) data = {};
                else if (pathname.startsWith('/api/')) {
                    unexpected.push(`${route.request().method()} ${pathname}`);
                    return route.fulfill({ status: 500, json: { error: 'Unmocked API' } });
                } else {
                    if (pathname.endsWith('/dashboard.js')) return route.fulfill({ contentType: 'text/javascript', body: script });
                    const relative = pathname.replace(/^\/dashboard\//, '');
                    const file = pathname === '/dashboard/my-portfolio' ? path.join(staticDir, 'index.html') : path.join(staticDir, relative);
                    if (!file.startsWith(staticDir + '/') || !fs.existsSync(file) || !fs.statSync(file).isFile()) return route.abort();
                    return route.fulfill({ path: file });
                }
                return route.fulfill({ json: { data } });
            });
            await page.goto('http://portfolio.test/dashboard/my-portfolio');
            await page.locator('#my-portfolio-holdings-rows tr[data-instrument-id]').first().waitFor();
            if (width === 640) await page.addStyleTag({ content: 'html { font-size: 32px; }' });
            await page.screenshot({ path: path.join(output, `${width}-initial.png`) });
            const geometry = await page.evaluate(() => ({
                viewport: innerWidth, document: document.documentElement.scrollWidth,
                workspace: document.querySelector('.workspace-viewport').getBoundingClientRect().toJSON(),
            }));
            assert.ok(geometry.document <= width + 1, `Document overflow at ${width}: ${JSON.stringify(geometry)}`);
            assert.equal(await page.locator('.my-portfolio-kpi-strip').evaluate(element => {
                const rect = element.getBoundingClientRect();
                const hit = document.elementFromPoint(rect.left + 20, rect.top + 30);
                return element.contains(hit);
            }), true, 'Initial summary obscured');
            await page.locator('#my-portfolio-risk-toggle').click();
            await page.locator('#my-portfolio-heatmap-toggle').click();
            assert.equal(await page.locator('.my-portfolio-heatmap-tile').count(), 48);
            await page.screenshot({ path: path.join(output, `${width}-risk.png`) });
            await page.locator('#my-portfolio-risk-toggle').click();
            const workspace = page.locator('.workspace-viewport');
            const status = page.locator('[data-smart-group="status"][data-smart-value="HEALTHY"]');
            await status.scrollIntoViewIfNeeded();
            await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
            const before = await workspace.evaluate(element => element.scrollTop);
            await status.click();
            const after = await workspace.evaluate(element => element.scrollTop);
            // Allow one line-box rounding adjustment from native scroll anchoring.
            assert.ok(Math.abs(after - before) <= 16, `Filter jumped at ${width}: ${before} -> ${after}`);
            assert.equal(await page.locator('#my-portfolio-holdings-rows tr[data-instrument-id]').count(), 24);
            await status.click();
            await page.locator('#my-portfolio-view-holdings').click();
            await page.locator('#my-portfolio-table-profile').selectOption('full_audit');
            assert.equal(await page.locator('#my-portfolio-holdings-table').getAttribute('data-table-profile'), 'full_audit');
            await page.locator('#my-portfolio-table-profile').selectOption('compact_scan');
            if (width > 920) {
                await workspace.evaluate(element => { element.scrollTop += 500; });
                await page.waitForFunction(() => {
                    const header = document.getElementById('my-portfolio-sticky-header');
                    const viewport = document.querySelector('.workspace-viewport');
                    return Math.abs(header.getBoundingClientRect().top - viewport.getBoundingClientRect().top) < 2;
                });
                await page.screenshot({ path: path.join(output, `${width}-sticky.png`) });
            }
            const row = page.locator('#my-portfolio-holdings-rows tr[data-instrument-id]').first();
            await row.click();
            const modal = page.locator('#my-portfolio-detail-modal');
            await modal.waitFor({ state: 'visible' });
            await page.locator('#my-portfolio-detail-body').evaluate(element => { element.scrollTop = 500; });
            await page.locator('#my-portfolio-detail-close').click();
            await row.click();
            await page.waitForFunction(() => document.getElementById('my-portfolio-detail-body').scrollTop === 0);
            await page.screenshot({ path: path.join(output, `${width}-detail.png`) });
            await page.locator('#my-portfolio-detail-close').click();
            const privacy = page.locator('#my-portfolio-privacy-toggle');
            await privacy.click();
            assert.ok(!(await page.locator('#tab-my-portfolio').innerText()).includes('95,80,000.12'));
            assert.ok(!(await page.locator('#my-portfolio-holdings-rows').innerText()).includes('1,456.78'));
            await row.click();
            await modal.waitFor({ state: 'visible' });
            assert.ok(!(await modal.innerText()).includes('1,234.56'));
            await page.locator('#my-portfolio-detail-close').click();
            await page.locator('#my-portfolio-reset-open').click();
            await page.locator('#my-portfolio-reset-modal').waitFor({ state: 'visible' });
            assert.equal(await page.locator('#my-portfolio-reset-submit').isDisabled(), true);
            await page.locator('#my-portfolio-reset-close').click();
            await page.locator('#my-portfolio-export-toggle').click();
            await page.locator('#my-portfolio-export-panel').waitFor({ state: 'visible' });
            const exportBounds = await page.locator('#my-portfolio-export-panel').boundingBox();
            assert.ok(exportBounds.x >= 0 && exportBounds.x + exportBounds.width <= width + 1,
                `Export clipped at ${width}`);
            await page.screenshot({ path: path.join(output, `${width}-export.png`) });
            await page.locator('#my-portfolio-export-close').click();
            assert.equal(await page.locator('#my-portfolio-export-panel').isVisible(), false);
            await page.locator('#my-portfolio-file').setInputFiles({ name: 'fixture.csv', mimeType: 'text/csv', buffer: Buffer.from('Symbol,Qty,Avg Price\nTEST,137,1234.56') });
            await page.locator('#my-portfolio-preview-modal').waitFor({ state: 'visible' });
            await page.screenshot({ path: path.join(output, `${width}-preview.png`) });
            await page.keyboard.press('Escape');
            await page.locator('#my-portfolio-sync').click();
            const blocker = page.locator('#my-portfolio-sync-overlay');
            await blocker.waitFor({ state: 'visible' });
            const bounds = await blocker.boundingBox();
            assert.ok(bounds.x <= 0 && bounds.y <= 0 && bounds.width >= width && bounds.height >= 900);
            releaseSync();
            await blocker.waitFor({ state: 'hidden' });
            syncStatus = 'FAILED';
            const failedPoll = page.waitForResponse(response => response.url().endsWith('/sync/fixture'));
            await page.locator('#my-portfolio-sync').click();
            await failedPoll;
            await blocker.waitFor({ state: 'hidden' });
            assert.deepEqual(errors, [], `Browser errors at ${width}`);
            assert.deepEqual(unexpected, [], `Unexpected APIs at ${width}`);
            console.log(`PASS ${width}px populated dashboard, detail reopen, privacy, preview and sync`);
            await context.close();
        }
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
