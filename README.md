# Cantonese Text Converter

Converts standard written Chinese (書面語) into genuine written Cantonese
(粵文) — real 係/唔/嘅/咗/佢/喺/冇 grammar, not standard Chinese with a
few Cantonese words swapped in. Personal, single-user tool. Built from
the locked System Specification Document (v1.0).

Paste text or upload `.txt` / `.srt` / `.docx` / `.pdf`, pick a translation
provider, review the 粵文 output in the browser, edit it if needed, and
save it to a file you can download later.

## Before anything else: the D1 quality gate

D1 was locked to Poe's `GPT-5.6-Luna` **without running the planned
four-way comparison** (see spec §9.1). Nobody has published a
benchmark for sustained 粵文 generation quality, so this can only be
checked by reading real output.

**The first time you run this app, do exactly this before relying on
it for anything real:**

1. Paste a paragraph of 書面語 that has at least one 咗/嘅/唔 situation
   and a couple of English words mixed in.
2. Translate it.
3. Read the result. Does it look like genuine 粵文, or like 書面語 with
   a few Cantonese words swapped in?

If it doesn't hold up, switch the provider dropdown to Gemini and
re-test, or change `POE_MODEL` in your environment to try a different
Poe model. Nothing else in the app depends on which model produced
that first output.

## Project layout

```
extractors/    input parsing - pasted text, .txt, .srt, .docx, .pdf
translator/    provider clients (Poe, Gemini), chunker, prompt builder
writers/       output formatting - .txt, .srt
auth/          Google OAuth, single-email allowlist
jobs/          in-memory job tracking + background translation runner
web/           Flask routes, templates, static assets
app.py         application factory / entrypoint
config.py      all environment variables in one place
```

Each provider is a small client behind one interface
(`translator/base.py`), so adding the deferred Custom endpoint (D8)
later means one new file here plus a few form fields - nothing else
in the app changes.

## File formats

| Upload  | Output | Notes |
| ------- | ------ | ----- |
| `.txt`  | `.txt` | UTF-8. |
| `.srt`  | `.srt` | Indexes and timestamps pass through untouched; only cue text is translated. |
| `.docx` | `.txt` | Paragraph text only - no tables, headers, or footers. |
| `.pdf`  | `.txt` | Text-based PDFs only (see below). |

Whatever you upload, the translation lands in the editable box first -
review and fix it there before saving.

### About PDFs

A PDF stores glyphs at coordinates rather than paragraphs, so
`extractors/pdf_extractor.py` reconstructs the paragraphs before
anything is translated: it undoes the hard line wrapping (joining CJK
lines with no separator and Latin lines with a space, re-joining words
split across a line break), drops page numbers and running
headers/footers, and merges a paragraph that runs over a page break.
That matters because the chunker splits on paragraphs - a page of
run-on text chunks badly and translates worse.

Two things it can't do:

- **Scans and photos of pages have no text to extract.** If a PDF is
  images of text, you get a clear error rather than an empty
  translation - run it through OCR first, or paste the text in.
- **Password-protected PDFs are rejected.** Remove the password and
  re-upload. (PDFs encrypted with an empty user password - common for
  print-restricted files - open fine.)

Complex layouts (multi-column pages, tables, text boxes) come out in
whatever reading order the PDF declares, which isn't always the one you
see on screen. Skim the output box before saving.

Uploads of any type are capped by `MAX_UPLOAD_MB` (10 MB by default);
PDFs are the format most likely to hit it, and the app answers with a
clear "File too large" message rather than failing obscurely.

## Setup

### 1. Google OAuth

In [Google Cloud Console](https://console.cloud.google.com/apis/credentials):

1. Create an OAuth 2.0 Client ID, type "Web application".
2. Add an authorized redirect URI: `https://<your-domain>/auth/callback`
   (and `http://localhost:8080/auth/callback` for local runs).
3. Copy the client ID and secret into `GOOGLE_CLIENT_ID` /
   `GOOGLE_CLIENT_SECRET`.
4. Set `ALLOWED_EMAIL` to the one Google account that should be able
   to sign in. Anyone else is rejected at the callback.

### 2. Translation providers

- **Poe** (locked default, D1): create a key at
  [poe.com/api/keys](https://poe.com/api/keys). Requires an active Poe
  subscription or add-on points - it's billed against your existing
  points, not a separate charge.
- **Gemini** (session-switchable alternative, R10): create a key at
  [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

Both keys can be set even if you only plan to use one - the dropdown
on the translate page switches between them per session without a
redeploy.

### 3. Environment variables

Copy `.env.example` to `.env` and fill it in. Every variable is
documented there; see spec section 8 for what each one means.

## Run locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

export $(grep -v '^#' .env | xargs)   # or use python-dotenv / direnv
python app.py
```

Open `http://localhost:8080`.

## Run with Docker

```bash
docker build -t cantonese-converter .
docker run -p 8080:8080 --env-file .env cantonese-converter
```

## Deploy to Railway

The repo is Railway-ready: `railway.json` pins the Dockerfile builder,
the `/healthz` health check, and a single replica.

1. **Create the service.** In [Railway](https://railway.com), create a
   project and add a service from this GitHub repo. Railway reads
   `railway.json` and builds the `Dockerfile` — no Nixpacks config
   needed.
2. **Set the variables.** Service → Variables → *Raw Editor*, then
   paste everything from `.env.example` and fill in the values. Don't
   set `PORT` (Railway injects it) and don't set `OUTPUT_DIR` (see the
   volume step). The four required ones are `GOOGLE_CLIENT_ID`,
   `GOOGLE_CLIENT_SECRET`, `ALLOWED_EMAIL`, `FLASK_SECRET_KEY` — the
   container exits at startup with a clear message if any is missing.
3. **Generate the domain.** Service → Settings → Networking → *Generate
   Domain*. Railway detects the exposed port automatically; if it asks,
   the port is `8080`. You get something like
   `cantonese-converter-production.up.railway.app`.
4. **Point Google OAuth at it.** In Google Cloud Console, add
   `https://<your-railway-domain>/auth/callback` as an authorized
   redirect URI, then redeploy. (The app trusts Railway's
   `X-Forwarded-Proto`, so the `redirect_uri` it builds is `https://` —
   no `redirect_uri_mismatch`.)
5. **Attach a volume (optional but recommended).** Service → *Create
   Volume*, mount path `/data`. With a volume attached the app writes
   saved translations to `<mount path>/outputs` automatically, so the
   Files page survives redeploys. Without one, saved files live in the
   container filesystem and are lost on every deploy — the original
   trade-off below.

### Railway specifics worth knowing

- **Keep it at one replica.** Job progress is tracked in memory
  (`jobs/registry.py`), and a Railway volume can only attach to one
  container at a time. `railway.json` sets `numReplicas: 1` and
  `overlapSeconds: 0` (no overlapping old/new containers during a
  deploy) for exactly those two reasons.
- **Health check.** Railway polls `/healthz`, which is deliberately
  outside the login gate, and won't switch traffic to a new deploy
  until it answers.
- **Redeploys interrupt running jobs.** A deploy replaces the
  container, so an in-flight translation is lost and the browser gets
  the "server may have restarted" message. Just translate again.
- **Logs.** Gunicorn access and error logs go to stdout, so they show
  up in the service's Deploy Logs.

## What's deliberately not here

Per spec section 4, out of scope for this version:

- No database. Saved files are plain files on disk. Attaching a
  Railway volume (step 5 above) makes them survive redeploys; without
  one they live in the container filesystem and are lost on redeploy -
  that was an explicit trade-off, not an oversight.
- No revision history - only the latest saved version of a file is
  kept, and D6 automatically prunes anything past the
  `FILE_RETENTION_COUNT` most recent files.
- No multi-user support - one Google account, set by `ALLOWED_EMAIL`.
- The Custom API endpoint option (D8) is deferred - the provider
  dropdown currently offers Poe and Gemini only.

## If a translation job gets interrupted

Job progress lives in memory, not a database (spec section 7). If the
container restarts mid-job, that job is gone - just translate again.
The same applies if you try to save a job whose server process has
since restarted; you'll get a clear error rather than a silent
mismatch.
