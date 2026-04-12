import { pathToFileURL } from "node:url";

const url = process.argv[2];
const playwrightModulePath = process.argv[3];
const rawRenderOptions = process.argv[4];

if (!url || !playwrightModulePath) {
  console.error("Usage: node scripts/render_page_with_playwright.mjs <url> <playwright-module-path> [render-options-json]");
  process.exit(1);
}

const renderOptions = rawRenderOptions ? JSON.parse(rawRenderOptions) : {};

const { chromium } = await import(pathToFileURL(playwrightModulePath).href);

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({
  viewport: { width: 1440, height: 2200 },
});

async function settlePage() {
  try {
    await page.waitForLoadState("networkidle", { timeout: 10000 });
  } catch {
    // Some sites keep background requests open indefinitely.
  }
  await page.waitForTimeout(2500);
}

async function scrollInstagramProfile(options) {
  const maxScrolls = Number.isInteger(options.max_scrolls) ? options.max_scrolls : 8;
  let stableIterations = 0;
  let previousCount = 0;

  for (let iteration = 0; iteration < maxScrolls; iteration += 1) {
    const currentCount = await page.evaluate(() => {
      return new Set(
        Array.from(document.querySelectorAll('a[href*="/p/"], a[href*="/reel/"]'))
          .map((node) => node.getAttribute("href"))
          .filter(Boolean),
      ).size;
    });

    if (currentCount <= previousCount) {
      stableIterations += 1;
      if (stableIterations >= 2) {
        break;
      }
    } else {
      stableIterations = 0;
      previousCount = currentCount;
    }

    await page.evaluate(() => {
      window.scrollBy(0, window.innerHeight * 1.5);
    });
    await page.waitForTimeout(1500);
  }
}

async function snapshot() {
  return {
    final_url: page.url(),
    title: await page.title(),
    content_type: "text/html; charset=utf-8",
    html: await page.content(),
  };
}

function looksLikeNetlify404(payload) {
  return (
    payload.title === "Page not found" &&
    payload.html.includes("Netlify") &&
    payload.html.includes("broken link")
  );
}

try {
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
  await settlePage();

  let payload = await snapshot();

  const target = new URL(url);
  if (looksLikeNetlify404(payload) && target.pathname !== "/") {
    await page.goto(target.origin, { waitUntil: "domcontentloaded", timeout: 60000 });
    await settlePage();
    let clicked = false;
    const routeLinks = page.locator(`a[href="${target.pathname}"]`);
    const routeLinkCount = await routeLinks.count();
    for (let index = 0; index < routeLinkCount; index += 1) {
      const candidate = routeLinks.nth(index);
      if (await candidate.isVisible()) {
        await candidate.click();
        clicked = true;
        break;
      }
    }
    if (!clicked) {
      await page.evaluate((nextPath) => {
        window.history.pushState({}, "", nextPath);
        window.dispatchEvent(new PopStateEvent("popstate"));
      }, `${target.pathname}${target.search}${target.hash}`);
    }
    try {
      await page.waitForURL((currentUrl) => new URL(currentUrl).pathname === target.pathname, {
        timeout: 5000,
      });
    } catch {
      // Fall through and capture whatever the app rendered.
    }
    await settlePage();
    payload = await snapshot();
  }

  if (renderOptions.scroll_profile) {
    await scrollInstagramProfile(renderOptions);
    await settlePage();
    payload = await snapshot();
  }

  process.stdout.write(JSON.stringify(payload));
} finally {
  await browser.close();
}
