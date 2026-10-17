"""Agent Routes"""

import json
import re
import uuid
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from agents.engine import AgentConfig, AgentEngine
from llm.router import get_router
from templates.registry import get_template, get_categories, TEMPLATES
import store

router = APIRouter()

# In-memory working set of custom agents (backed by disk via store.py)
_custom_agents: dict[str, AgentConfig] = {
    aid: AgentConfig(**cfg) for aid, cfg in store.get_custom_agents().items()
}


def _agent_exists(agent_id: str) -> bool:
    return get_template(agent_id) is not None or agent_id in _custom_agents


def _resolve_agent(agent_id: str) -> Optional[AgentConfig]:
    agent = get_template(agent_id)
    if not agent and agent_id in _custom_agents:
        agent = _custom_agents[agent_id]
    return agent


class AgentRunRequest(BaseModel):
    agent_id: str
    message: str
    model: Optional[str] = None
    session_id: Optional[str] = None
    history: Optional[List[dict]] = None


class AgentRunResponse(BaseModel):
    success: bool
    output: str
    agent_id: str
    tool_calls: List[str] = []
    tokens_used: int = 0
    error: Optional[str] = None


class StarRequest(BaseModel):
    delta: int = 1


class CreateAgentRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., max_length=500)
    category: str = Field(..., min_length=1, max_length=60)
    system_prompt: str = Field(..., min_length=1, max_length=8000)
    model: str = Field("llama3.2", max_length=100)
    tools: List[str] = []
    temperature: float = Field(0.7, ge=0.0, le=2.0)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v

    @field_validator("tools")
    @classmethod
    def _validate_tools(cls, v: List[str]) -> List[str]:
        from tools.registry import get_tool_registry
        valid = {t["name"] for t in get_tool_registry().list_tools()}
        unknown = [t for t in v if t not in valid]
        if unknown:
            raise ValueError(
                f"Unknown tools: {', '.join(unknown)}. Valid tools: {', '.join(sorted(valid))}"
            )
        return v


@router.get("/")
async def list_agents():
    """List all agents (templates + custom)"""
    all_agents = []
    stats = store.all_stats()

    # Add templates
    for t in TEMPLATES:
        st = stats.get(t.id, {})
        all_agents.append({
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "category": t.category,
            "tools": t.tools,
            "tags": t.tags,
            "author": t.author,
            "is_template": True,
            "run_count": st.get("run_count", 0),
            "star_count": st.get("star_count", 0),
        })

    # Add custom agents
    for aid, agent in _custom_agents.items():
        st = stats.get(aid, {})
        all_agents.append({
            "id": aid,
            "name": agent.name,
            "description": agent.description,
            "category": agent.category,
            "tools": agent.tools,
            "tags": agent.tags,
            "author": agent.author,
            "is_template": False,
            "run_count": st.get("run_count", 0),
            "star_count": st.get("star_count", 0),
        })

    return {"agents": all_agents, "total": len(all_agents)}


@router.get("/categories")
async def list_categories():
    """List all categories"""
    categories = get_categories()
    counts = {}
    for t in TEMPLATES:
        counts[t.category] = counts.get(t.category, 0) + 1

    return {
        "categories": [
            {"name": c, "count": counts.get(c, 0)}
            for c in categories
        ]
    }


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    """Get agent by ID"""
    agent = _resolve_agent(agent_id)
    if agent:
        return agent
    raise HTTPException(status_code=404, detail="Agent not found")


@router.post("/create")
async def create_agent(request: CreateAgentRequest):
    """Create a custom agent"""
    for t in TEMPLATES:
        if t.name.lower() == request.name.lower():
            raise HTTPException(status_code=409, detail="Agent name already exists")
    for agent in _custom_agents.values():
        if agent.name.lower() == request.name.lower():
            raise HTTPException(status_code=409, detail="Agent name already exists")

    agent_id = uuid.uuid4().hex[:12]

    agent = AgentConfig(
        id=agent_id,
        name=request.name,
        description=request.description,
        category=request.category,
        system_prompt=request.system_prompt,
        model=request.model,
        tools=request.tools,
        temperature=request.temperature,
        author="user",
        tags=[],
    )

    _custom_agents[agent_id] = agent
    store.put_custom_agent(agent.model_dump())

    return {"id": agent_id, "status": "created"}


@router.post("/{agent_id}/run")
async def increment_run(agent_id: str):
    """Increment the run counter for an agent"""
    if not _agent_exists(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")
    count = store.bump_run_count(agent_id)
    return {"agent_id": agent_id, "run_count": count}


@router.post("/{agent_id}/star")
async def star_agent(agent_id: str, request: StarRequest):
    """Adjust the star counter for an agent (delta 1 or -1, floored at 0)"""
    if not _agent_exists(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")
    count = store.adjust_star_count(agent_id, request.delta)
    return {"agent_id": agent_id, "star_count": count}


@router.post("/run", response_model=AgentRunResponse)
async def run_agent(request: AgentRunRequest):
    """Run an agent with a message"""
    agent_config = _resolve_agent(request.agent_id)

    if not agent_config:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Override model if specified (copy — never mutate the shared template)
    if request.model:
        agent_config = agent_config.model_copy(update={"model": request.model})

    # Create engine and run
    engine = AgentEngine(agent_config)
    result = await engine.run(
        message=request.message,
        history=request.history,
    )

    if result.success:
        store.bump_run_count(request.agent_id)

    return AgentRunResponse(
        success=result.success,
        output=result.output,
        agent_id=request.agent_id,
        tool_calls=result.tool_calls,
        tokens_used=result.tokens_used,
        error=result.error,
    )


@router.post("/stream")
async def stream_agent(request: AgentRunRequest):
    """Stream agent response via SSE"""
    agent_config = _resolve_agent(request.agent_id)
    if not agent_config:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Override model if specified (copy — never mutate the shared template)
    if request.model:
        agent_config = agent_config.model_copy(update={"model": request.model})

    async def event_stream():
        session_id = request.session_id or uuid.uuid4().hex[:8]
        yield f"data: {json.dumps({'type': 'start', 'session_id': session_id, 'agent_id': request.agent_id})}\n\n"

        try:
            engine = AgentEngine(agent_config)
            messages = [{"role": "system", "content": agent_config.system_prompt}]
            if request.history:
                messages.extend(request.history)
            messages.append({"role": "user", "content": request.message})

            # Run tools before streaming (same as engine.run does)
            tool_calls: List[str] = []
            if engine.tools:
                messages, tool_calls = await engine._execute_tools(
                    request.message, messages, tool_calls
                )
                for name in tool_calls:
                    yield f"data: {json.dumps({'type': 'tool', 'name': name})}\n\n"

            router = get_router()
            full = []
            async for token in router.stream(
                model=agent_config.model,
                messages=messages,
                temperature=agent_config.temperature,
            ):
                full.append(token)
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

            yield f"data: {json.dumps({'type': 'end', 'content': ''.join(full)})}\n\n"
            store.bump_run_count(request.agent_id)
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str):
    """Delete a custom agent"""
    if agent_id in _custom_agents:
        del _custom_agents[agent_id]
        store.remove_custom_agent(agent_id)
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Agent not found (templates cannot be deleted)")


def _safe_comment(text: str) -> str:
    return text.replace("\n", " ").replace("\r", " ")


def _python_identifier(name: str) -> str:
    ident = re.sub(r"[^0-9a-zA-Z]", "", name)
    if not ident:
        ident = "Agent"
    if ident[0].isdigit():
        ident = f"_{ident}"
    return ident


@router.get("/{agent_id}/export")
async def export_agent(agent_id: str, format: str = "python"):
    """Export agent as Python or TypeScript code"""
    agent = _resolve_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    tools_str = ", ".join(f'"{t}"' for t in agent.tools)
    header_comment = _safe_comment(agent.name)
    category_comment = _safe_comment(agent.category)
    tools_comment = _safe_comment(", ".join(agent.tools)) if agent.tools else "none"

    if format == "typescript":
        code = f'''// AgentVerse Hub Export - {header_comment}
// Category: {category_comment}
// Tools: {tools_comment}

export interface AgentConfig {{
  name: string;
  systemPrompt: string;
  model: string;
  tools: string[];
  temperature: number;
}}

export const agentConfig: AgentConfig = {{
  name: {json.dumps(agent.name)},
  systemPrompt: {json.dumps(agent.system_prompt)},
  model: {json.dumps(agent.model)},
  tools: [{tools_str}],
  temperature: {agent.temperature},
}};

export async function runAgent(message: string, history: Array<{{role: string, content: string}}> = []) {{
  const response = await fetch("/api/agents/run", {{
    method: "POST",
    headers: {{ "Content-Type": "application/json" }},
    body: JSON.stringify({{
      agent_id: {json.dumps(agent.id)},
      message,
      history,
    }}),
  }});
  return response.json();
}}
'''
    else:
        ident = _python_identifier(agent.name)
        code = f'''# {header_comment} - AgentVerse Hub Export
# Category: {category_comment}
# Tools: {tools_comment}

import httpx
from typing import List, Dict, Optional


class {ident}Agent:
    {agent.description!r}

    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.agent_id = {agent.id!r}
        self.config = {{
            "name": {agent.name!r},
            "system_prompt": {agent.system_prompt!r},
            "model": {agent.model!r},
            "tools": [{tools_str}],
            "temperature": {agent.temperature},
        }}

    async def run(self, message: str, history: Optional[List[Dict]] = None) -> Dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{{self.base_url}}/api/agents/run",
                json={{
                    "agent_id": self.agent_id,
                    "message": message,
                    "history": history or [],
                }},
                timeout=120,
            )
            return response.json()


# Usage
if __name__ == "__main__":
    import asyncio

    agent = {ident}Agent()
    result = asyncio.run(agent.run("Hello!"))
    print(result["output"])
'''

    return {"format": format, "code": code, "agent": agent.name}
