import { expect, test } from "@playwright/test";

// S: simulated API responses exercise the real desktop components and scene.
// These checks do not establish backend authorization, delivery, or persistence.
const preferencesKey = "theumst.magical-lofi.preferences.v1";
const windowFor = (page, name) => page.locator(`.window[data-page="${name}"]`);
const dockFor = (page, name) => page.locator(`.dock-item[data-page="${name}"]`);

async function simulatedServices(page, { signedIn = true, subscribed = false } = {}) {
  let authenticated = signedIn;
  let news = subscribed;
  const loginRequests = [];
  const subscriptionWrites = [];
  const unexpected = [];
  const user = {
    user_id: 801, username: "test_reader", alias: "Test reader", description: "",
    email: "reader@example.invalid", email_verified: true,
    authority_type: "user", access_points: ["profile", "api-keys"]
  };
  await page.route("**/api/**", async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/me") {
      return route.fulfill({ status: authenticated ? 200 : 401, json: authenticated ? { user } : { detail: "Sign in" } });
    }
    if (path === "/api/me/subscriptions") {
      if (request.method() === "PUT") {
        const payload = request.postDataJSON();
        subscriptionWrites.push(payload);
        news = payload.news;
      }
      return route.fulfill({ json: {
        news, status: news ? "active" : "off", email: user.email,
        consent_at: news ? "2026-09-11T10:00:00Z" : null,
        consent_source: news ? "profile" : null, confirmed_at: news ? "2026-09-11T10:00:00Z" : null
      } });
    }
    if (path === "/api/news") return route.fulfill({ json: { posts: [] } });
    if (path === "/api/api-keys") return route.fulfill({ json: { keys: [] } });
    if (path === "/api/demo/access") return route.fulfill({ json: { can_enter: false, can_review: false, account_type: "user", request: null } });
    unexpected.push(`${request.method()} ${path}`);
    return route.fulfill({ status: 404, json: { detail: "No simulated response for this request" } });
  });
  await page.route("**/auth/**", async route => {
    const request = route.request();
    if (new URL(request.url()).pathname !== "/auth/login") {
      unexpected.push(`${request.method()} ${request.url()}`);
      return route.fulfill({ status: 404, json: {} });
    }
    const type = request.headers()["content-type"];
    const fields = Object.fromEntries(await new Response(request.postDataBuffer(), { headers: { "content-type": type } }).formData());
    loginRequests.push({ method: request.method(), type, fields });
    authenticated = true;
    if (fields.news_opt_in === "on") news = true;
    return route.fulfill({ json: { ok: true, user } });
  });
  // Avoid depending on a separate image server for account forms in this suite.
  await page.route("**/images/**", route => route.fulfill({
    contentType: "image/png",
    body: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLbtAAAAABJRU5ErkJggg==", "base64")
  }));
  return { loginRequests, subscriptionWrites, unexpected };
}

async function accountPosition(page) {
  return page.locator(".account-button").evaluate(button => {
    const rect = button.getBoundingClientRect();
    const style = getComputedStyle(button);
    return {
      top: rect.top, right: innerWidth - rect.right,
      color: style.backgroundColor, token: style.getPropertyValue("--control").trim(),
      headerPosition: getComputedStyle(button.closest(".topbar")).position
    };
  });
}

function rgb(hex) {
  const clean = hex.replace("#", "");
  const full = clean.length === 3 ? [...clean].map(part => part + part).join("") : clean;
  return `rgb(${[0, 2, 4].map(offset => Number.parseInt(full.slice(offset, offset + 2), 16)).join(", ")})`;
}

test.describe("S: shared desktop regression", () => {
  test.use({ reducedMotion: "reduce" });
  test.beforeEach(async ({ page }, testInfo) => {
    testInfo.annotations.push({ type: "evidence", description: "S: simulated API; real Vue UI, browser layout and scene renderer" });
    await page.addInitScript(() => localStorage.setItem("language", "en"));
  });

  for (const signedIn of [false, true]) {
    test(`dock toggles each destination twice for a ${signedIn ? "signed-in" : "guest"} visit`, async ({ page }) => {
      const service = await simulatedServices(page, { signedIn });
      await page.goto("/");
      await expect(page.locator(".account-button")).toContainText(signedIn ? "Your profile" : "Login");
      const destinations = ["home", "about", "news", "wiki", "demo", ...(!signedIn ? ["login"] : []), "get", "settings"];
      await expect(page.locator(".dock-item")).toHaveCount(destinations.length);
      await expect(page.locator('.dock-item[data-page="profile"]')).toHaveCount(0);
      await expect(page.getByRole("button", { name: /^(?:A|B|C)(?:\s*[·—–-]|$)/ })).toHaveCount(0);
      await expect(page.locator(".sample-control, .comparison-bar, .variant-switcher")).toHaveCount(0);
      await expect(page.locator('link[rel="icon"]')).toHaveAttribute("href", /logo-clear.*\.svg/);
      for (const destination of destinations) {
        const startsOpen = destination === "home";
        for (let cycle = 0; cycle < 2; cycle += 1) {
          await dockFor(page, destination).click();
          await expect(dockFor(page, destination)).toHaveAttribute("aria-pressed", String(!startsOpen));
          if (startsOpen) await expect(windowFor(page, destination)).toBeHidden();
          else await expect(windowFor(page, destination)).toBeVisible();
          await dockFor(page, destination).click();
          await expect(dockFor(page, destination)).toHaveAttribute("aria-pressed", String(startsOpen));
          if (startsOpen) await expect(windowFor(page, destination)).toBeVisible();
          else await expect(windowFor(page, destination)).toBeHidden();
        }
      }
      expect(service.unexpected).toEqual([]);
    });
  }

  for (const viewport of [{ width: 1280, height: 900 }, { width: 390, height: 844 }]) {
    test(`Profile tabs are adjacent, keyboard accessible, and reopen on Details at ${viewport.width}px`, async ({ page }) => {
      await page.setViewportSize(viewport);
      const service = await simulatedServices(page);
      await page.goto("/");
      await page.getByRole("button", { name: "Your profile", exact: true }).click();
      const profile = windowFor(page, "profile");
      const details = profile.getByRole("tab", { name: "Details", exact: true });
      const subscriptions = profile.getByRole("tab", { name: "Subscriptions", exact: true });
      await expect(details).toHaveAttribute("aria-selected", "true");
      const [left, right] = await Promise.all([details.boundingBox(), subscriptions.boundingBox()]);
      expect(Math.abs(left.y - right.y)).toBeLessThan(2);
      expect(right.x).toBeGreaterThanOrEqual(left.x + left.width - 1);
      expect(right.x - left.x - left.width).toBeLessThan(15);
      await details.focus();
      await details.press("ArrowRight");
      await expect(subscriptions).toBeFocused();
      await expect(subscriptions).toHaveAttribute("aria-selected", "true");
      await expect(profile.getByRole("checkbox")).not.toBeChecked();
      await profile.getByRole("button", { name: "Close Profile", exact: true }).click();
      await expect(profile).toBeHidden();
      await page.getByRole("button", { name: "Your profile", exact: true }).click();
      await expect(details).toHaveAttribute("aria-selected", "true");
      await expect(subscriptions).toHaveAttribute("aria-selected", "false");
      expect(service.subscriptionWrites).toEqual([]);
      expect(service.unexpected).toEqual([]);
    });

    test(`palette survives reload and colors the fixed account control at ${viewport.width}px`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await simulatedServices(page);
      await page.goto("/");
      await expect(page.locator(".account-button")).toContainText("Your profile");
      const original = await accountPosition(page);
      const noteColors = () => page.locator('.field-note').evaluate(note => {
        const style = getComputedStyle(note);
        return [style.backgroundColor, style.color, style.borderColor];
      });
      const originalNote = await noteColors();
      expect(original.headerPosition).toBe("fixed");
      expect(original.top).toBeGreaterThanOrEqual(8);
      expect(original.top).toBeLessThanOrEqual(24);
      expect(original.right).toBeGreaterThanOrEqual(8);
      expect(original.right).toBeLessThanOrEqual(32);
      await dockFor(page, "settings").click();
      const colors = page.getByRole("combobox", { name: "Colors", exact: true });
      await expect(colors).toHaveValue("paper");
      await colors.selectOption("blue");
      await expect(page.locator("html")).toHaveAttribute("data-palette", "blue");
      const blue = await accountPosition(page);
      expect(blue.color).toBe(rgb(blue.token));
      expect(blue.color).not.toBe(original.color);
      expect(await noteColors()).toEqual(originalNote);
      expect(Math.abs(blue.right - original.right)).toBeLessThan(1);
      expect(Math.abs(blue.top - original.top)).toBeLessThan(1);
      await page.reload();
      await expect(page.locator("html")).toHaveAttribute("data-palette", "blue");
      await dockFor(page, "settings").click();
      await expect(colors).toHaveValue("blue");
      expect((await accountPosition(page)).color).toBe(blue.color);
      expect(await noteColors()).toEqual(originalNote);
      await page.setViewportSize({ width: viewport.width + 70, height: viewport.height });
      expect(Math.abs((await accountPosition(page)).right - blue.right)).toBeLessThan(1);
      await colors.selectOption("paper");
      expect((await accountPosition(page)).color).toBe(original.color);
    });
  }

  for (const scenario of [
    { checked: false, subscribed: false, name: "unchecked new consent" },
    { checked: true, subscribed: false, name: "checked new consent" },
    { checked: false, subscribed: true, name: "unchecked with prior consent" }
  ]) {
    test(`login sends only the chosen opt-in and keeps prior consent: ${scenario.name}`, async ({ page }) => {
      const service = await simulatedServices(page, { signedIn: false, subscribed: scenario.subscribed });
      await page.goto("/login");
      const login = windowFor(page, "login");
      const optIn = login.locator('input[name="news_opt_in"]');
      await expect(optIn).not.toBeChecked();
      await login.getByLabel("Username", { exact: true }).fill("test_reader");
      await login.getByLabel("Password", { exact: true }).fill("simulated-only-password");
      if (scenario.checked) await optIn.check();
      await login.getByRole("button", { name: "Log In", exact: true }).click();
      await expect(windowFor(page, "profile")).toBeVisible();
      expect(service.loginRequests).toHaveLength(1);
      expect(service.loginRequests[0].method).toBe("POST");
      expect(service.loginRequests[0].type).toContain("multipart/form-data;");
      expect(service.loginRequests[0].fields).toEqual({
        username: "test_reader", password: "simulated-only-password", ...(scenario.checked ? { news_opt_in: "on" } : {})
      });
      await windowFor(page, "profile").getByRole("tab", { name: "Subscriptions", exact: true }).click();
      const selected = windowFor(page, "profile").getByRole("checkbox");
      if (scenario.checked || scenario.subscribed) await expect(selected).toBeChecked();
      else await expect(selected).not.toBeChecked();
      expect(service.subscriptionWrites).toEqual([]);
      expect(service.unexpected).toEqual([]);
    });
  }

  test("scene keeps rotating through window interactions and stops only at Pause", async ({ page }) => {
    test.setTimeout(60000);
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.emulateMedia({ reducedMotion: "no-preference" });
    await page.addInitScript(key => {
      localStorage.setItem(key, JSON.stringify({ scene: { speed: 2, dust: 0, pixel: 0, quality: 1, auto: true } }));
    }, preferencesKey);
    await simulatedServices(page);
    await page.goto("/");
    await expect(page.locator("#scene")).toHaveAttribute("data-loaded", "true", { timeout: 20000 });
    const heading = page.locator("#heading");
    const number = async () => Number.parseInt(await heading.innerText(), 10);
    const advances = async () => {
      const start = await number();
      await expect.poll(async () => ((await number()) - start + 360) % 360, { timeout: 12000 }).toBeGreaterThanOrEqual(2);
      await expect(page.getByRole("button", { name: "Pause slow rotation", exact: true })).toBeVisible();
    };
    await advances();
    await dockFor(page, "about").click();
    await expect(windowFor(page, "about")).toBeVisible();
    await advances();
    await windowFor(page, "about").getByRole("button", { name: "Close About", exact: true }).click();
    await page.getByRole("button", { name: "Your profile", exact: true }).click();
    await windowFor(page, "profile").getByRole("tab", { name: "Subscriptions", exact: true }).click();
    await advances();
    await page.getByRole("button", { name: "Pause slow rotation", exact: true }).click();
    await expect(page.getByRole("button", { name: "Resume slow rotation", exact: true })).toBeVisible();
    const paused = await heading.innerText();
    // At 2 degrees/sec this interval distinguishes a stopped scene from rounded text.
    await page.waitForTimeout(1800);
    expect(await heading.innerText()).toBe(paused);
    await page.getByRole("button", { name: "Resume slow rotation", exact: true }).click();
    await advances();
  });
});
