"""Streamlit Web UI for the API Discovery Agent — Concierge AI design.

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
    page_title="Concierge AI — API Discovery Agent",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Design system CSS (inspired by Google Stitch design)
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700;800&family=Inter:wght@400;500;600&display=swap');

    /* Global */
    .stApp { background-color: #f8f9fa; }
    .stApp > header { background-color: transparent; }
    .main .block-container { max-width: 900px; padding-top: 2rem; }
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    h1, h2, h3 { font-family: 'Manrope', sans-serif !important; }

    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #f8fafc;
        border-right: 1px solid #e2e8f0;
    }
    section[data-testid="stSidebar"] .stMarkdown h1 {
        font-family: 'Manrope', sans-serif !important;
        color: #003fa3;
        font-size: 1.2rem;
        font-weight: 800;
    }

    /* Chat message styling */
    .stChatMessage { background-color: transparent !important; border: none !important; }

    /* Custom option card */
    .option-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 20px;
        cursor: pointer;
        transition: all 0.2s ease;
        margin-bottom: 8px;
    }
    .option-card:hover {
        background: #f8fafc;
        box-shadow: 0 8px 24px rgba(0,0,0,0.06);
        transform: translateY(-1px);
    }
    .option-card h4 {
        font-family: 'Manrope', sans-serif;
        font-weight: 700;
        color: #191c1d;
        margin: 0 0 4px 0;
        font-size: 0.95rem;
    }
    .option-card p {
        color: #424654;
        font-size: 0.82rem;
        margin: 0;
        line-height: 1.5;
    }

    /* Verdict card */
    .verdict-card {
        border-radius: 24px;
        overflow: hidden;
        box-shadow: 0 12px 32px rgba(0,163,108,0.12);
        border: 1px solid rgba(0,0,0,0.05);
        margin: 16px 0;
    }
    .verdict-header-pass {
        background: #e6f4ea;
        padding: 24px 32px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .verdict-header-partial {
        background: #fef9c3;
        padding: 24px 32px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .verdict-header-fail {
        background: #fce4ec;
        padding: 24px 32px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .verdict-title {
        font-family: 'Manrope', sans-serif;
        font-size: 1.8rem;
        font-weight: 800;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .verdict-score {
        text-align: right;
    }
    .verdict-score-label {
        font-size: 0.65rem;
        text-transform: uppercase;
        letter-spacing: 0.15em;
        font-weight: 700;
    }
    .verdict-score-value {
        font-family: 'Manrope', sans-serif;
        font-size: 2.5rem;
        font-weight: 800;
    }
    .verdict-body {
        background: white;
        padding: 32px;
    }

    /* Tool status */
    .tool-step {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 6px 0;
        font-size: 0.9rem;
        color: #424654;
    }
    .tool-step-icon { color: #003fa3; }

    /* Hide streamlit elements */
    .stDeployButton { display: none; }
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }

    /* Button styling */
    .stButton > button {
        border-radius: 12px;
        font-weight: 600;
        border: 1px solid #e2e8f0;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        border-color: #003fa3;
        color: #003fa3;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def extract_clickable_options(text: str) -> list[str]:
    """Extract bullet-point options from agent text."""
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
    for match in re.finditer(r'\{[^{}]*"type"\s*:\s*"clarifying_question"[^{}]*\}', text):
        try:
            parsed = json.loads(match.group())
            if "question" in parsed and "options" in parsed:
                questions.append(parsed)
        except (json.JSONDecodeError, KeyError):
            continue
    return questions


def strip_json_blocks(text: str) -> str:
    """Remove JSON clarifying_question blocks from text."""
    cleaned = re.sub(r'\{[^{}]*"type"\s*:\s*"clarifying_question"[^{}]*\}', '', text)
    return re.sub(r'\n{3,}', '\n\n', cleaned).strip()


def render_text_with_options(content: str, msg_idx: int, key_prefix: str):
    """Render agent text with interactive option cards."""

    # 1. Check for JSON clarifying questions
    questions = parse_clarifying_questions(content)
    if questions:
        prose = strip_json_blocks(content)
        if prose:
            st.markdown(prose)

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
            st.markdown("")
        return True

    # 2. Check for bullet options
    options = extract_clickable_options(content)
    st.markdown(content)

    if options and len(options) >= 2:
        st.caption("**Quick replies** — click to answer, or type your own below")
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


def render_tool_step(name: str, success: bool):
    """Render a tool execution step like the Stitch design."""
    icon = "✓" if success else "✗"
    color = "#00a36c" if success else "#ba1a1a"
    # Friendly tool names
    friendly = {
        "web_search": "Searching the web",
        "scrape_documentation": "Reading documentation",
        "discover_api_spec": "Discovering API specification",
        "lookup_api_directory": "Searching API directory",
        "fetch_openapi_spec": "Parsing API specification",
        "list_endpoints": "Listing available endpoints",
        "search_endpoints": "Finding relevant endpoints",
        "authenticate": "Authenticating",
        "call_api": "Testing API endpoint",
        "validate_integration": "Validating integration feasibility",
        "generate_pdf_report": "Generating PDF report",
    }.get(name, name)
    st.markdown(
        f'<div class="tool-step"><span style="color:{color};font-weight:700;">{icon}</span> {friendly}</div>',
        unsafe_allow_html=True
    )


# ---------------------------------------------------------------------------
# Event handler
# ---------------------------------------------------------------------------
def handle_event(event: dict, key_prefix: str):
    """Render a single agent event."""
    if event["type"] == "text":
        content = event["content"]
        msg_idx = len(st.session_state.messages)
        render_text_with_options(content, msg_idx, key_prefix)
        st.session_state.messages.append({
            "role": "assistant", "type": "text", "content": content
        })

    elif event["type"] == "tool_call":
        tool_name = event["name"]
        st.session_state.messages.append({
            "role": "assistant", "type": "tool_call",
            "content": f"Calling {tool_name}",
            "tool_name": tool_name, "tool_input": event["input"],
        })

    elif event["type"] == "tool_result":
        tool_name = event["name"]
        success = event.get("success", True)
        render_tool_step(tool_name, success)
        with st.expander(f"Details: {tool_name}"):
            st.code(event["result"][:2000], language="text")
        st.session_state.messages.append({
            "role": "assistant", "type": "tool_result",
            "content": f"{tool_name}: {'success' if success else 'failed'}",
            "tool_name": tool_name, "result": event["result"], "success": success,
        })

    elif event["type"] == "pdf_ready":
        filepath = event["file_path"]
        st.session_state.pdf_path = filepath
        if os.path.exists(filepath):
            st.markdown("""
            <div style="background:#003fa3;color:white;padding:20px 32px;border-radius:16px;text-align:center;margin:16px 0;">
                <div style="font-family:Manrope;font-weight:800;font-size:1.1rem;">📄 Your Discovery Report is Ready</div>
            </div>
            """, unsafe_allow_html=True)
            with open(filepath, "rb") as f:
                st.download_button(
                    "⬇ Download PDF Report",
                    data=f.read(),
                    file_name="api_discovery_report.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
        st.session_state.messages.append({
            "role": "assistant", "type": "pdf",
            "content": "PDF Report generated", "file_path": filepath,
        })


# ---------------------------------------------------------------------------
# Session state
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
    st.markdown("""
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">
        <div style="width:32px;height:32px;background:#003fa3;border-radius:8px;display:flex;align-items:center;justify-content:center;color:white;font-weight:800;font-size:16px;">✦</div>
        <div>
            <div style="font-family:Manrope;font-weight:800;color:#003fa3;font-size:1.1rem;">Concierge AI</div>
            <div style="font-size:10px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.15em;">API Discovery Agent</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # API Key
    default_key = ""
    try:
        default_key = st.secrets["ANTHROPIC_API_KEY"]
    except (KeyError, FileNotFoundError):
        default_key = os.getenv("ANTHROPIC_API_KEY", "")

    api_key = st.text_input(
        "API Key",
        value=default_key,
        type="password",
        help="Your Anthropic API key",
    )
    api_key = api_key.strip() if api_key else ""

    if api_key and not api_key.startswith("sk-ant-"):
        st.warning("Key should start with 'sk-ant-'")
    elif api_key:
        st.success(f"Connected ({api_key[:12]}...)")

    st.divider()

    st.markdown("**One-Click Demos**")

    if st.button("⚡ Sync Shopify Orders", use_container_width=True):
        st.session_state.button_answer = (
            "Our customer needs to sync their Shopify orders into our platform "
            "and update fulfillment status. "
            "The API spec is at https://petstore3.swagger.io/api/v3/openapi.json"
        )

    if st.button("📊 Export CRM Leads", use_container_width=True):
        st.session_state.button_answer = (
            "I need to find a public API for managing a to-do list application. "
            "I need endpoints to create, read, update, and delete tasks."
        )

    st.divider()

    # Auth
    st.markdown("**Authentication**")
    auth_type = st.selectbox("Type", ["None", "Bearer Token", "API Key", "Basic Auth"], label_visibility="collapsed")

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

    if st.button("🗑 Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.conversation_history = []
        st.session_state.pdf_path = None
        st.session_state.button_answer = None
        st.rerun()

# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------

# Show welcome screen if no messages
if not st.session_state.messages:
    st.markdown("""
    <div style="text-align:center;padding:80px 20px 40px;">
        <div style="width:72px;height:72px;margin:0 auto 24px;background:linear-gradient(135deg,#003fa3,#0055d4);border-radius:20px;display:flex;align-items:center;justify-content:center;box-shadow:0 8px 24px rgba(0,63,163,0.2);">
            <span style="color:white;font-size:32px;">✦</span>
        </div>
        <h1 style="font-family:Manrope;font-size:2.2rem;font-weight:800;color:#191c1d;margin-bottom:12px;letter-spacing:-0.02em;">
            Welcome to your API Discovery Agent.
        </h1>
        <p style="color:#424654;font-size:1.05rem;max-width:480px;margin:0 auto 48px;line-height:1.7;">
            Describe your integration use case and I'll discover, test, and validate the APIs for you.
        </p>
        <div style="display:flex;justify-content:center;gap:48px;margin-bottom:48px;">
            <div style="text-align:center;">
                <div style="width:48px;height:48px;margin:0 auto 12px;background:#e7e8e9;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:20px;">🔗</div>
                <div style="font-family:Manrope;font-weight:700;font-size:0.85rem;">1. Connect an API</div>
            </div>
            <div style="text-align:center;">
                <div style="width:48px;height:48px;margin:0 auto 12px;background:#e7e8e9;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:20px;">📝</div>
                <div style="font-family:Manrope;font-weight:700;font-size:0.85rem;">2. Describe your use case</div>
            </div>
            <div style="text-align:center;">
                <div style="width:48px;height:48px;margin:0 auto 12px;background:#e7e8e9;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:20px;">📊</div>
                <div style="font-family:Manrope;font-weight:700;font-size:0.85rem;">3. Get your feasibility report</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
else:
    # Render chat history
    for idx, msg in enumerate(st.session_state.messages):
        role = msg["role"]
        content = msg["content"]
        msg_type = msg.get("type", "text")

        if role == "user":
            with st.chat_message("user"):
                st.write(content)

        elif role == "assistant":
            with st.chat_message("assistant", avatar="✦"):
                if msg_type == "text":
                    render_text_with_options(content, idx, "hist")
                elif msg_type == "tool_call":
                    pass  # Don't re-render tool calls in history
                elif msg_type == "tool_result":
                    tool_name = msg.get("tool_name", "")
                    success = msg.get("success", True)
                    render_tool_step(tool_name, success)
                elif msg_type == "pdf":
                    filepath = msg.get("file_path", "")
                    if filepath and os.path.exists(filepath):
                        with open(filepath, "rb") as f:
                            st.download_button(
                                "⬇ Download PDF Report",
                                data=f.read(),
                                file_name="api_discovery_report.pdf",
                                mime="application/pdf",
                                use_container_width=True,
                            )

# ---------------------------------------------------------------------------
# Handle button clicks
# ---------------------------------------------------------------------------
if st.session_state.button_answer:
    answer = st.session_state.button_answer
    st.session_state.button_answer = None
    st.session_state.messages.append({"role": "user", "content": answer, "type": "text"})
    st.session_state._pending_input = answer
    st.rerun()

# Process pending input
if hasattr(st.session_state, '_pending_input') and st.session_state._pending_input:
    pending = st.session_state._pending_input
    st.session_state._pending_input = None
    if not api_key:
        st.error("Please enter your API key in the sidebar.")
    else:
        full_message = pending
        if auth_info and len(st.session_state.conversation_history) == 0:
            full_message = f"{pending}\n\n[Auth info: {auth_info}]"

        with st.chat_message("assistant", avatar="✦"):
            with st.spinner("Discovering APIs..."):
                events = run_agent_turn(full_message, st.session_state.conversation_history, api_key)
            for event in events:
                handle_event(event, "btn")
        st.rerun()

# ---------------------------------------------------------------------------
# Chat input
# ---------------------------------------------------------------------------
if user_input := st.chat_input("Describe your integration use case..."):
    if not api_key:
        st.error("Please enter your API key in the sidebar.")
    else:
        st.session_state.messages.append({"role": "user", "content": user_input, "type": "text"})

        full_message = user_input
        if auth_info and len(st.session_state.conversation_history) == 0:
            full_message = f"{user_input}\n\n[Auth info: {auth_info}]"

        with st.chat_message("assistant", avatar="✦"):
            with st.spinner("Discovering APIs..."):
                events = run_agent_turn(full_message, st.session_state.conversation_history, api_key)
            for event in events:
                handle_event(event, "chat")
        st.rerun()
