"""
N8nClient: Thin requests wrapper for n8n Public REST API.

Handles:
- Authentication (X-N8N-API-KEY header)
- Base URL configuration
- Typed error handling
- Secret redaction in logs
- Timeout enforcement
"""

import os
import requests
import json
from typing import Dict, Any, Optional
from requests.exceptions import Timeout, ConnectionError


class AuthError(Exception):
    """401/403: authentication failed."""
    pass


class BadWorkflowError(Exception):
    """400: workflow JSON is invalid."""
    pass


class NotFoundError(Exception):
    """404: workflow not found."""
    pass


class N8nUnavailableError(Exception):
    """Connection error: n8n is not running or unreachable."""
    pass


class N8nClient:
    """Client for n8n Public REST API."""
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout_secs: int = 10,
    ):
        """
        Initialize N8nClient.
        
        Args:
            base_url: n8n API base URL (default from N8N_BASE_URL env)
            api_key: API key (default from N8N_API_KEY env)
            timeout_secs: request timeout in seconds
        """
        self.base_url = base_url or os.getenv("N8N_BASE_URL", "http://localhost:5678/api/v1")
        self.api_key = api_key or os.getenv("N8N_API_KEY")
        self.timeout_secs = timeout_secs
        
        if not self.api_key:
            raise ValueError("N8N_API_KEY environment variable is required")
    
    def _redact_secrets(self, obj: Any) -> Any:
        """Recursively redact sensitive fields from an object for logging."""
        if isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                if any(s in k.lower() for s in ["key", "secret", "password", "token", "auth"]):
                    result[k] = "***REDACTED***"
                else:
                    result[k] = self._redact_secrets(v)
            return result
        elif isinstance(obj, (list, tuple)):
            return [self._redact_secrets(item) for item in obj]
        return obj
    
    def _make_request(
        self,
        method: str,
        path: str,
        json_body: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make an authenticated HTTP request to the n8n API.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: API path (e.g., "/workflows", "/workflows/123/activate")
            json_body: request body (for POST/PUT)
            params: query parameters
        
        Returns:
            Response JSON
        
        Raises:
            AuthError: 401/403
            BadWorkflowError: 400
            NotFoundError: 404
            N8nUnavailableError: connection error
        """
        url = f"{self.base_url}{path}"
        headers = {
            "X-N8N-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }
        
        try:
            response = requests.request(
                method=method,
                url=url,
                json=json_body,
                params=params,
                headers=headers,
                timeout=self.timeout_secs,
            )
        except (ConnectionError, TimeoutError, Timeout) as e:
            raise N8nUnavailableError(
                f"Cannot connect to n8n at {self.base_url}. Is it running? Error: {e}"
            )
        
        # Log redacted request for debugging
        log_body = self._redact_secrets(json_body) if json_body else None
        print(f"[N8nClient] {method} {path} -> {response.status_code}")
        if log_body:
            print(f"  Request: {json.dumps(log_body, indent=2)[:200]}")
        
        # Handle errors
        if response.status_code in (401, 403):
            raise AuthError(
                f"Authentication failed (status {response.status_code}). "
                f"Check N8N_API_KEY and that the n8n Public API is enabled."
            )
        
        if response.status_code == 404:
            raise NotFoundError(f"Not found: {path}")
        
        if response.status_code == 400:
            try:
                error_data = response.json()
                error_msg = error_data.get("message", response.text)
            except:
                error_msg = response.text
            raise BadWorkflowError(f"Bad request: {error_msg}")
        
        if response.status_code >= 500:
            raise N8nUnavailableError(
                f"n8n server error (status {response.status_code}): {response.text[:200]}"
            )
        
        # Parse and return response
        try:
            return response.json() if response.text else {}
        except:
            return {"raw": response.text}
    
    def list_workflows(self) -> Dict[str, Any]:
        """
        GET /workflows — list all workflows.
        
        Returns:
            { "data": [workflow, ...], "nodesUpsertedAt": ... }
        """
        return self._make_request("GET", "/workflows")
    
    def get_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """
        GET /workflows/{id} — get a single workflow.
        
        Args:
            workflow_id: workflow ID
        
        Returns:
            workflow object
        """
        return self._make_request("GET", f"/workflows/{workflow_id}")
    
    def create_workflow(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        POST /workflows — create a new workflow.
        
        Args:
            workflow: workflow JSON (name, nodes, connections, settings)
        
        Returns:
            created workflow object with id, name, etc.
        """
        return self._make_request("POST", "/workflows", json_body=workflow)
    
    def update_workflow(self, workflow_id: str, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        PUT /workflows/{id} — update an existing workflow.
        
        Args:
            workflow_id: workflow ID
            workflow: updated workflow JSON
        
        Returns:
            updated workflow object
        """
        return self._make_request("PUT", f"/workflows/{workflow_id}", json_body=workflow)
    
    def delete_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """
        DELETE /workflows/{id} — delete a workflow.
        
        Args:
            workflow_id: workflow ID
        
        Returns:
            response (usually empty on success)
        """
        return self._make_request("DELETE", f"/workflows/{workflow_id}")
    
    def activate_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """
        POST /workflows/{id}/activate — activate a workflow.
        
        Args:
            workflow_id: workflow ID
        
        Returns:
            { "active": true, ... }
        """
        return self._make_request("POST", f"/workflows/{workflow_id}/activate")
    
    def deactivate_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """
        POST /workflows/{id}/deactivate — deactivate a workflow.
        
        Args:
            workflow_id: workflow ID
        
        Returns:
            { "active": false, ... }
        """
        return self._make_request("POST", f"/workflows/{workflow_id}/deactivate")
    
    def get_workflow_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        List workflows and find one by name.
        
        Args:
            name: workflow name
        
        Returns:
            workflow object or None if not found
        """
        try:
            response = self.list_workflows()
            workflows = response.get("data", [])
            for wf in workflows:
                if wf.get("name") == name:
                    return wf
        except:
            pass
        return None
