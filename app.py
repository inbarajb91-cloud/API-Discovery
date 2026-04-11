"""Streamlit Web UI for the API Discovery Agent.

Run with: streamlit run app.py
"""

import json
import os
import re
import streamlit as st

from agent import run_agent_turn

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="API Discovery Agent",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    .stApp { max-width: 1200px; margin: 0 auto; }
    .option-btn {
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 8px 16px;
        margin: 4px;
        background: #f8fafc;
        cursor: pointer;
    }
    .option-btn:hover { background: #e2e8f0; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def extract_clickable_options(text: str) -> list[str]:
    """Extract bullet-point options from agent text for rendering as buttons."""
    options = []
    for line in text.split("\n"):
        stripped = line.strip()
        match = re.match(r'^[\-\*○●◦▸►•]\s+(.+)$', stripped)
        if match:
            opt = match.group(1).strip()
            if len(opt) > 5 and len(opt) < 120:
                options.append(opt)
    return options


def parse_clarifying_questions(text: str) -> list[dict]:
    """Extract JSON clarifying_question blocks embedded in text."""
    questions = []
    # Find all JSON objects in the text
    for match in re.finditer(r'\{[^{}]*"type"\s*:\s*"clarifying_question"[^{}]*\}', text):
        try:
            parsed = json.loads(match.group())
            if "question" in parsed and "options" in parsed:
                questions.append(parsed)
        except (json.JSONDecodeError, KeyError):
            continue
    return questions


def strip_json_blocks(text: str) -> str:
    """Remove JSON clarifying_question blocks from text, leaving only prose."""
    cleaned = re.sub(r'\{[^{}]*"type"\s*:\s*"clarifying_question"[^{}]*\}', '', text)
    # Clean up extra blank lines
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()
    return cleaned


def render_text_with_options(content: str, msg_idx: int, key_prefix: str):
    """Render agent text. Detects inline JSON questions and bullet options, renders as buttons."""

    # 1. Check for JSON clarifying questions embedded in text
    questions = parse_clarifying_questions(content)
    if questions:
        # Show the prose text (without JSON blocks)
        prose = strip_json_blocks(content)
        if prose:
            st.markdown(prose)

        # Render each question as a card with buttons
        for q_idx, q in enumerate(questions):
            question_text = q["question"]
            options = q["options"]
            st.markdown(f"**{question_text}**")
            cols = st.columns(min(len(options), 3))
            for i, opt in enumerate(options):
                with cols[i % min(len(options), 3)]:
                    btn_key = f"{key_prefix}_q{msg_idx}_{q_idx}_{i}"
                    if st.button(opt, key=btn_key, use_container_width=True):
                        st.session_state.button_answer = opt
            st.markdown("")  # spacing
        return True

    # 2. Check for bullet-point options
    options = extract_clickable_options(content)

    # Show the full text
    st.markdown(content)

    # Render bullet options as buttons
    if options and len(options) >= 2:
        st.markdown("---")
        st.caption("**Quick replies** (click to answer, or type your own below)")
        for row_start in range(0, len(options), 2):
            row_options = options[row_start:row_start + 2]
            cols = st.columns(len(row_options))
            for i, opt in enumerate(row_options):
                with cols[i]:
                    btn_key = f"{key_prefix}_{msg_idx}_{row_start + i}"
                    if st.button(opt, key=btn_key, use_container_width=True):
                        st.session_state.button_answer = opt
        return True

    return False


# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []
if "pdf_path" not in st.session_state:
    st.session_state.pdf_path = None
if "button_answer" not in st.session_state:
    st.session_state.button_answer = None

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("⚙️ Configuration")

    # API Key
    default_key = ""
    try:
        default_key = st.secrets["ANTHROPIC_API_KEY"]
    except (KeyError, FileNotFoundError):
        default_key = os.getenv("ANTHROPIC_API_KEY", "")

    api_key = st.text_input(
        "Anthropic API Key",
        value=default_key,
        type="password",
        help="Enter your Anthropic API key, or set it in Streamlit Cloud Secrets",
    )
    api_key = api_key.strip() if api_key else ""

    if api_key and not api_key.startswith("sk-ant-"):
        st.warning("Key should start with 'sk-ant-'. Please check your API key.")
    elif api_key:
        st.success(f"Key loaded ({api_key[:10]}...)")

    st.divider()

    # Quick start demos
    st.subheader("🚀 Quick Start")

    if st.button("🐾 Load Petstore Demo", use_container_width=True):
        st.session_state.button_answer = (
            "I want to build a pet adoption platform. I need to: "
            "1) List available pets with status filtering, "
            "2) Get detailed info about a specific pet, "
            "3) Place an adoption order for a pet. "
            "The API spec is at https://petstore3.swagger.io/api/v3/openapi.json"
        )

    if st.button("📦 Try Custom API", use_container_width=True):
        st.session_state.button_answer = (
            "I need to find a public API for managing a to-do list application. "
            "I need endpoints to create, read, update, and delete tasks."
        )

    st.divider()

    # Auth configuration
    st.subheader("🔐 Auth (Optional)")
    auth_type = st.selectbox("Auth Type", ["None", "Bearer Token", "API Key", "Basic Auth"])

    auth_info = None
    if auth_type == "Bearer Token":
        token = st.text_input("Token", type="password")
        if token:
            auth_info = f"Please authenticate with bearer token: {token}"
    elif auth_type == "API Key":
        key_name = st.text_input("Header Name", value="api_key")
        key_val = st.text_input("Key Value", type="password")
        if key_val:
            auth_info = f"Please authenticate with API key. Header: {key_name}, Key: {key_val}"
    elif auth_type == "Basic Auth":
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if username:
            auth_info = f"Please authenticate with basic auth. Username: {username}, Password: {password}"

    st.divider()

    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.conversation_history = []
        st.session_state.pdf_path = None
        st.session_state.button_answer = None
        st.rerun()

# ---------------------------------------------------------------------------
# Main chat area
# ---------------------------------------------------------------------------
st.title("🔍 API Discovery Agent")
st.caption("Describe your integration use case and I'll discover, test, and validate the APIs for you.")

# ---------------------------------------------------------------------------
# Event handler (must be defined before use)
# ---------------------------------------------------------------------------
def _handle_event(event: dict, key_prefix: str):
    """Render a single agent event and save to message history."""
    if event["type"] == "text":
        content = event["content"]
        msg_idx = len(st.session_state.messages)
        render_text_with_options(content, msg_idx, key_prefix)
        st.session_state.messages.append({
            "role": "assistant", "type": "text", "content": content
        })

    elif event["type"] == "tool_call":
        tool_name = event["name"]
        with st.status(f"🔧 {tool_name}", state="complete"):
            st.json(event["input"])
        st.session_state.messages.append({
            "role": "assistant", "type": "tool_call",
            "content": f"Calling {tool_name}",
            "tool_name": tool_name, "tool_input": event["input"],
        })

    elif event["type"] == "tool_result":
        tool_name = event["name"]
        success = event.get("success", True)
        icon = "✅" if success else "❌"
        with st.expander(f"{icon} {tool_name} result"):
            st.code(event["result"], language="text")
        st.session_state.messages.append({
            "role": "assistant", "type": "tool_result",
            "content": f"{tool_name}: {'success' if success else 'failed'}",
            "tool_name": tool_name, "result": event["result"], "success": success,
        })

    elif event["type"] == "pdf_ready":
        filepath = event["file_path"]
        st.session_state.pdf_path = filepath
        st.success("📄 PDF Report generated!")
        if os.path.exists(filepath):
            with open(filepath, "rb") as f:
                st.download_button(
                    "📥 Download PDF Report",
                    data=f.read(),
                    file_name="api_discovery_report.pdf",
                    mime="application/pdf",
                )
        st.session_state.messages.append({
            "role": "assistant", "type": "pdf",
            "content": "PDF Report generated",
            "file_path": filepath,
        })

# ---------------------------------------------------------------------------
# Render chat history
# ---------------------------------------------------------------------------
for idx, msg in enumerate(st.session_state.messages):
    role = msg["role"]
    content = msg["content"]
    msg_type = msg.get("type", "text")

    if role == "user":
        with st.chat_message("user"):
            st.write(content)

    elif role == "assistant":
        with st.chat_message("assistant"):
            if msg_type == "text":
                render_text_with_options(content, idx, "hist")
            elif msg_type == "tool_call":
                tool_name = msg.get("tool_name", "")
                with st.status(f"🔧 {tool_name}", state="complete"):
                    st.json(msg.get("tool_input", {}))
            elif msg_type == "tool_result":
                tool_name = msg.get("tool_name", "")
                success = msg.get("success", True)
                icon = "✅" if success else "❌"
                with st.expander(f"{icon} {tool_name} result"):
                    st.code(msg.get("result", ""), language="text")
            elif msg_type == "pdf":
                st.success("📄 PDF Report generated!")
                filepath = msg.get("file_path", "")
                if filepath and os.path.exists(filepath):
                    with open(filepath, "rb") as f:
                        st.download_button(
                            "📥 Download PDF Report",
                            data=f.read(),
                            file_name="api_discovery_report.pdf",
                            mime="application/pdf",
                        )

# ---------------------------------------------------------------------------
# Handle button clicks (demo buttons + quick reply buttons)
# ---------------------------------------------------------------------------
if st.session_state.button_answer:
    answer = st.session_state.button_answer
    st.session_state.button_answer = None
    st.session_state.messages.append({"role": "user", "content": answer, "type": "text"})
    st.session_state._pending_input = answer
    st.rerun()

# ---------------------------------------------------------------------------
# Process pending input (from button clicks)
# ---------------------------------------------------------------------------
if hasattr(st.session_state, '_pending_input') and st.session_state._pending_input:
    pending = st.session_state._pending_input
    st.session_state._pending_input = None
    if not api_key:
        st.error("Please enter your Anthropic API key in the sidebar.")
    else:
        full_message = pending
        if auth_info and len(st.session_state.conversation_history) == 0:
            full_message = f"{pending}\n\n[Auth info: {auth_info}]"

        with st.chat_message("assistant"):
            with st.spinner("🤔 Thinking..."):
                events = run_agent_turn(full_message, st.session_state.conversation_history, api_key)

            for event in events:
                _handle_event(event, "btn")

        st.rerun()

# ---------------------------------------------------------------------------
# Chat input
# ---------------------------------------------------------------------------
if user_input := st.chat_input("Describe your integration use case..."):
    if not api_key:
        st.error("⚠️ Please enter your Anthropic API key in the sidebar.")
    else:
        st.session_state.messages.append({"role": "user", "content": user_input, "type": "text"})

        full_message = user_input
        if auth_info and len(st.session_state.conversation_history) == 0:
            full_message = f"{user_input}\n\n[Auth info: {auth_info}]"

        with st.chat_message("assistant"):
            with st.spinner("🤔 Thinking..."):
                events = run_agent_turn(full_message, st.session_state.conversation_history, api_key)

            for event in events:
                _handle_event(event, "chat")

        st.rerun()
