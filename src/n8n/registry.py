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
        cron = params["cron"]
        if isinstance(cron, str):
            expression = cron
        elif isinstance(cron, dict):
            # Convert cron parts into a single cron expression string.
            expression = " ".join(
                str(cron.get(part, "*"))
                for part in ["minute", "hour", "dayOfMonth", "month", "dayOfWeek"]
            )
        else:
            expression = str(cron)

        return {
            "rule": {
                "interval": [
                    {
                        "field": "cronExpression",
                        "expression": expression,
                    }
                ]
            }
        }

    interval = params.get("interval", 1)
    unit = params.get("unit", "hours")
    rule_item: Dict[str, Any] = {
        "field": unit,
        f"{unit}Interval": interval,
    }

    if unit in ["hours", "days", "weeks", "months"] and params.get("minute") is not None:
        rule_item["triggerAtMinute"] = params["minute"]

    if unit in ["days", "weeks", "months"] and params.get("hour") is not None:
        rule_item["triggerAtHour"] = params["hour"]

    if unit == "weeks" and params.get("dayOfWeek") is not None:
        rule_item["triggerAtDay"] = params["dayOfWeek"]

    if unit == "months" and params.get("dayOfMonth") is not None:
        rule_item["triggerAtDayOfMonth"] = params["dayOfMonth"]

    return {
        "rule": {
            "interval": [rule_item]
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
    """Email Send node. Requires 'from_email', 'to', and 'subject'."""
    config: Dict[str, Any] = {
        "fromEmail": params.get("from_email", ""),
        "toEmail": params.get("to", ""),
        "subject": params.get("subject", ""),
    }

    if params.get("body") is not None:
        config["emailFormat"] = "html"
        config["html"] = params.get("body", "")

    if params.get("cc"):
        config["options"] = {"ccEmail": params["cc"]}

    return config


def build_gmail_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Gmail node parameters (n8n gmail). Uses authenticated account; requires 'to' and 'subject'.

    This produces a minimal parameter set for the Gmail send node. n8n's Gmail node
    authenticates with OAuth and sends from the connected account, so 'from' is optional.
    """
    cfg: Dict[str, Any] = {
        "operation": "send",
        "resource": "message",
        "to": params.get("to", ""),
        "subject": params.get("subject", ""),
    }

    # Body: prefer html when provided
    if params.get("body") is not None:
        # If the caller explicitly requests html, use 'html'; otherwise set 'text'
        if params.get("html", False) or ("<" in str(params.get("body", "")) and ">" in str(params.get("body", ""))):
            cfg["html"] = params.get("body", "")
        else:
            cfg["text"] = params.get("body", "")

    # Optional cc and attachments
    if params.get("cc"):
        cfg["cc"] = params["cc"]

    if params.get("attachments"):
        cfg["attachments"] = params["attachments"]

    return cfg


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
        "required_params": ["from_email", "to", "subject"],
        "optional_params": ["cc", "body"],
    },
    "gmail": {
        "type": "n8n-nodes-base.gmail",
        "version": 1,
        "build": build_gmail_params,
        "required_params": ["to", "subject"],
        "optional_params": ["cc", "body", "attachments"],
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
        # Treat missing or empty-string values as missing
        if req_param not in params or params[req_param] is None or (isinstance(params[req_param], str) and params[req_param].strip() == ""):
            errors.append(f"Missing required param '{req_param}' for {kind}")
    
    return errors
