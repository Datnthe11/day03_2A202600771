"""
N8n integration for ReActAgent.

Modules:
- spec: WorkflowSpec, NodeSpec, EdgeSpec (Pydantic models)
- registry: Node registry and builders
- compiler: WorkflowSpec -> native n8n JSON
- client: N8nClient (REST API wrapper)
- tools: Tool definitions and execution
"""

from src.n8n.spec import WorkflowSpec, NodeSpec, EdgeSpec
from src.n8n.client import N8nClient, AuthError, BadWorkflowError, NotFoundError, N8nUnavailableError
from src.n8n.tools import create_n8n_tools
from src.n8n.compiler import compile_spec, validate_spec

__all__ = [
    "WorkflowSpec",
    "NodeSpec",
    "EdgeSpec",
    "N8nClient",
    "create_n8n_tools",
    "compile_spec",
    "validate_spec",
    "AuthError",
    "BadWorkflowError",
    "NotFoundError",
    "N8nUnavailableError",
]
