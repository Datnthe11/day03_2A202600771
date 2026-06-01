"""
Node Registry: Maps logical node kinds to n8n native types and parameter builders.

This is the single source of truth for which node types are supported and how to
compile them into n8n's native format.
"""

from typing import Dict, Any, Callable, List


def build_manual_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Manual trigger has no parameters."""
    return {}


def build_webhook_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Webhook requires path, method, auth-enabled flag."""
    return {
        "path": params.get("path", "webhook"),
        "responseMode": params.get("response_mode", "onReceived"),
        "responseData": params.get("response_data", "success"),
        "httpMethod": params.get("method", "POST"),
        "authentication": params.get("authentication", "none"),
    }


def build_schedule_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Schedule/cron trigger. Supports both interval and cron modes."""
    if "cron" in params:
        return {
            "rule": {
                "mode": "cron",
                "cronExpression": params["cron"]
            }
        }
    # Interval mode: interval + unit (seconds, minutes, hours, days, weeks, months)
    interval = params.get("interval", 1)
    unit = params.get("unit", "hours")
    return {
        "rule": {
            "mode": "interval",
            "interval": [{"field": "interval", "value": interval}, {"field": "unit", "value": unit}]
        }
    }


def build_http_request_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """HTTP Request node - minimal valid config."""
    config = {
        "url": params.get("url", ""),
        "method": params.get("method", "GET"),
        "authentication": params.get("authentication", "none"),
    }
    
    # Add optional sections only if provided
    if params.get("headers"):
        config["sendHeaders"] = True
        config["headers"] = params["headers"]
    
    if params.get("body"):
        config["sendBody"] = True
        config["bodyContent"] = {
            "mimeType": "application/json",
            "content": params["body"]
        }
    
    return config


def build_set_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Set/Edit Fields node."""
    return {
        "keepOnlySet": params.get("keep_only_set", False),
        "values": params.get("values", {"ui": {"valueUi": []}}),
    }


def build_if_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """IF node: simple binary branching based on a condition."""
    return {
        "conditions": params.get("conditions", {"conditions": []}),
    }


def build_email_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Email Send node. Requires 'to', 'subject', 'body'."""
    return {
        "fromEmail": params.get("from_email", ""),
        "toEmail": params.get("to", ""),
        "ccEmail": params.get("cc", ""),
        "subject": params.get("subject", ""),
        "textHtml": params.get("body", ""),
    }


# Node Registry: maps logical kind -> n8n native type info
NODE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "manual": {
        "type": "n8n-nodes-base.manualTrigger",
        "version": 1,
        "build": build_manual_params,
        "required_params": [],
        "optional_params": [],
    },
    "webhook": {
        "type": "n8n-nodes-base.webhook",
        "version": 2,
        "build": build_webhook_params,
        "required_params": ["path"],
        "optional_params": ["method", "response_mode", "authentication"],
    },
    "schedule": {
        "type": "n8n-nodes-base.scheduleTrigger",
        "version": 1.2,
        "build": build_schedule_params,
        "required_params": [],  # Either "cron" or ("interval" + "unit")
        "optional_params": ["cron", "interval", "unit"],
    },
    "http": {
        "type": "n8n-nodes-base.httpRequest",
        "version": 4.2,
        "build": build_http_request_params,
        "required_params": ["url"],
        "optional_params": ["method", "headers", "body", "authentication"],
    },
    "set": {
        "type": "n8n-nodes-base.set",
        "version": 3.4,
        "build": build_set_params,
        "required_params": [],
        "optional_params": ["keep_only_set", "values"],
    },
    "if": {
        "type": "n8n-nodes-base.if",
        "version": 2,
        "build": build_if_params,
        "required_params": [],
        "optional_params": ["conditions"],
    },
    "email": {
        "type": "n8n-nodes-base.emailSend",
        "version": 2.1,
        "build": build_email_params,
        "required_params": ["to", "subject"],
        "optional_params": ["from_email", "cc", "body"],
    },
}


def get_supported_kinds() -> List[str]:
    """Return list of all supported node kinds."""
    return list(NODE_REGISTRY.keys())


def is_trigger_kind(kind: str) -> bool:
    """Check if a kind is a trigger (can be the first node)."""
    return kind in ["manual", "webhook", "schedule"]


def get_node_type(kind: str) -> str:
    """Get the native n8n type for a logical kind."""
    if kind not in NODE_REGISTRY:
        raise ValueError(f"Unknown node kind: {kind}")
    return NODE_REGISTRY[kind]["type"]


def get_node_version(kind: str) -> float:
    """Get the typeVersion for a kind."""
    if kind not in NODE_REGISTRY:
        raise ValueError(f"Unknown node kind: {kind}")
    return NODE_REGISTRY[kind]["version"]


def build_node_params(kind: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Build native n8n parameters for a node kind."""
    if kind not in NODE_REGISTRY:
        raise ValueError(f"Unknown node kind: {kind}")
    builder = NODE_REGISTRY[kind]["build"]
    return builder(params)


def validate_node_params(kind: str, params: Dict[str, Any]) -> List[str]:
    """Validate parameters for a node kind. Return list of errors (empty = valid)."""
    if kind not in NODE_REGISTRY:
        return [f"Unknown node kind: '{kind}'"]
    
    required = NODE_REGISTRY[kind]["required_params"]
    errors = []
    
    for req_param in required:
        if req_param not in params or params[req_param] is None:
            errors.append(f"Missing required param '{req_param}' for {kind}")
    
    return errors
