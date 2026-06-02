import re
from typing import List, Dict, Any, Optional
from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger

class ReActAgent:
    """
    SKELETON: A ReAct-style Agent that follows the Thought-Action-Observation loop.
    Students should implement the core loop logic and tool execution.
    """
    
    def __init__(self, llm: LLMProvider, tools: List[Dict[str, Any]], max_steps: int = 5):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps
        self.history = []
        # Full conversational memory: the ENTIRE running transcript across all
        # turns — every Question / Thought / Action / Observation / Final Answer.
        # It persists between run() calls and is fed back to the model in full,
        # so the agent never forgets earlier steps, even mid-clarification.
        self.transcript = ""

    def get_system_prompt(self) -> str:
        """
        TODO: Implement the system prompt that instructs the agent to follow ReAct.
        Should include:
        1.  Available tools and their descriptions.
        2.  Format instructions: Thought, Action, Observation.
        """
        import os

        # Attempt to load the detailed system prompt from file. Fall back to a simple
        # generated prompt that lists available tools if the file is missing.
        prompt_path = os.path.join(os.path.dirname(__file__), "system_prompt.txt")
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                base = f.read()
        except Exception:
            base = None

        tool_descriptions = "\n".join([f"- {t['name']}: {t.get('description','')}" for t in self.tools])

        if base:
            return f"{base}\n\nAvailable tools:\n{tool_descriptions}\n"

        return f"""
        You are an intelligent assistant. You have access to the following tools:
        {tool_descriptions}

        Use the following format:
        Thought: your line of reasoning.
        Action: tool_name(arguments)
        Observation: result of the tool call.
        ... (repeat Thought/Action/Observation if needed)
        Final Answer: your final response.
        """

    def run(self, user_input: str) -> str:
        """
        ReAct loop: Thought -> Action -> Observation, repeated until the LLM
        emits a Final Answer or we hit max_steps.

        1. Ask the LLM for the next Thought + Action.
        2. Parse the Action line (see CONTRACT.md §2) and dispatch the tool.
        3. Append the Observation to the transcript and loop.
        """
        logger.log_event("AGENT_START", {"input": user_input, "model": self.llm.model_name})

        system_prompt = self.get_system_prompt()
        self.history.append({"role": "User", "content": user_input})

        # Preserve all prior turns so follow-up questions retain dialogue context.
        transcript = ""
        for entry in self.history:
            transcript += f"{entry['role']}: {entry['content']}\n"

        steps = 0
        final_answer = None

        while steps < self.max_steps:
            steps += 1

            # 1. Generate the next chunk of reasoning from the FULL transcript.
            result = self.llm.generate(self.transcript, system_prompt=system_prompt)
            text = result["content"] if isinstance(result, dict) else str(result)

            # The model often hallucinates its own "Observation:" — cut it off so we
            # only keep its Thought/Action and supply the REAL observation ourselves.
            text = text.split("Observation:")[0].strip()

            logger.log_event("AGENT_STEP", {"step": steps, "llm_output": text})

            # 2. Stop condition A: the model produced a Final Answer (this also covers
            #    the agent stopping to ask the user for more information).
            final_match = re.search(r"Final Answer:\s*(.*)", text, re.DOTALL)
            if final_match:
                final_answer = final_match.group(1).strip()
                self.transcript += text + "\n"
                break

            # 3. Parse the Action line. (Loop passes args VERBATIM — no json parsing here.)
            action_match = re.search(r"Action:\s*(\w+)\((.*)\)", text, re.DOTALL)
            if not action_match:
                # No Action and no Final Answer — nudge the model back on format.
                observation = "error: could not parse Action line. Use 'Action: tool_name(<args>)' or 'Final Answer: ...'."
                self.transcript += text + f"\nObservation: {observation}\n"
                continue

            tool_name = action_match.group(1).strip()
            args = action_match.group(2).strip()

            # 4. Dispatch the tool and append the real Observation.
            observation = self._execute_tool(tool_name, args)
            logger.log_event("TOOL_CALL", {"tool": tool_name, "args": args, "observation": observation})

            self.transcript += text + f"\nObservation: {observation}\n"

        # Stop condition B: we exhausted max_steps without a Final Answer.
        if final_answer is None:
            final_answer = "I could not reach a final answer within the step budget."
            self.transcript += f"Final Answer: {final_answer}\n"

        # Keep a structured per-turn record too (handy for inspection/telemetry).
        self.history.append({"user": user_input, "assistant": final_answer})

        self.history.append({"role": "Assistant", "content": final_answer})
        logger.log_event("AGENT_END", {"steps": steps, "final_answer": final_answer})
        return final_answer

    def reset_memory(self) -> None:
        """Clear all memory (start a fresh conversation)."""
        self.history = []
        self.transcript = ""

    def _execute_tool(self, tool_name: str, args: str) -> str:
        """
        Dispatch to the matching tool's `func` (see CONTRACT.md §5).
        Tools own their own arg parsing and never raise; we defensively wrap
        anyway so a misbehaving tool can't crash the loop.
        """
        for tool in self.tools:
            if tool["name"] == tool_name:
                try:
                    return tool["func"](args)
                except Exception as e:  # contract says func should never raise, but be safe
                    return f"error: tool '{tool_name}' crashed: {e}"
        return f"error: tool '{tool_name}' not found"
