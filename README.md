# Cantonese Text Converter

Converts standard written Chinese (書面語) into genuine written Cantonese
(粵文) — real 係/唔/嘅/咗/佢/喺/冇 grammar, not standard Chinese with a
few Cantonese words swapped in. Personal, single-user tool. Built from
the locked System Specification Document (v1.0).

Paste text or upload `.txt` / `.srt` / `.docx`, pick a translation
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
extractors/    input parsing - pasted text, .txt, .srt, .docx
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

## Deploy to Zeabur

1. Push this repo to GitHub (or connect it however Zeabur expects).
2. Create a new Zeabur service from the repo - it will detect the
   `Dockerfile` automatically.
3. Set every variable from `.env.example` in Zeabur's environment
   variables panel. Zeabur injects `PORT` itself; you don't need to
   set it.
4. Update the Google OAuth redirect URI to your Zeabur domain once
   it's assigned, and redeploy.

## What's deliberately not here

Per spec section 4, out of scope for this version:

- No database, no persistent volume. Saved files live in the
  container's filesystem and are lost on redeploy - this was an
  explicit trade-off, not an oversight.
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
