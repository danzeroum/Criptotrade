"""Simple registry for Model Context Protocol compatible tools."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict

ToolCallable = Callable[..., Any]


@dataclass
class MCPToolRegistry:
    """Registry that stores callables following the MCP style interface."""

    tools: Dict[str, ToolCallable] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.tools:
            self.register_core_tools()

    def register_tool(self, name: str) -> Callable[[ToolCallable], ToolCallable]:
        """Decorator used to register a new tool callable."""

        def decorator(func: ToolCallable) -> ToolCallable:
            self.tools[name] = func
            return func

        return decorator

    def register_core_tools(self) -> None:
        """Register a small set of baseline tools."""

        @self.register_tool("analyze_code_quality")
        def analyze_quality(file_path: str) -> Dict[str, Any]:
            return {"file": file_path, "complexity": 0, "coverage": 0, "issues": []}

        @self.register_tool("generate_tests")
        def generate_tests(code: str, framework: str = "pytest") -> str:
            return f"Tests for {framework} generated for snippet length {len(code)}"

        @self.register_tool("optimize_performance")
        def optimize_performance(code: str) -> Dict[str, Any]:
            return {"suggestions": [], "estimated_gain": "0%"}

    def execute(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """Execute a registered tool by name."""

        if name not in self.tools:
            raise KeyError(f"Tool '{name}' não registrada")
        return self.tools[name](*args, **kwargs)
