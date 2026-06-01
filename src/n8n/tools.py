"""
N8n Tools for ReActAgent (CONTRACT.md compliant).

Tool Contract (§1-§6 of CONTRACT.md):
- tool shape: {"name": str, "description": str, "func": Callable[[str], str]}
- func takes ONE string argument (raw JSON or bare value), returns ONE string
- func NEVER raises; always returns "ok | ..." or "error: ..."
- Loop passes args VERBATIM (no parsing); tool parses its own args

Tool Catalog (Phase 1 names):
1. list_node_types: list available node kinds + required/optional params
2. validate_spec: check spec structure and params
3. compile_spec: spec -> n8n JSON (dry run)
4. create_workflow: deploy spec to n8n
5. activate_workflow: activate workflow by id
6. get_workflow: retrieve workflow by id
7. delete_workflow: delete workflow by id
"""

import json
from typing import Tuple, List, Dict, Any, Callable, Optional

from src.n8n.spec import WorkflowSpec
from src.n8n.registry import NODE_REGISTRY, get_supported_kinds
from src.n8n.compiler import compile_spec, validate_spec as compiler_validate_spec, CompilationError
from src.n8n.client import N8nClient, AuthError, BadWorkflowError, NotFoundError, N8nUnavailableError


# ========== Individual Tool Functions ==========
# Each function: str -> str (takes raw args, never raises, returns "ok | ..." or "error: ...")

def tool_list_node_types(args: str) -> str:
    """
    List supported node kinds with required/optional params.
    
    Args:
        args: optional query string (empty, or {"query": "email"})
    
    Returns:
        ok | <formatted catalog>
    """
    try:
        # Parse args (can be empty, bare string, or JSON object)
        query = ""
        if args.strip():
            try:
                parsed = json.loads(args)
                if isinstance(parsed, dict):
                    query = parsed.get("query", "").lower()
                elif isinstance(parsed, str):
                    query = parsed.lower()
            except json.JSONDecodeError:
                # Try as bare string
                query = args.strip().lower()
        
        lines = []
        for kind in get_supported_kinds():
            if query and query not in kind:
                continue
            
            entry = NODE_REGISTRY[kind]
            required = entry.get("required_params", [])
            optional = entry.get("optional_params", [])
            
            params_str = ""
            if required or optional:
                params_parts = []
                if required:
                    params_parts.append(f"required: {', '.join(required)}")
                if optional:
                    params_parts.append(f"optional: {', '.join(optional)}")
                params_str = " (" + " | ".join(params_parts) + ")"
            
            lines.append(f"{kind}{params_str}")
        
        if not lines:
            return "ok | (no node types found for query)"
        
        return "ok | " + ", ".join(lines)
    
    except Exception as e:
        return f"error: list_node_types failed: {e}"


def tool_validate_spec(args: str) -> str:
    """
    Validate a WorkflowSpec JSON.
    
    Args:
        args: WorkflowSpec JSON object
    
    Returns:
        ok | (no errors) or error: <list of errors>
    """
    try:
        if not args.strip():
            return "error: validate_spec requires a WorkflowSpec JSON argument"
        
        # Parse WorkflowSpec
        try:
            spec_dict = json.loads(args)
        except json.JSONDecodeError as e:
            return f"error: invalid JSON in validate_spec: {e}"
        
        try:
            spec = WorkflowSpec(**spec_dict)
        except Exception as e:
            return f"error: spec parsing failed: {e}"
        
        # Validate
        errors = compiler_validate_spec(spec)
        
        if not errors:
            return "ok"
        
        return "error: " + " | ".join(errors)
    
    except Exception as e:
        return f"error: validate_spec internal error: {e}"


def tool_compile_spec(args: str) -> str:
    """
    Compile a WorkflowSpec to native n8n JSON (dry run, no API call).
    
    Args:
        args: WorkflowSpec JSON object
    
    Returns:
        ok | <n8n workflow JSON> or error: <reason>
    """
    try:
        if not args.strip():
            return "error: compile_spec requires a WorkflowSpec JSON argument"
        
        # Parse spec
        try:
            spec_dict = json.loads(args)
        except json.JSONDecodeError as e:
            return f"error: invalid JSON in compile_spec: {e}"
        
        try:
            spec = WorkflowSpec(**spec_dict)
        except Exception as e:
            return f"error: spec parsing failed: {e}"
        
        # Compile
        try:
            workflow_json = compile_spec(spec)
        except CompilationError as e:
            return f"error: compilation failed: {e}"
        
        # Return compiled JSON
        compiled_str = json.dumps(workflow_json, indent=0)  # compact
        return f"ok | {compiled_str}"
    
    except Exception as e:
        return f"error: compile_spec internal error: {e}"


def tool_create_workflow(args: str, client: N8nClient) -> str:
    """
    Create a workflow on the n8n instance from a WorkflowSpec.
    
    Args:
        args: WorkflowSpec JSON object
        client: N8nClient instance (bound at tool creation)
    
    Returns:
        ok | {"id":"...", "name":"...", "url":"..."} or error: <reason>
    """
    try:
        if not args.strip():
            return "error: create_workflow requires a WorkflowSpec JSON argument"
        
        # Parse spec
        try:
            spec_dict = json.loads(args)
        except json.JSONDecodeError as e:
            return f"error: invalid JSON in create_workflow: {e}"
        
        try:
            spec = WorkflowSpec(**spec_dict)
        except Exception as e:
            return f"error: spec parsing failed: {e}"
        
        # Validate spec first
        errors = compiler_validate_spec(spec)
        if errors:
            return f"error: spec validation failed: " + " | ".join(errors)
        
        # Compile to n8n JSON
        try:
            workflow_json = compile_spec(spec)
        except CompilationError as e:
            return f"error: compilation failed: {e}"
        
        # Create on n8n
        try:
            response = client.create_workflow(workflow_json)
        except AuthError as e:
            return f"error: authentication failed: {e}"
        except BadWorkflowError as e:
            return f"error: n8n rejected workflow: {e}"
        except N8nUnavailableError as e:
            return f"error: n8n unavailable: {e}"
        except Exception as e:
            return f"error: API call failed: {e}"
        
        # Extract result
        workflow_id = response.get("id")
        name = response.get("name")
        
        result = {
            "id": workflow_id,
            "name": name,
            "url": f"http://localhost:5678/workflow/{workflow_id}",
        }
        
        return f"ok | {json.dumps(result, separators=(',', ':'))}"
    
    except Exception as e:
        return f"error: create_workflow internal error: {e}"


def tool_activate_workflow(args: str, client: N8nClient) -> str:
    """
    Activate a workflow so it starts listening/firing.
    
    Args:
        args: workflow ID (JSON string or bare, e.g. "abc123" or abc123)
    
    Returns:
        ok | {"id":"...", "active":true} or error: <reason>
    """
    try:
        if not args.strip():
            return "error: activate_workflow requires a workflow ID argument"
        
        # Parse ID (bare string or JSON string)
        workflow_id = args.strip()
        if workflow_id.startswith('"') and workflow_id.endswith('"'):
            try:
                workflow_id = json.loads(workflow_id)
            except:
                pass
        
        # Activate
        try:
            response = client.activate_workflow(workflow_id)
        except AuthError as e:
            return f"error: authentication failed: {e}"
        except NotFoundError:
            return f"error: workflow '{workflow_id}' not found"
        except N8nUnavailableError as e:
            return f"error: n8n unavailable: {e}"
        except Exception as e:
            return f"error: activation failed: {e}"
        
        # Check result
        active = response.get("active", False)
        
        result = {
            "id": workflow_id,
            "active": active,
        }
        
        return f"ok | {json.dumps(result, separators=(',', ':'))}"
    
    except Exception as e:
        return f"error: activate_workflow internal error: {e}"


def tool_get_workflow(args: str, client: N8nClient) -> str:
    """
    Retrieve a workflow by ID (verify creation, check status).
    
    Args:
        args: workflow ID (JSON string or bare)
    
    Returns:
        ok | {"id":"...", "name":"...", "active":bool, "node_count":int, ...} or error: <reason>
    """
    try:
        if not args.strip():
            return "error: get_workflow requires a workflow ID argument"
        
        # Parse ID
        workflow_id = args.strip()
        if workflow_id.startswith('"') and workflow_id.endswith('"'):
            try:
                workflow_id = json.loads(workflow_id)
            except:
                pass
        
        # Get workflow
        try:
            response = client.get_workflow(workflow_id)
        except AuthError as e:
            return f"error: authentication failed: {e}"
        except NotFoundError:
            return f"error: workflow '{workflow_id}' not found"
        except N8nUnavailableError as e:
            return f"error: n8n unavailable: {e}"
        except Exception as e:
            return f"error: retrieval failed: {e}"
        
        # Build summary
        result = {
            "id": response.get("id"),
            "name": response.get("name"),
            "active": response.get("active", False),
            "node_count": len(response.get("nodes", [])),
            "connection_count": len(response.get("connections", {})),
        }
        
        return f"ok | {json.dumps(result, separators=(',', ':'))}"
    
    except Exception as e:
        return f"error: get_workflow internal error: {e}"


def tool_delete_workflow(args: str, client: N8nClient) -> str:
    """
    Delete a workflow (cleanup/rollback).
    
    Args:
        args: workflow ID (JSON string or bare)
    
    Returns:
        ok | deleted <id> or error: <reason>
    """
    try:
        if not args.strip():
            return "error: delete_workflow requires a workflow ID argument"
        
        # Parse ID
        workflow_id = args.strip()
        if workflow_id.startswith('"') and workflow_id.endswith('"'):
            try:
                workflow_id = json.loads(workflow_id)
            except:
                pass
        
        # Delete
        try:
            client.delete_workflow(workflow_id)
        except AuthError as e:
            return f"error: authentication failed: {e}"
        except NotFoundError:
            return f"error: workflow '{workflow_id}' not found"
        except N8nUnavailableError as e:
            return f"error: n8n unavailable: {e}"
        except Exception as e:
            return f"error: deletion failed: {e}"
        
        return f"ok | deleted {workflow_id}"
    
    except Exception as e:
        return f"error: delete_workflow internal error: {e}"


# ========== Tool Factory ==========

def create_n8n_tools(client: Optional[N8nClient] = None) -> Tuple[List[Dict[str, Any]], Callable]:
    """
    Create n8n tools for ReActAgent (CONTRACT.md §1-5).
    
    Returns:
        (tools, execute_fn) where:
        - tools: List[{"name": str, "description": str}] (no "func" field)
        - execute_fn: callable(tool_name: str, args: str) -> str
    """
    if client is None:
        client = N8nClient()
    
    # Bind client to tools that need it
    create_workflow_bound = lambda args: tool_create_workflow(args, client)
    activate_workflow_bound = lambda args: tool_activate_workflow(args, client)
    get_workflow_bound = lambda args: tool_get_workflow(args, client)
    delete_workflow_bound = lambda args: tool_delete_workflow(args, client)
    
    # Tool definitions (includes "func" for dispatch, but we'll strip it for the agent)
    _tools_internal = [
        {
            "name": "list_node_types",
            "description": "List all supported node kinds with required/optional parameters. "
                          "Use this to discover available workflow building blocks.",
            "func": tool_list_node_types,
        },
        {
            "name": "validate_spec",
            "description": "Validate a WorkflowSpec JSON. Returns ok or error list. "
                          "Use before creating to catch mistakes.",
            "func": tool_validate_spec,
        },
        {
            "name": "compile_spec",
            "description": "Compile a WorkflowSpec to native n8n JSON (dry run). "
                          "Use to preview the exact JSON without deploying.",
            "func": tool_compile_spec,
        },
        {
            "name": "create_workflow",
            "description": "Create a workflow on n8n from a WorkflowSpec. "
                          "Returns workflow id and editor URL. Does NOT activate.",
            "func": create_workflow_bound,
        },
        {
            "name": "activate_workflow",
            "description": "Activate a workflow so it starts listening (webhook) or firing (schedule). "
                          "Only activate auto-triggers or on explicit request.",
            "func": activate_workflow_bound,
        },
        {
            "name": "get_workflow",
            "description": "Retrieve a workflow by ID. Use to verify creation or check status.",
            "func": get_workflow_bound,
        },
        {
            "name": "delete_workflow",
            "description": "Delete a workflow by ID. Use for cleanup or rollback.",
            "func": delete_workflow_bound,
        },
    ]
    
    # Tool list for agent (without "func" field)
    tools_for_agent = [
        {"name": t["name"], "description": t["description"]}
        for t in _tools_internal
    ]
    
    # Dispatcher function (CONTRACT.md §5)
    def execute_tool(tool_name: str, args: str) -> str:
        """
        Execute a tool by name with raw args.
        
        CONTRACT.md §5:
        - Find tool by name
        - If found: call tool["func"](args)
        - If not found: return "error: tool '<name>' not found"
        """
        tool = next((t for t in _tools_internal if t["name"] == tool_name), None)
        if not tool:
            return f"error: tool '{tool_name}' not found"
        
        # Call tool (never raises; tool returns "ok | ..." or "error: ...")
        return tool["func"](args)
    
    return tools_for_agent, execute_tool
