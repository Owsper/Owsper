# OWSPER — design and research record

## Concept

**Instrument Study.** A single machined object occupies the right side of the plate: concentric turned-metal
rings, an engraved tick band, bolt heads, an optical aperture and one thin signal trace. The left side is
carried by the wordmark and a short technical line. There is no slogan.

The page is an engineering journal rather than a dashboard: warm off-white type on a near-black ground,
hairline rules, numbered sections, and project writing that states what each system is and what it does.

Motion is deliberately sparse — one slow ring rotation, a raking highlight across the metal, and a faint
pulse in the signal channel. All of it is CSS inside the SVG, disabled under
`prefers-reduced-motion: reduce`; the composition is complete with motion off.

The activity graphic reuses the same idea: a monthly signal trace with a faint weekly texture behind it,
not a GitHub contribution heatmap.

## Visual system

| Token | Value | Use |
| --- | --- | --- |
| Void | `#070707` | Asset grounds |
| Graphite | `#0e0d0c` | Instrument body |
| Line | `#232323` | Hairlines, rules |
| Steel | `#3a3835` | Machined edges, weekly ticks |
| Muted | `#9a958b` | Secondary text, month labels |
| Silver | `#c9c5bc` | Fine data, wordmark finish |
| Paper | `#f2efe8` | Primary data, highlights |

Contrast against `#070707`: Paper 17.5:1, Silver 11.7:1, Muted 6.8:1, `#8a857c` 5.5:1. No essential
text is set below 4.5:1.

Typography inside assets:

- **Display:** `Georgia, "Times New Roman", serif` for the large contribution totals. The serif is the
  editorial counterweight to GitHub's sans-serif page.
- **Technical:** `ui-monospace, SFMono-Regular, Menlo, Consolas, "Courier New", monospace` for short
  labels, with tracking between 1.4 and 2.6 px. No 4–5 px tracking, no microtype carrying meaning.
- **Body:** GitHub's own sans-serif. The README does not try to restyle the platform.

No external fonts, images, CSS or JavaScript.

## Information architecture

1. Hero — wordmark, instrument plate, no slogan.
2. Direction note — an honest statement of interest in firmware, sensors and physical systems.
3. `01 Selected systems` — Vera, CONSUL, WW2-Dogfight.
4. `02 Index` — all ten project repositories, grouped by product, perception and interactive work.
5. `03 Bench` — tools verified in those repositories.
6. `04 Signal` — monthly contribution trace.
7. `05 Contact` — GitHub only, with a short colophon.

Section anchors are generated from the plain headings (`#01-selected-systems`, `#02-index`, and so on)
rather than custom HTML anchors, which GitHub prefixes and can break.

## Motion storyboard

| Element | Behaviour | Timing | Reduced motion |
| --- | --- | --- | --- |
| Outer tick ring | Slow rotation | 320 s linear | Static |
| Inner ring | Counter-rotation | 460 s linear | Static |
| Raking light | Soft highlight crosses the metal | 26 s alternate | Static |
| Signal trace | Short dashes travel the channel | 9 s linear | Static |
| Aperture point | Faint breathing | 13 s | Static |

No text moves, nothing flashes, and no element depends on animation to be understood.

## Verified repository inventory

All public repositories were read through the GitHub API, their file trees, READMEs, manifests and
language endpoints. At the time of this record there are 11 public repositories: the `Owsper` profile
repository plus ten project repositories. None are forks or archived.

| Repository | Primary | Evidence used |
| --- | --- | --- |
| Vera showcase | — | README, architecture and product-decision docs, four interface screenshots |
| CONSUL | Python | README (13 connectors, 117 mocked tests, Ground Truth ledger), requirements |
| WW2-Dogfight | HLSL | `ProjectVersion` 6000.5.9f1, HDRP 17.5 manifest, terrain scene, `planeThrust.cs` |
| IDMS | Python | README, Flask/SQLite source, more than 20 test files, 202 commits |
| Alpine | TypeScript | README, React 19 / Vite 8 frontend, Hono and FastAPI services, Whisper and Kokoro |
| Assistive-Object-Classifier | Jupyter Notebook | README, Gradio app, exported evaluation reports |
| rimes-ocr-benchmark | Python | README results table, per-engine scripts, 15.43% CER for PaddleOCR |
| MINT | — | README description; `src/main.py` is a placeholder |
| Minom | Java | README, Fabric 1.19.2 build files, `minom:wet_sand` block |
| Barthelomew | JavaScript | README, Manifest V3, `content.js`, MIT licence |

Contribution data is read live. The current public calendar begins in **April 2026**; the chart starts at
the first active month rather than padding half the frame with zeros. Totals in `assets/activity.svg` are
generated, never hard-coded in the README.

## Assets

| File | Dimensions | Purpose |
| --- | --- | --- |
| `assets/hero.svg` | 1200 × 560 | Instrument plate and wordmark; ambient motion with static fallback |
| `assets/activity.svg` | 1200 × 360 | Monthly signal trace, totals and weekly texture; generated |
| `assets/footer.svg` | — | Removed; replaced by the text colophon |

Constraints honoured: explicit `width`/`height`/`viewBox`, own background, `<title>`/`<desc>` with
`role="img"`, no external references, no JavaScript, both assets under 11 KB.

## Decisions

- **Featured trio:** Vera → CONSUL → WW2-Dogfight, in that order.
- **Alpine and Assistive Object Classifier** are removed from the featured section but remain in the
  complete index. Removing them from the index would make the public collection incomplete.
- **No Vera screenshot.** The four public screenshots were reviewed: no personal data is visible, but the
  product's warm yellow interface would break the monochrome system, and the cleanest frame is an empty
  “Add Member” form. The case study stays typographic.
- **No hero slogan.** The wordmark and the instrument carry the opening; the direction note and project
  writing do the explaining.
- **Physical computing is stated as direction, not experience.** No public repository demonstrates
  firmware, electronics, robotics or hardware integration, so the profile does not claim it.
- **No footer graphic.** The repeated signature motif added length without information.

## Updating

- **Activity data:** run `python scripts/generate_activity.py`, or dispatch the
  *Refresh activity asset* workflow. A `GITHUB_TOKEN` enables the GraphQL path; without one the script
  falls back to the public contribution calendar. If both fail, the existing asset is kept and the
  workflow exits successfully rather than committing an empty graphic.
- **Hero:** edit the SVG directly. The wordmark is geometry, not a font; if the name changes, the paths
  must change too.
- **Repositories or stack:** update the README, then re-check every claim against the repository READMEs.
  The Bench list is an inventory, not a proficiency rating.

## Verification performed

- Both SVGs parse as XML and expose the expected `width`, `height`, `viewBox`, `<title>` and `<desc>`.
- Rendered in headless Edge at 1200 px and at a 390 px CSS frame; the README harness reports zero
  horizontal overflow and two images.
- GitHub Markdown API output contains no tables, scripts or iframes, and preserves both asset paths.
- All twelve external links in the README returned HTTP 200.
- Contrast ratios calculated for every text fill used at small sizes.
- Activity generator run twice from the live public calendar; the workflow assertion now expects
  `0 0 1200 360`.
- GitHub image caching and the live profile were not available for a final visual pass; the profile
  repository now exists, but these changes have not been pushed.

## Known limitations

- Contribution totals change as the public calendar updates, so the SVG differs from any number quoted in
  prose.
- `MINT` is still an incomplete scaffold and is labelled as early.
- The assets use dark grounds by design, so they appear as dark cards in GitHub's light theme.
- The profile repository exists but the redesign is not deployed; deployment requires a commit and push.
