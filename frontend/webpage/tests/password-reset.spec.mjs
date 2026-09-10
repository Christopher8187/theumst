import { expect, test } from "@playwright/test";

const messages = {
  en: {
    mismatch: "The passwords do not match.",
    success: "Your password has been updated. You can now log in.",
    invalid: "This reset link is invalid or has expired."
  },
  zh: {
    mismatch: "两次输入的密码不一致。",
    success: "密码已更新。现在可以登录。",
    invalid: "此重置链接无效或已过期。"
  },
  ja: {
    mismatch: "パスワードが一致しません。",
    success: "パスワードを更新しました。ログインできます。",
    invalid: "このリセットリンクは無効か、有効期限が切れています。"
  }
};

for (const [language, copy] of Object.entries(messages)) {
  for (const scenario of ["mismatch", "success", "invalid"]) {
    test(`${language}: password reset ${scenario}`, async ({ page }) => {
      const errors = [];
      const requests = [];
      page.on("pageerror", error => errors.push(error.message));
      page.on("console", message => {
        if (message.type() === "error" && message.text().includes("tr is not defined")) {
          errors.push(message.text());
        }
      });
      await page.addInitScript(value => localStorage.setItem("language", value), language);
      await page.route("**/api/me", route => route.fulfill({ json: { user: null } }));
      await page.route("**/auth/reset-password", async route => {
        requests.push({ method: route.request().method(), body: route.request().postDataJSON() });
        // Simulate server outcomes without delivering mail or changing an account.
        await route.fulfill({ status: scenario === "invalid" ? 400 : 200, json: {} });
      });
      await page.goto("/reset-password?token=ui-regression-not-a-real-token");
      await expect(page).toHaveURL(/\/reset-password$/);
      const fields = page.locator("input[type=password]");
      await fields.nth(0).fill("test-only-password-A");
      await fields.nth(1).fill(scenario === "mismatch" ? "test-only-password-B" : "test-only-password-A");
      await page.locator("form button[type=submit]").click();

      await expect(page.locator(".login-status")).toHaveText(copy[scenario]);
      await expect(page.locator(".login-status")).toHaveClass(scenario === "success" ? /is-success/ : /is-error/);
      await expect(page.locator("form")).toHaveCount(scenario === "success" ? 0 : 1);
      expect(errors).toEqual([]);
      expect(requests).toEqual(scenario === "mismatch" ? [] : [{
        method: "POST",
        body: { token: "ui-regression-not-a-real-token", new_password: "test-only-password-A" }
      }]);
    });
  }
}
