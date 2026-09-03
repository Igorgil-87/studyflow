# StudyFlow Responsive UX Refactor

## Status

P0 foundation implemented on top of the existing Flask/Jinja frontend. The backend/API contracts were not changed.

## Responsive architecture

The app shell now uses three working ranges:

- Mobile: up to 639px
- Tablet / compact desktop: 640px to 1023px
- Desktop: 1024px+

Breakpoints remain content-driven for legacy page-specific components. Existing page breakpoints are not blindly removed during P0; they will be consolidated as each page is migrated.

## Navigation

Desktop keeps the existing 248px sidebar.

Below 1024px the sidebar becomes an off-canvas drawer and a compact top app bar appears. The drawer includes:

- backdrop
- close button
- Escape-to-close
- click-outside-to-close
- focus trap
- focus restoration
- body scroll lock
- `aria-expanded`, `aria-controls` and `aria-hidden`
- 44px minimum touch targets for primary navigation controls
- safe-area-aware spacing

Files:

- `templates/partials/_mobile_header.html`
- `templates/partials/_sidebar.html`
- `static/js/navigation.js`

## Module identity system

Brand identity is semantic and does not rename backend code.

- Georgina / Study: `--module-study` (`#d4ff4f`)
- Marcos Cezar / Creator: `--module-creator` (`#a855f7`)
- Youtuber / Video: `--module-video` (`#ff3b4f`)

Application templates expose `data-module="study|creator|video|neutral"` on `body`. Components can consume `--module-accent` instead of hardcoding module colors.

The sidebar labels now expose the product names Georgina and Marcos Cezar while preserving existing routes and internal module names.

## Module artwork

Web-optimized module art is stored under:

`static/images/modules/`

Each identity has:

- source JPG
- 256px WebP
- 512px WebP
- 1024px WebP

These are not eagerly loaded by the P0 app shell. They are ready for the home/dashboard and module hero migrations without forcing large downloads into every page.

## Design-system foundation

P0 added reusable tokens and primitives for:

- spacing
- radii
- content width
- sidebar width
- module accents
- responsive form grid
- form control stacking
- helpers
- stack/cluster layout
- auto-fit responsive grid
- fluid stage padding
- fluid main headline

These primitives are intentionally additive. Page-specific forms are migrated in P1/P2 rather than changed globally in one risky operation.

## Overflow policy

The global `html, body { overflow-x: hidden; }` mask was removed. Page-specific overflow rules remain until the owning screen is migrated and tested. New P0 layout uses `minmax(0, 1fr)` / `min-width: 0` to prevent grid overflow at the source.

## Mobile input behavior

At <=639px, inputs/selects/textareas use an effective minimum 16px font size to avoid Safari's automatic input zoom.

## Local / cloud compatibility

P0 adds no new runtime dependency, CDN dependency, backend service, environment variable, hardcoded host, or filesystem path. The same Flask/Jinja/static structure is used locally and in the current cloud deployment.

## Validation performed

- `node --check static/js/navigation.js`: passed
- `git diff --check`: passed
- Jinja render smoke test passed for the main P0 targets (`curso.html`, `estudio.html`, `youtuber.html`, `automacoes.html`, and most other app templates). Templates requiring runtime course JSON/CSRF context cannot be fully rendered with an empty standalone Jinja context.
- Focused Python regression subset: 22 passed, 1 skipped.
- Full pytest collection cannot run in the current execution environment because project runtime dependencies including `langchain_core`, `yt_dlp`, and `psycopg2` are not installed here. This is an environment limitation, not a P0 code failure.

## Next phase

P1 — Georgina Experience:

1. Course hero and information hierarchy
2. YouTube vs Material mode selector
3. Creative-material form migration to stacked responsive controls
4. Progressive disclosure for optional course parameters
5. Course Engine state/loading/error UX
6. `curso.html` ID-preserving migration
7. responsive validation at 320/360/390/430/768/1024 widths

Then migrate Marcos Cezar / Estúdio and Youtuber using the same primitives.

## P2 — Marcos Cezar Experience

The Creator/Estúdio screen was migrated into a product-branded creative workspace while preserving all existing backend/API contracts and every pre-existing DOM ID used by `static/js/estudio.js`.

### UX changes

- Added a responsive Marcos Cezar hero using the optimized violet line-art asset.
- Reframed the page around the user outcome: **“O que você quer criar?”**.
- Video/Image tabs now expose proper tab semantics (`role=tab`, `aria-selected`, `aria-controls`).
- Primary video and image prompts were rewritten around intent instead of technical parameters.
- Video/image technical settings are visible as a side panel on desktop and become a native collapsible **Personalizar criação** block on tablet/mobile.
- Creator accent is now semantically inherited from `--module-creator`, rather than relying on the global study-lime accent.
- Toggle groups expose `aria-pressed` state.
- Script accordion exposes `aria-expanded` / `aria-controls`.
- Mobile forms use 16px text, full-width controls, touch targets, responsive toggle grids and one-column result cards.
- Result headers, image-reference controls and pipeline steps were made resilient to narrow viewports and long text.

### Contract safety

DOM-ID comparison against the P1 `estudio.html`:

- P1 IDs: 52
- P2 IDs: 55
- Existing IDs removed: **0**
- New semantic IDs: `estCreateHeading`, `tabEstudio`, `tabImagens`

No endpoint, request body field, SSE event or backend route was renamed.

### Validation

- `node --check static/js/estudio.js`: passed
- P1 → P2 DOM ID regression check: passed (0 existing IDs removed)
- duplicate ID check on `estudio.html`: passed
- `python _layout_test.py`: passed
- `python _cache_test.py`: passed
- `pytest -q tests/test_anti_slop.py`: **2 passed**
- Broader pytest collection still requires project runtime dependencies such as `yt_dlp` that are not installed in this execution environment.

### Next phase

P3 — Youtuber Experience:

1. red video-creator identity hero
2. clips flow simplified around URL → duration → quantity → language → generate
3. advanced options collapsed on mobile
4. video-first result hierarchy
5. responsive Shorts/Reels controls
6. preserve all existing `youtuber.js` IDs/API contracts

## P3 — Youtuber Experience

The Youtuber production flow was rebuilt around an essential-first mobile experience while preserving the existing generation API and every pre-existing DOM ID.

### UX changes

- Added a responsive red Video Creator identity section using the optimized Youtuber line-art asset.
- Reframed the primary task as **video → format → generate** instead of exposing the entire parameter panel at once.
- Moved the essential controls into the main flow: source URL, Shorts/Cortes, duration, quantity and language.
- Consolidated niche, burned captions, translation and closing-video options under **Opções avançadas**.
- Added an always-obvious primary **Gerar Clips** action; on mobile it becomes a safe-area-aware sticky action zone.
- Reworked Shorts/Cortes and language controls into mobile-safe responsive grids.
- Kept the product-level tabs horizontally scrollable on narrow screens rather than squeezing/cropping them.
- Added semantic `aria-pressed` updates to content type, duration and language controls.
- Added `aria-expanded` / `aria-controls` state to advanced options.
- Preserved the existing pipeline and result rendering while adapting the pipeline grid for mobile.

### Contract safety

DOM-ID comparison against P2 `templates/youtuber.html`:

- P2 IDs: 53
- P3 IDs: 54
- Existing IDs removed: **0**
- New semantic ID: `ytmCreatorTitle`

No endpoint, request body field, SSE event, job contract or backend route was renamed.

### Performance

- The module artwork uses responsive WebP sources (256/512) and does not load the 1024px asset for normal hero rendering.
- No new JS framework, CSS framework or runtime dependency was added.
- Existing video output keeps `preload="metadata"`.

### Validation

- `node --check static/js/youtuber.js`: passed
- P2 → P3 DOM-ID regression check: passed (0 existing IDs removed)
- duplicate ID check on `templates/youtuber.html`: passed
- Focused pytest run encountered a pre-existing/fixture-state failure in `_obs_core_test.py` because the trace store contained 3 rows while that test assumes exactly 2. This area is unrelated to the Youtuber UX changes.

### Next phase

P4 — cross-product responsive QA and remaining screens:

1. Trends responsive experience
2. Catálogo / Trilhas / Dashboard
3. Eventos / Certificados / Configurações
4. automated overflow checks at target widths
5. asset/cache review and Lighthouse pass

## P4 — Product-wide experience

- Home redesenhada como seletor de experiências com identidades Georgina, Marcos Cezar e Youtuber.
- Assets responsivos 256/512 usados nos cards; apenas Georgina é eager, demais lazy.
- Vídeo de fundo da home alterado de preload=auto para preload=metadata e removido visualmente com prefers-reduced-motion.
- Corrigidos wrappers HTML duplicados em Catálogo, Trilhas, Eventos e Certificados.
- Catálogo: filtros viram faixa horizontal touch-friendly no mobile; cards 1 coluna.
- Trilhas: construtor empilha no mobile e cards ficam fluidos.
- Eventos: calendário + formulário deixam de usar layout 1fr/360px no mobile; form rows empilham.
- Certificados: grid e ações adaptadas para telas estreitas.
- Planejamento: modal e calendário endurecidos para teclado/viewport mobile.
- Trends: categorias, pipeline e grids adaptados para mobile.
- Automações: URL do n8n deixa de ser localhost fixo e aceita `n8n_url`, com fallback relativo `/n8n`.

Nenhum endpoint ou contrato de payload foi alterado.
