"""Agent Execution Engine"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from pydantic import BaseModel
from llm.router import get_router


class AgentConfig(BaseModel):
    """Agent configuration"""
    id: str
    name: str
    description: str
    category: str
    system_prompt: str
    model: str = "llama3.2"
    tools: List[str] = []
    temperature: float = 0.7
    max_tokens: int = 4096
    author: str = "system"
    tags: List[str] = []


@dataclass
class AgentResult:
    """Agent execution result"""
    success: bool
    output: str
    tool_calls: List[str] = field(default_factory=list)
    tokens_used: int = 0
    error: Optional[str] = None


class AgentEngine:
    """Execute agents with tool support"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.router = get_router()
        self.tools = self._load_tools(config.tools)
    
    def _load_tools(self, tool_names: List[str]) -> Dict[str, Any]:
        """Load tools by name"""
        from tools.registry import get_tool_registry
        registry = get_tool_registry()
        return {name: registry.get_tool(name) for name in tool_names if registry.has_tool(name)}
    
    async def run(
        self,
        message: str,
        history: List[Dict] = None,
    ) -> AgentResult:
        """Run agent with message"""
        try:
            # Build messages
            messages = [{"role": "system", "content": self.config.system_prompt}]
            
            # Add history
            if history:
                messages.extend(history)
            
            # Add user message
            messages.append({"role": "user", "content": message})
            
            # Check if tools needed
            tool_calls = []
            if self.tools:
                messages, tool_calls = await self._execute_tools(message, messages, tool_calls)
            
            # Generate response
            response = await self.router.generate(
                model=self.config.model,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )
            
            return AgentResult(
                success=True,
                output=response.content,
                tool_calls=tool_calls,
                tokens_used=response.tokens_used,
            )
            
        except Exception as e:
            return AgentResult(
                success=False,
                output="",
                error=str(e),
            )
    
    async def _execute_tools(
        self,
        message: str,
        messages: List[Dict],
        tool_calls: List[str],
    ) -> tuple:
        """Execute tools based on message content"""
        message_lower = message.lower()
        
        # Web search
        if "web_search" in self.tools and any(kw in message_lower for kw in ["search", "find", "look up", "latest", "current"]):
            query = self._extract_search_query(message)
            if query:
                tool = self.tools["web_search"]
                result = await tool.search(query)
                tool_calls.append("web_search")
                if result.success:
                    messages.append({
                        "role": "system",
                        "content": f"Search results:\n{result.output}"
                    })
        
        # Code execution
        elif "code_execution" in self.tools and any(kw in message_lower for kw in ["run", "execute", "test"]):
            code = self._extract_code(message)
            if code:
                tool = self.tools["code_execution"]
                lang = self._detect_language(code)
                result = await tool.execute(code, lang)
                tool_calls.append("code_execution")
                if result.success:
                    messages.append({
                        "role": "system",
                        "content": f"Code output:\n{result.output}"
                    })
        
        return messages, tool_calls
    
    def _extract_search_query(self, message: str) -> str:
        """Extract search query"""
        prefixes = ["search for ", "search ", "find ", "look up "]
        query = message
        for prefix in prefixes:
            if query.lower().startswith(prefix):
                query = query[len(prefix):]
                break
        return query.strip()
    
    def _extract_code(self, message: str) -> Optional[str]:
        """Extract code from message"""
        if "```" in message:
            parts = message.split("```")
            if len(parts) >= 2:
                return parts[1].strip()
        return None
    
    def _detect_language(self, code: str) -> str:
        """Detect programming language"""
        if "def " in code or "import " in code or "print(" in code:
            return "python"
        elif "function " in code or "console.log" in code:
            return "javascript"
        return "python"
