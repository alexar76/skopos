"""Activate a Streamlit tab from agent navigation (``?tab=`` / sessionStorage)."""

from __future__ import annotations

import json

import streamlit.components.v1 as components


def inject_tab_deeplink(tab_keys: list[str] | tuple[str, ...]) -> None:
    """After ``st.tabs(...)``, activate the tab named in ``skoposDesiredTab`` or ``?tab=``.

    Tab keys must be stable English tokens (not translated labels), in the same
    order as the ``st.tabs`` call.
    """
    keys = [str(k).strip().lower() for k in tab_keys if str(k).strip()]
    if not keys:
        return
    payload = json.dumps(keys)
    components.html(
        f"""
<script>
(function () {{
  var keys = {payload};
  var root;
  try {{ root = window.parent || window; }} catch (e) {{ return; }}
  if (!root || !root.document) return;
  var desired = null;
  try {{
    var u = new URL(root.location.href);
    desired = (u.searchParams.get('tab') || '').toLowerCase();
  }} catch (e) {{}}
  try {{
    if (!desired) desired = (root.sessionStorage.getItem('skoposDesiredTab') || '').toLowerCase();
    root.sessionStorage.removeItem('skoposDesiredTab');
  }} catch (e) {{}}
  if (!desired) return;
  var idx = keys.indexOf(desired);
  if (idx < 0) return;
  function clickTab() {{
    var tabs = root.document.querySelectorAll(
      'div[data-testid="stTabs"] button[role="tab"], button[data-baseweb="tab"]'
    );
    if (!tabs || !tabs.length) return false;
    // Prefer the first tab group on the page (main content).
    if (tabs[idx]) {{
      tabs[idx].click();
      return true;
    }}
    return false;
  }}
  clickTab();
  root.setTimeout(clickTab, 250);
  root.setTimeout(clickTab, 900);
}})();
</script>
""",
        height=0,
    )
