# 🚀 AgentVerse Hub

**AI Agent Marketplace** - Build, test, and share AI agents with multi-model support.

## ✨ Features

- **65+ Agent Templates** - Ready-to-use agents across Writing, Coding, Research, Marketing
- **Multi-Model Support** - OpenAI, Anthropic, Ollama, Google
- **Agent Builder** - Create custom agents with system prompts and tools
- **Tool Integration** - Web search, code execution, file operations
- **Live Testing** - Test agents in browser

## 🛠️ Tech Stack

- **Frontend:** React + Vite + Tailwind CSS
- **Backend:** FastAPI (Python)
- **LLM:** Multi-provider router (Ollama, OpenAI, Anthropic, Google)
- **Tools:** DuckDuckGo search, code execution, file ops

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- Ollama (for local models)

### Backend Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
cp ..\.env ..\.env.local  # Edit with your config
python -m uvicorn main:app --reload --port 8001
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3001

## 📦 Agent Categories

| Category | Count | Description |
|----------|-------|-------------|
| Writing | 15 | Content, copy, technical writing |
| Coding | 20 | Development, debugging, review |
| Research | 15 | Analysis, market research, data |
| Marketing | 15 | SEO, social media, growth |

## 🔧 Tools

- **Web Search** - DuckDuckGo integration
- **Code Execution** - Python/JavaScript
- **File Operations** - Read/write files

## 📝 API Endpoints

- `GET /api/agents/` - List all agents
- `GET /api/agents/categories` - List categories
- `GET /api/agents/{id}` - Get agent details
- `POST /api/agents/run` - Run an agent
- `POST /api/agents/create` - Create custom agent
- `DELETE /api/agents/{id}` - Delete custom agent

## 🤝 Contributing

1. Fork the repo
2. Create your feature branch
3. Commit your changes
4. Open a pull request

## 📄 License

MIT License

---

**Built with ❤️ by Priyanshu**
