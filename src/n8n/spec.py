"""
WorkflowSpec: Intermediate representation between LLM and native n8n JSON.

Models:
- NodeSpec: a logical node (kind, params, ref)
- EdgeSpec: connection between nodes (src -> dst)
- WorkflowSpec: the complete workflow definition
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class NodeSpec(BaseModel):
    """Logical node in a workflow.
    
    Attributes:
        ref: stable handle used by LLM, e.g. "trigger", "http1", "email_send"
        kind: logical kind - "schedule" | "webhook" | "http" | "set" | "if" | "email" | "manual"
        label: human display name; defaults from kind if not provided
        params: kind-specific parameters (url, cron, to_address, etc.)
    """
    ref: str = Field(..., description="Unique stable reference for this node")
    kind: str = Field(..., description="Node kind: manual, webhook, schedule, http, set, if, email")
    label: Optional[str] = Field(None, description="Display name; defaults from kind")
    params: Dict[str, Any] = Field(default_factory=dict, description="Kind-specific parameters")


class EdgeSpec(BaseModel):
    """Connection between two nodes.
    
    Attributes:
        src: source node ref (must match a NodeSpec.ref)
        dst: destination node ref (must match a NodeSpec.ref)
        branch: output port - "main" (default), "true", or "false" (for IF nodes)
    """
    src: str = Field(..., description="Source node ref")
    dst: str = Field(..., description="Destination node ref")
    branch: str = Field("main", description="Output branch: main, true, or false")


class WorkflowSpec(BaseModel):
    """Complete workflow definition.
    
    Attributes:
        name: workflow name, displayed in n8n UI
        nodes: list of node specifications
        edges: list of edge specifications (connections)
        activate: whether to auto-activate after creation (default: False)
    """
    name: str = Field(..., description="Workflow name")
    nodes: List[NodeSpec] = Field(default_factory=list, description="List of nodes")
    edges: List[EdgeSpec] = Field(default_factory=list, description="List of edges")
    activate: bool = Field(False, description="Auto-activate after creation")

    def get_node_by_ref(self, ref: str) -> Optional[NodeSpec]:
        """Find a node by its ref."""
        for node in self.nodes:
            if node.ref == ref:
                return node
        return None
