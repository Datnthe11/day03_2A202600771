"""
chatbot.py — manual test harness for the ReAct agent (src/agent/agent.py).

Wires up:  OpenAIProvider  +  DUMMY_TOOLS  ->  ReActAgent

Run modes:
    python chatbot.py            # interactive chat (type questions, 'quit' to exit)
    python chatbot.py --demo     # run a few scripted questions and print results
    python chatbot.py --fake     # use a scripted FakeLLM (NO API key / no network needed)

Requires OPENAI_API_KEY in .env  (unless you pass --fake).
"""

import os
import sys
import argparse
from typing import Dict, Any, Optional

from dotenv import load_dotenv

# Make `src` importable when running this file directly from the repo root.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.agent.agent import ReActAgent
from src.agent.dummy_tools import DUMMY_TOOLS


# ── A no-network fake LLM, so you can test the LOOP without spending API quota ──
class FakeLLM:
    """
    Minimal stand-in for an LLMProvider. It ignores the prompt and just replays
    a scripted list of responses, one per step. Great for proving that the
    parse -> dispatch -> observe -> finish loop works deterministically.
    """

    def __init__(self, scripted_responses):
        self.model_name = "fake-llm"
        self._responses = list(scripted_responses)
        self._i = 0

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        # A fresh run() starts with a transcript that has no Observation yet —
        # use that to rewind the script so the scenario replays for each question.
        if "Observation:" not in prompt:
            self._i = 0
        if self._i < len(self._responses):
            content = self._responses[self._i]
        else:
            content = "Final Answer: (fake llm ran out of script)"
        self._i += 1
        return {"content": content, "usage": {}, "latency_ms": 0, "provider": "fake"}


def build_fake_agent() -> ReActAgent:
    """Scripts a 2-step ReAct run: call add([2,3]) -> read Observation -> Final Answer."""
    script = [
        "Thought: I need to add 2 and 3.\nAction: add([2, 3])",
        "Thought: The tool returned 5, so I can answer.\nFinal Answer: The sum of 2 and 3 is 5.",
    ]
    return ReActAgent(FakeLLM(script), DUMMY_TOOLS, max_steps=5)


def build_openai_agent() -> ReActAgent:
    """Builds the real agent backed by OpenAI. Reads OPENAI_API_KEY from the environment."""
    from src.core.openai_provider import OpenAIProvider

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your_openai_api_key_here":
        print("OPENAI_API_KEY is missing or still the placeholder in .env.")
        print("   Set a real key, or run with --fake to test the loop offline.")
        sys.exit(1)

    model_name = os.getenv("DEFAULT_MODEL", "gpt-4o")
    # DEFAULT_MODEL in .env may be a Gemini name; fall back to an OpenAI model if so.
    if model_name.startswith("gemini"):
        model_name = "gpt-4o"

    provider = OpenAIProvider(model_name=model_name, api_key=api_key)
    return ReActAgent(provider, DUMMY_TOOLS, max_steps=5)


# ── Run modes ────────────────────────────────────────────────────────────────

DEMO_QUESTIONS = [
    "What is 12 plus 30?",
    "Reverse the word 'chatbot' for me.",
    "What's the weather in Hanoi?",
    "Echo back the phrase 'hello world'.",
]


def run_demo(agent: ReActAgent):
    print("=== DEMO MODE: scripted questions ===\n")
    for q in DEMO_QUESTIONS:
        print(f"User: {q}")
        answer = agent.run(q)
        print(f"Agent: {answer}\n" + "-" * 60)


def run_interactive(agent: ReActAgent):
    print("=== INTERACTIVE MODE ===")
    print("Available tools:", ", ".join(t["name"] for t in DUMMY_TOOLS))
    print("Type a question, or 'quit' / 'exit' to stop.\n")
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break
        if user_input.lower() in {"quit", "exit", "q"}:
            print("Bye!")
            break
        if not user_input:
            continue
        answer = agent.run(user_input)
        print(f"Agent: {answer}\n")


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Test harness for the ReAct chatbot agent.")
    parser.add_argument("--demo", action="store_true", help="Run scripted demo questions.")
    parser.add_argument("--fake", action="store_true", help="Use an offline scripted FakeLLM (no API key).")
    args = parser.parse_args()

    if args.fake:
        agent = build_fake_agent()
        print("Using FakeLLM (offline). The loop is deterministic regardless of your input.\n")
    else:
        agent = build_openai_agent()

    if args.demo:
        run_demo(agent)
    else:
        run_interactive(agent)


if __name__ == "__main__":
    main()
