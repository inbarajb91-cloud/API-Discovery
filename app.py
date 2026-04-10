"""Streamlit Web UI for the API Discovery Agent.

Run with: streamlit run app.py
"""

import json
import os
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
    .tool-call {
        background-color: #f0f4f8;
        border-left: 3px solid #4a90d9;
        padding: 8px 12px;
        margin: 4px 0;
        border-radius: 0 4px 4px 0;
        font-size: 0.85em;
    }
    .tool-success { border-left-color: #16a34a; }
    .tool-error { border-left-color: #dc2626; }
    .verdict-achievable {
        background-color: #dcfce7;
        border: 2px solid #16a34a;
        padding: 16px;
        border-radius: 8px;
        text-align: center;
    }
    .verdict-partial {
        background-color: #fef9c3;
        border: 2px solid #ca8a04;
        padding: 16px;
        border-radius: 8px;
        text-align: center;
    }
    .verdict-fail {
        background-color: #fce4ec;
        border: 2px solid #dc2626;
        padding: 16px;
        border-radius: 8px;
        text-align: center;
    }
    .question-card {
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px;
        margin: 8px 0;
        background: #f8fafc;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []  # Display messages for the UI
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []  # Claude message history
if "pdf_path" not in st.session_state:
    st.session_state.pdf_path = None
if "pending_question" not in st.session_state:
    st.session_state.pending_question = None
if "button_answer" not in st.session_state:
    st.session_state.button_answer = None

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("⚙️ Configuration")

    # API Key
    api_key = st.text_input(
        "Anthropic API Key",
        value=os.getenv("ANTHROPIC_API_KEY", ""),
        type="password",
        help="Enter your Anthropic API key or set ANTHROPIC_API_KEY env var",
    )

    st.divider()

    # Quick start demos
    st.subheader("🚀 Quick Start")

    if st.button("🐾 Load Petstore Demo", use_container_width=True):
        demo_msg = (
            "I want to build a pet adoption platform. I need to: "
            "1) List available pets with status filtering, "
            "2) Get detailed info about a specific pet, "
            "3) Place an adoption order for a pet. "
            "The API spec is at https://petstore3.swagger.io/api/v3/openapi.json"
        )
        st.session_state.button_answer = demo_msg

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
        st.session_state.pending_question = None
        st.session_state.button_answer = None
        st.rerun()

# ---------------------------------------------------------------------------
# Main chat area
# ---------------------------------------------------------------------------
st.title("🔍 API Discovery Agent")
st.caption("Describe your integration use case and I'll discover, test, and validate the APIs for you.")

# Render chat history
for msg in st.session_state.messages:
    role = msg["role"]
    content = msg["content"]
    msg_type = msg.get("type", "text")

    if role == "user":
        with st.chat_message("user"):
            st.write(content)

    elif role == "assistant":
        with st.chat_message("assistant"):
            if msg_type == "text":
                st.write(content)
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
            elif msg_type == "question_card":
                question = msg.get("question", "")
                options = msg.get("options", [])
                st.markdown(f"**{question}**")
                cols = st.columns(len(options))
                for i, opt in enumerate(options):
                    with cols[i]:
                        if st.button(opt, key=f"q_{msg.get('msg_idx', 0)}_{i}", use_container_width=True):
                            st.session_state.button_answer = opt

# ---------------------------------------------------------------------------
# Handle button answer from demo or question card
# ---------------------------------------------------------------------------
if st.session_state.button_answer:
    answer = st.session_state.button_answer
    st.session_state.button_answer = None
    st.session_state.messages.append({"role": "user", "content": answer, "type": "text"})
    st.session_state._pending_input = answer
    st.rerun()

# Check for pending input from button clicks
if hasattr(st.session_state, '_pending_input') and st.session_state._pending_input:
    pending = st.session_state._pending_input
    st.session_state._pending_input = None
    if not api_key:
        st.error("Please enter your Anthropic API key in the sidebar.")
    else:
        # Add auth context if configured
        full_message = pending
        if auth_info and len(st.session_state.conversation_history) == 0:
            full_message = f"{pending}\n\n[Auth info: {auth_info}]"

        with st.chat_message("assistant"):
            with st.spinner("🤔 Thinking..."):
                events = run_agent_turn(
                    full_message,
                    st.session_state.conversation_history,
                    api_key,
                )

            # Render events
            for event in events:
                if event["type"] == "text":
                    # Check if it's a clarifying question JSON
                    content = event["content"]
                    try:
                        parsed = json.loads(content)
                        if parsed.get("type") == "clarifying_question":
                            question = parsed["question"]
                            options = parsed["options"]
                            st.markdown(f"**{question}**")
                            msg_idx = len(st.session_state.messages)
                            cols = st.columns(min(len(options), 4))
                            for i, opt in enumerate(options):
                                with cols[i % len(cols)]:
                                    if st.button(opt, key=f"live_q_{msg_idx}_{i}", use_container_width=True):
                                        st.session_state.button_answer = opt
                            st.session_state.messages.append({
                                "role": "assistant",
                                "type": "question_card",
                                "content": question,
                                "question": question,
                                "options": options,
                                "msg_idx": msg_idx,
                            })
                            continue
                    except (json.JSONDecodeError, KeyError, TypeError):
                        pass

                    st.write(content)
                    st.session_state.messages.append({
                        "role": "assistant", "type": "text", "content": content
                    })

                elif event["type"] == "tool_call":
                    tool_name = event["name"]
                    with st.status(f"🔧 {tool_name}", state="complete"):
                        st.json(event["input"])
                    st.session_state.messages.append({
                        "role": "assistant", "type": "tool_call", "content": f"Calling {tool_name}",
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

        st.rerun()

# ---------------------------------------------------------------------------
# Chat input
# ---------------------------------------------------------------------------
if user_input := st.chat_input("Describe your integration use case..."):
    if not api_key:
        st.error("⚠️ Please enter your Anthropic API key in the sidebar.")
    else:
        st.session_state.messages.append({"role": "user", "content": user_input, "type": "text"})

        # Add auth context if configured and this is the first message
        full_message = user_input
        if auth_info and len(st.session_state.conversation_history) == 0:
            full_message = f"{user_input}\n\n[Auth info: {auth_info}]"

        with st.chat_message("assistant"):
            with st.spinner("🤔 Thinking..."):
                events = run_agent_turn(
                    full_message,
                    st.session_state.conversation_history,
                    api_key,
                )

            # Render events
            for event in events:
                if event["type"] == "text":
                    content = event["content"]
                    # Check for clarifying question JSON
                    try:
                        parsed = json.loads(content)
                        if parsed.get("type") == "clarifying_question":
                            question = parsed["question"]
                            options = parsed["options"]
                            st.markdown(f"**{question}**")
                            msg_idx = len(st.session_state.messages)
                            cols = st.columns(min(len(options), 4))
                            for i, opt in enumerate(options):
                                with cols[i % len(cols)]:
                                    if st.button(opt, key=f"chat_q_{msg_idx}_{i}", use_container_width=True):
                                        st.session_state.button_answer = opt
                            st.session_state.messages.append({
                                "role": "assistant", "type": "question_card",
                                "content": question, "question": question,
                                "options": options, "msg_idx": msg_idx,
                            })
                            continue
                    except (json.JSONDecodeError, KeyError, TypeError):
                        pass

                    st.write(content)
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
                        "tool_name": tool_name, "result": event["result"],
                        "success": success,
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

        st.rerun()
