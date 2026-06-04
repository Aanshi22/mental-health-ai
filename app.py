import base64
import json
import os
import re
import textwrap
import urllib.error
import urllib.request
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from PIL import Image
import PyPDF2

# ── Bootstrap ─────────────────────────────────────────────────────────────────
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

def get_key(n):
    try:
        value = st.secrets[n]
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    except Exception:
        pass

    # Support common nested Streamlit secret structures, for example:
    # [ollama]\nhost=...\napi_key=...\nmodel=...
    try:
        secret_groups = [st.secrets["ollama"], st.secrets["OLLAMA"], st.secrets["Ollama"]]
    except Exception:
        secret_groups = []

    candidates = [n, n.lower(), n.upper()]
    if n.startswith("OLLAMA_"):
        short = n.replace("OLLAMA_", "", 1)
        candidates.extend([short, short.lower(), short.upper()])

    for group in secret_groups:
        for candidate in candidates:
            try:
                value = group[candidate]
                if value is not None and str(value).strip() != "":
                    return str(value).strip()
            except Exception:
                continue

    return os.getenv(n)

def get_first_key(*names, default=""):
    for name in names:
        value = get_key(name)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return default

IN_STREAMLIT_CLOUD = bool(os.getenv("STREAMLIT_SHARING_MODE") or os.getenv("STREAMLIT_RUNTIME"))

OLLAMA_API_KEY = get_first_key("OLLAMA_API_KEY", "OLLAMA_KEY", default="")
OLLAMA_HOST = get_first_key("OLLAMA_HOST", "OLLAMA_BASE_URL", "OLLAMA_URL", default="http://localhost:11434")

# On Streamlit Cloud, if only an API key is provided, prefer hosted Ollama automatically.
if IN_STREAMLIT_CLOUD and OLLAMA_HOST == "http://localhost:11434" and OLLAMA_API_KEY:
    OLLAMA_HOST = "https://api.ollama.com"

if re.match(r"^https?://ollama\.com/?$", OLLAMA_HOST):
    OLLAMA_HOST = "https://api.ollama.com"
OLLAMA_HOST = OLLAMA_HOST.rstrip("/")
OLLAMA_BASE_URL = OLLAMA_HOST[:-4] if OLLAMA_HOST.endswith("/api") else OLLAMA_HOST
MODEL = get_first_key("OLLAMA_MODEL", "MODEL", default="llama3.1")
VISION_MODEL = get_first_key("OLLAMA_VISION_MODEL", "VISION_MODEL", default="llava")
IN_CODESPACES = bool(os.getenv("CODESPACES"))

st.set_page_config(
    page_title="MindAI – Mental Health Platform",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

def deploy_diagnostics():
    issues = []

    if not IN_STREAMLIT_CLOUD:
        return issues

    key_value = (OLLAMA_API_KEY or "").strip()
    if not key_value or key_value.upper().startswith("REPLACE_WITH_"):
        issues.append(
            "Deploy config issue: OLLAMA_API_KEY is missing in Streamlit Cloud secrets."
        )

    if "localhost" in OLLAMA_BASE_URL:
        issues.append(
            "Deploy config issue: OLLAMA_HOST points to localhost, which is unreachable from Streamlit Cloud. "
            "Use a hosted Ollama URL such as https://api.ollama.com."
        )

    return issues

for issue in deploy_diagnostics():
    st.warning(issue, icon="⚠️")

# ══════════════════════════════════════════════════════════════════════════════
# GLOBAL CSS
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

*, html, body { font-family: 'Inter', sans-serif !important; }

html, body { overflow-x: hidden; }
.stApp * { box-sizing: border-box; }
h1, h2, h3, h4, h5, h6, p, li, span, label {
    overflow-wrap: anywhere;
    word-break: break-word;
}

/* Hide sidebar collapse control (double-arrow) across Streamlit variants */
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarNavCollapseButton"],
button[aria-label="Close sidebar"],
button[aria-label="Open sidebar"],
button[title="Close sidebar"],
button[title="Open sidebar"] {
    display: none !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: linear-gradient(160deg,#0d0d1a 0%,#1a0a2e 50%,#0a1628 100%) !important;
    border-right: 1px solid rgba(108,99,255,0.3);
}
[data-testid="stSidebar"] * { color: #e8e8f8 !important; }
[data-testid="stSidebar"] .stRadio > label { display:none; }
[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label {
    background: rgba(108,99,255,0.08);
    border: 1px solid rgba(108,99,255,0.2);
    border-radius: 10px; padding: 10px 14px;
    margin-bottom: 6px; cursor: pointer;
    transition: all 0.2s; display: block;
    font-size: 14px;
}
[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label span {
    white-space: normal !important;
    line-height: 1.35 !important;
}
[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label:hover {
    background: rgba(108,99,255,0.25);
    border-color: rgba(108,99,255,0.6);
    transform: translateX(3px);
}

/* ── Main background ── */
.stApp { background: #0F0F1A; }
.main .block-container { padding-top: 1.5rem; }

/* ── Hero banner ── */
.hero {
    background: linear-gradient(135deg,#1a0a2e 0%,#0d1b3e 50%,#0a2a1a 100%);
    border: 1px solid rgba(108,99,255,0.3);
    border-radius: 20px; padding: 36px 40px; margin-bottom: 28px;
    position: relative; overflow: hidden;
}
.hero::before {
    content:''; position:absolute; top:-60px; right:-60px;
    width:220px; height:220px; border-radius:50%;
    background: radial-gradient(circle,rgba(108,99,255,0.15) 0%,transparent 70%);
    z-index: 0;
    pointer-events: none;
}
.hero::after {
    content:''; position:absolute; bottom:-40px; left:10%;
    width:160px; height:160px; border-radius:50%;
    background: radial-gradient(circle,rgba(0,210,150,0.1) 0%,transparent 70%);
    z-index: 0;
    pointer-events: none;
}
.hero h1 { font-size:30px; font-weight:700; margin:0; color:#fff;
    background: linear-gradient(90deg,#fff,#a78bfa); -webkit-background-clip:text;
    -webkit-text-fill-color:transparent;
    line-height: 1.25;
    overflow-wrap: anywhere;
    position: relative;
    z-index: 1;
}
.hero p  {
    margin:8px 0 0;
    color:rgba(232,232,248,0.7);
    font-size:14px;
    line-height: 1.65;
    overflow-wrap: anywhere;
    position: relative;
    z-index: 1;
}

@media (max-width: 640px) {
    .hero {
        padding: 26px 18px;
    }
    .hero h1 {
        font-size: 24px;
        line-height: 1.3;
    }
    .hero p {
        font-size: 13px;
        line-height: 1.6;
    }
}

/* ── Glass cards ── */
.glass {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 16px; padding: 22px 26px; margin-bottom: 18px;
    backdrop-filter: blur(10px);
    transition: border-color 0.2s, transform 0.2s;
}
.glass:hover { border-color: rgba(108,99,255,0.4); transform: translateY(-2px); }
.glass h3 { color: #a78bfa; margin-top:0; font-size:15px; font-weight:600; }
.glass p, .glass li { color: rgba(232,232,248,0.8); font-size:13.5px; line-height:1.7; }

/* ── Feature tiles ── */
.feat-tile {
    background: linear-gradient(135deg,rgba(108,99,255,0.12),rgba(0,210,150,0.06));
    border: 1px solid rgba(108,99,255,0.25);
    border-radius: 16px; padding: 22px 16px; text-align:center;
    transition: all 0.25s; cursor:default;
}
.feat-tile:hover { transform:translateY(-4px); border-color:rgba(108,99,255,0.6);
    box-shadow: 0 8px 30px rgba(108,99,255,0.2); }
.feat-tile .fi   { font-size:36px; }
.feat-tile .ft   { font-size:14px; font-weight:600; color:#c4b5fd; margin-top:8px; }
.feat-tile .fd   { font-size:12px; color:rgba(232,232,248,0.55); margin-top:4px; }

/* ── Glow stat boxes ── */
.stat-box {
    background: rgba(108,99,255,0.1); border:1px solid rgba(108,99,255,0.3);
    border-radius:14px; padding:18px; text-align:center;
}
.stat-box .sv { font-size:32px; font-weight:700; color:#a78bfa; }
.stat-box .sl { font-size:12px; color:rgba(232,232,248,0.6); margin-top:4px; }

/* ── Section label ── */
.section-label {
    font-size:11px; font-weight:600; letter-spacing:1.5px;
    color:#6C63FF; text-transform:uppercase; margin-bottom:6px;
}

/* ── Chat bubbles ── */
.bubble-user {
    background: linear-gradient(135deg,#6C63FF,#8b5cf6);
    border-radius:18px 18px 4px 18px; padding:12px 16px;
    margin:8px 0; max-width:78%; margin-left:auto;
    color:#fff; font-size:14px; line-height:1.6;
}
.bubble-ai {
    background: rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.1);
    border-radius:18px 18px 18px 4px; padding:12px 16px;
    margin:8px 0; max-width:78%;
    color:rgba(232,232,248,0.9); font-size:14px; line-height:1.6;
}

/* ── Score bar ── */
.sbar-wrap { background:rgba(255,255,255,0.08); border-radius:99px; height:14px; overflow:hidden; }
.sbar-fill  { height:14px; border-radius:99px; transition:width 0.8s ease; }

/* ── Result bands ── */
.res-great  { background:rgba(16,185,129,0.12); border-left:4px solid #10B981;
    border-radius:10px; padding:16px 20px; color:#6ee7b7; }
.res-mild   { background:rgba(245,158,11,0.12); border-left:4px solid #F59E0B;
    border-radius:10px; padding:16px 20px; color:#fcd34d; }
.res-mod    { background:rgba(244,63,94,0.12); border-left:4px solid #F43F5E;
    border-radius:10px; padding:16px 20px; color:#fda4af; }
.res-sev    { background:rgba(220,38,38,0.15); border-left:4px solid #DC2626;
    border-radius:10px; padding:16px 20px; color:#fca5a5; }

/* ── Disclaimer ── */
.disclaim {
    background:rgba(245,158,11,0.08); border-left:4px solid #F59E0B;
    border-radius:8px; padding:12px 16px; font-size:12.5px;
    color:rgba(253,211,77,0.85); margin-top:16px;
}

/* ── Buttons ── */
.stButton > button {
    background: linear-gradient(135deg,#6C63FF,#8b5cf6) !important;
    color: white !important; border: none !important;
    border-radius: 10px !important; padding: 10px 28px !important;
    font-weight: 600 !important; font-size: 14px !important;
    line-height: 1.35 !important;
    height: auto !important;
    white-space: normal !important;
    transition: all 0.2s !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(108,99,255,0.4) !important;
}

/* ── Radio buttons in assessment ── */
.stRadio > label { color: rgba(232,232,248,0.8) !important; font-size:13.5px !important; }
div[role="radiogroup"] label span { color:rgba(232,232,248,0.85) !important; }

/* ── Inputs ── */
.stTextInput input, .stTextArea textarea, .stSelectbox select {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(108,99,255,0.3) !important;
    border-radius: 10px !important; color: #e8e8f8 !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    border-color: rgba(108,99,255,0.7) !important;
    box-shadow: 0 0 0 2px rgba(108,99,255,0.15) !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: rgba(255,255,255,0.04) !important;
    border-radius: 12px !important; padding: 4px !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    gap: 4px !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 9px !important; color: rgba(232,232,248,0.6) !important;
    font-size: 13px !important; font-weight: 500 !important;
    padding: 8px 16px !important;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg,rgba(108,99,255,0.4),rgba(139,92,246,0.3)) !important;
    color: #c4b5fd !important; font-weight: 600 !important;
}

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    background: rgba(108,99,255,0.06) !important;
    border: 2px dashed rgba(108,99,255,0.35) !important;
    border-radius: 12px !important;
}
[data-testid="stFileUploader"] [data-testid="stBaseButton-secondary"] {
    min-height: 42px !important;
}
[data-testid="stFileUploader"] [data-testid="stBaseButton-secondary"] p,
[data-testid="stFileUploader"] [data-testid="stBaseButton-secondary"] span {
    line-height: 1.2 !important;
    white-space: nowrap !important;
    position: static !important;
}
/* Streamlit can render duplicate text nodes in uploader buttons on some themes. */
[data-testid="stFileUploader"] [data-testid="stBaseButton-secondary"] p + p,
[data-testid="stFileUploader"] [data-testid="stBaseButton-secondary"] span + span {
    display: none !important;
}

/* ── Slider ── */
.stSlider > div > div > div { background: #6C63FF !important; }

/* ── Expander ── */
.streamlit-expanderHeader {
    background: rgba(108,99,255,0.08) !important;
    border-radius: 8px !important; color: #a78bfa !important;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #0F0F1A; }
::-webkit-scrollbar-thumb { background: rgba(108,99,255,0.4); border-radius: 3px; }

#MainMenu, footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── Ollama ────────────────────────────────────────────────────────────────────
def format_ollama_error(exc, detail="", model=""):
    message = (detail or str(exc) or "").strip()

    # Ollama often returns JSON error payloads; surface the nested message when present.
    if message.startswith("{"):
        try:
            parsed = json.loads(message)
            if isinstance(parsed, dict) and parsed.get("error"):
                message = str(parsed["error"]).strip()
        except json.JSONDecodeError:
            pass

    if not message:
        message = "No response body was returned by Ollama."

    lowered = message.lower()

    if "connection refused" in lowered or "failed to establish a new connection" in lowered:
        extra = ""
        if IN_CODESPACES and "localhost" in OLLAMA_HOST:
            extra = (
                " In Codespaces, localhost points to the container. "
                "Run Ollama inside the same container or set OLLAMA_HOST to a reachable Ollama URL."
            )
        elif IN_STREAMLIT_CLOUD and "localhost" in OLLAMA_HOST:
            extra = (
                " On Streamlit Cloud, localhost points to the app container. "
                "Set OLLAMA_HOST to a hosted Ollama API URL (for example https://api.ollama.com) "
                "and provide OLLAMA_API_KEY in Streamlit secrets."
            )
        return (
            f"Ollama server is not reachable at {OLLAMA_BASE_URL}. "
            "Start Ollama and make sure the local server is running."
            f"{extra}"
        )

    if "timed out" in lowered:
        return (
            f"The Ollama request timed out while using model '{model}'. "
            "Try a smaller model or retry once the server is responsive."
        )

    if "403" in lowered or "forbidden" in lowered:
        return (
            "Ollama rejected the request (403 Forbidden). "
            "Verify OLLAMA_API_KEY is valid for this endpoint and model."
        )

    if "404" in lowered:
        return (
            f"Ollama endpoint returned 404 at {OLLAMA_BASE_URL}/api/generate. "
            "Check OLLAMA_HOST and ensure it points to an Ollama-compatible API base URL."
        )

    if "500" in lowered or "internal server error" in lowered:
        model_part = f" '{model}'" if model else ""
        return (
            f"Ollama server returned an internal error while using model{model_part}. "
            "Retry with a different model or try again shortly."
        )

    if "not found" in lowered and model:
        return (
            f"Ollama model '{model}' is not available locally. "
            f"Run `ollama pull {model}` and try again."
        )

    model_part = f", model='{model}'" if model else ""
    return f"Ollama request failed (host={OLLAMA_BASE_URL}{model_part}): {message}"

def ollama_generate(prompt, model, images=None):
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }
    if images:
        payload["images"] = images

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "MindAI/1.0 (+https://streamlit.io)",
    }
    if OLLAMA_API_KEY:
        headers["Authorization"] = f"Bearer {OLLAMA_API_KEY}"

    request = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            raw_body = response.read().decode("utf-8", errors="replace")
            try:
                body = json.loads(raw_body)
            except json.JSONDecodeError as exc:
                preview = raw_body[:300] if raw_body else "<empty body>"
                raise RuntimeError(
                    f"Ollama returned a non-JSON response from {OLLAMA_BASE_URL}/api/generate: {preview}"
                ) from exc
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(format_ollama_error(exc, detail, model)) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(format_ollama_error(exc, model=model)) from exc

    if body.get("error"):
        raise RuntimeError(format_ollama_error(RuntimeError(body["error"]), body["error"], model))

    return (body.get("response") or "").strip()

def gemini(prompt, system=""):
    full = f"{system}\n\n{prompt}" if system else prompt
    return ollama_generate(full, MODEL)

def gemini_vision(image, prompt):
    if not VISION_MODEL:
        raise RuntimeError(
            "No Ollama vision model is configured. Set OLLAMA_VISION_MODEL in "
            f"{ENV_PATH} to a local multimodal model such as llava."
        )

    import io
    buf = io.BytesIO()
    image.save(buf, format="JPEG")
    encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
    try:
        return ollama_generate(prompt, VISION_MODEL, images=[encoded])
    except RuntimeError as exc:
        message = str(exc)
        lowered = message.lower()
        if "404" in lowered or "403" in lowered or "internal error" in lowered or "500" in lowered:
            raise RuntimeError(
                f"Vision model '{VISION_MODEL}' is currently unavailable on {OLLAMA_BASE_URL}. "
                "Use another vision model in OLLAMA_VISION_MODEL or switch to a local Ollama vision setup. "
                f"Original error: {message}"
            ) from exc
        raise

def extract_pdf(f):
    r = PyPDF2.PdfReader(f)
    return " ".join(p.extract_text() or "" for p in r.pages).strip()

# ── Assessment Data ───────────────────────────────────────────────────────────
CATEGORIES = {
    "🌊 Emotional Regulation": [
        "How easily can you calm yourself when upset or stressed?",
        "When you experience negative emotions, how long does it take to recover?",
        "Do you find it difficult to control your emotions in challenging situations?",
        "How often do you bottle up your emotions rather than express them?",
        "How often do you feel in control of your emotions and reactions?"
    ],
    "🧩 Cognitive & Behavioral Patterns": [
        "Do you often find yourself overthinking situations, even minor ones?",
        "How often do you engage in activities that help you relax or de-stress?",
        "How well do you manage daily responsibilities even when feeling stressed?",
        "How often do you experience intrusive thoughts that disrupt daily functioning?",
        "Do you find it difficult to break out of negative thinking patterns?"
    ],
    "🤝 Interpersonal Relationships": [
        "Do you find it easy to communicate your thoughts and feelings to others?",
        "How often do you feel disconnected from friends, family, or loved ones?",
        "When facing a problem, do you feel comfortable seeking support?",
        "Do you avoid social situations due to anxiety or discomfort?",
        "How often do you feel lonely, even when surrounded by people?"
    ],
    "🪞 Self-Perception & Self-Esteem": [
        "How often do you engage in self-criticism?",
        "Do you feel confident in your abilities and decisions?",
        "How often do you compare yourself to others in a negative way?",
        "Do you struggle with feelings of guilt or worthlessness?",
        "How do you generally feel about yourself and your self-worth?"
    ],
    "⚡ Stress & Anxiety Management": [
        "How often do you feel overwhelmed by stress?",
        "Do you experience frequent physical symptoms of stress (headaches, fatigue)?",
        "How do you typically cope with stressful situations?",
        "Do you struggle with restlessness or constant worry?",
        "How often do you have difficulty sleeping due to stress or anxiety?"
    ],
    "🌙 Mood & Emotional Well-being": [
        "How often do you feel sad or down without a clear reason?",
        "Do you experience frequent mood swings?",
        "How often do you feel emotionally drained or exhausted?",
        "Have you noticed decreased interest in activities you once enjoyed?",
        "Do you often feel hopeless about the future?"
    ],
    "🚀 Motivation & Productivity": [
        "Do you struggle with maintaining motivation for tasks and goals?",
        "How often do you procrastinate on important tasks?",
        "Do you feel a sense of accomplishment in your daily activities?",
        "How often do you find it difficult to concentrate or focus?",
        "Do you feel like you're making progress toward your goals?"
    ],
    "🛡️ Coping Mechanisms & Resilience": [
        "How effectively do you handle setbacks or failures?",
        "Do you have healthy ways to cope with stress and negative emotions?",
        "How often do you feel mentally and emotionally resilient in tough times?",
        "Do you rely on unhealthy coping mechanisms (avoidance, substance use)?",
        "How do you typically respond to unexpected challenges?"
    ]
}
MAX_SCORE = 80

CATEGORY_COLORS = {
    "🌊 Emotional Regulation":           "#6C63FF",
    "🧩 Cognitive & Behavioral Patterns": "#EC4899",
    "🤝 Interpersonal Relationships":     "#10B981",
    "🪞 Self-Perception & Self-Esteem":   "#F59E0B",
    "⚡ Stress & Anxiety Management":     "#EF4444",
    "🌙 Mood & Emotional Well-being":     "#8B5CF6",
    "🚀 Motivation & Productivity":       "#06B6D4",
    "🛡️ Coping Mechanisms & Resilience":  "#84CC16",
}

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align:center;padding:16px 0 8px;">
        <div style="font-size:48px;">🧠</div>
        <div style="font-size:20px;font-weight:700;color:#c4b5fd;margin-top:4px;">MindAI</div>
        <div style="font-size:11px;color:rgba(196,181,253,0.6);margin-top:2px;">Mental Health Platform</div>
    </div>
    <hr style="border-color:rgba(108,99,255,0.2);margin:12px 0;">
    """, unsafe_allow_html=True)

    if "page_nav" not in st.session_state:
        st.session_state.page_nav = "🏠  Home"

    nav_items = [
        "🏠  Home",
        "💬  Chat Q&A",
        "📝  Self-Assessment",
        "📄  PDF Analysis",
        "🖼️  Image Analysis",
        "📊  AI Prediction",
    ]

    for nav_item in nav_items:
        if st.button(nav_item, key=f"nav_btn_{nav_item}", use_container_width=True):
            st.session_state.page_nav = nav_item

    page = st.session_state.page_nav

    st.markdown("<hr style='border-color:rgba(108,99,255,0.2);margin:16px 0;'>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:12px;color:rgba(196,181,253,0.7);margin-bottom:12px;'>👤 Your Profile</div>", unsafe_allow_html=True)

    name       = st.text_input("Name",        placeholder="Your name", label_visibility="collapsed")
    st.markdown("<div style='font-size:11px;color:rgba(232,232,248,0.4);margin:-8px 0 4px;'>Name</div>", unsafe_allow_html=True)
    age        = st.text_input("Age",         placeholder="Age", label_visibility="collapsed")
    st.markdown("<div style='font-size:11px;color:rgba(232,232,248,0.4);margin:-8px 0 4px;'>Age</div>", unsafe_allow_html=True)
    gender     = st.selectbox("Gender",       ["Prefer not to say","Male","Female","Other"], label_visibility="collapsed")
    occupation = st.text_input("Occupation",  placeholder="Occupation", label_visibility="collapsed")
    st.markdown("<div style='font-size:11px;color:rgba(232,232,248,0.4);margin:-8px 0 4px;'>Occupation</div>", unsafe_allow_html=True)

    st.markdown("""
    <hr style="border-color:rgba(108,99,255,0.2);margin:16px 0;">
    <div style="font-size:11px;color:rgba(196,181,253,0.45);line-height:1.7;text-align:center;">
        ⚠️ For research & informational purposes only.<br>
        Always consult a licensed professional.<br><br>
        <span style="opacity:0.5;">M.Tech Dissertation · VIT Vellore<br>Anshi Bajaj · 23MCB0016</span>
    </div>
    """, unsafe_allow_html=True)

user_details = f"Name:{name}, Age:{age}, Gender:{gender}, Occupation:{occupation}" if name else "Not provided"
display_name = name if name else "there"


def go_home_button(btn_key):
    col_spacer, col_action = st.columns([6, 1])
    with col_action:
        if st.button("🏠 Home", key=btn_key):
            st.session_state.page_nav = "🏠  Home"
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: HOME
# ══════════════════════════════════════════════════════════════════════════════
if page == "🏠  Home":
    st.markdown(f"""
    <div class="hero">
        <div style="font-size:11px;letter-spacing:2px;color:#a78bfa;text-transform:uppercase;margin-bottom:8px;">
            🧬 AI-Powered Mental Health Platform
        </div>
        <h1>From Self-analysis to AI Precision</h1>
        <p>Transforming Mental Health Diagnosis with Multi-Modal Data<br>
        <span style="opacity:0.6;"> Mental _health </span></p>
    </div>
    """, unsafe_allow_html=True)

    if name:
        st.markdown(f"""
        <div style="background:rgba(108,99,255,0.1);border:1px solid rgba(108,99,255,0.3);
        border-radius:12px;padding:14px 20px;margin-bottom:20px;font-size:14px;color:#c4b5fd;">
            👋 Welcome back, <strong>{name}</strong>! Your mental wellness journey continues here.
        </div>""", unsafe_allow_html=True)

    # Feature tiles
    cols = st.columns(5)
    tiles = [
        ("💬","Chat Q&A","Natural language mental health assistant"),
        ("📝","Self-Assessment","40-question 8-domain wellness test"),
        ("📄","PDF Analysis","Query your therapy documents"),
        ("🖼️","Image Analysis","Visual mental health detection"),
        ("📊","AI Prediction","Condition match with confidence score"),
    ]
    for col,(icon,title,desc) in zip(cols,tiles):
        with col:
            st.markdown(f"""
            <div class="feat-tile">
                <div class="fi">{icon}</div>
                <div class="ft">{title}</div>
                <div class="fd">{desc}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Stats row
    s1,s2,s3,s4 = st.columns(4)
    for col,(val,lbl) in zip([s1,s2,s3,s4],[
        ("40","Questions in Assessment"),
        ("8","Mental Health Domains"),
        ("5","AI-Powered Modules"),
        ("1","Backend · Ollama"),
    ]):
        with col:
            st.markdown(f"""
            <div class="stat-box">
                <div class="sv">{val}</div>
                <div class="sl">{lbl}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("""
        <div class="glass">
            <h3>📌 About This Platform</h3>
            <p>MindAI is a research-grade AI system that analyses mental health through
            text, documents, images, and structured questionnaires — all powered by a local Ollama server.</p>
            <ul>
                <li>Personalised conversational Q&A with memory</li>
                <li>Clinically-inspired 40-question structured assessment</li>
                <li>Document-grounded contextual answers</li>
                <li>Vision-based emotional indicator analysis</li>
                <li>Condition match score with severity & urgency</li>
            </ul>
        </div>""", unsafe_allow_html=True)

    with col_b:
        st.markdown("""
        <div class="glass">
            <h3>🏗️ System Architecture</h3>
            <p style="font-family:monospace;font-size:12px;line-height:2;
            background:rgba(0,0,0,0.3);padding:14px;border-radius:8px;">
            User Input (Text / PDF / Image / Survey)<br>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;↓<br>
            Ollama Server (Local LLM + Vision)<br>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;↓<br>
            PyPDF2 · 8-Domain Scorer · JSON Parser<br>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;↓<br>
            Answer · Score · Prediction · Report<br>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;↓<br>
            Streamlit Cloud (Public URL)
            </p>
        </div>""", unsafe_allow_html=True)

    st.markdown("""
    <div class="disclaim">
        ⚠️ <strong>Disclaimer:</strong> MindAI is a research proof-of-concept (M.Tech Dissertation, VIT Vellore).
        It is <strong>NOT</strong> a substitute for professional medical advice, diagnosis, or treatment.
        Always consult a licensed mental health professional for any personal concerns.
    </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: CHAT Q&A
# ══════════════════════════════════════════════════════════════════════════════
elif page == "💬  Chat Q&A":
    go_home_button("go_home_chat")
    st.markdown("""
    <div class="hero">
        <h1>💬 Mental Health Chat</h1>
        <p>Ask anything — symptoms, conditions, coping strategies, treatments</p>
    </div>""", unsafe_allow_html=True)

    CHAT_SYS = """You are MindAI, a warm, knowledgeable, and compassionate mental health assistant.
Rules:
- Be empathetic, non-judgmental, supportive
- Provide accurate evidence-based information
- Never diagnose; always suggest professional help for personal concerns
- Format responses with clear sections when helpful
- Use a friendly, approachable tone"""

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Chat container
    chat_container = st.container()
    with chat_container:
        if not st.session_state.messages:
            st.markdown(f"""
            <div style="text-align:center;padding:40px 20px;color:rgba(232,232,248,0.5);">
                <div style="font-size:52px;margin-bottom:12px;">🧠</div>
                <div style="font-size:16px;font-weight:500;color:rgba(196,181,253,0.8);">
                    Hi {display_name}! I'm MindAI.</div>
                <div style="font-size:13px;margin-top:6px;">
                    Ask me anything about mental health — I'm here to help.</div>
                <div style="display:flex;gap:10px;justify-content:center;margin-top:20px;flex-wrap:wrap;">
                    <span style="background:rgba(108,99,255,0.15);border:1px solid rgba(108,99,255,0.3);
                    border-radius:20px;padding:6px 14px;font-size:12px;color:#a78bfa;">
                    💭 What is anxiety?</span>
                    <span style="background:rgba(108,99,255,0.15);border:1px solid rgba(108,99,255,0.3);
                    border-radius:20px;padding:6px 14px;font-size:12px;color:#a78bfa;">
                    🌙 How to sleep better?</span>
                    <span style="background:rgba(108,99,255,0.15);border:1px solid rgba(108,99,255,0.3);
                    border-radius:20px;padding:6px 14px;font-size:12px;color:#a78bfa;">
                    🧘 Coping with stress</span>
                </div>
            </div>""", unsafe_allow_html=True)

        for msg in st.session_state.messages:
            if msg["role"] == "user":
                st.markdown(f'<div style="display:flex;justify-content:flex-end;"><div class="bubble-user">{msg["content"]}</div></div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div style="display:flex;"><div style="font-size:20px;margin-right:8px;margin-top:4px;">🧠</div><div class="bubble-ai">{msg["content"]}</div></div>', unsafe_allow_html=True)

    col_input, col_btn = st.columns([5,1])
    with col_input:
        prompt = st.text_input(
            "Chat message",
            placeholder="Type your question here...",
            label_visibility="collapsed",
            key="chat_input"
        )
    with col_btn:
        send = st.button("Send →", key="send_btn")

    if send and prompt and prompt.strip():
        st.session_state.messages.append({"role":"user","content":prompt})
        with st.spinner(""):
            try:
                history = "\n".join(
                    f"{'User' if m['role']=='user' else 'MindAI'}: {m['content']}"
                    for m in st.session_state.messages[-8:]
                )
                reply = gemini(f"User details: {user_details}\n\nConversation:\n{history}", CHAT_SYS)
                st.session_state.messages.append({"role":"assistant","content":reply})
            except Exception as e:
                st.session_state.messages.append({"role":"assistant","content":f"Sorry, I encountered an error: {e}"})
        st.rerun()

    if st.session_state.messages:
        if st.button("🗑️ New conversation"):
            st.session_state.messages = []
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: SELF-ASSESSMENT
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📝  Self-Assessment":
    go_home_button("go_home_assess")
    st.markdown("""
    <div class="hero">
        <h1>📝 Mental Health Self-Assessment</h1>
        <p>40 research-inspired questions · 8 domains · Personalised AI report</p>
    </div>""", unsafe_allow_html=True)

    if not name:
        st.markdown("""
        <div style="background:rgba(108,99,255,0.1);border:1px solid rgba(108,99,255,0.3);
        border-radius:10px;padding:12px 18px;font-size:13px;color:#a78bfa;margin-bottom:16px;">
            👈 Enter your name in the sidebar for a personalised report
        </div>""", unsafe_allow_html=True)

    # Progress tracker
    if "assess_page" not in st.session_state:
        st.session_state.assess_page = 0
    if "assess_responses" not in st.session_state:
        st.session_state.assess_responses = {}

    cat_list = list(CATEGORIES.items())
    total_cats = len(cat_list)
    current_page = st.session_state.assess_page

    if current_page < total_cats:
        # Progress bar
        pct_done = int((current_page / total_cats) * 100)
        st.markdown(f"""
        <div style="margin-bottom:20px;">
            <div style="display:flex;justify-content:space-between;font-size:12px;
            color:rgba(232,232,248,0.5);margin-bottom:6px;">
                <span>Domain {current_page+1} of {total_cats}</span>
                <span>{pct_done}% complete</span>
            </div>
            <div class="sbar-wrap">
                <div class="sbar-fill" style="width:{pct_done}%;
                background:linear-gradient(90deg,#6C63FF,#8b5cf6);"></div>
            </div>
        </div>""", unsafe_allow_html=True)

        cat_name, questions = cat_list[current_page]
        cat_color = CATEGORY_COLORS.get(cat_name, "#6C63FF")

        st.markdown(f"""
        <div class="glass" style="border-color:rgba({int(cat_color[1:3],16)},{int(cat_color[3:5],16)},{int(cat_color[5:7],16)},0.4);">
            <h3 style="color:{cat_color};font-size:18px;">{cat_name}</h3>
            <p style="font-size:12px;opacity:0.6;">Answer honestly — there are no right or wrong answers</p>
        </div>""", unsafe_allow_html=True)

        page_responses = {}
        for i, question in enumerate(questions):
            q_key = f"{cat_name}_{i}"
            existing = st.session_state.assess_responses.get(q_key, "No")
            st.markdown(f"""
            <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
            border-radius:10px;padding:14px 18px;margin-bottom:8px;">
                <div style="font-size:13.5px;color:rgba(232,232,248,0.85);margin-bottom:10px;">
                    <span style="color:{cat_color};font-weight:600;">Q{i+1}.</span> {question}
                </div>""", unsafe_allow_html=True)
            page_responses[q_key] = st.radio(
                f"q_{cat_name}_{i}",
                ["No", "Sometimes", "Often"],
                horizontal=True,
                index=["No","Sometimes","Often"].index(existing),
                label_visibility="collapsed",
                key=f"radio_{cat_name}_{i}"
            )
            st.markdown("</div>", unsafe_allow_html=True)

        col_prev, col_next = st.columns([1,1])
        with col_prev:
            if current_page > 0:
                if st.button("← Previous"):
                    st.session_state.assess_responses.update(page_responses)
                    st.session_state.assess_page -= 1
                    st.rerun()
        with col_next:
            btn_label = "Next Domain →" if current_page < total_cats - 1 else "✨ Get My Results"
            if st.button(btn_label):
                st.session_state.assess_responses.update(page_responses)
                st.session_state.assess_page += 1
                st.rerun()

    else:
        # ── RESULTS PAGE ────────────────────────────────────────────────────
        responses = st.session_state.assess_responses

        score = sum(
            2 if responses.get(f"{c}_{i}","No") == "Often"
            else 1 if responses.get(f"{c}_{i}","No") == "Sometimes"
            else 0
            for c, qs in CATEGORIES.items()
            for i in range(len(qs))
        )

        cat_scores = {
            c: sum(
                2 if responses.get(f"{c}_{i}","No") == "Often"
                else 1 if responses.get(f"{c}_{i}","No") == "Sometimes"
                else 0
                for i in range(len(qs))
            )
            for c, qs in CATEGORIES.items()
        }

        pct = int((score / MAX_SCORE) * 100)
        bar_col = "#10B981" if pct<=25 else "#F59E0B" if pct<=50 else "#F43F5E" if pct<=75 else "#DC2626"

        st.markdown("### 🎯 Your Results")

        # Big score display
        c_score, c_verdict = st.columns([1,2])
        with c_score:
            st.markdown(f"""
            <div style="background:rgba(108,99,255,0.1);border:2px solid rgba(108,99,255,0.3);
            border-radius:20px;padding:30px;text-align:center;">
                <div style="font-size:64px;font-weight:800;color:{bar_col};line-height:1;">
                    {score}</div>
                <div style="font-size:16px;color:rgba(232,232,248,0.5);margin-top:4px;">
                    out of {MAX_SCORE}</div>
                <div style="margin-top:14px;">
                    <div class="sbar-wrap">
                        <div class="sbar-fill" style="width:{pct}%;background:{bar_col};"></div>
                    </div>
                    <div style="font-size:12px;color:rgba(232,232,248,0.4);margin-top:4px;">
                        {pct}th percentile</div>
                </div>
            </div>""", unsafe_allow_html=True)

        with c_verdict:
            if score <= 20:
                st.markdown(f'<div class="res-great"><strong>🌟 Excellent Mental Well-being</strong><br><br>{display_name}, your responses suggest a strong and healthy mental state. Keep nurturing these positive habits — you\'re doing great!</div>', unsafe_allow_html=True)
            elif score <= 40:
                st.markdown(f'<div class="res-mild"><strong>🌤️ Mild Stress Detected</strong><br><br>{display_name}, some areas show mild emotional strain. Small lifestyle adjustments and mindfulness practices can make a significant difference.</div>', unsafe_allow_html=True)
            elif score <= 60:
                st.markdown(f'<div class="res-mod"><strong>⚠️ Moderate Distress Indicated</strong><br><br>{display_name}, several domains show elevated scores. Speaking with a counsellor or therapist could provide meaningful support and relief.</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="res-sev"><strong>🚨 Please Seek Professional Support</strong><br><br>{display_name}, your responses indicate significant distress across multiple areas. We strongly encourage reaching out to a mental health professional as soon as possible.</div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### 🗂️ Domain Breakdown")

        cols = st.columns(2)
        for idx, (cat, cs) in enumerate(cat_scores.items()):
            cat_pct = int((cs / 10) * 100)
            cat_color = CATEGORY_COLORS.get(cat, "#6C63FF")
            with cols[idx % 2]:
                st.markdown(f"""
                <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
                border-radius:10px;padding:12px 16px;margin-bottom:10px;">
                    <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
                        <span style="font-size:13px;color:rgba(232,232,248,0.8);">{cat}</span>
                        <span style="font-size:13px;font-weight:600;color:{cat_color};">{cs}/10</span>
                    </div>
                    <div class="sbar-wrap">
                        <div class="sbar-fill" style="width:{cat_pct}%;background:{cat_color};"></div>
                    </div>
                </div>""", unsafe_allow_html=True)

        # AI Report
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### 🤖 Your Personalised AI Report")

        with st.spinner("✨ Generating your personalised mental health report..."):
            try:
                top3 = sorted(cat_scores.items(), key=lambda x: x[1], reverse=True)[:3]
                top_str = ", ".join(f"{d[0]} ({d[1]}/10)" for d in top3)
                prompt = f"""You are a compassionate mental health professional writing a personalised well-being report.

Patient: {user_details}
Total Score: {score}/{MAX_SCORE} ({pct}%)
Top Concern Domains: {top_str}

Write a warm, personalised, structured report with:
1. **Personal Summary** — Address them by name, acknowledge their effort
2. **Key Areas of Concern** — What the top domains mean in everyday life
3. **Your Strengths** — Positive patterns from lower-scoring domains
4. **Personalised Action Plan** — 5 specific, actionable, realistic recommendations
5. **Next Steps** — Clear guidance: self-manage / counselling / urgent help

Tone: warm, encouraging, constructive, non-clinical. Never diagnose."""
                report = gemini(prompt)
                st.markdown(f'<div class="glass">{report}</div>', unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Could not generate report: {e}")

        col_r1, col_r2 = st.columns(2)
        with col_r1:
            if st.button("🔄 Retake Assessment"):
                st.session_state.assess_page = 0
                st.session_state.assess_responses = {}
                st.rerun()

    st.markdown("""
    <div class="disclaim">
        ⚠️ This assessment is not a clinical diagnosis. Please consult a licensed mental health professional.
    </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: PDF ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📄  PDF Analysis":
    go_home_button("go_home_pdf")
    st.markdown("""
    <div class="hero">
        <h1>📄 Document Analysis</h1>
        <p>Upload a therapy report, clinical assessment, or any mental health PDF and ask questions</p>
    </div>""", unsafe_allow_html=True)

    uploaded_pdf = st.file_uploader(
        "Drop your PDF here or click to upload",
        type=["pdf"],
        key="pdf_upload"
    )

    if uploaded_pdf:
        with st.spinner("📖 Reading document..."):
            pdf_text = extract_pdf(uploaded_pdf)

        if not pdf_text:
            st.markdown("""
            <div style="background:rgba(220,38,38,0.1);border:1px solid #DC2626;border-radius:10px;
            padding:14px 18px;color:#fca5a5;font-size:13px;">
                ❌ Could not extract text. This may be a scanned/image-based PDF.
            </div>""", unsafe_allow_html=True)
        else:
            wc = len(pdf_text.split())
            st.markdown(f"""
            <div style="background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.4);
            border-radius:10px;padding:12px 18px;color:#6ee7b7;font-size:13px;margin-bottom:16px;">
                ✅ <strong>{uploaded_pdf.name}</strong> — {wc:,} words extracted successfully
            </div>""", unsafe_allow_html=True)

            with st.expander("📜 Preview extracted text"):
                st.markdown(f"""
                <div style="background:rgba(0,0,0,0.3);border-radius:8px;padding:14px;
                font-family:monospace;font-size:12px;color:rgba(232,232,248,0.7);
                max-height:200px;overflow-y:auto;white-space:pre-wrap;">
                {pdf_text[:2000]}{"..." if len(pdf_text)>2000 else ""}
                </div>""", unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # Suggested questions
            st.markdown("""
            <div style="font-size:12px;color:rgba(196,181,253,0.6);margin-bottom:8px;">
            💡 Suggested questions:
            </div>
            <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px;">
                <span style="background:rgba(108,99,255,0.12);border:1px solid rgba(108,99,255,0.25);
                border-radius:20px;padding:5px 12px;font-size:12px;color:#a78bfa;">
                What are the main symptoms?</span>
                <span style="background:rgba(108,99,255,0.12);border:1px solid rgba(108,99,255,0.25);
                border-radius:20px;padding:5px 12px;font-size:12px;color:#a78bfa;">
                What treatment was recommended?</span>
                <span style="background:rgba(108,99,255,0.12);border:1px solid rgba(108,99,255,0.25);
                border-radius:20px;padding:5px 12px;font-size:12px;color:#a78bfa;">
                Summarise the key findings</span>
            </div>""", unsafe_allow_html=True)

            question = st.text_input("Ask a question about this document:",
                placeholder="e.g. What are the main symptoms mentioned?")

            if st.button("🔍 Get Answer") and question:
                with st.spinner("Analysing document..."):
                    try:
                        ans = gemini(f"""Mental health document analyst. Answer ONLY from this document.

Document:
\"\"\"{pdf_text[:4000]}\"\"\"

Question: {question}

Be specific. Cite relevant parts. If not in document, say so.""")
                        st.markdown(f'<div class="glass"><h3>📋 Answer</h3>{ans}</div>', unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"Error: {e}")
    else:
        st.markdown("""
        <div class="glass">
            <h3>📌 How to use Document Analysis</h3>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px;">
                <div style="background:rgba(108,99,255,0.08);border-radius:8px;padding:12px;">
                    <div style="font-size:20px;">1️⃣</div>
                    <div style="font-size:13px;margin-top:6px;color:rgba(232,232,248,0.8);">
                    Upload any mental health PDF</div>
                </div>
                <div style="background:rgba(108,99,255,0.08);border-radius:8px;padding:12px;">
                    <div style="font-size:20px;">2️⃣</div>
                    <div style="font-size:13px;margin-top:6px;color:rgba(232,232,248,0.8);">
                    AI reads and understands it</div>
                </div>
                <div style="background:rgba(108,99,255,0.08);border-radius:8px;padding:12px;">
                    <div style="font-size:20px;">3️⃣</div>
                    <div style="font-size:13px;margin-top:6px;color:rgba(232,232,248,0.8);">
                    Ask any question about it</div>
                </div>
                <div style="background:rgba(108,99,255,0.08);border-radius:8px;padding:12px;">
                    <div style="font-size:20px;">4️⃣</div>
                    <div style="font-size:13px;margin-top:6px;color:rgba(232,232,248,0.8);">
                    Get accurate, grounded answers</div>
                </div>
            </div>
        </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: IMAGE ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🖼️  Image Analysis":
    go_home_button("go_home_image")
    st.markdown("""
    <div class="hero">
        <h1>🖼️ Visual Mental Health Analysis</h1>
        <p>Upload an image — artwork, expression, or visual journal — for AI-powered analysis</p>
    </div>""", unsafe_allow_html=True)

    col_up, col_res = st.columns([1,1])

    with col_up:
        uploaded_img = st.file_uploader("Upload image (JPG / PNG)", type=["jpg","jpeg","png"])
        context = st.text_area("Add context (optional):",
            placeholder="e.g. Patient drawing from therapy session, age 24...", height=80)

        if uploaded_img:
            img = Image.open(uploaded_img)
            st.image(img, caption="Uploaded Image", use_container_width=True)

            if st.button("🔍 Analyse This Image"):
                with col_res:
                    with st.spinner("👁️ Analysing..."):
                        try:
                            prompt = f"""Analyse this image in a mental health context. Provide:

1. **Emotional Tone** — What emotions or states are visually present
2. **Mental Health Indicators** — Colours, patterns, or expressions that may reflect mental state
3. **Well-being Impression** — Overall psychological reading of the image
4. **Supportive Observations** — Constructive, empathetic insights

Be warm, non-diagnostic, and evidence-informed.
{f'Context: {context}' if context else ''}"""
                            result = gemini_vision(img, prompt)
                            st.markdown(f'<div class="glass"><h3>🧠 Analysis</h3>{result}</div>', unsafe_allow_html=True)
                        except Exception as e:
                            st.error(f"Error: {e}")
        else:
            with col_res:
                st.markdown("""
                <div class="glass" style="height:100%;">
                    <h3>🎨 What can be analysed?</h3>
                    <ul>
                        <li>Patient artwork from therapy sessions</li>
                        <li>Facial expression photographs</li>
                        <li>Mood boards or visual journals</li>
                        <li>Drawings or sketches</li>
                        <li>Any image with mental health context</li>
                    </ul>
                    <p style="margin-top:14px;opacity:0.6;font-size:12px;">
                    Upload an image on the left to begin analysis</p>
                </div>""", unsafe_allow_html=True)

    st.markdown("""
    <div class="disclaim">
        ⚠️ Visual AI analysis is supplementary only and cannot clinically diagnose mental health conditions.
    </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: AI PREDICTION
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📊  AI Prediction":
    go_home_button("go_home_prediction")
    st.markdown("""
    <div class="hero">
        <h1>📊 AI Mental Health Prediction</h1>
        <p>Describe your symptoms · Get a condition match score · Severity & urgency rating</p>
    </div>""", unsafe_allow_html=True)

    col_form, col_info = st.columns([3,2])

    with col_form:
        st.markdown('<div class="glass"><h3>📝 Tell us how you\'ve been feeling</h3>', unsafe_allow_html=True)

        description = st.text_area("Describe your symptoms or mental state:",
            height=150,
            placeholder="e.g. For the past few weeks I've felt persistently sad, lost interest in hobbies, trouble sleeping, low energy, and difficulty concentrating at work...")

        col_d, col_s = st.columns(2)
        with col_d:
            duration = st.selectbox("How long?", [
                "Select duration","Less than 1 week","1–2 weeks",
                "2–4 weeks","1–3 months","3–6 months","More than 6 months"
            ])
        with col_s:
            severity = st.slider("Severity:", 1, 10, 5)

        pdf_report = st.file_uploader("Attach a PDF report (optional):", type=["pdf"], key="pred_pdf")
        report_ctx = ""
        if pdf_report:
            report_ctx = extract_pdf(pdf_report)[:1500]
            st.markdown(f"""
            <div style="background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.3);
            border-radius:8px;padding:8px 14px;font-size:12px;color:#6ee7b7;margin-top:6px;">
                ✅ Report attached: {pdf_report.name}
            </div>""", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

    with col_info:
        st.markdown("""
        <div class="glass">
            <h3>🎯 What you'll get</h3>
            <div style="display:flex;flex-direction:column;gap:10px;margin-top:8px;">
                <div style="display:flex;align-items:center;gap:10px;">
                    <span style="font-size:20px;">📈</span>
                    <span style="font-size:13px;">Condition match percentage</span>
                </div>
                <div style="display:flex;align-items:center;gap:10px;">
                    <span style="font-size:20px;">🏷️</span>
                    <span style="font-size:13px;">Primary & secondary conditions</span>
                </div>
                <div style="display:flex;align-items:center;gap:10px;">
                    <span style="font-size:20px;">🌡️</span>
                    <span style="font-size:13px;">Severity assessment</span>
                </div>
                <div style="display:flex;align-items:center;gap:10px;">
                    <span style="font-size:20px;">⏰</span>
                    <span style="font-size:13px;">Urgency rating</span>
                </div>
                <div style="display:flex;align-items:center;gap:10px;">
                    <span style="font-size:20px;">💡</span>
                    <span style="font-size:13px;">Personalised recommendations</span>
                </div>
            </div>
        </div>""", unsafe_allow_html=True)

        st.markdown("""
        <div class="glass" style="margin-top:0;">
            <h3>🔬 Conditions Assessed</h3>
            <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:6px;">
        """ + "".join(
            f'<span style="background:rgba(108,99,255,0.15);border:1px solid rgba(108,99,255,0.25);'
            f'border-radius:20px;padding:3px 10px;font-size:11px;color:#a78bfa;">{c}</span>'
            for c in ["Depression","Anxiety","PTSD","OCD","Bipolar","Schizophrenia","ADHD","Eating Disorder","Sleep Disorder"]
        ) + "</div></div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("✨ Generate AI Prediction"):
        if not description or len(description.strip()) < 20:
            st.markdown("""
            <div style="background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.4);
            border-radius:8px;padding:12px 16px;font-size:13px;color:#fcd34d;">
                ⚠️ Please describe your symptoms in more detail (at least 2–3 sentences).
            </div>""", unsafe_allow_html=True)
        else:
            with st.spinner("🔮 AI is analysing your input..."):
                try:
                    rpt = f"\nAttached report:\n{report_ctx}" if report_ctx else ""
                    pred_prompt = f"""Expert AI mental health assessment tool.

Patient: {user_details}
Description: {description}
Duration: {duration}
Severity: {severity}/10{rpt}

Respond ONLY with valid JSON (no markdown, no extra text):
{{
  "match_percentage": <0-100>,
  "primary_condition": "<condition>",
  "secondary_conditions": ["<c1>","<c2>"],
  "key_symptoms_identified": ["<s1>","<s2>","<s3>","<s4>"],
  "missing_indicators": ["<m1>","<m2>"],
  "severity_assessment": "<Mild|Moderate|Severe>",
  "urgency": "<Routine|Soon|Urgent>",
  "recommendation": "<2-3 empathetic sentences>"
}}"""
                    raw = gemini(pred_prompt)
                    raw = re.sub(r"```json|```","",raw).strip()
                    r   = json.loads(raw)

                    pct     = r.get("match_percentage", 0)
                    sev     = r.get("severity_assessment","N/A")
                    urg     = r.get("urgency","N/A")
                    primary = r.get("primary_condition","N/A")

                    bar_col  = "#10B981" if pct<40 else "#F59E0B" if pct<70 else "#DC2626"
                    sev_col  = {"Mild":"#10B981","Moderate":"#F59E0B","Severe":"#DC2626"}.get(sev,"#6B7280")
                    urg_icon = {"Routine":"🟢","Soon":"🟡","Urgent":"🔴"}.get(urg,"⚪")

                    st.markdown("---")
                    st.markdown("### 📊 Your Prediction Results")

                    # Big match score
                    st.markdown(f"""
                    <div style="background:rgba(108,99,255,0.08);border:1px solid rgba(108,99,255,0.25);
                    border-radius:16px;padding:24px;margin-bottom:20px;">
                        <div style="display:flex;align-items:center;gap:24px;flex-wrap:wrap;">
                            <div style="text-align:center;min-width:120px;">
                                <div style="font-size:56px;font-weight:800;color:{bar_col};line-height:1;">
                                    {pct}%</div>
                                <div style="font-size:12px;color:rgba(232,232,248,0.5);margin-top:4px;">
                                    Match Confidence</div>
                            </div>
                            <div style="flex:1;min-width:200px;">
                                <div style="font-size:18px;font-weight:600;color:#c4b5fd;margin-bottom:8px;">
                                    {primary}</div>
                                <div class="sbar-wrap" style="height:10px;">
                                    <div class="sbar-fill" style="width:{pct}%;background:{bar_col};height:10px;"></div>
                                </div>
                                <div style="display:flex;gap:16px;margin-top:12px;flex-wrap:wrap;">
                                    <span style="font-size:13px;color:{sev_col};">
                                        🌡️ Severity: <strong>{sev}</strong></span>
                                    <span style="font-size:13px;color:rgba(232,232,248,0.7);">
                                        {urg_icon} Urgency: <strong>{urg}</strong></span>
                                </div>
                            </div>
                        </div>
                    </div>""", unsafe_allow_html=True)

                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown('<div class="glass"><h3>✅ Symptoms Identified</h3>', unsafe_allow_html=True)
                        for s in r.get("key_symptoms_identified",[]):
                            st.markdown(f"<div style='padding:4px 0;font-size:13px;'>• {s}</div>", unsafe_allow_html=True)
                        st.markdown("</div>", unsafe_allow_html=True)

                        st.markdown('<div class="glass"><h3>🔍 Secondary Conditions</h3>', unsafe_allow_html=True)
                        for c in r.get("secondary_conditions",[]):
                            st.markdown(f"<div style='padding:4px 0;font-size:13px;'>• {c}</div>", unsafe_allow_html=True)
                        st.markdown("</div>", unsafe_allow_html=True)

                    with col_b:
                        st.markdown('<div class="glass"><h3>⚠️ Missing Indicators</h3>', unsafe_allow_html=True)
                        for m in r.get("missing_indicators",[]):
                            st.markdown(f"<div style='padding:4px 0;font-size:13px;'>• {m}</div>", unsafe_allow_html=True)
                        st.markdown("</div>", unsafe_allow_html=True)

                        st.markdown(f'<div class="glass"><h3>💡 Recommendation</h3><p>{r.get("recommendation","")}</p></div>', unsafe_allow_html=True)

                    st.markdown("""
                    <div class="disclaim">
                        ⚠️ <strong>Important:</strong> This AI prediction is for research & informational purposes only.
                        It is NOT a clinical diagnosis. Please consult a qualified mental health professional.
                    </div>""", unsafe_allow_html=True)

                except json.JSONDecodeError:
                    st.error("Could not parse AI response. Please try again.")
                except Exception as e:
                    st.error(f"Error: {e}")
