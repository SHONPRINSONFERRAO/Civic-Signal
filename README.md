# CivicSignal

CivicSignal is a hackathon MVP for **AI for Better Living and Smarter Communities**. It helps city teams turn citizen complaints into prioritized action with a single-page dashboard, explainable AI labels, and natural-language Q&A.

## What it does

- Loads a built-in complaint dataset or accepts CSV upload
- Categorizes issues and scores urgency
- Surfaces area hotspots and recommended city actions
- Answers questions like:
  - `What are the top three issues?`
  - `Which area needs attention first?`
  - `What actions should the city take this week?`

## Tech fit

- **Google Cloud story**: Gemini, Vertex AI, BigQuery, Cloud Run
- **Local MVP runtime**: Python standard library + static HTML/CSS/JS
- **Production AI path**: on Cloud Run, set `GOOGLE_CLOUD_PROJECT` and `VERTEX_LOCATION` to use Vertex AI with the service account automatically
- **Fallback AI path**: if `GOOGLE_API_KEY` or `GEMINI_API_KEY` is set, the app will use the Gemini API; otherwise it uses a local heuristic engine so the demo still works offline

## Run locally

```bash
python3 src/server.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Push to Git

```bash
git init
git add .
git commit -m "Initial CivicSignal MVP"
```

Then connect your remote and push:

```bash
git remote add origin <your-repo-url>
git branch -M main
git push -u origin main
```

## Deploy to Cloud Run

This repo includes a `Dockerfile` and is ready to containerize.

## Project structure

```text
src/              backend server and AI integration
web/              frontend entry page
web/assets/       frontend JavaScript and styles
data/samples/     demo complaint dataset
```

1. Authenticate and choose your project:

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

2. Build the container:

```bash
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/civicsignal
```

3. Deploy to Cloud Run:

```bash
gcloud run deploy civicsignal \
  --image gcr.io/YOUR_PROJECT_ID/civicsignal \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

4. Optional: add Gemini API access for live AI answers:

```bash
gcloud run services update civicsignal \
  --region us-central1 \
  --set-env-vars GEMINI_API_KEY=your_key_here
```

If you use Vertex AI auth instead of an API key, replace the current Gemini adapter with Vertex credentials at deploy time.

### Vertex AI production setup

For Cloud Run production mode, prefer Vertex AI with the Cloud Run service account:

```bash
gcloud run deploy civicsignal \
  --image gcr.io/YOUR_PROJECT_ID/civicsignal \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID,VERTEX_LOCATION=us-central1
```

The service account used by Cloud Run must have Vertex AI permissions such as `Vertex AI User`.

Optional model override:

```bash
gcloud run services update civicsignal \
  --region us-central1 \
  --set-env-vars VERTEX_MODEL=gemini-1.5-flash
```

## CSV format

Required columns:

- `timestamp`
- `area`
- `description`

Optional columns:

- `id`
- `category_raw`
- `source`
- `status`

## Deployment story

- Deploy the app container to Cloud Run
- Replace local file-backed records with BigQuery tables
- Point the AI adapter to Gemini on Vertex AI for classification, summarization, and Q&A
