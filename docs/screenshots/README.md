# Documentation screenshots

Screenshots are **locale-specific** (UI language of the capture):

| Folder | Used for doc languages |
|--------|-------------------------|
| `en/` | All except Russian and Spanish guides |
| `ru/` | Russian (`ru`) guides |
| `es/` | Spanish (`es`) guides |

Guides reference images as:

```markdown
![Caption](screenshots/analytics-premium.png)
```

The docs viewer resolves the folder automatically (`doc_locale` → `en` / `ru` / `es`, then fallback to `en/`).

## Bundled captures

| File | Description |
|------|-------------|
| `analytics-premium.png` | Analytics — Overview tab |
| `sidebar-nav.png` | Sidebar navigation and theme picker |
| `topbar-area.png` | Top header / menu area |
| `quick-start.png` | Quick Start wizard — Security & AI step |
| `ai-briefing-card.png` | AI Ecosystem briefing on Analytics |
| `security-summary-report.png` | Security → Summary Report with AI brief |
| `security-3d-map.png` | Security → 3D Threat Map |
| `settings-fleet.png` | Settings — fleet servers and save |
| `floating-agent.png` | Floating Security Agent chat panel |

### README assets

| Folder | Description |
|--------|-------------|
| `readme/` | Hero banner stitched from Analytics + Security 3D |
| `themes/` | Analytics page in each theme (`analytics-{light,premium,midnight,ocean,aurora,slate}.png`) |

Capture from production:

```bash
export SKOPOS_DASHBOARD_PASSWORD='…'
pip install playwright pillow && playwright install chromium
python scripts/capture_readme_screenshots.py --base-url https://skopos.modelmarket.dev/app/
```

Regenerate translated guides after editing strings:

```bash
python3 scripts/generate_skopos_i18n_docs.py
```
