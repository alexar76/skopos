from __future__ import annotations

from skopos.doc_i18n import DOC_LOCALE_CODES, screenshot_locale_for_doc
from skopos.docs_viewer import DOCS_ROOT, _read_doc, _resolve_image_path


def test_read_doc_en_index():
    body = _read_doc("en", "index")
    assert "SKOPOS" in body
    assert "nginx" in body.lower()


def test_read_doc_ru_nginx():
    body = _read_doc("ru", "nginx")
    assert "nginx" in body.lower()


def test_read_doc_zh_exists():
    body = _read_doc("zh", "index")
    assert "SKOPOS" in body


def test_all_doc_locales_have_guides():
    for code in DOC_LOCALE_CODES:
        for slug in ("index", "deployment", "configuration", "usage", "nginx"):
            path = DOCS_ROOT / code / "guide" / f"{slug}.md"
            assert path.is_file(), f"missing {path}"


def test_screenshot_locale_mapping():
    assert screenshot_locale_for_doc("ru") == "ru"
    assert screenshot_locale_for_doc("es") == "es"
    assert screenshot_locale_for_doc("en") == "en"
    assert screenshot_locale_for_doc("zh") == "en"


def test_docs_screenshots_exist():
    assert (DOCS_ROOT / "screenshots" / "en" / "analytics-premium.png").is_file()
    assert (DOCS_ROOT / "screenshots" / "es" / "analytics-premium.png").is_file()
    assert (DOCS_ROOT / "screenshots" / "ru" / "security-summary-report.png").is_file()


def test_resolve_image_path_uses_locale_folder():
    path = _resolve_image_path("screenshots/analytics-premium.png", doc_locale="ru")
    assert path is not None
    assert "/screenshots/ru/" in str(path).replace("\\", "/")


def test_show_doc_image_picks_supported_width_kw(monkeypatch):
    from skopos import docs_viewer

    calls: list[dict] = []

    def fake_image(path, **kwargs):
        calls.append({"path": path, **kwargs})

    monkeypatch.setattr(docs_viewer.st, "image", fake_image)
    docs_viewer._show_doc_image(
        DOCS_ROOT / "screenshots" / "en" / "analytics-premium.png",
        caption="test",
    )
    assert calls
    assert isinstance(calls[0]["path"], (bytes, bytearray))
    assert len(calls[0]["path"]) > 1000
    assert calls[0]["caption"] == "test"
    assert "use_container_width" in calls[0] or "use_column_width" in calls[0] or len(calls[0]) == 2
