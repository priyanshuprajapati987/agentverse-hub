"""Tool Registry"""

from typing import Optional, Any
from dataclasses import dataclass
import httpx


@dataclass
class ToolResult:
    success: bool
    output: str
    error: Optional[str] = None


class WebSearchTool:
    """Web search using DuckDuckGo"""
    
    async def search(self, query: str, max_results: int = 5) -> ToolResult:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.duckduckgo.com/",
                    params={"q": query, "format": "json", "no_html": 1},
                    timeout=10.0,
                )
                data = response.json()
                
                results = []
                for item in data.get("RelatedTopics", [])[:max_results]:
                    if isinstance(item, dict) and "Text" in item:
                        results.append(item["Text"])
                    elif isinstance(item, dict) and "Topics" in item:
                        for sub in item["Topics"][:2]:
                            if "Text" in sub:
                                results.append(sub["Text"])
                
                if results:
                    return ToolResult(success=True, output="\n".join(results))
                return ToolResult(success=True, output=f"No results found for: {query}")
                
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class CodeExecutionTool:
    """Execute Python/JavaScript code"""
    
    async def execute(self, code: str, language: str = "python") -> ToolResult:
        import asyncio
        
        try:
            if language == "python":
                proc = await asyncio.create_subprocess_exec(
                    "python", "-c", code,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            elif language == "javascript":
                proc = await asyncio.create_subprocess_exec(
                    "node", "-e", code,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                return ToolResult(success=False, output="", error=f"Unsupported language: {language}")
            
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            
            if proc.returncode == 0:
                output = stdout.decode().strip()
                return ToolResult(success=True, output=output or "(no output)")
            else:
                error = stderr.decode().strip()
                return ToolResult(success=False, output="", error=error)
                
        except asyncio.TimeoutError:
            return ToolResult(success=False, output="", error="Execution timed out (30s)")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class FileOpsTool:
    """File operations"""
    
    async def read_file(self, path: str) -> ToolResult:
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            return ToolResult(success=True, output=content)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
    
    async def write_file(self, path: str, content: str) -> ToolResult:
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return ToolResult(success=True, output=f"Written to {path}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class ToolRegistry:
    """Registry of available tools"""
    
    def __init__(self):
        self.tools = {
            "web_search": WebSearchTool(),
            "code_execution": CodeExecutionTool(),
            "file_ops": FileOpsTool(),
        }
    
    def get_tool(self, name: str) -> Optional[Any]:
        return self.tools.get(name)
    
    def has_tool(self, name: str) -> bool:
        return name in self.tools
    
    def list_tools(self) -> list:
        return [
            {"name": "web_search", "description": "Search the web"},
            {"name": "code_execution", "description": "Execute code"},
            {"name": "file_ops", "description": "File operations"},
        ]


_registry: Optional[ToolRegistry] = None

def get_tool_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
