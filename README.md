# ownAi

Audio intelligence: upload an audio file, get a transcript and an AI analysis (summary, topics, sentiment, action items, language).

- **Backend:** Python 3.11, FastAPI, MongoDB (motor), JWT auth, OpenAI API
- **Frontend:** Vue 3 + Vite + Pinia + Vue Router
- **No Docker.** MongoDB runs locally (Homebrew, mongod, or Atlas URI).

## Project layout

```
ownAi/
├── backend/
│   ├── Pipfile
│   ├── .env.example
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── database.py
│       ├── auth.py
│       ├── models.py
│       ├── openai_service.py
│       └── routers/
│           ├── auth.py
│           └── transcriptions.py
└── frontend/
    ├── package.json
    ├── vite.config.js
    ├── index.html
    └── src/
        ├── main.js, App.vue, router.js, api.js, style.css
        ├── stores/auth.js
        ├── components/AppHeader.vue
        └── views/{Login,Register,Dashboard,Upload,Transcription}View.vue
```

## Backend — setup

Prerequisites: Python 3.11, Pipenv, a running MongoDB.

```bash
cd backend
cp .env.example .env
# edit .env — set OPENAI_API_KEY, JWT_SECRET, MONGO_URI

pipenv install
pipenv run uvicorn app.main:app --reload --port 8000
```

API will be at `http://localhost:8000`, Swagger UI at `http://localhost:8000/docs`.

### Env vars

| Variable | Default | Notes |
|---|---|---|
| `MONGO_URI` | `mongodb://localhost:27017` | |
| `MONGO_DB` | `ownai` | |
| `JWT_SECRET` | `change-me` | Use a long random string |
| `JWT_ALGORITHM` | `HS256` | |
| `JWT_EXPIRE_MINUTES` | `10080` | 7 days |
| `OPENAI_API_KEY` | — | **required** |
| `OPENAI_TRANSCRIBE_MODEL` | `gpt-4o-transcribe` | also: `gpt-4o-mini-transcribe`, `whisper-1` |
| `OPENAI_ANALYSIS_MODEL` | `gpt-4o-mini` | |
| `CORS_ORIGINS` | `http://localhost:5173` | comma-separated |

### API

- `POST /api/auth/register` `{name, email, password}` → `{access_token, user}`
- `POST /api/auth/login-json` `{email, password}` → `{access_token, user}`
- `POST /api/auth/login` (OAuth2 form) → `{access_token, user}`
- `GET  /api/auth/me`
- `POST /api/transcriptions` (multipart `file=...`) → creates + transcribes + analyzes
- `GET  /api/transcriptions`
- `GET  /api/transcriptions/{id}`
- `DELETE /api/transcriptions/{id}`

All `/api/transcriptions/*` and `/api/auth/me` require `Authorization: Bearer <token>`.

## Frontend — setup

Prerequisites: Node 18+.

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The dev server proxies `/api` → `http://localhost:8000`, so no CORS issues.

## Running MongoDB locally (macOS)

```bash
brew tap mongodb/brew
brew install mongodb-community@7.0
brew services start mongodb-community@7.0
```

Or use a free Atlas cluster and put the URI in `backend/.env`.

## Notes

- Audio file size capped at 25 MB (OpenAI limit).
- Supported formats: mp3, wav, m4a, ogg, webm, mp4, flac.
- Transcription is synchronous — the request blocks until OpenAI returns. For long files, expect a multi-second wait.
