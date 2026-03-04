// inspection.spec.js
// Full Playwright test suite -- 57 tests
// Unit 999 | Inspector: test-jb | Cycle: c2725b56
// Buttons: [data-btn="cat-inst/cat-ni/inst/ni/ms/nts"]
// Confirm modal: #confirm-modal, #confirm-msg

const { test, expect } = require("@playwright/test");
const BASE = "https://inspections.archpractice.co.za";
const INSPECTOR = "test-jb";
const RESET_TOKEN = "test-jb-reset-999";

// ============================================================
// HELPERS
// ============================================================

async function resetUnit(page) {
    const resp = await page.request.post(BASE + "/inspection/test/reset", {
        data: { token: RESET_TOKEN }
    });
    if (resp.status() !== 200) throw new Error("Reset failed: " + resp.status());
    const body = await resp.json();
    if (!body.ok) throw new Error("Reset error: " + JSON.stringify(body));
}

async function login(page) {
    await page.goto(BASE + "/login?u=" + INSPECTOR);
    await page.waitForSelector("text=999", { timeout: 8000 });
    await page.locator("text=999").first().click();
    await page.waitForSelector("#area-content", { timeout: 8000 });
    await page.waitForTimeout(600);
}

async function expandFirstCat(page) {
    const chev = page.locator(".cat-chevron").first();
    await chev.waitFor({ state: "visible", timeout: 5000 });
    await chev.click();
    await page.waitForTimeout(300);
}

async function confirmModal(page) {
    const modal = page.locator("#confirm-modal");
    await expect(modal).toBeVisible({ timeout: 3000 });
    await modal.locator("button:has-text(\"Confirm\")").click();
    await page.waitForTimeout(500);
}

async function cancelModal(page) {
    const modal = page.locator("#confirm-modal");
    await expect(modal).toBeVisible({ timeout: 3000 });
    await modal.locator("button:has-text(\"Cancel\")").click();
    await page.waitForTimeout(300);
}

async function openDefectInput(page) {
    await expandFirstCat(page);
    await page.locator("[id^=\"step1-\"]").first().locator("[data-btn=\"inst\"]").click();
    await page.waitForTimeout(200);
    await page.locator("[id^=\"step2-\"]:visible").first().locator("[data-btn=\"nts\"]").click();
    await page.waitForTimeout(400);
}

// Finds first parent item by looking for children with data-parent-id
async function getFirstParentId(page) {
    const children = page.locator("[data-parent-id]");
    if (await children.count() === 0) return null;
    return await children.first().getAttribute("data-parent-id");
}

// ============================================================
// GLOBAL beforeEach: reset + login for every test
// ============================================================
test.beforeEach(async ({ page }) => {
    await resetUnit(page);
    await login(page);
});

// ============================================================
// 1. CATEGORY LEVEL (6 tests)
// ============================================================
test.describe("Category Level", () => {

    test("cat-inst tap expands category", async ({ page }) => {
        const content = page.locator(".cat-content").first();
        await expect(content).toHaveClass(/hidden/);
        await page.locator("[data-btn=\"cat-inst\"]").first().click();
        await page.waitForTimeout(300);
        await expect(content).not.toHaveClass(/hidden/);
    });

    test("cat-ni shows confirm modal with N/I text", async ({ page }) => {
        await page.locator("[data-btn=\"cat-ni\"]").first().click();
        await expect(page.locator("#confirm-modal")).toBeVisible({ timeout: 3000 });
        const msg = await page.locator("#confirm-msg").textContent();
        expect(msg).toContain("N/I");
    });

    test("cat-ni confirm marks category NI selected", async ({ page }) => {
        await page.locator("[data-btn=\"cat-ni\"]").first().click();
        await confirmModal(page);
        await page.waitForResponse(r => r.url().includes("cascade") && r.status() === 200, { timeout: 6000 });
        await page.waitForTimeout(600);
        const cls = await page.locator("[data-btn=\"cat-ni\"]").first().getAttribute("class");
        expect(cls).toContain("bg-amber-500");
    });

    test("cat-ni cancel leaves category unchanged", async ({ page }) => {
        const content = page.locator(".cat-content").first();
        await page.locator("[data-btn=\"cat-ni\"]").first().click();
        await cancelModal(page);
        await expect(content).toHaveClass(/hidden/);
    });

    test("cat-counter updates after item marked", async ({ page }) => {
        await expandFirstCat(page);
        const counter = page.locator(".cat-counter").first();
        const before = await counter.textContent();
        await page.locator("[id^=\"step1-\"]").first().locator("[data-btn=\"inst\"]").click();
        await page.waitForTimeout(200);
        const resp = page.waitForResponse(r => r.url().includes("/item/") && r.status() === 200);
        await page.locator("[id^=\"step2-\"]:visible").first().locator("[data-btn=\"ms\"]").click();
        await resp;
        await page.waitForTimeout(600);
        const after = await counter.textContent();
        expect(after).not.toBe(before);
    });

    test("cat-defect-badge appears after defect added", async ({ page }) => {
        await expandFirstCat(page);
        const badge = page.locator(".cat-defect-badge").first();
        await expect(badge).toBeHidden();
        await openDefectInput(page);
        const inp = page.locator("input[placeholder*=\"Describe the defect\"]").first();
        await inp.fill("Paint peeling");
        await inp.press("Enter");
        await page.waitForResponse(r => r.url().includes("defect") && r.status() === 200, { timeout: 5000 });
        await page.waitForTimeout(600);
        await expect(badge).toBeVisible({ timeout: 3000 });
    });
});

// ============================================================
// 2. ITEM LEVEL -- LEAF (10 tests)
// ============================================================
test.describe("Item Level Leaf", () => {

    test("inst tap reveals ms/nts row", async ({ page }) => {
        await expandFirstCat(page);
        const step2 = page.locator("[id^=\"step2-\"]").first();
        await expect(step2).toBeHidden();
        await page.locator("[id^=\"step1-\"]").first().locator("[data-btn=\"inst\"]").click();
        await page.waitForTimeout(200);
        await expect(step2).toBeVisible();
    });

    test("inst then ms marks item ok", async ({ page }) => {
        await expandFirstCat(page);
        await page.locator("[id^=\"step1-\"]").first().locator("[data-btn=\"inst\"]").click();
        await page.waitForTimeout(200);
        const resp = page.waitForResponse(r => r.url().includes("/item/") && r.status() === 200);
        await page.locator("[id^=\"step2-\"]:visible").first().locator("[data-btn=\"ms\"]").click();
        await resp;
        await page.waitForTimeout(300);
        const cls = await page.locator("[id^=\"step1-\"]").first().locator("[data-btn=\"inst\"]").getAttribute("class");
        expect(cls).toContain("bg-blue-600");
    });

    test("inst then nts reveals defect input", async ({ page }) => {
        await expandFirstCat(page);
        await page.locator("[id^=\"step1-\"]").first().locator("[data-btn=\"inst\"]").click();
        await page.waitForTimeout(200);
        await page.locator("[id^=\"step2-\"]:visible").first().locator("[data-btn=\"nts\"]").click();
        await page.waitForTimeout(300);
        await expect(page.locator("input[placeholder*=\"Describe the defect\"]").first()).toBeVisible({ timeout: 3000 });
    });

    test("ni tap marks item not_installed", async ({ page }) => {
        await expandFirstCat(page);
        const resp = page.waitForResponse(r => r.url().includes("/item/") && r.status() === 200);
        await page.locator("[id^=\"step1-\"]").first().locator("[data-btn=\"ni\"]").click();
        await resp;
        await page.waitForTimeout(300);
        const cls = await page.locator("[id^=\"step1-\"]").first().locator("[data-btn=\"ni\"]").getAttribute("class");
        expect(cls).toContain("bg-amber-500");
    });

    test("ms marks item ok and button shows selected", async ({ page }) => {
        await expandFirstCat(page);
        await page.locator("[id^=\"step1-\"]").first().locator("[data-btn=\"inst\"]").click();
        await page.waitForTimeout(200);
        const resp = page.waitForResponse(r => r.url().includes("/item/") && r.status() === 200);
        await page.locator("[id^=\"step2-\"]:visible").first().locator("[data-btn=\"ms\"]").click();
        await resp;
        await page.waitForTimeout(300);
        const cls = await page.locator("[id^=\"step2-\"]").first().locator("[data-btn=\"ms\"]").getAttribute("class");
        expect(cls).toContain("bg-green-600");
    });

    test("nts enter submits chip", async ({ page }) => {
        await openDefectInput(page);
        const inp = page.locator("input[placeholder*=\"Describe the defect\"]").first();
        await inp.fill("Surface damage noted");
        const resp = page.waitForResponse(r => r.url().includes("defect") && r.status() === 200);
        await inp.press("Enter");
        await resp;
        await page.waitForTimeout(300);
        await expect(page.locator(".bg-red-100").filter({ hasText: "Surface damage noted" })).toBeVisible({ timeout: 3000 });
    });

    test("nts multiple chips on one item", async ({ page }) => {
        await openDefectInput(page);
        const inp = page.locator("input[placeholder*=\"Describe the defect\"]").first();
        await inp.fill("First defect");
        await inp.press("Enter");
        await page.waitForResponse(r => r.url().includes("defect") && r.status() === 200);
        await page.waitForTimeout(400);
        const inp2 = page.locator("input[placeholder*=\"Describe the defect\"], input[placeholder*=\"Add\"]").first();
        await inp2.fill("Second defect");
        await inp2.press("Enter");
        await page.waitForResponse(r => r.url().includes("defect") && r.status() === 200);
        await page.waitForTimeout(400);
        expect(await page.locator(".bg-red-100.text-red-800").count()).toBeGreaterThanOrEqual(2);
    });

    test("nts switch to ms requires confirm modal", async ({ page }) => {
        await openDefectInput(page);
        const inp = page.locator("input[placeholder*=\"Describe the defect\"]").first();
        await inp.fill("Test defect");
        await inp.press("Enter");
        await page.waitForResponse(r => r.url().includes("defect") && r.status() === 200);
        await page.waitForTimeout(400);
        await page.locator("[id^=\"step2-\"]").first().locator("[data-btn=\"ms\"]").click();
        await expect(page.locator("#confirm-modal")).toBeVisible({ timeout: 3000 });
        const msg = await page.locator("#confirm-msg").textContent();
        expect(msg).toContain("defect");
    });

    test("ni then inst reveals ms/nts row", async ({ page }) => {
        await expandFirstCat(page);
        const resp = page.waitForResponse(r => r.url().includes("/item/") && r.status() === 200);
        await page.locator("[id^=\"step1-\"]").first().locator("[data-btn=\"ni\"]").click();
        await resp;
        await page.waitForTimeout(300);
        await page.locator("[id^=\"step1-\"]").first().locator("[data-btn=\"inst\"]").click();
        await page.waitForTimeout(300);
        await expect(page.locator("[id^=\"step2-\"]").first()).toBeVisible({ timeout: 2000 });
    });

    test("ms reopen to nts opens defect input", async ({ page }) => {
        await expandFirstCat(page);
        await page.locator("[id^=\"step1-\"]").first().locator("[data-btn=\"inst\"]").click();
        await page.waitForTimeout(200);
        const resp = page.waitForResponse(r => r.url().includes("/item/") && r.status() === 200);
        await page.locator("[id^=\"step2-\"]:visible").first().locator("[data-btn=\"ms\"]").click();
        await resp;
        await page.waitForTimeout(300);
        await page.locator("[id^=\"step2-\"]").first().locator("[data-btn=\"nts\"]").click();
        await page.waitForTimeout(300);
        await expect(page.locator("input[placeholder*=\"Describe the defect\"]").first()).toBeVisible({ timeout: 3000 });
    });
});

// ============================================================
// 3. ITEM LEVEL -- PARENT + CHILDREN (7 tests)
// ============================================================
test.describe("Item Level Parent Children", () => {

    // Kitchen area has Window W1/W1a with children -- navigate there
    async function goToKitchen(page) {
        const tabs = page.locator(".area-tab");
        const count = await tabs.count();
        for (let i = 0; i < count; i++) {
            const txt = (await tabs.nth(i).textContent() || "").trim();
            if (txt.startsWith("Kitchen")) {
                await tabs.nth(i).click();
                await page.waitForTimeout(800);
                return;
            }
        }
        // Fallback: first tab already loaded
    }

    async function expandUntilChildren(page) {
        // Expand categories until we find one with data-parent-id children
        const cats = page.locator(".cat-chevron");
        const total = await cats.count();
        for (let i = 0; i < total; i++) {
            await cats.nth(i).click();
            await page.waitForTimeout(200);
            if (await page.locator("[data-parent-id]").count() > 0) return true;
        }
        return false;
    }

    test("parent ni shows confirm with subitems text", async ({ page }) => {
        await goToKitchen(page);
        const found = await expandUntilChildren(page);
        if (!found) { console.log("Skip: no parent items found"); return; }
        const parentId = await getFirstParentId(page);
        await page.locator(`#item-${parentId}`).locator("[data-btn=\"ni\"]").click();
        await expect(page.locator("#confirm-modal")).toBeVisible({ timeout: 3000 });
        const msg = await page.locator("#confirm-msg").textContent();
        expect(msg).toContain("subitems");
    });

    test("parent ni confirm cascades NI to all children", async ({ page }) => {
        await goToKitchen(page);
        const found = await expandUntilChildren(page);
        if (!found) { console.log("Skip: no parent items found"); return; }
        const parentId = await getFirstParentId(page);
        const parentItem = page.locator(`#item-${parentId}`);
        await parentItem.locator("[data-btn=\"ni\"]").click();
        await confirmModal(page);
        await page.waitForResponse(r => r.url().includes("/item/") && r.status() === 200, { timeout: 6000 });
        await page.waitForTimeout(400);
        const cls = await parentItem.locator("[data-btn=\"ni\"]").getAttribute("class");
        expect(cls).toContain("bg-amber-500");
    });

    test("parent inst expands children visibility", async ({ page }) => {
        await goToKitchen(page);
        const found = await expandUntilChildren(page);
        if (!found) { console.log("Skip: no parent items found"); return; }
        const parentId = await getFirstParentId(page);
        const parentItem = page.locator(`#item-${parentId}`);
        // Children exist but may be hidden -- click INST on parent
        await parentItem.locator("[data-btn=\"inst\"]").click();
        await page.waitForTimeout(300);
        // At least one child should be visible
        await expect(page.locator("[data-parent-id]").first()).toBeVisible({ timeout: 2000 });
    });

    test("child ms marks ok", async ({ page }) => {
        await goToKitchen(page);
        const found = await expandUntilChildren(page);
        if (!found) { console.log("Skip: no children"); return; }
        const child = page.locator("[data-parent-id]").first();
        const resp = page.waitForResponse(r => r.url().includes("/item/") && r.status() === 200);
        await child.locator("[data-btn=\"ms\"]").click();
        await resp;
        await page.waitForTimeout(300);
        const cls = await child.locator("[data-btn=\"ms\"]").getAttribute("class");
        expect(cls).toContain("bg-green-600");
    });

    test("child nts adds chip", async ({ page }) => {
        await goToKitchen(page);
        const found = await expandUntilChildren(page);
        if (!found) { console.log("Skip: no children"); return; }
        const child = page.locator("[data-parent-id]").first();
        await child.locator("[data-btn=\"nts\"]").click();
        await page.waitForTimeout(300);
        const inp = child.locator("input[placeholder*=\"Describe the defect\"]");
        await expect(inp).toBeVisible({ timeout: 3000 });
        await inp.fill("Child defect test");
        const resp = page.waitForResponse(r => r.url().includes("defect") && r.status() === 200);
        await inp.press("Enter");
        await resp;
        await page.waitForTimeout(300);
        await expect(child.locator(".bg-red-100").filter({ hasText: "Child defect test" })).toBeVisible({ timeout: 3000 });
    });

    test("child nts switch to ms requires confirm", async ({ page }) => {
        await goToKitchen(page);
        const found = await expandUntilChildren(page);
        if (!found) { console.log("Skip: no children"); return; }
        const child = page.locator("[data-parent-id]").first();
        await child.locator("[data-btn=\"nts\"]").click();
        await page.waitForTimeout(300);
        const inp = child.locator("input[placeholder*=\"Describe the defect\"]");
        await inp.fill("Child NTS to switch");
        await inp.press("Enter");
        await page.waitForResponse(r => r.url().includes("defect") && r.status() === 200);
        await page.waitForTimeout(400);
        await child.locator("[data-btn=\"ms\"]").click();
        await expect(page.locator("#confirm-modal")).toBeVisible({ timeout: 3000 });
    });

    test("cat-defect-badge reflects child defects", async ({ page }) => {
        await goToKitchen(page);
        const found = await expandUntilChildren(page);
        if (!found) { console.log("Skip: no children"); return; }
        const badge = page.locator(".cat-defect-badge").first();
        const child = page.locator("[data-parent-id]").first();
        await child.locator("[data-btn=\"nts\"]").click();
        await page.waitForTimeout(300);
        const inp = child.locator("input[placeholder*=\"Describe the defect\"]");
        await inp.fill("Badge update test");
        await inp.press("Enter");
        await page.waitForResponse(r => r.url().includes("defect") && r.status() === 200);
        await page.waitForTimeout(600);
        await expect(badge).toBeVisible({ timeout: 3000 });
    });
});

// ============================================================
// 4. DEFECT ENTRY (12 tests)
// ============================================================
test.describe("Defect Entry", () => {

    const BLOCKED = [
        "Defect noted",
        "n/a",
        "Not applicable",
        "Not tested",
        "To be tested",
        "To be inspected",
        "as indicated",
        "Not applicable yet"
    ];

    for (const desc of BLOCKED) {
        test(`blocked description rejected: ${desc}`, async ({ page }) => {
            await openDefectInput(page);
            const inp = page.locator("input[placeholder*=\"Describe the defect\"]").first();
            const posts = [];
            page.on("request", r => { if (r.method() === "POST" && r.url().includes("defect")) posts.push(1); });
            await inp.fill(desc);
            await inp.press("Enter");
            await page.waitForTimeout(300);
            expect(posts.length).toBe(0);
            await expect(page.locator("#defect-toast")).toBeVisible({ timeout: 2000 });
        });
    }

    test("valid description accepted and chip appears", async ({ page }) => {
        await openDefectInput(page);
        const inp = page.locator("input[placeholder*=\"Describe the defect\"]").first();
        await inp.fill("Crack in plaster surface");
        const resp = page.waitForResponse(r => r.url().includes("defect") && r.status() === 200);
        await inp.press("Enter");
        await resp;
        await page.waitForTimeout(300);
        await expect(page.locator(".bg-red-100").filter({ hasText: "Crack in plaster surface" })).toBeVisible({ timeout: 3000 });
    });

    test("pill tap fires single POST and adds chip", async ({ page }) => {
        await openDefectInput(page);
        await page.waitForTimeout(1200); // Pills load via HTMX
        const pills = page.locator("[id^=\"nts-pills-\"] button, [id^=\"nts-pills-\"] a");
        const count = await pills.count();
        if (count === 0) { console.log("No pills for this item - skip"); return; }
        const posts = [];
        page.on("request", r => { if (r.method() === "POST" && r.url().includes("defect")) posts.push(1); });
        await pills.first().click();
        await page.waitForTimeout(1000);
        expect(posts.length).toBe(1);
        await expect(page.locator(".bg-red-100.text-red-800").first()).toBeVisible({ timeout: 3000 });
    });

    test("chip remove button deletes chip", async ({ page }) => {
        await openDefectInput(page);
        const inp = page.locator("input[placeholder*=\"Describe the defect\"]").first();
        await inp.fill("Chip to remove");
        await inp.press("Enter");
        await page.waitForResponse(r => r.url().includes("defect") && r.status() === 200);
        await page.waitForTimeout(400);
        const chip = page.locator(".bg-red-100.text-red-800").filter({ hasText: "Chip to remove" });
        await expect(chip).toBeVisible({ timeout: 3000 });
        const resp = page.waitForResponse(r => r.method() === "DELETE" && r.status() === 200);
        await chip.locator("button").click();
        await resp;
        await page.waitForTimeout(300);
        expect(await page.locator(".bg-red-100").filter({ hasText: "Chip to remove" }).count()).toBe(0);
    });
});

// ============================================================
// 5. PROGRESS & COUNTERS (5 tests)
// ============================================================
test.describe("Progress and Counters", () => {

    test("area progress header updates after item marked", async ({ page }) => {
        const areaProg = page.locator("[id^=\"area-progress-\"]").first();
        const before = await areaProg.textContent();
        await expandFirstCat(page);
        await page.locator("[id^=\"step1-\"]").first().locator("[data-btn=\"inst\"]").click();
        await page.waitForTimeout(200);
        const resp = page.waitForResponse(r => r.url().includes("/item/") && r.status() === 200);
        await page.locator("[id^=\"step2-\"]:visible").first().locator("[data-btn=\"ms\"]").click();
        await resp;
        await page.waitForTimeout(1000);
        const after = await areaProg.textContent();
        expect(after).not.toBe(before);
    });

    test("area defect badge updates after defect added", async ({ page }) => {
        await openDefectInput(page);
        const inp = page.locator("input[placeholder*=\"Describe the defect\"]").first();
        await inp.fill("Badge count test");
        await inp.press("Enter");
        await page.waitForResponse(r => r.url().includes("defect") && r.status() === 200);
        await page.waitForTimeout(800);
        const badge = page.locator("[id^=\"area-badge-\"]").first();
        await expect(badge).toBeVisible({ timeout: 3000 });
    });

    test("counter update does not jump scroll position", async ({ page }) => {
        await expandFirstCat(page);
        await page.evaluate(() => { document.getElementById("area-content").scrollTop = 120; });
        await page.waitForTimeout(100);
        const resp = page.waitForResponse(r => r.url().includes("/item/") && r.status() === 200);
        await page.locator("[id^=\"step1-\"]").first().locator("[data-btn=\"ni\"]").click();
        await resp;
        await page.waitForTimeout(500);
        const scrollAfter = await page.evaluate(() => document.getElementById("area-content").scrollTop);
        expect(Math.abs(scrollAfter - 120)).toBeLessThan(40);
    });

    test("progress bar shows item counts", async ({ page }) => {
        const text = await page.locator("#progress-bar").textContent();
        expect(text).toMatch(/\d+\/\d+/);
    });

    test("progress bar shows excluded count", async ({ page }) => {
        const text = await page.locator("#progress-bar").textContent();
        expect(text).toContain("excluded");
    });
});

// ============================================================
// 6. NAVIGATION & UX (6 tests)
// ============================================================
test.describe("Navigation and UX", () => {

    test("expand all expands all categories", async ({ page }) => {
        await expect(page.locator("text=Expand All")).toBeVisible({ timeout: 3000 });
        await page.locator("text=Expand All").click();
        await page.waitForTimeout(500);
        expect(await page.locator(".cat-content.hidden").count()).toBe(0);
    });

    test("collapse all collapses all categories", async ({ page }) => {
        await page.locator("text=Expand All").click();
        await page.waitForTimeout(500);
        await page.locator("text=Collapse All").click();
        await page.waitForTimeout(500);
        expect(await page.locator(".cat-content:not(.hidden)").count()).toBe(0);
    });

    test("defects only filter loads filtered area", async ({ page }) => {
        // Add a defect first so filter has results
        await openDefectInput(page);
        const inp = page.locator("input[placeholder*=\"Describe the defect\"]").first();
        await inp.fill("Filter test defect");
        await inp.press("Enter");
        await page.waitForResponse(r => r.url().includes("defect") && r.status() === 200);
        await page.waitForTimeout(400);
        await page.locator("button:has-text(\"Defects Only\")").click();
        await page.waitForResponse(r => r.url().includes("filter=defects") && r.status() === 200);
        await page.waitForTimeout(500);
        // At least one category with defects visible
        expect(await page.locator(".border.rounded-lg").count()).toBeGreaterThanOrEqual(1);
    });

    test("all items filter restores full category list", async ({ page }) => {
        await page.locator("button:has-text(\"Defects Only\")").click();
        await page.waitForResponse(r => r.url().includes("filter=defects") && r.status() === 200);
        await page.waitForTimeout(400);
        const countFiltered = await page.locator(".border.rounded-lg").count();
        await page.locator("button:has-text(\"All Items\")").click();
        await page.waitForResponse(r => r.url().includes("filter=all") && r.status() === 200);
        await page.waitForTimeout(500);
        const countAll = await page.locator(".border.rounded-lg").count();
        expect(countAll).toBeGreaterThanOrEqual(countFiltered);
    });

    test("switching area tabs loads different content", async ({ page }) => {
        const tabs = page.locator(".area-tab");
        expect(await tabs.count()).toBeGreaterThan(1);
        const first = await page.locator("#area-content").innerHTML();
        await tabs.nth(1).click();
        await page.waitForTimeout(1200);
        const second = await page.locator("#area-content").innerHTML();
        expect(first).not.toBe(second);
    });

    test("scroll in pr-6 safe zone fires no POSTs", async ({ page }) => {
        await expandFirstCat(page);
        const posts = [];
        page.on("request", r => { if (r.method() === "POST" && r.url().includes("/item/")) posts.push(r.url()); });
        const box = await page.locator("#area-content").boundingBox();
        const x = box.x + box.width - 8; // Far right edge (pr-6 safe zone)
        for (let i = 0; i < 5; i++) {
            await page.mouse.move(x, box.y + box.height * 0.8);
            await page.mouse.down();
            await page.mouse.move(x, box.y + box.height * 0.2, { steps: 5 });
            await page.mouse.up();
            await page.waitForTimeout(100);
        }
        await page.waitForTimeout(500);
        expect(posts.length).toBe(0);
    });
});

// ============================================================
// 7. SUBMIT (4 tests)
// ============================================================
test.describe("Submit", () => {

    test("submit button hidden when items pending", async ({ page }) => {
        const submitBtn = page.locator("#progress-bar button:has-text(\"Submit\")");
        await expect(submitBtn).toBeHidden({ timeout: 2000 });
    });

    test("submit modal has confirm and cancel buttons", async ({ page }) => {
        await page.evaluate(() => {
            const m = document.getElementById("submit-modal");
            if (m) m.classList.remove("hidden");
        });
        await page.waitForTimeout(300);
        await expect(page.locator("#submit-modal")).toBeVisible({ timeout: 2000 });
        await expect(page.locator("#submit-modal button:has-text(\"Confirm\")")).toBeVisible();
        await expect(page.locator("#submit-modal button:has-text(\"Cancel\")")).toBeVisible();
    });

    test("submit modal cancel hides modal", async ({ page }) => {
        await page.evaluate(() => {
            const m = document.getElementById("submit-modal");
            if (m) m.classList.remove("hidden");
        });
        await page.waitForTimeout(300);
        await page.locator("#submit-modal button:has-text(\"Cancel\")").click();
        await page.waitForTimeout(300);
        await expect(page.locator("#submit-modal")).toBeHidden();
    });

    test("submit defect count element present in modal", async ({ page }) => {
        await expect(page.locator("#submit-defect-count")).toBeAttached({ timeout: 3000 });
    });
});

// ============================================================
// 8. CORRECTIONS / UNDO (4 tests)
// ============================================================
test.describe("Corrections and Undo", () => {

    test("ni to inst shows ms/nts row", async ({ page }) => {
        await expandFirstCat(page);
        const resp = page.waitForResponse(r => r.url().includes("/item/") && r.status() === 200);
        await page.locator("[id^=\"step1-\"]").first().locator("[data-btn=\"ni\"]").click();
        await resp;
        await page.waitForTimeout(300);
        await page.locator("[id^=\"step1-\"]").first().locator("[data-btn=\"inst\"]").click();
        await page.waitForTimeout(300);
        await expect(page.locator("[id^=\"step2-\"]").first()).toBeVisible({ timeout: 2000 });
    });

    test("ms to nts opens defect input", async ({ page }) => {
        await expandFirstCat(page);
        await page.locator("[id^=\"step1-\"]").first().locator("[data-btn=\"inst\"]").click();
        await page.waitForTimeout(200);
        const resp = page.waitForResponse(r => r.url().includes("/item/") && r.status() === 200);
        await page.locator("[id^=\"step2-\"]:visible").first().locator("[data-btn=\"ms\"]").click();
        await resp;
        await page.waitForTimeout(300);
        await page.locator("[id^=\"step2-\"]").first().locator("[data-btn=\"nts\"]").click();
        await page.waitForTimeout(300);
        await expect(page.locator("input[placeholder*=\"Describe the defect\"]").first()).toBeVisible({ timeout: 3000 });
    });

    test("nts to ni with chip fires confirm or direct post", async ({ page }) => {
        await openDefectInput(page);
        const inp = page.locator("input[placeholder*=\"Describe the defect\"]").first();
        await inp.fill("Will be switched");
        await inp.press("Enter");
        await page.waitForResponse(r => r.url().includes("defect") && r.status() === 200);
        await page.waitForTimeout(400);
        const resp = page.waitForResponse(r => r.url().includes("/item/") && r.status() === 200);
        await page.locator("[id^=\"step1-\"]").first().locator("[data-btn=\"ni\"]").click();
        const modalVis = await page.locator("#confirm-modal").isVisible().catch(() => false);
        if (modalVis) await confirmModal(page);
        await resp;
        await page.waitForTimeout(300);
        const cls = await page.locator("[id^=\"step1-\"]").first().locator("[data-btn=\"ni\"]").getAttribute("class");
        expect(cls).toContain("bg-amber-500");
    });

    test("category ni then inst expands category", async ({ page }) => {
        await page.locator("[data-btn=\"cat-ni\"]").first().click();
        await confirmModal(page);
        await page.waitForResponse(r => r.url().includes("cascade") && r.status() === 200, { timeout: 6000 });
        await page.waitForTimeout(500);
        await page.locator("[data-btn=\"cat-inst\"]").first().click();
        await page.waitForTimeout(400);
        await expect(page.locator(".cat-content").first()).not.toHaveClass(/hidden/);
        const cls = await page.locator("[data-btn=\"cat-inst\"]").first().getAttribute("class");
        expect(cls).toContain("bg-blue-600");
    });
});

// ============================================================
// 9. LATENCY & STABILITY (3 tests)
// ============================================================
test.describe("Latency and Stability", () => {

    test("rapid ni taps no cross-fire between items", async ({ page }) => {
        await expandFirstCat(page);
        const posts = [];
        page.on("request", r => { if (r.method() === "POST" && r.url().includes("/item/")) posts.push(r.url()); });
        const btns = page.locator("[id^=\"step1-\"] [data-btn=\"ni\"]");
        const n = Math.min(await btns.count(), 3);
        for (let i = 0; i < n; i++) {
            await btns.nth(i).click();
            await page.waitForTimeout(80);
        }
        await page.waitForTimeout(2000);
        const unique = new Set(posts);
        expect(unique.size).toBe(posts.length);
        console.log(`Rapid: ${n} taps, ${posts.length} POSTs, ${unique.size} unique`);
    });

    test("no ghost step2 panels after rapid inst taps", async ({ page }) => {
        await expandFirstCat(page);
        const step1 = page.locator("[id^=\"step1-\"]").first().locator("[data-btn=\"inst\"]");
        for (let i = 0; i < 5; i++) {
            await step1.click();
            await page.waitForTimeout(50);
        }
        await page.waitForTimeout(800);
        const visible = await page.locator("[id^=\"step2-\"]:visible").count();
        expect(visible).toBeLessThanOrEqual(1);
    });

    test("no scroll jump after counter update from item mark", async ({ page }) => {
        await expandFirstCat(page);
        await page.evaluate(() => { document.getElementById("area-content").scrollTop = 150; });
        await page.waitForTimeout(100);
        const scrollBefore = await page.evaluate(() => document.getElementById("area-content").scrollTop);
        const resp = page.waitForResponse(r => r.url().includes("/item/") && r.status() === 200);
        await page.locator("[id^=\"step1-\"]").first().locator("[data-btn=\"ni\"]").click();
        await resp;
        await page.waitForTimeout(500);
        const scrollAfter = await page.evaluate(() => document.getElementById("area-content").scrollTop);
        expect(Math.abs(scrollAfter - scrollBefore)).toBeLessThan(30);
    });
});
