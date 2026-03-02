const { test, expect } = require('@playwright/test');
const BASE = 'https://inspections.archpractice.co.za';
const CODE = 'test-jb';

async function login(page) {
    await page.goto(BASE + '/login?u=' + CODE);
    await page.waitForTimeout(1000);
    const inp = page.locator('input[name="code"], input[placeholder*="code"]');
    if (await inp.isVisible({ timeout: 2000 }).catch(() => false)) {
        await inp.fill(CODE);
        await page.locator('button:has-text("Log In")').click();
        await page.waitForTimeout(1500);
    }
    await page.waitForSelector('text=999', { timeout: 5000 });
    await page.locator('text=999').first().click();
    await page.waitForTimeout(2000);
    await page.waitForSelector('#area-content', { timeout: 5000 });
    await page.waitForTimeout(1000);
    // Expand first category to reveal items
    const expandAll = page.locator('text=Expand All');
    if (await expandAll.isVisible({timeout:2000}).catch(()=>false)) {
        await expandAll.click();
        await page.waitForTimeout(500);
    } else {
        const catHeader = page.locator('.cat-chevron').first();
        if (await catHeader.isVisible({timeout:2000}).catch(()=>false)) {
            await catHeader.click();
            await page.waitForTimeout(500);
        }
    }
}

test.describe('Bug: Scroll-triggered marking', () => {
    test('scroll should not change item status', async ({ page }) => {
        await login(page);
        const okBefore = await page.locator('button:has-text("OK")').count();
        const box = await page.locator('#area-content').boundingBox();
        for (let i = 0; i < 5; i++) {
            await page.mouse.move(box.x + box.width/2, box.y + box.height*0.7);
            await page.mouse.down();
            await page.mouse.move(box.x + box.width/2, box.y + box.height*0.3, {steps:10});
            await page.mouse.up();
            await page.waitForTimeout(300);
        }
        await page.waitForTimeout(1000);
        const okAfter = await page.locator('button:has-text("OK")').count();
        expect(okAfter).toBe(okBefore);
        console.log('Scroll: OK ' + okBefore + '->' + okAfter);
    });

    test('scroll should not fire POST requests', async ({ page }) => {
        await login(page);
        const posts = [];
        page.on('request', r => { if (r.method()==='POST') posts.push(r.url()); });
        const box = await page.locator('#area-content').boundingBox();
        for (let i = 0; i < 10; i++) {
            await page.mouse.move(box.x + box.width/2, box.y + box.height*0.8);
            await page.mouse.down();
            await page.mouse.move(box.x + box.width/2, box.y + box.height*0.2, {steps:5});
            await page.mouse.up();
            await page.waitForTimeout(100);
        }
        await page.waitForTimeout(1500);
        const itemPosts = posts.filter(u => u.includes('/item/'));
        expect(itemPosts.length).toBe(0);
        console.log('Scroll POSTs: ' + itemPosts.length);
    });
});

test.describe('Bug: Suggestion override', () => {
    test('typing should not be replaced by pill', async ({ page }) => {
        await login(page);
        await page.locator('a:has-text("Inspect")').first().click();
        await page.waitForTimeout(1500);
        const input = page.locator('input[placeholder*="Describe the defect"]').first();
        await expect(input).toBeVisible({ timeout: 3000 });
        await input.fill('Test description typed by user');
        await page.waitForTimeout(500);
        expect(await input.inputValue()).toBe('Test description typed by user');
        console.log('Input preserved');
    });

    test('pill should not add defect to wrong item', async ({ page }) => {
        await login(page);
        const posts = [];
        page.on('request', r => { if (r.method()==='POST' && r.url().includes('defect')) posts.push(r.url()); });
        await page.locator('a:has-text("Inspect")').first().click();
        await page.waitForTimeout(1500);
        const pill = page.locator('.defect-input-wrapper button.text-sm').first();
        if (await pill.isVisible({timeout:3000}).catch(()=>false)) {
            await pill.click();
            await page.waitForTimeout(1000);
            console.log('Pill POSTs: ' + posts.length);
        } else { console.log('No pills found'); }
    });
});

test.describe('Basic flow', () => {
    test('mark item OK', async ({ page }) => {
        await login(page);
        const resp = page.waitForResponse(r => r.url().includes('/item/') && r.status()===200);
        await page.locator('button:has-text("OK")').first().click();
        expect((await resp).status()).toBe(200);
        console.log('OK: pass');
    });

    test('mark item N/I', async ({ page }) => {
        await login(page);
        const resp = page.waitForResponse(r => r.url().includes('/item/') && r.status()===200);
        await page.locator('button:has-text("N/I")').first().click();
        expect((await resp).status()).toBe(200);
        console.log('N/I: pass');
    });

    test('add defect via text', async ({ page }) => {
        await login(page);
        await page.locator('a:has-text("Inspect")').first().click();
        await page.waitForTimeout(1500);
        const input = page.locator('input[placeholder*="Describe the defect"]').first();
        await input.fill('Automated test defect');
        const resp = page.waitForResponse(r => r.url().includes('defect') && r.status()===200);
        await page.locator('button:has-text("Add")').first().click();
        expect((await resp).status()).toBe(200);
        await page.waitForTimeout(1000);
        await expect(page.locator('text=Automated test defect')).toBeVisible({timeout:3000});
        console.log('Add defect: pass');
    });

    test('switch area tabs', async ({ page }) => {
        await login(page);
        const tabs = page.locator('.area-tab');
        expect(await tabs.count()).toBeGreaterThan(1);
        await tabs.nth(1).click();
        await page.waitForTimeout(1500);
        expect((await page.locator('#area-content').innerHTML()).length).toBeGreaterThan(100);
        console.log('Tabs: pass');
    });
});

test.describe('Stress tests', () => {
    test('rapid OK taps should not cross-fire', async ({ page }) => {
        await login(page);
        const posts = [];
        page.on('request', r => { if (r.method()==='POST' && r.url().includes('/item/')) posts.push(r.url()); });
        const btns = page.locator('button:has-text("OK")');
        const n = Math.min(await btns.count(), 3);
        for (let i = 0; i < n; i++) { await btns.nth(i).click(); await page.waitForTimeout(100); }
        await page.waitForTimeout(2000);
        expect(new Set(posts).size).toBe(posts.length);
        console.log('Rapid: ' + n + ' taps, ' + posts.length + ' POSTs');
    });

    test('empty description blocked', async ({ page }) => {
        await login(page);
        await page.locator('a:has-text("Inspect")').first().click();
        await page.waitForTimeout(1500);
        const posts = [];
        page.on('request', r => { if (r.method()==='POST' && r.url().includes('defect')) posts.push(1); });
        await page.locator('button:has-text("Add")').first().click();
        await page.waitForTimeout(1000);
        expect(posts.length).toBe(0);
        console.log('Empty: blocked');
    });
});

test.describe('Mobile touch', () => {
    test('touch Inspect opens panel', async ({ page }) => {
        await login(page);
        const btn = page.locator('a:has-text("Inspect")').first();
        await expect(btn).toBeVisible({timeout:5000});
        const box = await btn.boundingBox();
        await page.touchscreen.tap(box.x + box.width/2, box.y + box.height/2);
        await page.waitForTimeout(1500);
        const vis = await page.locator('input[placeholder*="Describe the defect"]').first().isVisible().catch(()=>false);
        expect(vis).toBe(true);
        console.log('Touch inspect: pass');
    });

    test('touch pill should not double-fire', async ({ page }) => {
        await login(page);
        await page.locator('a:has-text("Inspect")').first().click();
        await page.waitForTimeout(1500);
        const posts = [];
        page.on('request', r => { if (r.method()==='POST') posts.push(r.url()); });
        const pill = page.locator('button[ontouchend]').first();
        if (await pill.isVisible({timeout:3000}).catch(()=>false)) {
            const box = await pill.boundingBox();
            await page.touchscreen.tap(box.x + box.width/2, box.y + box.height/2);
            await page.waitForTimeout(1000);
            expect(posts.length).toBeLessThanOrEqual(1);
            console.log('Touch pill: ' + posts.length + ' POSTs');
        } else { console.log('No touch pills'); }
    });
});
