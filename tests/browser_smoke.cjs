const assert = require("node:assert/strict");
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || process.argv[2] || "playwright");

(async function () {
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.PLAYWRIGHT_BROWSER_PATH || process.argv[3] || undefined,
  });
  const errors = [];
  const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error") console.error(message.text()); });
  await page.route("**/*", route => {
    const hostname = new URL(route.request().url()).hostname;
    return hostname === "127.0.0.1" || hostname === "localhost" ? route.continue() : route.abort();
  });
  const base = process.env.WORKBENCH_URL || "http://127.0.0.1:8765";
  try {
    await page.goto(base);
    assert.ok(await page.getByRole("link", {name: "Causal coding home"}).isVisible());
    assert.ok(await page.locator(".brand-signal").evaluate(element => element.complete && element.naturalWidth > 0));
    await page.locator(".topbar").screenshot({path: "/tmp/causal-coding-brand.png"});
    assert.equal(await page.locator(".node").count(), 4);
    assert.equal(await page.locator(".edge").count(), 3);
    assert.ok(await page.locator("#viewport").getAttribute("transform"));
    const initialScale = await page.locator("#zoom-level").textContent();
    await page.getByRole("button", {name: "Zoom in", exact: true}).click();
    assert.notEqual(await page.locator("#zoom-level").textContent(), initialScale);
    await page.getByRole("button", {name: "Fit to screen"}).click();
    await page.getByRole("button", {name: "Full model", exact: true}).click();
    await page.waitForFunction(() => document.querySelectorAll(".node").length === 70);
    await page.getByRole("searchbox").fill("agentic task share");
    await page.locator('[data-search-id="agentic_task_share"]').click();
    await page.waitForFunction(() => document.querySelector("#graph-panel").dataset.focus === "agentic_task_share");
    assert.equal(await page.locator("#graph-panel").getAttribute("data-view"), "neighborhood");
    await page.locator('.edge[data-id="K6"] .edge-hit').focus();
    await page.keyboard.press("Enter");
    await page.getByText("Peng et al.", {exact: false}).waitFor();
    assert.ok(await page.getByText("Becker et al.", {exact: false}).isVisible());
    assert.equal(await page.getByText("Estimable now", {exact: true}).count(), 0);
    await page.getByRole("button", {name: "Data sources"}).click();
    await page.locator("#sources-form").waitFor();
    await page.getByRole("button", {name: "Select all", exact: true}).click();
    assert.equal(await page.locator("#sources-form input:checked").count(), 13);
    await page.getByRole("button", {name: "Apply source preview"}).click();
    await page.waitForFunction(() => document.querySelector("#graph-panel").dataset.sources.includes("finance"));
    await page.getByRole("button", {name: "Clear all", exact: true}).click();
    await page.getByRole("button", {name: "Apply source preview"}).click();
    await page.waitForFunction(() => document.querySelector("#graph-panel").dataset.sources === "none");
    assert.equal(await page.locator("#sources-form input:checked").count(), 0);
    assert.match(await page.locator("#coverage-tag").textContent(), /Hypothetical source preview/);
    await page.reload();
    assert.equal(await page.locator("#graph-panel").getAttribute("data-sources"), "none");
    assert.equal(await page.locator("#graph-panel").getAttribute("data-focus"), "agentic_task_share");
    await page.getByRole("button", {name: "Data sources"}).click();
    await page.getByRole("button", {name: "Use live data", exact: true}).click();
    await page.waitForFunction(() => document.querySelector("#graph-panel").dataset.sources === "connected");
    await page.getByRole("button", {name: "Key pathways", exact: true}).click();
    await page.waitForFunction(() => document.querySelector("#graph-panel").dataset.view === "overview");
    await page.goBack();
    await page.waitForFunction(() => document.querySelector("#graph-panel").dataset.view === "neighborhood");
    await page.goto(base);
    const selected = page.locator('.node[data-id="revenue"]');
    await selected.focus();
    await page.keyboard.press("Enter");
    await page.waitForFunction(() => document.querySelector("#graph-panel").dataset.focus === "revenue");
    await page.locator('.node[data-id="revenue"]').waitFor();
    await page.screenshot({path: "/tmp/causal-coding-desktop.png", fullPage: true});
    await page.setViewportSize({width: 390, height: 844});
    await page.goto(base);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false);
    await page.getByRole("button", {name: "Data sources"}).click();
    await page.locator("#sources-form").waitFor();
    assert.ok(await page.locator("#inspector").evaluate(element => element.scrollHeight <= element.clientHeight + 1));
    await page.locator('#sources-form input[value="survey"]').check();
    await page.getByRole("button", {name: "Clear all", exact: true}).click();
    await page.getByRole("button", {name: "Apply source preview"}).click();
    await page.waitForFunction(() => document.querySelector("#graph-panel").dataset.sources === "none");
    assert.ok(await page.locator("#coverage-tag").isVisible());
    await page.screenshot({path: "/tmp/causal-coding-mobile.png", fullPage: true});
    await page.setViewportSize({width: 320, height: 740});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false);
    assert.ok(await page.getByRole("link", {name: "Causal coding home"}).isVisible());
    await page.setViewportSize({width: 390, height: 844});
    await page.route("**/graph?**", route => route.fulfill({status: 500, body: "Test failure"}));
    await page.getByRole("button", {name: "Full model", exact: true}).click();
    await page.locator("#request-error:not([hidden])").waitFor();
    assert.equal(await page.locator("#graph-panel").getAttribute("data-view"), "neighborhood");
    assert.deepEqual(errors, []);
    console.log("Browser checks passed: offline assets, views, search, evidence, source selection, history, keyboard, mobile and request errors.");
  } catch (error) {
    await page.screenshot({path: "/tmp/causal-coding-browser-failure.png", fullPage: true});
    console.error("Page errors:", errors);
    console.error("Current state:", await page.locator("#graph-panel").getAttribute("data-view"), "nodes:", await page.locator(".node").count());
    throw error;
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
