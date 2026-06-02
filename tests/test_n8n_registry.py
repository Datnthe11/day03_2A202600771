import os
import sys

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.n8n.registry import build_email_params, validate_node_params


def test_build_email_params_maps_body_to_html_and_cc_to_options():
    params = {
        "from_email": "sender@example.com",
        "to": "recipient@example.com",
        "subject": "Hello",
        "body": "<p>Hi there!</p>",
        "cc": "cc@example.com",
    }

    result = build_email_params(params)

    assert result["fromEmail"] == "sender@example.com"
    assert result["toEmail"] == "recipient@example.com"
    assert result["subject"] == "Hello"
    assert result["emailFormat"] == "html"
    assert result["html"] == "<p>Hi there!</p>"
    assert result["options"] == {"ccEmail": "cc@example.com"}


def test_validate_node_params_requires_from_email_for_email_node():
    errors = validate_node_params("email", {"to": "recipient@example.com", "subject": "Hello"})
    assert errors == ["Missing required param 'from_email' for email"]
