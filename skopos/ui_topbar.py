"""Fixed top application bar — docs & quick links in the header zone."""

from __future__ import annotations

import html

import streamlit as st

from skopos.i18n import t
from skopos.themes import get_active_theme

# Compact header row (Running… + left-aligned nav).
_BAR_H = "2.125rem"
_CONTENT_MAX = "1400px"
_TOP_GAP = "16px"


def _app_base() -> str:
    """Streamlit subpath when served behind nginx at /app/."""
    try:
        base = st.get_option("server.baseUrlPath") or ""
    except Exception:
        import os

        base = os.environ.get("STREAMLIT_SERVER_BASE_URL_PATH", "")
    base = str(base).strip().strip("/")
    return f"/{base}" if base else ""


def _page_href(script_path: str) -> str:
    """Best-effort Streamlit multipage URL slug."""
    base = _app_base()
    name = script_path.replace("\\", "/").split("/")[-1]
    if name == "dashboard.py":
        return f"{base}/" if base else "/"
    if name.endswith(".py"):
        slug = name.replace(".py", "").split("_", 1)[-1]
        return f"{base}/{slug}" if base else f"/{slug}"
    slug = name
    return f"{base}/{slug}" if base else f"/{slug}"


def build_topbar_css(theme) -> str:
    th = theme
    cosmic = theme.id == "midnight"
    link_bg = "rgba(18,12,22,0.72)" if cosmic else f"color-mix(in srgb, {th.card_bg} 82%, transparent)"
    link_border = "rgba(255,160,80,0.22)" if cosmic else th.border
    link_shadow = "0 4px 18px rgba(0,0,0,0.35)" if cosmic else "0 2px 10px rgba(0,0,0,0.08)"
    link_hover_shadow = "0 8px 28px rgba(255,140,42,0.22)" if cosmic else "0 6px 20px rgba(0,0,0,0.12)"
    return f"""
<style id="skopos-topbar">
  :root {{
    --skopos-header-height: {_BAR_H};
    --sidebar-width: var(--skopos-sidebar-expanded-width, 17rem);
  }}
  section[data-testid="stSidebar"] {{
    z-index: 999993 !important;
    position: relative !important;
  }}
  /* No Streamlit header strip — transparent shell only */
  header[data-testid="stHeader"] {{
    display: none !important;
    height: 0 !important;
    min-height: 0 !important;
    max-height: 0 !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    overflow: hidden !important;
  }}
  [data-testid="stDecoration"] {{
    display: none !important;
  }}
  [data-testid="stToolbar"] {{
    display: flex !important;
    align-items: center !important;
    justify-content: flex-end !important;
    position: fixed !important;
    top: {_TOP_GAP} !important;
    right: 1rem !important;
    left: auto !important;
    height: auto !important;
    width: auto !important;
    max-width: 9rem !important;
    margin: 0 !important;
    padding: 0 !important;
    background: transparent !important;
    z-index: 999992 !important;
    pointer-events: auto !important;
  }}
  [data-testid="stToolbarActions"],
  [data-testid="stMainMenu"],
  #MainMenu {{
    display: none !important;
  }}
  [data-testid="stStatusWidget"],
  [data-testid="stConnectionStatus"] {{
    background: {link_bg} !important;
    color: {th.text} !important;
    border: 1px solid {link_border} !important;
    border-radius: 999px !important;
    padding: 0.12rem 0.45rem !important;
    font-size: 0.72rem !important;
    line-height: 1.2 !important;
    backdrop-filter: blur(14px) saturate(1.1) !important;
    -webkit-backdrop-filter: blur(14px) saturate(1.1) !important;
    box-shadow: {link_shadow} !important;
    max-width: 100% !important;
  }}
  [data-testid="stStatusWidget"] label,
  [data-testid="stStatusWidget"] span,
  [data-testid="stStatusWidget"] p,
  [data-testid="stStatusWidget"] div,
  [data-testid="stConnectionStatus"] label,
  [data-testid="stConnectionStatus"] span {{
    color: {th.text} !important;
  }}
  [data-testid="stStatusWidget"] button,
  [data-testid="stConnectionStatus"] button {{
    background: transparent !important;
    color: {th.text_muted} !important;
    border-color: {link_border} !important;
  }}
  .skopos-topbar {{
    position: fixed;
    top: {_TOP_GAP};
    left: var(--sidebar-width, 17rem);
    right: 0;
    height: var(--skopos-header-height);
    z-index: 999991;
    display: flex;
    align-items: center;
    justify-content: flex-start;
    box-sizing: border-box;
    padding: 0 1rem;
    pointer-events: none;
    background: transparent;
  }}
  .skopos-topbar-inner {{
    width: 100%;
    max-width: {_CONTENT_MAX};
    margin: 0;
    display: flex;
    align-items: center;
    justify-content: flex-start;
    box-sizing: border-box;
    padding: 0 1rem;
  }}
  .skopos-topbar-nav {{
    display: inline-flex;
    align-items: center;
    justify-content: flex-start;
    flex-wrap: nowrap;
    gap: 0.35rem;
    pointer-events: auto;
    max-width: 100%;
  }}
  .skopos-topbar-link {{
    display: inline-flex;
    align-items: center;
    gap: 0.28rem;
    padding: 0.32rem 0.72rem;
    border-radius: 999px;
    font-family: 'Outfit', system-ui, sans-serif;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-decoration: none !important;
    color: {th.text} !important;
    border: 1px solid {link_border};
    background: {link_bg};
    backdrop-filter: blur(14px) saturate(1.1);
    -webkit-backdrop-filter: blur(14px) saturate(1.1);
    box-shadow: {link_shadow};
    transition: background 0.18s ease, border-color 0.18s ease, color 0.18s ease, box-shadow 0.22s ease, transform 0.15s ease;
    white-space: nowrap;
  }}
  .skopos-topbar-link:hover {{
    color: {th.accent} !important;
    border-color: color-mix(in srgb, {th.accent} 55%, transparent);
    background: color-mix(in srgb, {th.accent} 14%, {link_bg});
    box-shadow: {link_hover_shadow};
    transform: translateY(-1px);
  }}
  .skopos-topbar-link.is-active {{
    color: {th.accent} !important;
    border-color: color-mix(in srgb, {th.accent} 65%, transparent);
    background: color-mix(in srgb, {th.accent} 18%, {link_bg});
    box-shadow: 0 0 24px color-mix(in srgb, {th.accent} 35%, transparent), {link_shadow};
  }}
  .skopos-topbar-link .material-symbols-outlined {{
    font-size: 0.95rem;
    line-height: 1;
  }}
  [data-testid="stAppViewContainer"] > section.main {{
    padding-top: calc({_TOP_GAP} + var(--skopos-header-height) + {_TOP_GAP}) !important;
  }}
  @media (max-width: 768px) {{
    .skopos-topbar {{
      left: 0;
      padding: 0 3.25rem 0 1rem;
    }}
    .skopos-topbar-inner {{
      padding: 0;
    }}
    [data-testid="stToolbar"] {{
      right: 0.35rem !important;
      max-width: 6.5rem !important;
    }}
    .skopos-topbar-link {{
      padding: 0.38rem 0.55rem;
      font-size: 0.78rem;
    }}
    .skopos-topbar-link span.label {{ display: none; }}
  }}
</style>
"""


_TOPBAR_DEDUPE_JS = """
<script id="skopos-topbar-dedupe">
(function () {
  function normPath(p) {
    if (!p) return "/";
    var u = p.split("?")[0].split("#")[0];
    if (!u.startsWith("/")) u = "/" + u;
    return u.replace(/\\/+$/, "") || "/";
  }
  function syncSidebarInset() {
    var sb = document.querySelector('section[data-testid="stSidebar"]');
    if (!sb) return;
    var w = sb.getBoundingClientRect().width;
    if (w > 32) {
      document.documentElement.style.setProperty("--sidebar-width", w + "px");
    }
  }
  function topbarNavigate(targetPath, e) {
    var norm = normPath(targetPath);
    var slug = norm.split("/").pop();
    var sidebarLinks = document.querySelectorAll(
      'section[data-testid="stSidebar"] [data-testid="stPageLink"] a'
    );
    for (var i = 0; i < sidebarLinks.length; i += 1) {
      var href = normPath(sidebarLinks[i].getAttribute("href") || "");
      var hrefSlug = href.split("/").pop();
      if (
        href === norm ||
        (norm !== "/" && href.endsWith(norm)) ||
        (slug && hrefSlug && slug === hrefSlug)
      ) {
        if (e) e.preventDefault();
        sidebarLinks[i].click();
        return true;
      }
    }
    return false;
  }
  function wireTopbarLinks() {
    document.querySelectorAll(".skopos-topbar-link").forEach(function (a) {
      if (a.dataset.skoposWired === "1") return;
      a.dataset.skoposWired = "1";
      a.addEventListener("click", function (e) {
        topbarNavigate(a.getAttribute("href") || "", e);
      });
    });
  }
  function dedupeTopbars() {
    var bars = document.querySelectorAll(".skopos-topbar");
    for (var i = 0; i < bars.length - 1; i += 1) {
      bars[i].remove();
    }
    syncSidebarInset();
    wireTopbarLinks();
  }
  dedupeTopbars();
  new MutationObserver(dedupeTopbars).observe(document.body, {
    childList: true,
    subtree: true,
  });
  window.addEventListener("resize", syncSidebarInset);
})();
</script>
"""


def render_topbar(*, locale: str, active: str | None = None) -> None:
    """Render fixed header links (docs, quick start, settings)."""
    links = (
        ("documentation", "pages/4_Documentation.py", "app.documentation", "menu_book"),
        ("quick_start", "pages/0_Quick_Start.py", "app.quick_start", "rocket_launch"),
        ("settings", "pages/2_Settings.py", "app.settings", "settings"),
    )
    parts = [
        '<div class="skopos-topbar" role="navigation" aria-label="SKOPOS">',
        '<div class="skopos-topbar-inner">',
        '<nav class="skopos-topbar-nav">',
    ]
    for slug, path, key, icon in links:
        href = _page_href(path)
        label = html.escape(t(key, locale))
        active_cls = " is-active" if active == slug else ""
        parts.append(
            f'<a class="skopos-topbar-link{active_cls}" href="{html.escape(href, quote=True)}">'
            f'<span class="material-symbols-outlined" aria-hidden="true">{icon}</span>'
            f'<span class="label">{label}</span></a>'
        )
    parts.append("</nav></div></div>")
    parts.append(_TOPBAR_DEDUPE_JS)
    st.markdown("".join(parts), unsafe_allow_html=True)
