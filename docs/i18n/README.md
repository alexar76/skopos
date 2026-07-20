# SKOPOS documentation i18n (20 languages)

Aligned with [ARGUS user guides](../../../argus/docs/user-guide/README.md):  
`en`, `zh`, `es`, `hi`, `ar`, `pt`, `ru`, `ja`, `fr`, `de`, `ko`, `it`, `tr`, `id`, `vi`, `th`, `hr`, `sk`, `nl`, `fa`.

The **app UI** stays on 3 languages (`en`, `ru`, `es`). The **Documentation** page has its own language selector for all 20.

## Source files

| File | Purpose |
|------|---------|
| `skopos/docs_i18n_render.py` | English base + markdown renderers |
| `skopos/docs_i18n_translations.py` | `ru`, `es` overlays |
| `skopos/docs_i18n_translations_rest.py` | Other 17 locale overlays |
| `skopos/docs_i18n_ui.py` | Page chrome strings (title, tabs, disclaimer) |

## Generated output

```bash
python3 scripts/generate_skopos_i18n_docs.py
```

Writes:

- `docs/{lang}/guide/*.md` — five sections per language
- `docs/i18n/guides.json` — cached rendered markdown
- `docs/i18n/ui.json` — docs page UI strings

## Screenshots

- Russian and Spanish guides → `docs/screenshots/es/`
- All other doc languages → `docs/screenshots/en/`
