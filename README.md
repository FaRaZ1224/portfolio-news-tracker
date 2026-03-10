# Portfolio News Tracker (Initialized Portfolio)

Tracks companies from Initialized’s portfolio and generates a short **2–3 sentence** “what’s happening” summary per company based on recent news mentions.

## Deployed URLs

- **Frontend (Netlify)**: https://portfolio-news-tracker.netlify.app
- **Backend (Render)**: https://portfolio-news-tracker.onrender.com

## Run locally

### Prerequisites

- Node.js (18+ recommended)
- Python 3.12+
- A PostgreSQL database (Supabase recommended)

### 1) Backend (FastAPI)

From the repo root:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `backend/.env`:

```bash
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/postgres?sslmode=require
OPENAI_API_KEY=YOUR_OPENAI_KEY
NEWSAPI_KEY=YOUR_NEWSAPI_KEY   # optional fallback
CORS_ALLOW_ORIGINS=http://localhost:3000
```

Start the API:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Sanity check:

- http://localhost:8000/health

### 2) Frontend (Next.js)

From the repo root:

```bash
cd frontend
npm install
```

Create `frontend/.env.local`:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Start the web app:

```bash
npm run dev
```

Open:

- http://localhost:3000

## How summaries are generated

- Click **Refresh** (one company) or **Refresh All**.
- The backend discovers recent articles for the company.
- It extracts article text (when possible) and calls an LLM to generate a concise 2–3 sentence summary.
- The summary is stored in Postgres and returned via `GET /companies`.

## Data Pipeline Design

### Scraping (company ingestion)

- **Source**: https://initialized.com/companies
- **Implementation**: `backend/app/services/scraper.py`
- **Approach**:
  - Prefer the site’s Next.js data feed (more structured/complete than DOM scraping).
  - Fall back to DOM parsing if needed.
  - Normalize URLs (relative → absolute) and filter obvious non-company tokens (asset filenames / category labels).
  - Upsert into the `companies` table.

### News discovery

- **Implementation**: `backend/app/services/news.py`
- **Primary**: Google News RSS search for the company name.
- **Fallback**: NewsAPI (`/v2/everything`) if RSS returns no recent results.
- **Relevance**:
  - Company name is wrapped in quotes (exact-phrase match) to reduce noise for ambiguous names.
- **Recency windows**:
  - Tries smaller windows first (e.g. 7/14 days) and expands if needed.

### Data modeling

- **Implementation**: `backend/app/models.py`
- **Tables**:
  - `companies`: core entity with `name`, `website`, `sector`, `logo_url`.
  - `articles`: discovered mentions (unique per `company_id + url`), stores title/source/date/snippet and extracted `content_text`.
  - `summaries`: one row per company (1:1) containing the latest generated summary + timestamp.
- **API shape**:
  - `GET /companies` returns each company with its stored summary (and articles may exist in the DB even if not shown in the UI).

### AI integration

- **Implementation**: `backend/app/services/summarizer.py`
- **Model**: OpenAI `gpt-4o-mini`
- **Inputs**:
  - Uses up to 2–3 of the most recent mentions per company.
  - Prefers full extracted `ArticleText` when available; falls back to title/snippet.
- **Output**:
  - A strict **2–3 sentence** company-level summary describing recent developments.
- **Triggering**:
  - Generated on-demand via `POST /refresh/{company_id}` or `POST /refresh-all`.

### Are the summaries useful? Is the prompt designed well?

- **Usefulness**:
  - Designed for quick scanning: you get a compact “what happened recently” snapshot per company.
  - When articles lack concrete business updates, the system returns a clear fallback instead of hallucinating.
- **Prompt design**:
  - Strong factual constraints (no speculation) and a defined set of “business development” categories.
  - Explicit prioritization of extracted article text over titles/snippets.

### Edge cases

- **Rate limits / provider failures**:
  - `Refresh All` runs sequentially (company-by-company) to reduce burst load and rate-limit risk.
  - If the LLM call fails, the backend stores a safe fallback summary and surfaces an error string in the refresh response.
- **Empty or irrelevant results**:
  - If no usable recent mentions are found, the summary is set to:
    - `No clear recent company announcements were reported in the available articles.`
- **Extraction failures**:
  - If article text extraction fails, summarization can still proceed using titles/snippets.

## AI tools used

- **OpenAI Chat Completions** via the `openai` Python SDK
  - Model: `gpt-4o-mini`
  - Used for: company-level news summary generation

## Design decisions / tradeoffs

- **Company-level summary only**: We intentionally do not display the raw article list in the UI; the product goal is a quick “what’s happening” snapshot.
- **Phrase-quoted queries for relevance**: News queries wrap the company name in quotes to reduce noise for ambiguous names.
- **Sequential Refresh All**: `Refresh All` processes companies one-by-one to avoid overwhelming upstream services (news sources, extraction, OpenAI) and to reduce rate-limit risk. This is slower but more reliable.
- **Startup stability**: The backend does not hard-fail on boot if the database is temporarily unreachable (helps keep the Render web service online), but DB-backed endpoints still require a working `DATABASE_URL`.

## Notes

- If summaries are not generating in production, verify Render has a valid `OPENAI_API_KEY` configured.
- If the backend cannot connect to Supabase, confirm your pooler connection string and credentials in Render’s `DATABASE_URL` (including `sslmode=require`).
