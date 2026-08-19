from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_team_contains_chris_randall_and_tina():
    about = (ROOT / "frontend/webpage/src/pages/AboutPage.vue").read_text(encoding="utf-8")
    assert '{ id: "chris"' in about
    assert '{ id: "randall"' in about
    assert '{ id: "tina"' in about
    for removed in ("penny", "kiki", "lawrence"):
        assert f'id: "{removed}"' not in about
    translations = (ROOT / "frontend/webpage/src/utils/language.js").read_text(encoding="utf-8")
    assert '"team.randall.role": "Strategy Advisor"' in translations
    assert '"team.tina.role": "Social Media Advisor"' in translations


def test_admin_and_superadmin_tools_are_separated():
    admin = (ROOT / "frontend/dashboard/src/pages/AdminPage.vue").read_text(encoding="utf-8")
    superadmin = (ROOT / "frontend/dashboard/src/pages/SuperadminPage.vue").read_text(encoding="utf-8")
    assert "Qdrant search" in admin or "qdrantTitle" in admin
    assert "sql-box" not in admin
    assert "sql-box" in superadmin


def test_demo_navigation_and_search_indexing_policy():
    header = (ROOT / "frontend/webpage/src/components/SiteHeader.vue").read_text(encoding="utf-8")
    index = (ROOT / "frontend/webpage/index.html").read_text(encoding="utf-8")
    frontend = (ROOT / "backend/python/app/routers/frontend.py").read_text(encoding="utf-8")
    assert '["/demo", "nav.demo", "demo"]' in header
    assert "dashboardUrl('/dashboard/demo/')" in header
    assert "<title>The Ultimate Mega Study Tool</title>" in index
    assert '<link rel="canonical" href="https://theumst.com/"' in index
    assert '@router.get("/sitemap.xml")' in frontend
    assert "Disallow: /demo/" in frontend


def test_dashboard_hides_internal_privileged_role_names_from_visible_copy():
    translations = (ROOT / "frontend/dashboard/src/utils/i18n.js").read_text(encoding="utf-8")
    profile = (ROOT / "frontend/dashboard/src/pages/ProfilePage.vue").read_text(encoding="utf-8")
    demo = (ROOT / "frontend/dashboard/src/pages/DemoPage.vue").read_text(encoding="utf-8")
    assert 'roleAdmin: "Admin"' not in translations
    assert 'roleSuperadmin: "Superadmin"' not in translations
    assert "Admins and superadmins" not in translations
    assert "An admin or superadmin" not in translations
    assert 'admin: "roleAdmin"' not in profile
    assert "access.authority" not in demo


def test_demo_visibility_users_and_email_confirmation_ui_are_present():
    books = (ROOT / "frontend/dashboard/src/pages/BooksPage.vue").read_text(encoding="utf-8")
    users = (ROOT / "frontend/dashboard/src/pages/UsersPage.vue").read_text(encoding="utf-8")
    app = (ROOT / "frontend/webpage/src/App.vue").read_text(encoding="utf-8")
    privacy = (ROOT / "frontend/webpage/src/pages/PrivacyPage.vue").read_text(encoding="utf-8")
    assert "demo_enabled" in books
    assert "active_api_keys" in users
    assert "VerifyEmailPage" in app
    assert "Email-confirmation links expire after 24 hours" in privacy
    profile = (ROOT / "frontend/dashboard/src/pages/ProfilePage.vue").read_text(encoding="utf-8")
    assert 'type="email" readonly' in profile
    assert 'autocomplete="current-password"' in profile
