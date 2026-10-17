"""Agent Routes"""

import json
import uuid
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from agents.engine import AgentConfig, AgentEngine
from llm.router import get_router
from templates.registry import get_templates, get_template, get_categories, TEMPLATES

router = APIRouter()

# In-memory agent storage (for now)
_custom_agents = {}


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


class CreateAgentRequest(BaseModel):
    name: str
    description: str
    category: str
    system_prompt: str
    model: str = "llama3.2"
    tools: List[str] = []
    temperature: float = 0.7


@router.get("/")
async def list_agents():
    """List all agents (templates + custom)"""
    all_agents = []
    
    # Add templates
    for t in TEMPLATES:
        all_agents.append({
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "category": t.category,
            "tools": t.tools,
            "tags": t.tags,
            "author": t.author,
            "is_template": True,
        })
    
    # Add custom agents
    for aid, agent in _custom_agents.items():
        all_agents.append({
            "id": aid,
            "name": agent.name,
            "description": agent.description,
            "category": agent.category,
            "tools": agent.tools,
            "tags": agent.tags,
            "author": agent.author,
            "is_template": False,
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
    # Check templates first
    template = get_template(agent_id)
    if template:
        return template
    
    # Check custom agents
    if agent_id in _custom_agents:
        return _custom_agents[agent_id]
    
    raise HTTPException(status_code=404, detail="Agent not found")


@router.post("/create")
async def create_agent(request: CreateAgentRequest):
    """Create a custom agent"""
    import hashlib
    
    agent_id = hashlib.md5(f"{request.name}{request.system_prompt}".encode()).hexdigest()[:12]
    
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
    
    return {"id": agent_id, "status": "created"}


@router.post("/run", response_model=AgentRunResponse)
async def run_agent(request: AgentRunRequest):
    """Run an agent with a message"""
    # Get agent config
    agent_config = get_template(request.agent_id)
    
    if not agent_config and request.agent_id in _custom_agents:
        agent_config = _custom_agents[request.agent_id]
    
    if not agent_config:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Override model if specified
    if request.model:
        agent_config.model = request.model
    
    # Create engine and run
    engine = AgentEngine(agent_config)
    result = await engine.run(
        message=request.message,
        history=request.history,
    )
    
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
    agent_config = get_template(request.agent_id)
    if not agent_config and request.agent_id in _custom_agents:
        agent_config = _custom_agents[request.agent_id]
    if not agent_config:
        raise HTTPException(status_code=404, detail="Agent not found")

    if request.model:
        agent_config.model = request.model

    async def event_stream():
        session_id = request.session_id or uuid.uuid4().hex[:8]
        yield f"data: {json.dumps({'type': 'start', 'session_id': session_id, 'agent_id': request.agent_id})}\n\n"

        try:
            engine = AgentEngine(agent_config)
            messages = [{"role": "system", "content": agent_config.system_prompt}]
            if request.history:
                messages.extend(request.history)
            messages.append({"role": "user", "content": request.message})

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
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Agent not found (templates cannot be deleted)")


@router.get("/{agent_id}/export")
async def export_agent(agent_id: str, format: str = "python"):
    """Export agent as Python or TypeScript code"""
    agent = get_template(agent_id)
    if not agent and agent_id in _custom_agents:
        agent = _custom_agents[agent_id]
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    tools_str = ", ".join(f'"{t}"' for t in agent.tools)

    if format == "typescript":
        code = f'''// AgentVerse Hub Export - {agent.name}
// Category: {agent.category}
// Tools: {', '.join(agent.tools) if agent.tools else 'none'}

export interface AgentConfig {{
  name: string;
  systemPrompt: string;
  model: string;
  tools: string[];
  temperature: number;
}}

export const agentConfig: AgentConfig = {{
  name: "{agent.name}",
  systemPrompt: `{agent.system_prompt.replace('`', "'")}`,
  model: "{agent.model}",
  tools: [{tools_str}],
  temperature: {agent.temperature},
}};

export async function runAgent(message: string, history: Array<{{role: string, content: string}}> = []) {{
  const response = await fetch("/api/agents/run", {{
    method: "POST",
    headers: {{ "Content-Type": "application/json" }},
    body: JSON.stringify({{
      agent_id: "{agent.id}",
      message,
      history,
    }}),
  }});
  return response.json();
}}
'''
    else:
        code = f'''"""
{agent.name} - AgentVerse Hub Export
Category: {agent.category}
Tools: {', '.join(agent.tools) if agent.tools else 'none'}
"""

import httpx
from typing import List, Dict, Optional


class {agent.name.replace(" ", "").replace("-", "").replace("_", "")}Agent:
    """{agent.description}"""

    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.agent_id = "{agent.id}"
        self.config = {{
            "name": "{agent.name}",
            "system_prompt": """{agent.system_prompt}""",
            "model": "{agent.model}",
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

    agent = {agent.name.replace(" ", "").replace("-", "").replace("_", "")}Agent()
    result = asyncio.run(agent.run("Hello!"))
    print(result["output"])
'''

    return {"format": format, "code": code, "agent": agent.name}
