"""
chatbot.py — runnable n8n workflow-builder agent.

Wires together:
    LLM (OpenAIProvider)                        -> the brain
    system prompt (src/agent/system_prompt.txt) -> loaded by ReActAgent.get_system_prompt()
    n8n tools (src/n8n/tools.py)                 -> the hands (validate/compile/create/... workflows)
    ReActAgent (src/agent/agent.py)              -> the Thought/Action/Observation loop

Run:
    python chatbot.py            # interactive chat (describe a workflow, 'quit' to exit)

Environment (.env):
    OPENAI_API_KEY   required                        -> the LLM
    N8N_API_KEY      required to deploy workflows     -> n8n REST API auth
    N8N_BASE_URL     optional (default http://localhost:5678/api/v1)
    DEFAULT_MODEL    optional (default gpt-4o-mini)
"""

import os
import sys
from typing import Optional

from dotenv import load_dotenv

# Make `src` importable when running this file directly from the repo root.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.agent.agent import ReActAgent
from src.n8n.tools import create_n8n_tools
from src.n8n.client import N8nClient


# ── Wiring: build a ReActAgent that uses the real n8n tools ──────────────────

def build_agent() -> ReActAgent:
    """
    Connect the LLM + the n8n tools + the ReAct loop.

    create_n8n_tools() returns (tools, execute_tool): the tool list carries only
    name/description (no "func"), and dispatch goes through `execute_tool`. The
    agent loop calls self._execute_tool(name, args), so we override that bound
    method with the n8n dispatcher — that's the whole integration seam.
    get_system_prompt() already reads src/agent/system_prompt.txt, so the system
    prompt is wired up by construction.
    """
    from src.core.openai_provider import OpenAIProvider

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your_openai_api_key_here":
        print("OPENAI_API_KEY is missing or still the placeholder in .env.")
        sys.exit(1)

    model_name = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")
    if model_name.startswith("gemini"):  # .env may carry a non-OpenAI model name
        model_name = "gpt-4o-mini"

    if not os.getenv("N8N_API_KEY"):
        print("⚠️  N8N_API_KEY not set — offline tools work, but create/activate/get/")
        print("    delete will fail with an auth error until you set it in .env.\n")

    llm = OpenAIProvider(model_name=model_name, api_key=api_key)

    base_url = os.getenv("N8N_BASE_URL", "http://localhost:5678/api/v1")
    client = N8nClient(base_url=base_url, api_key=os.getenv("N8N_API_KEY") or "offline-no-key")
    tools, execute_tool = create_n8n_tools(client)

    agent = ReActAgent(llm, tools, max_steps=100)
    agent._execute_tool = execute_tool  # route dispatch to the n8n tools
    return agent


def run_interactive(agent: ReActAgent):
    print("=== n8n Workflow Builder Agent ===")
    print("Available tools:", ", ".join(t["name"] for t in agent.tools))
    print("Describe the workflow you want. Commands: 'clear' (forget memory), 'quit' to stop.\n")
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break
        if user_input.lower() in {"quit", "exit", "q"}:
            print("Bye!")
            break
        if user_input.lower() in {"clear", "reset"}:
            agent.reset_memory()
            print("(short-term memory cleared)\n")
            continue
        if not user_input:
            continue
        answer = agent.run(user_input)
        print(f"Agent: {answer}\n")


def main():
    load_dotenv()
    agent = build_agent()
    run_interactive(agent)


if __name__ == "__main__":
    main()
