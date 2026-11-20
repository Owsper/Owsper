# OWSPER — design and research record

## Concept

**Nocturne Aperture.** A single cinematic object dominates: a thin orbital aperture over a silver
horizon, half-lost in atmospheric haze. The wordmark is drawn as geometry rather than set in a font,
so it renders identically everywhere and never depends on an external font request. Everything else
is a hairline, a measurement tick, or quiet monochrome text.

Motion is limited to one slow orbital drift, a faint dust parallax and an occasional light pass
along the horizon. All animation is CSS inside the SVG and is disabled under
`prefers-reduced-motion: reduce`; the composition is fully legible with motion off.

## Visual system

| Token | Value | Use |
| --- | --- | --- |
| void | `#080808` | All asset backgrounds, page ground |
| surface | `#111111` | — |
| line | `#1f1f1f` / `#242424` | Hairlines, rules |
| muted | `#626262` | Secondary labels |
| silver | `#a3a3a3` | Supporting text |
| white | `#f4f4f4` | Wordmark, primary data |
| activity ramp | `#141414` → `#cfcfcf` | Five contribution levels |

Typography inside assets: a geometric stroke wordmark, and a system monospace stack for labels
(`ui-monospace, SFMono-Regular, Menlo, Consolas, Courier New`). No external fonts, no neon, no
gradient accents beyond neutral luminance.

## Verified repository inventory

All ten public repositories were retrieved with the GitHub REST API and inspected through their file
trees, READMEs, dependency manifests and language endpoints. None are forks or archived.

| Repository | Primary | Evidence used |
| --- | --- | --- |
| Alpine | TypeScript | README, frontend/package.json (React 19, Vite 8), backend-ts/package.json (Hono, Supabase), backend/requirements.txt (FastAPI, faster-whisper, Kokoro) |
| Consul-Formerly-HireMeQuackers | Python | README (13 connectors, 117 tests, evidence ledger), requirements.txt |
| WW2-Dogfight | HLSL | ProjectVersion 6000.5.9f1, manifest (HDRP 17.5), terrain scene, planeThrust.cs |
| rimes-ocr-benchmark | Python | README results table, per-engine scripts |
| MINT | — | README description; `src/main.py` is empty |
| vera-church-management-system-showcase | — | README, architecture and product-decision docs, screenshots |
| Minom | Java | README, Fabric 1.19.2 build files, wet_sand block |
| Assistive-Object-Classifier | Jupyter | README, web_interface/app.py, exported evaluation reports |
| IDMS | Python | README, Flask/SQLite source, test files |
| Barthelomew | JavaScript | README, manifest.json, content.js |

Profile facts used: account created 2022-04-16, 10 public repositories, no public bio, blog, email,
location or social links. No personal claims were added beyond that.

Contribution figure shown in `assets/activity.svg` is read from the public contribution calendar
(1,287 contributions and 10 repositories at the time of generation) and is not hard-coded in the
README.

## Assets

| File | Dimensions | Purpose |
| --- | --- | --- |
| `assets/hero.svg` | 1200 × 460 | Wordmark, aperture, horizon; ambient motion with static fallback |
| `assets/activity.svg` | 1200 × 410 | Live contribution calendar and primary-language mix; generated |
| `assets/footer.svg` | 1200 × 140 | Signature and account origin year |

Constraints honoured: explicit `width`/`height`/`viewBox`, own background, `<title>`/`<desc>` with
`role="img"`, no external images or fonts, no JavaScript, every asset under 60 KB.

## Updating

- **Activity data:** run `python scripts/generate_activity.py`, or dispatch the
  *Refresh activity asset* workflow. A `GITHUB_TOKEN` enables the GraphQL path; without one the
  script falls back to the public contribution calendar. If both fail, the existing asset is kept and
  the workflow exits successfully rather than committing an empty graphic.
- **Hero and footer:** edit the SVG directly. Keep the monochrome ramp and update the wordmark paths
  only if the name changes.
- **Repositories or stack:** update the README, then re-check the claims against the repository
  READMEs rather than adding aspirational technologies.

## Known limitations

- The README was validated with GitHub's Markdown rendering API and local browser screenshots at
  desktop and mobile widths, not on the live profile (the profile repository does not yet exist).
- GitHub image caching can delay asset updates after a push.
- The assets use dark grounds by design, so they appear as dark cards in GitHub's light theme.
- `MINT` is incomplete in its repository and is labelled as an early scaffold.
