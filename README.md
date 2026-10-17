# AgentVerse Hub

**AI Agent Marketplace** — build, test, stream, and share AI agents with multi-model support.

[![CI](https://github.com/priyanshuprajapati987/agentverse-hub/actions/workflows/ci.yml/badge.svg)](https://github.com/priyanshuprajapati987/agentverse-hub/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![React 18](https://img.shields.io/badge/react-18-61dafb.svg)](https://reactjs.org)
[![Tests](https://img.shields.io/badge/tests-134%20passing-brightgreen.svg)](#-tests)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

---

## Highlights

- **100+ agent templates** — ready-to-use agents across Writing, Coding, Research, Marketing, Design, Business, Education, and Productivity.
- **Multi-model** — Ollama (local), OpenAI, Anthropic, Google through one router.
- **Live streaming** — SSE token streaming in the browser chat UI, with stop support.
- **Agent builder** — create custom agents with system prompt, tools, model, and temperature.
- **Agent export** — export any agent as Python or TypeScript code.
- **Favorites & runs** — star agents, filter to your Starred list, track run counts, sort by Popular or A–Z.
- **Tool integration** — DuckDuckGo web search, code execution, file operations.
- **Security layer** — rate limiting, input sanitization, and optional API-key auth built in.
- **Docker ready** — one-command deploy with docker-compose.

---

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- [Ollama](https://ollama.com) (for local models — optional if using cloud keys)

### Backend (port 8001)

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows (use `source venv/bin/activate` on macOS/Linux)
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8001
```

### Frontend (port 3001)

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:3001**

### Docker

```bash
docker-compose up -d
# Backend :8001 + frontend :3001

# Uses host Ollama by default (host.docker.internal:11434)
# Override: OLLAMA_URL=http://your-ollama:11434 docker-compose up -d
```

---

## Configuration

```env
# LLM providers — at least one required
OLLAMA_URL=http://localhost:11434
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Security (optional)
AGENTVERSE_API_KEY=           # enable API-key auth when set
RATE_LIMIT_CAPACITY=30        # burst size per client
RATE_LIMIT_REFILL=0.5         # tokens per second
AGENTVERSE_CORS_ORIGINS=http://localhost:3001,http://localhost:5173
```

---

## Security

The backend ships a middleware layer (`backend/security.py`) that is on by default:

| Control | Behavior |
|---------|----------|
| **Rate limiting** | Token-bucket per client — default burst 30, refill 0.5/s (env-configurable). Exceeding it returns `429`. |
| **Input sanitization** | Every JSON body is scrubbed of XSS (`<script>`/`<iframe>`), SQL injection keywords, path traversal (`../`), and null bytes before it reaches your agents. |
| **API-key auth** | Off by default. Set `AGENTVERSE_API_KEY` to require `x-api-key: <key>` or `Authorization: Bearer <key>` on all non-public routes. Constant-time comparison. |
| **CORS** | Explicit origin allowlist — no wildcard. Configure via `AGENTVERSE_CORS_ORIGINS`. |

---

## API

Interactive docs while running: **http://localhost:8001/docs**

| Method | Path | Purpose |
|--------|------|---------|
| `GET`  | `/api/agents/` | List all agents |
| `GET`  | `/api/agents/categories` | List categories with counts |
| `GET`  | `/api/agents/{id}` | Get agent details (`404` if unknown) |
| `POST` | `/api/agents/run` | Run an agent (full reply) |
| `POST` | `/api/agents/stream` | **SSE streaming** reply (start / token / end / error events) |
| `POST` | `/api/agents/create` | Create a custom agent |
| `DELETE` | `/api/agents/{id}` | Delete a custom agent (templates are protected) |
| `GET`  | `/api/agents/{id}/export?format=python\|typescript` | Export agent as code |

### Streaming example

```bash
curl -N -X POST http://localhost:8001/api/agents/stream \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "content-writer", "message": "Write a haiku about code"}'
```

```
data: {"type": "start", "session_id": "a1b2c3d4", "agent_id": "content-writer"}
data: {"type": "token", "content": "Sil"}
data: {"type": "token", "content": "ent "}
...
data: {"type": "end", "content": "full response text"}
```

---

## Agent Categories

| Category | Count | Description |
|----------|------:|-------------|
| Writing | 15 | Content, copy, technical writing |
| Coding | 20 | Development, debugging, review |
| Research | 15 | Analysis, market research, data |
| Marketing | 15 | SEO, social media, growth |
| Design | 10 | UI/UX, branding, visual design |
| Business | 10 | Strategy, finance, operations |
| Education | 8 | Teaching, tutoring, curriculum |
| Productivity | 8 | Planning, automation, workflows |

## Tools

- **Web Search** — DuckDuckGo integration
- **Code Execution** — Python / JavaScript
- **File Operations** — read / write

---

## Tests

```bash
cd backend
python -m pytest -q
```

**134 tests passing** across three suites:

| Suite | Count | Covers |
|-------|------:|--------|
| `test_api.py` | 47 | templates, engine, tools, router, API endpoints |
| `test_security.py` | 40 | sanitizer, token-bucket, rate limiter, API-key auth, middleware |
| `test_edge_cases.py` | 47 | SSE streaming, export, custom agents, templates, engine, router |

CI runs lint (`ruff`) + the full suite + a frontend build on every push.

---

## Project Structure

```
agentverse-hub/
├── backend/
│   ├── main.py            # App entry + middleware wiring
│   ├── security.py        # Rate limit / sanitizer / auth
│   ├── routes/            # agents + health endpoints (run, stream, export)
│   ├── agents/            # Agent engine (config, tools, results)
│   ├── llm/               # Multi-provider router with streaming
│   ├── templates/         # 100+ agent template registry
│   └── tools/             # Web search, code exec, files
├── frontend/              # React + Vite + Tailwind
├── docker-compose.yml
└── .github/workflows/     # CI (lint + test + build)
```

---

## Contributing

1. Fork the repo
2. Create your feature branch
3. Commit your changes
4. Open a pull request

## License

MIT License

---

**Built with ❤️ by [Priyanshu](https://github.com/priyanshuprajapati987)**
