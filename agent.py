"""Core agent loop — the heart of the API Discovery Agent.

Uses Claude's tool_use to run an agentic loop:
1. Send user message + conversation history to Claude
2. If Claude responds with text → yield it for display
3. If Claude responds with tool_use → execute the tool, send result back
4. Repeat until Claude stops calling tools (end_turn)
"""

import json
import anthropic

from tool_definitions import TOOLS
from tools import execute_tool
from config import SYSTEM_PROMPT, MODEL, MAX_TOKENS, MAX_TOOL_LOOPS


def run_agent_turn(user_message: str, conversation_history: list, api_key: str) -> list:
    """
    Run one full agent turn. May involve multiple Claude API calls if tools are used.

    Args:
        user_message: The user's input text
        conversation_history: List of message dicts (mutated in place)
        api_key: Anthropic API key

    Returns:
        List of events for the UI to render:
        - {"type": "text", "content": "..."}
        - {"type": "tool_call", "name": "...", "input": {...}}
        - {"type": "tool_result", "name": "...", "result": "...", "success": bool}
        - {"type": "pdf_ready", "file_path": "..."}
    """
    client = anthropic.Anthropic(api_key=api_key)

    # Add user message to history
    conversation_history.append({"role": "user", "content": user_message})

    events = []

    for iteration in range(MAX_TOOL_LOOPS):
        # Call Claude
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=conversation_history,
        )

        # Process each content block
        assistant_content = response.content
        tool_use_blocks = []
        tool_result_messages = []

        for block in assistant_content:
            if block.type == "text":
                text = block.text.strip()
                if text:
                    events.append({"type": "text", "content": text})

            elif block.type == "tool_use":
                tool_use_blocks.append(block)
                events.append({
                    "type": "tool_call",
                    "name": block.name,
                    "input": block.input,
                })

                # Execute the tool
                result = execute_tool(block.name, block.input)

                is_success = not result.startswith("Error")
                events.append({
                    "type": "tool_result",
                    "name": block.name,
                    "result": result,
                    "success": is_success,
                })

                # Check for PDF
                if block.name == "generate_pdf_report" and is_success and not result.startswith("Error"):
                    events.append({"type": "pdf_ready", "file_path": result})

                tool_result_messages.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        # Add assistant response to conversation history
        # Convert content blocks to serializable format
        serialized_content = []
        for block in assistant_content:
            if block.type == "text":
                serialized_content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                serialized_content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })

        conversation_history.append({"role": "assistant", "content": serialized_content})

        # If tools were called, send results back and continue the loop
        if tool_result_messages:
            conversation_history.append({"role": "user", "content": tool_result_messages})
            continue

        # No tool calls → agent is done with this turn
        break

    return events
