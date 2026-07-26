# Equity Research Report Generator

Upload a company's financial context document (PDF, CSV, TXT, XLSX, JSON), and
get back a downloadable four-page equity research PDF — financial tables,
narrative sections and charts, laid out to match the reference retail-research
note format.

```
Upload  ──►  text extraction  ──►  LLM (structured output)  ──►  ReportModel
                                                                      │
                        PDF  ◄──  headless Chromium  ◄──  Jinja + CSS ─┘
                                                           + charts
```

---

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows;  source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
python -m playwright install chromium

copy .env.example .env            # cp on macOS/Linux — then add an API key

uvicorn app.main:app --reload
```

For the API key, the cheapest path is Google's free tier: get one at
[aistudio.google.com/apikey](https://aistudio.google.com/apikey) (no card
required) and put it in `.env` as `GEMINI_API_KEY=...`. Any of the other
providers below works just as well — see [Choosing a provider](#choosing-a-provider).

Open <http://127.0.0.1:8000>, enter a company name, drop in a document, click
**Generate report**, then **Download PDF**.

### Example output

`output/` contains three reports generated from the sample documents in
`samples/`, all with Gemini:

| Report | Source | Notes |
|---|---|---|
| `LTTS_Q2FY26.pdf` | `LTTS Q2FY26.pdf` | IT services; 20-row quarterly P&L, 3 charts |
| `JSW_Energy_Q2FY26.pdf` | `JSW Energy Q2FY26.pdf` | Power; Q2 + H1 columns, 4 charts |
| `ICICI_Q2FY26.pdf` | `ICICI Q2FY26.pdf` | Bank; NII / provisions P&L instead of a sales-to-PAT one |

The bank case is the useful one to look at — nothing in the code knows what a
bank is. The row labels come from the document via the schema, so the P&L
reshapes itself around NII, provisions and core operating profit without a
special case anywhere.

Note that these are press releases, not broker notes: none of them carry market
data, a rating or a target price. Those fields render as dashes, which is the
intended behaviour rather than a gap.

There is also a CLI that runs the identical pipeline:

```bash
python generate.py "L&T Technology Services" "samples/LTTS Q2FY26.pdf"
python generate.py "Meridian Industrial" samples/meridian_financials.csv -o output/meridian.pdf
python generate.py "Acme" doc.pdf --html output/debug.html   # inspect the HTML before printing
```

**Without any API key the app still runs**, in offline mode: the full report
renders with correct layout and every financial field deliberately left blank.
The UI shows a banner and the API returns `used_llm: false`, so stub output is
never presented as a real extraction.

---

## Tech used

| Concern | Choice | Why |
|---|---|---|
| API + UI | FastAPI + a single static HTML page | Minimal surface; no build step |
| Text extraction | `pdfplumber`, `csv`, `openpyxl` | Extracts ruled tables from PDFs, not just flat text |
| Field extraction | Gemini / Claude / any OpenAI-compatible model, with **structured outputs** | The Pydantic schema *is* the output contract — no JSON repair or field mapping |
| Charts | `matplotlib` → base64 data URIs | Self-contained HTML; no temp image files |
| Layout | Jinja2 + print CSS (`@page`, A4) | Table-heavy layout is far easier to maintain in CSS than in a drawing API |
| PDF | Playwright headless Chromium | Ships its own browser — no system libraries |

**Why Chromium and not WeasyPrint:** WeasyPrint needs a GTK/Pango system
install, which fails out of the box on Windows. `playwright install chromium`
is one command and works identically on all three platforms.

---

## Choosing a provider

The prompt and the schema are provider-independent, so the only thing that
varies is how the Pydantic model is handed over as an output contract.
`app/providers.py` covers three shapes of that, and **auto-selects the first
provider it finds a key for** — no code change to switch.

| Provider | Env var | Cost | Default model |
|---|---|---|---|
| **Gemini** | `GEMINI_API_KEY` | Free tier, no card | `gemini-2.5-flash` |
| Claude | `ANTHROPIC_API_KEY` | Paid | `claude-opus-5` |
| OpenAI | `OPENAI_API_KEY` | Paid | set `LLM_MODEL` |
| Groq | `GROQ_API_KEY` | Free tier | set `LLM_MODEL` |
| OpenRouter | `OPENROUTER_API_KEY` | Free models available | set `LLM_MODEL` |
| Ollama | *(none — local)* | Free | set `LLM_MODEL` |

Providers with no default model are left blank on purpose: guessing a model id
that may not exist produces a worse error than being asked for one.

**One wrinkle worth knowing.** Gemini enforces `response_schema` with
constrained decoding, and this schema is too big for it — the API rejects it
with *"the specified schema produces a constraint that has too many states for
serving"*. Shrinking the report to fit would let the vendor dictate the
template, so the Gemini backend uses plain JSON mode with the schema in the
prompt instead, and validates the reply against `ReportModel` on the way out. A
malformed response still fails loudly; it just fails after generation rather
than during it. Claude and the OpenAI-compatible providers take the schema
directly.

```bash
LLM_PROVIDER=anthropic                  # force one instead of auto-detecting
LLM_MODEL=gemini-2.5-pro                # override the model
LLM_BASE_URL=http://localhost:11434/v1  # any OpenAI-compatible endpoint
```

Ollama runs fully offline and needs no key (`LLM_PROVIDER=ollama`,
`LLM_MODEL=llama3.1:8b`), but be realistic about it: this task emits ~15k
tokens of nested JSON, which is slow on CPU and beyond what most small local
models can hold together. Treat it as a fallback, not the default.

---

## Where the template fields are defined

**`app/schema.py` is the single source of truth.** It defines the Pydantic
model that the LLM fills and the template renders, so adding a field flows
through both sides automatically.

| What | Where |
|---|---|
| Report structure (all sections and fields) | `app/schema.py` → `ReportModel` |
| Canonical row labels for each table | `app/schema.py` → `PROFIT_LOSS_ROWS`, `BALANCE_SHEET_ROWS`, `CASHFLOW_ROWS`, `RATIO_ROWS`, … |
| Extraction rules given to the model | `app/llm.py` → `SYSTEM_PROMPT` |
| LLM backends and provider selection | `app/providers.py` → `PRESETS` |
| Page layout / section order | `app/templates/report.html` |
| Colours, typography, page geometry | `app/templates/report.css` |
| Brand name, disclaimers, rating criteria | `app/branding.py` |

### Adding a field

1. Add it to the relevant model in `app/schema.py`.
2. Render it in `app/templates/report.html`.

That's it — the prompt is generated from the schema, so the model is asked for
the new field on the next run. To add a whole table, append its row labels to
the constants in `schema.py` and drop a `{{ table(report.your_table) }}` call
into the template; the generic `table()` macro handles headers, group headers,
section rows, bold/italic and missing cells.

---

## Report structure

| Page | Contents |
|---|---|
| 1 | Masthead, rating badge, target/CMP/return box, Key Changes strip, stock identity codes · left rail: Company Data, Shareholding, Price Performance, price-vs-index chart, Y.E March summary · main: thesis headline, company blurb, result bullets, Outlook & Valuation, Quarterly Financials |
| 2 | Key highlights · up to four bar+line combo charts · Change in Estimates |
| 3 | Consolidated Financials: Profit & Loss, Balance Sheet, Cashflow, Ratios (5 years each) |
| 4 | Recommendation Summary + rating history · Investment Rating Criteria · definitions · disclaimer |

---

## A note on branding

**The reports carry a placeholder brand, not the brand of the note this layout
was modelled on.** That is deliberate, and it is the one place where this
project departs from "recreate the sample".

What was reproduced is the *structure*: page count and section order, the table
and column layouts, the colour palette, the typography, the rating-criteria
grid, the dash convention for undisclosed data. That is what makes a generated
report recognisable as the same format, and it is what the acceptance criteria
actually test.

What was not reproduced is the *identity*: the logo and wordmark, the
registered address, SEBI registration numbers, compliance-officer contact
details, and the analyst certification. Those elements are what make a research
note attributable to a firm. Copying them onto an automatically generated,
unverified document about a real listed company would produce a counterfeit
research note — one that looks like a named brokerage published a
recommendation it never made. No amount of "this is only a demo" fixes that,
because the file outlives the context it was generated in.

So `app/branding.py` holds a neutral stand-in (`EQUIRESEARCH`), the disclaimer
states plainly that the document is machine-generated, unverified and not
investment advice, and no analyst is credited. Everything is overridable:

```bash
BRAND_NAME=...        # or edit app/branding.py directly
BRAND_TAGLINE=...
BRAND_WEBSITE=...
```

If you are deploying this for a real firm, put that firm's own marks and
disclosures in — the point is that the identity should be supplied by whoever
takes responsibility for the output, not copied from a third party by the
template.

The same reasoning is why `tests/fixture_report.py` uses a fictional issuer:
a fully populated layout preview shouldn't double as a fake note on a real
company.

---

## Handling missing data

Extraction never invents figures. The prompt requires a null for anything the
source doesn't support, and the renderer prints nulls as a grey en dash (`–`) —
the same convention the reference format uses for undisclosed data. Rows are
positional, so a partial extraction leaves gaps rather than shifting columns.
Empty tables and charts are dropped rather than rendered as empty frames.

---

## Project layout

```
app/
  main.py          FastAPI: /api/health, /api/generate, /api/download/{id}
  schema.py        ReportModel — the template contract  ← start here
  extract.py       PDF / CSV / TXT / JSON / XLSX -> plain text
  llm.py           Extraction prompt + offline fallback
  providers.py     LLM backends: Gemini / Claude / OpenAI-compatible
  charts.py        matplotlib combo + price charts -> data URIs
  render.py        Jinja -> HTML -> Chromium -> PDF
  branding.py      Brand strings, rating criteria, disclaimers
  templates/       report.html, report.css
  static/index.html  upload UI
generate.py        CLI entry point
tests/
  fixture_report.py  fully-populated ReportModel for template regression checks
samples/           example CSV and TXT inputs
output/            generated PDFs (gitignored)
```

---

## Verifying the template without an API key

`tests/fixture_report.py` builds a fully-populated `ReportModel` — every table,
chart, group header, section row, bold/italic row and a few deliberately blank
cells — and renders it:

```bash
python -m tests.fixture_report      # -> output/_fixture.pdf
```

The issuer in that fixture is fictional on purpose, so the rendered PDF exercises
the full layout without producing something that could be mistaken for a genuine
research note on a listed company.

`tests/check_schema.py` guards the other half of the contract. Every vendor
accepts a slightly different subset of JSON Schema, and the failure only shows
up as a 400 at request time — after you have already paid for the document
tokens. This runs the same transforms the SDKs apply (plus a prompt-size budget
for Gemini, whose schema is resent on every request), so a bad schema change is
caught locally and for free:

```bash
python -m tests.check_schema
```

---

## Notes and limitations

- **Branding is a placeholder** — see [A note on branding](#a-note-on-branding).
  Replace `app/branding.py` before distributing anything this produces.
- **Scanned PDFs are not supported** — extraction needs a text layer. The API
  returns a clear error rather than an empty report; OCR would be the fix.
- Long filings are trimmed to ~120k characters (head + tail) before extraction;
  see `MAX_CHARS` in `app/extract.py`.
- **Free-tier providers train on your prompts.** Google's free tier in
  particular reuses submitted content to improve their products. Fine for
  published quarterly results; not fine for anything confidential — use a paid
  tier or Ollama for that.
- Generation is synchronous and can take a minute or two on a long document. For
  production this would move to a job queue with a polling endpoint.
- Generated PDFs are written to `output/` and served by id; there is no
  retention policy or auth.
