# Research: markdown-to-PDF resume pipeline (#7)

**Question:** What is the best deterministic markdown→PDF rendering pipeline for clean, single-column, ATS-parseable resumes, driven from Python?

**Constraints:** The LLM writes content (markdown or structured data); the pipeline owns ALL layout. PDF is the only required output.

**Method:** Primary sources only — official docs, GitHub repos/release notes, PyPI, vendor documentation. Researched 2026-07-15.

---

## TL;DR comparison

| Criterion | Typst (via `typst` PyPI) | WeasyPrint (HTML/CSS) | Pandoc + LaTeX | ReportLab / fpdf2 | Chromium routes |
|---|---|---|---|---|---|
| Markdown input | No (own markup; md via pandoc) | No (md→HTML in Python first) | Yes, native | No (build from AST yourself) | Yes (md-to-pdf) / via HTML |
| ATS-safety (text layer) | Tagged PDF by default, PDF/UA-1 (0.14+) | Tagged PDF + PDF/UA-1/2 opt-in | ToUnicode auto since LaTeX 2021; PDF/UA-2 needs TeX Live 2025 + lualatex | Good but undocumented guarantees | Tagged PDF **off by default** |
| Template control | Full scripting language; JSON/YAML data loading | CSS Paged Media (`@page`, break control) | Pandoc templates + LaTeX class | Fully programmatic (code = layout) | Full web CSS |
| Install weight | One ~30 MB pip wheel, zero deps | pip + native Pango dep | ~35 MB binary + 600 MB BasicTeX (or Tectonic) | Pure pip | Full Chromium (hundreds of MB) |
| Python integration | In-process compiled bindings | In-process pure-Python API | Subprocess (pypandoc) | In-process, pure Python | Playwright / Node |
| Deterministic output | Yes, official (`timestamp`, SOURCE_DATE_EPOCH) | Yes, official (SOURCE_DATE_EPOCH) | Yes, official (SOURCE_DATE_EPOCH + trailer-id) | Yes (no external engine) | Weakest (browser version drift) |

Recommendation-shaped summary at the end; the human makes the pick in the feature-spec ticket.

---

## 1. Typst

### Python integration
- The [`typst` PyPI package](https://pypi.org/project/typst/) ([messense/typst-py](https://github.com/messense/typst-py)) statically links the Rust compiler into the wheel via maturin/PyO3 — no external binary, zero runtime dependencies, Python >= 3.8. Current version 0.15.0 (2026-06-16), released one day after upstream Typst 0.15.0 and version-locked to it.
- API: `typst.compile()`, `typst.query()`, and a reusable `Compiler` class that avoids reinitialization across compiles (in-process analogue of the CLI's incremental watch mode). Parameters include `font_paths`, `sys_inputs` (dict of strings), `pdf_standards` (e.g. `"ua-1"`, `"a-2a"`), and `timestamp` for reproducible PDFs ([typst-py README](https://github.com/messense/typst-py)).
- The [typst CLI](https://github.com/typst/typst) alternative offers `typst compile` / `typst watch` with officially claimed "fast compile times thanks to incremental compilation" (no published ms figures).

### Install weight
- Wheels are ~29–34 MB with no listed runtime dependencies ([PyPI files](https://pypi.org/project/typst/#files)).
- Compiler embeds fonts (Libertinus Serif, New Computer Modern, DejaVu Sans Mono); `--font-path` > system fonts > embedded, plus `--ignore-system-fonts` for hermetic builds ([typst/typst README](https://github.com/typst/typst), [Typst forum: included fonts](https://forum.typst.app/t/which-fonts-are-included-in-the-compiler/1510)).

### Template control / content-layout separation
- Typst is a full scripting language with first-class data loading: `json()`, `yaml()`, `toml()`, `csv()` ([data loading docs](https://typst.app/docs/reference/data-loading/)) — resume content can live in JSON/YAML while a pure-layout `.typ` template renders it.
- `sys.inputs` accepts values passed via `--input` / Python `sys_inputs=`; docs suggest passing richer structures as JSON strings ([sys docs](https://typst.app/docs/reference/foundations/sys/)) — the whole resume payload can be piped in without touching the filesystem.
- **No markdown input.** Content is Typst markup ([syntax docs](https://typst.app/docs/reference/syntax/)); the sanctioned md path is pandoc, which supports typst as an output format and `--pdf-engine=typst` ([pandoc MANUAL](https://pandoc.org/MANUAL.html)).

### ATS-safety
- Typst 0.14.0 (2025-10-24) rewrote PDF export on the krilla library: **tagged, accessible PDFs by default**, PDF/UA-1 conformance option, all PDF/A variants; release notes also fix text extraction ("copy-paste now works correctly even when multiple different characters result in the same glyph"; line-break spaces "correctly retained for text extraction") ([v0.14.0 release notes](https://github.com/typst/typst/releases/tag/v0.14.0)). The PDF/UA work was NLnet grant-funded ([NLnet project page](https://nlnet.nl/project/Typst-Accessibility/)).
- Known extraction issues are edge cases irrelevant to a Latin-script single-column resume: complex shaping (Devanagari) [#4225](https://github.com/typst/typst/issues/4225); ligature toggling [#1783](https://github.com/typst/typst/issues/1783) — ligatures can be disabled in the template (`set text(ligatures: false)`) as belt-and-suspenders.

### Maintenance health
- [typst/typst](https://github.com/typst/typst): ~54.9k stars, Apache-2.0, latest 0.15.0 (2026-06-15); ~2 feature releases/year plus patches ([releases](https://github.com/typst/typst/releases)). Backed by Typst GmbH (founded by the original developers; compiler fully open source, web app is the commercial product) ([typst.app/about](https://typst.app/about/), [open-source page](https://typst.app/open-source/)).

### Determinism
- Honors `SOURCE_DATE_EPOCH` and `--creation-timestamp` ([issue #3806](https://github.com/typst/typst/issues/3806) demonstrates identical checksums); 0.15.0 fixed the last known wrinkle (local timezone leaking into output) ([v0.15.0 release notes](https://github.com/typst/typst/releases/tag/v0.15.0)). Exposed in Python as the `timestamp` parameter ([typst-py README](https://github.com/messense/typst-py)).

---

## 2. WeasyPrint (HTML/CSS)

### Python integration
- Pure in-process library, no subprocess: `HTML(string=html).write_pdf()` returns bytes when no target given; layout engine is written in Python, designed for pagination ([API reference](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html), [PyPI](https://pypi.org/project/weasyprint/)).
- Markdown front-end: pair with [markdown-it-py](https://pypi.org/project/markdown-it-py/) or [Python-Markdown](https://pypi.org/project/Markdown/) plus Jinja2 — the whole md→HTML→PDF pipeline stays in one Python process.
- Documented iteration levers: reuse a `cache={}` across `write_pdf()` calls; docs note hand-written stylesheets are the fast path (large CSS frameworks hurt cascade performance) ([Common Use Cases](https://doc.courtbouillon.org/weasyprint/stable/common_use_cases.html)).

### Install weight
- One true native dependency: **Pango >= 1.44** (brings HarfBuzz); rest is pure-Python (Pillow, fontTools, pydyf, tinycss2, ...). macOS: `brew install weasyprint`; Windows needs MSYS2 for Pango or the standalone executable; Python >= 3.10 since v67.0 ([First Steps](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html), [changelog](https://doc.courtbouillon.org/weasyprint/stable/changelog.html)).

### Template control
- CSS Paged Media Level 3 is first-class: `@page` rules, margin boxes, page counters, named pages; CSS Fragmentation `break-*`, `orphans`/`widows` ([Features](https://doc.courtbouillon.org/weasyprint/stable/features.html)).
- No JavaScript by design; flexbox "works for simple use cases but is not deeply tested"; Grid added v62.0 (2024-04-30) but partial ([Features](https://doc.courtbouillon.org/weasyprint/stable/features.html), [changelog](https://doc.courtbouillon.org/weasyprint/stable/changelog.html)). A single-column resume needs only block flow + `@page` + break control — squarely in the best-supported feature set.

### ATS-safety
- Fonts automatically embedded and subset (HarfBuzz subsetter by default since v63.0); `full_fonts` disables subsetting ([Features](https://doc.courtbouillon.org/weasyprint/stable/features.html), [changelog](https://doc.courtbouillon.org/weasyprint/stable/changelog.html)).
- `pdf_variant` supports PDF/A (1b–4b, 1a–3a, u/e/f variants), **PDF/UA-1 and UA-2**, PDF/X; PDF/UA requires `<title>` and `lang` on `<html>`; docs caution conformance is "not guaranteed" — validate with veraPDF ([API reference](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html), [Common Use Cases](https://doc.courtbouillon.org/weasyprint/stable/common_use_cases.html)).
- Standalone tagged-PDF output without full UA: `pdf_tags` option added v66.0 (2025-07-24), NLnet-funded ([v66 announcement](https://www.courtbouillon.org/blog/00058-weasyprint-66/), [v66.0 release](https://github.com/Kozea/WeasyPrint/releases/tag/v66.0)).
- Tracker-documented extraction gotchas, all avoidable in a resume stylesheet: ligatures disabled under justification ([#1469](https://github.com/Kozea/WeasyPrint/issues/1469)); `letter-spacing` can degrade word extraction ([#976](https://github.com/Kozea/WeasyPrint/issues/976), [#1662](https://github.com/Kozea/WeasyPrint/issues/1662)); set `hyphens: none` so parsers never see split words ([#176](https://github.com/Kozea/WeasyPrint/issues/176)).

### Maintenance health
- v69.0 (2026-06-02); 3–4 significant releases/year; 9.4k stars, BSD-3-Clause; maintained commercially by CourtBouillon, funded via [Open Collective](https://opencollective.com/courtbouillon) and feature sponsorships (PDF/A, PDF/UA, NLnet accessibility work) ([changelog](https://doc.courtbouillon.org/weasyprint/stable/changelog.html), [GitHub](https://github.com/Kozea/WeasyPrint)).

### Determinism
- Reproducible generation since v55.0b1 via `SOURCE_DATE_EPOCH` ([issue #1553](https://github.com/Kozea/WeasyPrint/issues/1553), [SOURCE_DATE_EPOCH spec](https://reproducible-builds.org/specs/source-date-epoch/)); plus `pdf_identifier`, `dcterms.created`/`modified` meta tags, `uncompressed_pdf` for diffing ([API reference](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html)). Pin the version and hash-test in CI (one historical reproducibility regression: [#1666](https://github.com/Kozea/WeasyPrint/issues/1666), fixed).

---

## 3. Pandoc + LaTeX (and pandoc's other engines)

### Pipeline shape
- Native markdown input; default PDF path is LaTeX. Supported `--pdf-engine` values: pdflatex, lualatex, xelatex, latexmk, tectonic, wkhtmltopdf (deprecated), weasyprint, pagedjs-cli, prince, context, groff, pdfroff, **typst** ([MANUAL — --pdf-engine](https://pandoc.org/MANUAL.html#option--pdf-engine)); typst engine support since pandoc 3.1.2 (2023-03-26) ([changelog](https://pandoc.org/releases.html)).
- Full template language (conditionals, loops, partials) via `--template`; LaTeX variables (`documentclass`, `geometry`, `mainfont`, ...) ([MANUAL — Templates](https://pandoc.org/MANUAL.html#templates), [Variables for LaTeX](https://pandoc.org/MANUAL.html#variables-for-latex); [default.latex source](https://github.com/jgm/pandoc/blob/main/data/templates/default.latex)).

### Install weight
- Pandoc is a single ~26–42 MB binary ([releases](https://github.com/jgm/pandoc/releases/tag/3.10)). The LaTeX engine is the heavy part: pandoc's own install page warns full MacTeX is ~4 GB and recommends BasicTeX/TinyTeX (~600 MB per [TUG quickinstall](https://tug.org/texlive/quickinstall.html)) ([pandoc.org/installing](https://pandoc.org/installing.html)).
- **Tectonic** (self-contained XeTeX-based single binary) is not archived but went dormant: 0.15.0 (2024-02-05) then nothing until 0.16.0 (2026-04-11, "The first release of tectonic in several years!"), latest 0.16.9 (2026-04-17) — freshly revived but the 2-year gap is a bus-factor signal ([tectonic releases](https://github.com/tectonic-typesetting/tectonic/releases), [0.16.0 notes](https://github.com/tectonic-typesetting/tectonic/releases/tag/tectonic%400.16.0)).

### Python integration
- [pypandoc 1.17](https://pypi.org/project/pypandoc/) (2026-03-14) is a thin subprocess wrapper; `pypandoc_binary` bundles pandoc. Plain `subprocess.run` is equivalent. No in-process API exists.
- Iteration speed: no official benchmarks; LaTeX is multi-pass by design (latexmk exists to orchestrate reruns, [CTAN](https://ctan.org/pkg/latexmk)), though a one-page resume without cross-references typically converges in one pass.

### ATS-safety
- The classic ligature copy-paste problem (fi/fl extracting as garbage) is primary-source documented by pdfTeX's author ([TUGboat 29-1, Thành](https://tug.org/TUGboat/tb29-1/tb91thanh-fonts.pdf)) — and **fixed by default since the LaTeX 2021-06 kernel**: glyphtounicode mapping "is now added automatically to the PDF file... this allows the most common ligatures to be copied as intended" ([LaTeX News 33](https://www.latex-project.org/news/latex2e-news/), [ltnews33 source](https://github.com/latex3/latex2e/blob/develop/base/doc/ltnews33.tex)). XeLaTeX's backend generates ToUnicode from the font's own cmap ([dvipdfmx manual](https://tug.org/dvipdfmx/doc/dvipdfmx/dvipdfmx.pdf)).
- Tagged PDF: pandoc has a dedicated "Accessible PDFs" section — `pandoc -V pdfstandard=ua-2 --pdf-engine=lualatex` produces tagged PDF/UA-2, but "requires LuaLaTeX in TeX Live 2025 with LaTeX kernel 2025-06-01 or newer" ([MANUAL — Creating a PDF](https://pandoc.org/MANUAL.html#creating-a-pdf)); underpinned by the LaTeX tagging project ([latex3 tagging project](https://latex3.github.io/tagging-project/), [LaTeX project news](https://www.latex-project.org/news/)). Pandoc itself cautions it cannot verify standards compliance.

### Maintenance health
- Pandoc 3.10 (2026-06-04); a release roughly every 1–2 months; maintained by John MacFarlane ([releases](https://github.com/jgm/pandoc/releases)).

### Determinism
- Official "Reproducible builds" manual section: `SOURCE_DATE_EPOCH` plus `pdf-trailer-id` (auto-derived from epoch + content hash if unset) ([MANUAL — Reproducible builds](https://pandoc.org/MANUAL.html#reproducible-builds)); TeX Live >= 2016 honors `SOURCE_DATE_EPOCH` ("complete" support per [reproducible-builds.org](https://reproducible-builds.org/docs/source-date-epoch/)).

---

## 4. Other candidates

### ReportLab (programmatic)
- Open-source Python PDF engine with the Platypus flowable layer; no markdown or HTML input — layout is code ([PyPI](https://pypi.org/project/reportlab/)). v5.0.0 (2026-06-18), BSD, corporate-maintained for 25 years; pure pip since 4.0 removed the C accelerator ([Release Notes 4.0](https://docs.reportlab.com/releases/notes/whats-new-40/)). The commercial PLUS/RML tier is not needed for this use case ([RML docs](https://docs.reportlab.com/rml/userguide/Chapter_1_Introduction/)). Fit: maximal determinism and code-owned layout, but you must write a markdown-AST→flowables mapper yourself; no documented ToUnicode guarantee found.

### fpdf2 (pure Python, lightweight)
- v2.8.7 (2026-02-28), pure Python, few deps, Unicode TrueType subset embedding ([PyPI](https://pypi.org/project/fpdf2/)). `write_html()` covers only an HTML subset with no CSS, and the docs themselves recommend ReportLab/WeasyPrint for robust HTML conversion ([HTML docs](https://py-pdf.github.io/fpdf2/HTML.html)); `markdown=True` on cells is inline styling sugar (bold/italic), not a document pipeline ([Text styling docs](https://py-pdf.github.io/fpdf2/TextStyling.html)). Text shaping optional via uharfbuzz ([TextShaping docs](https://py-pdf.github.io/fpdf2/TextShaping.html)).

### Chromium print routes (md-to-pdf, Playwright)
- [simonhaenisch/md-to-pdf](https://github.com/simonhaenisch/md-to-pdf) (Node, 5.2.5, 2025-12-03): Marked → Puppeteer/headless Chromium; the tool is tiny but drags in a full Chromium download.
- Python route: Playwright `page.pdf()` works only in headless Chromium ([playwright-python #2909](https://github.com/microsoft/playwright-python/issues/2909)); prints with print CSS by default ([Playwright page.pdf docs](https://playwright.dev/python/docs/api/class-page#page-pdf)).
- **Tagged PDF is off by default**: Playwright's `tagged` option "Defaults to false" ([class-page docs](https://playwright.dev/docs/api/class-page)); the underlying CDP `Page.printToPDF` `generateTaggedPDF` parameter is experimental ([Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/tot/Page/)). Determinism is the weakest of all routes (output tracks the bundled Chromium's layout engine across upgrades).

### Excluded
- **wkhtmltopdf / pdfkit**: repo archived 2023-01-02; the project's own status page says its WebKit "hasn't been updated since 2012" and recommends WeasyPrint/Puppeteer ([wkhtmltopdf.org/status](https://wkhtmltopdf.org/status.html), [GitHub](https://github.com/wkhtmltopdf/wkhtmltopdf)).
- **xhtml2pdf**: maintained but slow-moving (0.2.17, 2025-02-23) and a weaker CSS subset than WeasyPrint on top of ReportLab — adds little ([GitHub](https://github.com/xhtml2pdf/xhtml2pdf)).
- **Paged.js CLI**: requires Puppeteer/Chromium anyway — inherits the Chromium route's downsides.

---

## 5. What ATS vendors actually document about PDF parseability

- **Greenhouse** (ATS): supports doc/docx/pdf/rtf/txt uploads ([supported formats](https://support.greenhouse.io/hc/en-us/articles/360052218132-Supported-formats-for-resumes-cover-letters-and-other-candidate-uploads)). Their parse-failure article explicitly lists what breaks parsing: image-only resumes, "complex resumes with tables, headers, and footers", "resumes with a columned layout", graphics/word art, and contact info in the header/footer/text box ([Unsuccessful resume parse](https://support.greenhouse.io/hc/en-us/articles/200989175-Unsuccessful-resume-parse)). This is the strongest direct vendor confirmation of the single-column / no-tables / real-text-layer guidance.
- **Lever** (ATS): cannot parse image files; documented litmus test is text selectability — if you cannot highlight the text, it likely will not parse ([Understanding Resume Parsing](https://help.lever.co/hc/en-us/articles/20087345054749-Understanding-Resume-Parsing)).
- **Textkernel** (parser vendor behind many ATSs): notes that corrupt PDFs are their top parse-bug source and that "PDF is a broken standard that often hides issues with the underlying text" — a mild vendor preference for DOCX, worth knowing even though PDF is this project's required output ([Tx Parser Getting Started](https://developer.textkernel.com/tx-platform/v9/resume-parser/overview/getting-started/)).
- **Affinda** (parser vendor): text-layer PDFs parse directly; scanned images fall back to lossier OCR ([integration docs](https://docs.affinda.com/resumes/integration)).
- **Spec basis**: reliable extraction depends on mapping glyph codes to Unicode — ISO 32000-1 §9.10 "Extraction of Text Content": readers use the font's ToUnicode CMap, standard encodings, or glyph-name heuristics, in that order; if none applies, extraction fails even though the PDF renders fine ([Adobe PDF 32000-1:2008](https://opensource.adobe.com/dc-acrobat-sdk-docs/pdfstandards/PDF32000_2008.pdf)).
- **Practical implication for any pick**: add a CI check that round-trips the generated PDF through `pdftotext`/pypdf and diffs against the source content — that directly tests the property ATS parsers depend on.
- Not found in any vendor doc (folklore, do not design around): "ATS can't read PDFs", "must use .docx", keyword-stuffing tricks.

---

## 6. Recommendation-shaped summary (human decides in the feature-spec ticket)

Given the constraint that the LLM produces content and the pipeline owns all layout, the "markdown" requirement is soft — structured data (JSON/YAML) into a fixed template is an equally valid contract, and a stricter one.

- **Typst (via `typst` PyPI)** — strongest overall fit if content is structured data. One ~30 MB self-contained wheel, in-process compile, tagged PDF/UA-1 by default since 0.14, officially deterministic output, full scripting for layout with `json()`/`sys.inputs` for content injection. Trade-off: templates are written in Typst markup (a new small language), and markdown input would require a pandoc hop.
- **WeasyPrint** — strongest fit if content stays markdown. Fully in-process Python (markdown-it-py → Jinja2 → `write_pdf()`), familiar HTML/CSS templating with first-class paged-media control, PDF/UA + tagged output, `SOURCE_DATE_EPOCH` determinism. Trade-off: one native dependency (Pango) complicates clean installs, especially on Windows; must consciously avoid ligature/letter-spacing/hyphenation CSS gotchas.
- **Pandoc + LaTeX** — most mature markdown ingestion and the manual even documents reproducible builds and PDF/UA-2, but the tooling weight (600 MB BasicTeX minimum, or a freshly-revived-after-2-years Tectonic) and subprocess-only integration make it the heaviest option for a single-template resume pipeline. Its most useful trick here may be `--pdf-engine=typst` as a md→typst bridge.
- **ReportLab / fpdf2** — maximal determinism and zero native deps, but you hand-build the layout engine glue (markdown AST → flowables/cells); more code to own for no ATS advantage over Typst/WeasyPrint.
- **Chromium routes (md-to-pdf, Playwright)** — ruled out on the stated criteria: heaviest dependency, weakest determinism, tagged PDF off by default. **wkhtmltopdf** is archived; exclude.
