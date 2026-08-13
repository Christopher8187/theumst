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
