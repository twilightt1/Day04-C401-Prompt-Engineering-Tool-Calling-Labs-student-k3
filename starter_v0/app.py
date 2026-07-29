"""
Research Agent — Streamlit UI
Reuses `run_model_tool_loop` from chat.py for the agent loop.
Shows: chat messages, tool traces, transcript logs, artifact version info.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

# ── Project imports (same path as chat.py) ──────────────────────────
from env_loader import load_lab_env
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools
from versioning import build_artifact_version, artifact_version_dict
from chat import run_model_tool_loop, write_transcript, now_iso, safe_slug

ROOT = Path(__file__).parent
ARTIFACTS_DIR = ROOT / "artifacts"
TRANSCRIPTS_DIR = ROOT / "transcripts"
RUNS_DIR = ROOT / "runs"

# Load .env once
load_lab_env(ROOT)

# ── Page config ─────────────────────────────────────────────────────
st.set_page_config(
    page_title="🔬 Research Agent",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS — premium dark glassmorphism theme ───────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Global ── */
html, body, .stApp {
    font-family: 'Inter', sans-serif;
}
.stApp {
    background: linear-gradient(135deg, #0a0e1a 0%, #0c1929 40%, #111d2e 100%);
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: rgba(10, 14, 30, 0.94) !important;
    backdrop-filter: blur(20px);
    border-right: 1px solid rgba(14, 165, 233, 0.15);
}
section[data-testid="stSidebar"] .stSelectbox label,
section[data-testid="stSidebar"] .stTextInput label,
section[data-testid="stSidebar"] .stNumberInput label {
    color: #7dd3fc !important;
    font-weight: 500;
    font-size: 0.82rem;
    letter-spacing: 0.02em;
}

/* ── Chat messages ── */
.stChatMessage {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(14, 165, 233, 0.08);
    border-radius: 16px !important;
    backdrop-filter: blur(8px);
    margin-bottom: 0.5rem;
    padding: 1rem 1.2rem !important;
}
.stChatMessage p,
.stChatMessage li,
.stChatMessage span,
.stChatMessage div {
    color: #f1f5f9 !important;
}
.stMarkdown p, .stMarkdown li, .stMarkdown span {
    color: #f1f5f9 !important;
}

/* ── Tool trace card ── */
.tool-trace-card {
    background: linear-gradient(135deg, rgba(12,25,45,0.95) 0%, rgba(15,30,52,0.95) 100%);
    border: 1px solid rgba(14,165,233,0.18);
    border-radius: 12px;
    padding: 14px 18px;
    margin-bottom: 10px;
    backdrop-filter: blur(12px);
    transition: border-color 0.25s;
}
.tool-trace-card:hover {
    border-color: rgba(14,165,233,0.45);
}
.tool-name {
    color: #38bdf8;
    font-weight: 700;
    font-size: 0.95rem;
    margin-bottom: 4px;
}
.tool-args {
    color: #94a3b8;
    font-size: 0.82rem;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    background: rgba(0,0,0,0.25);
    padding: 8px 12px;
    border-radius: 8px;
    margin-top: 6px;
    word-break: break-all;
    white-space: pre-wrap;
}
.tool-status-ok { color: #34d399; font-weight: 600; }
.tool-status-err { color: #f87171; font-weight: 600; }

/* ── Metric pill ── */
.metric-pill {
    display: inline-block;
    background: rgba(14,165,233,0.12);
    border: 1px solid rgba(14,165,233,0.25);
    border-radius: 20px;
    padding: 4px 14px;
    color: #7dd3fc;
    font-size: 0.78rem;
    font-weight: 500;
    margin-right: 6px;
    margin-bottom: 4px;
}

/* ── Header hero ── */
.hero-title {
    background: linear-gradient(135deg, #38bdf8, #0ea5e9, #0284c7);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 1.8rem;
    font-weight: 700;
    letter-spacing: -0.03em;
    margin-bottom: 2px;
}
.hero-sub {
    color: #94a3b8;
    font-size: 0.92rem;
    margin-bottom: 1.2rem;
}

/* ── Buttons ── */
.stButton > button {
    background: linear-gradient(135deg, #0284c7 0%, #0ea5e9 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    padding: 0.5rem 1.2rem !important;
    transition: transform 0.15s, box-shadow 0.25s !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 20px rgba(14,165,233,0.35) !important;
}

/* ── Expander ── */
.streamlit-expanderHeader {
    background: rgba(12,25,45,0.7) !important;
    border-radius: 10px !important;
    color: #7dd3fc !important;
    font-weight: 500 !important;
}

/* ── Dividers ── */
hr {
    border-color: rgba(14,165,233,0.12) !important;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(14,165,233,0.3); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(14,165,233,0.5); }
</style>
""", unsafe_allow_html=True)


# ── Helpers ─────────────────────────────────────────────────────────
def _render_tool_card(event: dict[str, Any], round_idx: int) -> None:
    """Render a single tool event as a styled card."""
    tool_name = event.get("tool", "unknown")
    args = event.get("args", {})
    result = event.get("result", {})
    has_error = isinstance(result, dict) and ("error" in result)
    status_class = "tool-status-err" if has_error else "tool-status-ok"
    status_text = f"❌ {result.get('error', '')}" if has_error else "✅ OK"

    args_json = json.dumps(args, ensure_ascii=False, indent=2, default=str)
    result_preview = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    if len(result_preview) > 600:
        result_preview = result_preview[:600] + "\n... (truncated)"

    st.markdown(f"""
    <div class="tool-trace-card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <span class="tool-name">🔧 {tool_name}</span>
            <span style="font-size:0.75rem; color:#64748b;">Round {round_idx}</span>
        </div>
        <span class="{status_class}" style="font-size:0.8rem;">{status_text}</span>
        <div class="tool-args"><b>Args:</b>\n{args_json}</div>
        <details style="margin-top:6px;">
            <summary style="color:#94a3b8; font-size:0.78rem; cursor:pointer;">Result preview</summary>
            <div class="tool-args" style="margin-top:4px;">{result_preview}</div>
        </details>
    </div>
    """, unsafe_allow_html=True)


def _available_providers() -> list[str]:
    """Detect which providers have keys configured."""
    import os
    providers = []
    if os.getenv("OPENROUTER_API_KEY"):
        providers.append("openrouter")
    if os.getenv("OPENAI_API_KEY"):
        providers.append("openai")
    if os.getenv("ANTHROPIC_API_KEY"):
        providers.append("anthropic")
    if os.getenv("GEMINI_API_KEY"):
        providers.append("gemini")
    return providers or ["openrouter"]


def _list_transcripts() -> list[Path]:
    """List existing transcript files."""
    if not TRANSCRIPTS_DIR.exists():
        return []
    return sorted(TRANSCRIPTS_DIR.glob("*.transcript.json"), reverse=True)


def _list_run_files() -> list[Path]:
    """List existing run JSON files."""
    if not RUNS_DIR.exists():
        return []
    return sorted(RUNS_DIR.glob("*.json"), reverse=True)


# ── Session state init ──────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []           # Chat display messages
if "history" not in st.session_state:
    st.session_state.history = []            # Context for model (role/content pairs)
if "tool_events_all" not in st.session_state:
    st.session_state.tool_events_all = []    # All tool events across turns
if "transcript" not in st.session_state:
    st.session_state.transcript = None       # Active transcript dict
if "transcript_path" not in st.session_state:
    st.session_state.transcript_path = None
if "turn_index" not in st.session_state:
    st.session_state.turn_index = 0


# ── Sidebar ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="hero-title">🔬 Research Agent</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-sub">Tool-calling Research Assistant</div>', unsafe_allow_html=True)
    st.markdown("---")

    # Provider selection
    available = _available_providers()
    provider_name = st.selectbox("🌐 Provider", available, index=0)

    # Model override
    model_override = st.text_input(
        "🤖 Model (blank = default)",
        value="",
        placeholder="e.g. gpt-4o-mini",
        help="Leave blank to use the provider's default model.",
    )

    # Version
    version = st.selectbox("📌 Version", ["v0", "v1", "v2", "v3", "v4", "v5"], index=0)

    # Advanced settings
    with st.expander("⚙️ Advanced", expanded=False):
        history_window = st.number_input("History window (pairs)", min_value=1, max_value=20, value=5)
        max_tool_rounds = st.number_input("Max tool rounds", min_value=1, max_value=10, value=4)

    st.markdown("---")

    # Artifact version info
    try:
        av = build_artifact_version(
            version,
            ARTIFACTS_DIR / "system_prompt.md",
            ARTIFACTS_DIR / "tools.yaml",
        )
        st.markdown("**📋 Artifact Fingerprint**")
        st.markdown(f"""
        <span class="metric-pill">ver: {av.artifact_version[:30]}</span><br/>
        <span class="metric-pill">prompt: {av.prompt_hash[:12]}</span><br/>
        <span class="metric-pill">tools: {av.tools_hash[:12]}</span>
        """, unsafe_allow_html=True)
    except Exception:
        st.warning("Cannot compute artifact version. Check artifacts/ files.")

    st.markdown("---")

    # New chat button
    if st.button("🗑️ New Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.history = []
        st.session_state.tool_events_all = []
        st.session_state.transcript = None
        st.session_state.transcript_path = None
        st.session_state.turn_index = 0
        st.rerun()

    # Transcript viewer
    st.markdown("---")
    st.markdown("**📜 Saved Transcripts**")
    transcript_files = _list_transcripts()
    if transcript_files:
        selected_transcript = st.selectbox(
            "View transcript",
            ["(none)"] + [f.name for f in transcript_files],
            index=0,
            label_visibility="collapsed",
        )
        if selected_transcript != "(none)":
            tp = TRANSCRIPTS_DIR / selected_transcript
            with st.expander(f"📄 {selected_transcript}", expanded=False):
                try:
                    data = json.loads(tp.read_text(encoding="utf-8"))
                    st.json(data)
                except Exception as exc:
                    st.error(f"Error reading: {exc}")
    else:
        st.caption("No transcripts yet.")

    # Run logs viewer
    st.markdown("**📊 Run Logs**")
    run_files = _list_run_files()
    if run_files:
        selected_run = st.selectbox(
            "View run log",
            ["(none)"] + [f.name for f in run_files],
            index=0,
            label_visibility="collapsed",
        )
        if selected_run != "(none)":
            rp = RUNS_DIR / selected_run
            with st.expander(f"📄 {selected_run}", expanded=False):
                try:
                    data = json.loads(rp.read_text(encoding="utf-8"))
                    # Show summary if present
                    if "summary" in data:
                        st.markdown("**Summary:**")
                        for k, v in data["summary"].items():
                            st.markdown(f"- **{k}**: `{v}`")
                    st.json(data)
                except Exception as exc:
                    st.error(f"Error reading: {exc}")
    else:
        st.caption("No run logs yet.")


# ── Main area ───────────────────────────────────────────────────────
# Header
st.markdown('<div class="hero-title">🔬 Research Agent Chat</div>', unsafe_allow_html=True)
st.markdown(f"""
<div class="hero-sub">
    Provider: <b>{provider_name}</b> &nbsp;|&nbsp; Version: <b>{version}</b>
    &nbsp;|&nbsp; Model: <b>{model_override or "default"}</b>
</div>
""", unsafe_allow_html=True)

# Two-column layout: chat (left) + tool traces (right)
col_chat, col_traces = st.columns([3, 2], gap="medium")

with col_chat:
    st.markdown("#### 💬 Conversation")

    # Render chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="🧑‍💻" if msg["role"] == "user" else "🤖"):
            st.markdown(msg["content"])
            # If this message has tool events attached, show a brief indicator
            if "tool_summary" in msg and msg["tool_summary"]:
                tool_names = [e.get("tool", "?") for e in msg["tool_summary"]]
                pills = " ".join(f'<span class="metric-pill">🔧 {name}</span>' for name in tool_names)
                st.markdown(pills, unsafe_allow_html=True)

with col_traces:
    st.markdown("#### 🔧 Tool Traces")
    if st.session_state.tool_events_all:
        for i, event in enumerate(reversed(st.session_state.tool_events_all), 1):
            _render_tool_card(event, event.get("_round", 0))
    else:
        st.markdown(
            '<div style="color:#64748b; text-align:center; padding:2rem;">No tool calls yet. Start chatting!</div>',
            unsafe_allow_html=True,
        )


# ── Chat input ──────────────────────────────────────────────────────
user_input = st.chat_input("Ask the research agent anything…")

if user_input:
    # 1) Append user message to display
    st.session_state.messages.append({"role": "user", "content": user_input, "tool_summary": []})

    # 2) Load artifacts
    try:
        system_prompt_path = ARTIFACTS_DIR / "system_prompt.md"
        tools_yaml_path = ARTIFACTS_DIR / "tools.yaml"
        system_prompt = system_prompt_path.read_text(encoding="utf-8")
        tool_declarations = load_tool_declarations(tools_yaml_path)
        openai_tools = to_openai_tools(tool_declarations)
    except Exception as exc:
        st.error(f"Failed to load artifacts: {exc}")
        st.stop()

    # 3) Build artifact version
    try:
        artifact_version = build_artifact_version(version, system_prompt_path, tools_yaml_path)
    except Exception:
        artifact_version = None

    # 4) Create provider
    try:
        provider = make_provider(provider_name)
    except Exception as exc:
        st.error(f"Provider error: {exc}")
        st.stop()

    selected_model = model_override or getattr(provider, "default_model", None)

    # 5) Build message list with history window
    window = int(history_window) if history_window else 5
    trimmed_history = st.session_state.history[-(window * 2):] if window > 0 else []
    messages_for_model = [
        {"role": "system", "content": system_prompt},
        *trimmed_history,
        {"role": "user", "content": user_input},
    ]

    # 6) Initialize transcript if first turn
    if st.session_state.transcript is None:
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
        transcript_id = "_".join([safe_slug(version), safe_slug(provider_name), timestamp])
        st.session_state.transcript_path = TRANSCRIPTS_DIR / f"{transcript_id}.transcript.json"
        st.session_state.transcript = {
            "transcript_id": transcript_id,
            **(artifact_version_dict(artifact_version) if artifact_version else {}),
            "provider": provider_name,
            "model": selected_model,
            "system_prompt": str(system_prompt_path),
            "tools": str(tools_yaml_path),
            "history_window": window,
            "max_tool_rounds": int(max_tool_rounds),
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "turns": [],
        }

    # 7) Run agent loop
    st.session_state.turn_index += 1
    turn_record: dict[str, Any] = {
        "turn_index": st.session_state.turn_index,
        "started_at": now_iso(),
        "user": user_input,
        "status": "started",
        "assistant_text": None,
        "rounds": [],
        "tool_events": [],
    }

    with st.spinner("🔬 Agent is thinking…"):
        try:
            result = run_model_tool_loop(
                provider=provider,
                messages=messages_for_model,
                tools=openai_tools,
                model=selected_model if model_override else None,
                max_tool_rounds=int(max_tool_rounds),
            )
            turn_record.update(result)
            assistant_text = result.get("assistant_text", "")
            tool_events = result.get("tool_events", [])

            # Tag each event with its round index for display
            for r in result.get("rounds", []):
                for te in r.get("tool_results", []):
                    te["_round"] = r.get("round", 0)

            # Collect all tool events from rounds (with _round tag)
            all_events_this_turn = []
            for r in result.get("rounds", []):
                all_events_this_turn.extend(r.get("tool_results", []))

            # Add to session
            st.session_state.tool_events_all.extend(all_events_this_turn)
            st.session_state.messages.append({
                "role": "assistant",
                "content": assistant_text,
                "tool_summary": all_events_this_turn,
            })
            st.session_state.history.append({"role": "user", "content": user_input})
            st.session_state.history.append({"role": "assistant", "content": assistant_text})

        except Exception as exc:
            turn_record.update({
                "status": "provider_error",
                "error": f"{type(exc).__name__}: {str(exc)}",
            })
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"❌ **Error:** {type(exc).__name__}: {str(exc)}",
                "tool_summary": [],
            })

    # 8) Save transcript
    turn_record["ended_at"] = now_iso()
    st.session_state.transcript["turns"].append(turn_record)
    write_transcript(st.session_state.transcript_path, st.session_state.transcript)

    st.rerun()
