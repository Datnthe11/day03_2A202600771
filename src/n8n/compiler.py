"""
Compiler: Converts WorkflowSpec (intermediate repr.) to native n8n workflow JSON.

Handles:
- Validation of the spec structure
- Node position assignment (left-to-right topological)
- Connection building (spec edges -> n8n connections)
- Final JSON assembly
"""

import uuid
from typing import List, Dict, Any, Set, Tuple, Optional
from src.n8n.spec import WorkflowSpec, NodeSpec, EdgeSpec
from src.n8n.registry import (
    get_node_type,
    get_node_version,
    build_node_params,
    validate_node_params,
    is_trigger_kind,
    NODE_REGISTRY,
)


class ValidationError(Exception):
    """Raised when spec validation fails."""
    pass


class CompilationError(Exception):
    """Raised when compilation to n8n JSON fails."""
    pass


def validate_spec(spec: WorkflowSpec) -> List[str]:
    """
    Validate a WorkflowSpec. Return list of errors (empty = valid).
    
    Checks:
    - At least one node
    - Exactly one trigger node (manual/webhook/schedule)
    - All edge endpoints exist
    - No unknown node kinds
    - All required params present for each node
    - No cycles (must be a DAG)
    - No orphan/unreachable nodes
    """
    errors = []
    
    # Check: has nodes
    if not spec.nodes:
        errors.append("Workflow must have at least one node")
        return errors
    
    # Build node ref set
    node_refs = {node.ref for node in spec.nodes}
    
    # Check: exactly one trigger
    triggers = [n for n in spec.nodes if is_trigger_kind(n.kind)]
    if len(triggers) == 0:
        errors.append("Workflow must have exactly one trigger node (manual, webhook, or schedule)")
    elif len(triggers) > 1:
        errors.append(f"Workflow can have only one trigger node; found {len(triggers)}")
    
    # Check: all node kinds are known
    for node in spec.nodes:
        if node.kind not in NODE_REGISTRY:
            errors.append(f"Unknown node kind: '{node.kind}' in node '{node.ref}'")
    
    # Check: all required params present
    for node in spec.nodes:
        param_errors = validate_node_params(node.kind, node.params)
        errors.extend([f"Node '{node.ref}': {e}" for e in param_errors])
    
    # Check: all edge endpoints exist
    for edge in spec.edges:
        if edge.src not in node_refs:
            errors.append(f"Edge source '{edge.src}' does not exist")
        if edge.dst not in node_refs:
            errors.append(f"Edge destination '{edge.dst}' does not exist")
    
    # Check: no cycles (topological sort)
    if not has_valid_dag(spec.nodes, spec.edges):
        errors.append("Workflow contains a cycle; must be a DAG (directed acyclic graph)")
    
    # Check: no orphan nodes (all reachable from trigger)
    if triggers:  # Only check if we have a valid trigger
        trigger_ref = triggers[0].ref
        reachable = get_reachable_nodes(trigger_ref, spec.edges)
        orphans = node_refs - reachable
        if orphans:
            errors.append(f"Unreachable nodes: {', '.join(orphans)}")
    
    return errors


def has_valid_dag(nodes: List[NodeSpec], edges: List[EdgeSpec]) -> bool:
    """Check if the graph is a valid DAG using topological sort."""
    try:
        topological_sort(nodes, edges)
        return True
    except:
        return False


def topological_sort(nodes: List[NodeSpec], edges: List[EdgeSpec]) -> List[str]:
    """Topological sort of nodes. Raises if cycle detected."""
    node_refs = {n.ref for n in nodes}
    
    # Build adjacency list
    graph: Dict[str, List[str]] = {ref: [] for ref in node_refs}
    in_degree: Dict[str, int] = {ref: 0 for ref in node_refs}
    
    for edge in edges:
        if edge.src in graph and edge.dst in node_refs:
            graph[edge.src].append(edge.dst)
            in_degree[edge.dst] += 1
    
    # Kahn's algorithm
    queue = [ref for ref in node_refs if in_degree[ref] == 0]
    result = []
    
    while queue:
        node = queue.pop(0)
        result.append(node)
        for neighbor in graph[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    
    if len(result) != len(node_refs):
        raise ValueError("Cycle detected in workflow graph")
    
    return result


def get_reachable_nodes(start_ref: str, edges: List[EdgeSpec]) -> Set[str]:
    """Get all nodes reachable from start_ref via edges."""
    visited = set()
    stack = [start_ref]
    
    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        
        for edge in edges:
            if edge.src == current and edge.dst not in visited:
                stack.append(edge.dst)
    
    return visited


def assign_positions(spec: WorkflowSpec) -> Dict[str, Tuple[int, int]]:
    """
    Assign x, y positions to each node left-to-right based on topological order.
    
    Returns:
        dict: { node_ref: (x, y) }
    """
    sorted_refs = topological_sort(spec.nodes, spec.edges)
    positions = {}
    
    x_base = 240
    y_base = 300
    x_spacing = 240
    y_spacing = 100
    
    for i, ref in enumerate(sorted_refs):
        x = x_base + (i * x_spacing)
        y = y_base
        positions[ref] = (x, y)
    
    return positions


def build_n8n_nodes(
    spec: WorkflowSpec,
    positions: Dict[str, Tuple[int, int]]
) -> List[Dict[str, Any]]:
    """Convert NodeSpecs to n8n node objects."""
    n8n_nodes = []
    
    for node in spec.nodes:
        x, y = positions.get(node.ref, (240, 300))
        label = node.label or node.kind
        node_type = get_node_type(node.kind)
        type_version = get_node_version(node.kind)
        params = build_node_params(node.kind, node.params)
        
        n8n_node = {
            "id": str(uuid.uuid4()),  # Stable UUID for this node
            "name": label,
            "type": node_type,
            "typeVersion": type_version,
            "position": [x, y],
            "parameters": params,
        }
        n8n_nodes.append(n8n_node)
    
    return n8n_nodes


def build_n8n_connections(spec: WorkflowSpec) -> Dict[str, Any]:
    """
    Convert EdgeSpecs to n8n connections format.
    
    n8n connections are: { "source_node_name": { "main": [[{ "node": "dest_name", ...}]] } }
    """
    connections: Dict[str, Dict[str, List[List[Dict]]]] = {}
    
    # Group edges by source node
    edges_by_src: Dict[str, List[EdgeSpec]] = {}
    for edge in spec.edges:
        if edge.src not in edges_by_src:
            edges_by_src[edge.src] = []
        edges_by_src[edge.src].append(edge)
    
    # Build connections for each source
    for src_ref, edges in edges_by_src.items():
        src_node = spec.get_node_by_ref(src_ref)
        if not src_node:
            continue
        
        src_label = src_node.label or src_node.kind
        connections[src_label] = {"main": [[]]}
        
        for edge in edges:
            dst_node = spec.get_node_by_ref(edge.dst)
            if not dst_node:
                continue
            
            dst_label = dst_node.label or dst_node.kind
            connection_entry = {
                "node": dst_label,
                "type": "main",
                "index": 0,
            }
            connections[src_label]["main"][0].append(connection_entry)
    
    return connections


def compile_spec(spec: WorkflowSpec) -> Dict[str, Any]:
    """
    Compile a WorkflowSpec to native n8n workflow JSON.
    
    Raises CompilationError if validation fails.
    """
    # Validate spec
    errors = validate_spec(spec)
    if errors:
        raise CompilationError(f"Spec validation failed:\n" + "\n".join(f"  - {e}" for e in errors))
    
    # Assign positions
    positions = assign_positions(spec)
    
    # Build nodes and connections
    n8n_nodes = build_n8n_nodes(spec, positions)
    connections = build_n8n_connections(spec)
    
    # Assemble final workflow
    workflow = {
        "name": spec.name,
        "nodes": n8n_nodes,
        "connections": connections,
        "settings": {
            "executionOrder": "v1",
        },
    }
    
    return workflow
