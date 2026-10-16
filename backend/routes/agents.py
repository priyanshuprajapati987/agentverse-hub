"""Agent Routes"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from agents.engine import AgentConfig, AgentEngine
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


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str):
    """Delete a custom agent"""
    if agent_id in _custom_agents:
        del _custom_agents[agent_id]
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Agent not found (templates cannot be deleted)")
