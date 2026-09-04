"""Central configuration — loads environment variables once.

Provider-agnostic LLM config. Default is local Ollama (no rate limits, free),
with Groq available as a fallback by changing LLM_MODEL in .env.
"""
import os

from dotenv import load_dotenv

load_dotenv()

# --- LLM ---
# litellm model string. Examples:
#   ollama_chat/qwen2.5:7b            (local, free)
#   openai/gpt-4o-mini                (OpenAI, cheap & fast)
#   openai/gpt-4o                     (OpenAI, strong reasoning/creative)
#   anthropic/claude-sonnet-4-6       (Claude, paid — fast & high quality)
#   groq/llama-3.3-70b-versatile      (cloud, free tier)
LLM_MODEL = os.getenv("LLM_MODEL", "ollama_chat/qwen2.5:7b")

# Per-agent overrides (fall back to LLM_MODEL): match each agent's task to the
# cheapest model that does it well.
AGENT_MODELS = {
    "account_manager": os.getenv("MODEL_ACCOUNT_MANAGER", LLM_MODEL),
    "strategist": os.getenv("MODEL_STRATEGIST", LLM_MODEL),
    "validator": os.getenv("MODEL_VALIDATOR", LLM_MODEL),
    "copywriter": os.getenv("MODEL_COPYWRITER", LLM_MODEL),
}

# Ollama runs on the host; from inside Docker reach it via host.docker.internal.
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")

# Provider API keys (only the ones matching used models are needed)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# --- Database ---
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://sma:sma_pass@localhost:5432/social_agency",
)

# Demo brief shown in the dashboard (lives here so the UI never has to import
# the heavy pipeline/CrewAI stack — native libs segfault inside Streamlit).
SAMPLE_BRIEF = (
    "Brand: 'Bean There', an independent vegan coffee shop in Bandra, Mumbai. "
    "We roast our own beans and bake fresh vegan pastries. Our vibe is cozy, "
    "witty, and a little cheeky. We want to grow on Instagram and LinkedIn, "
    "targeting young urban professionals (25-35) who care about sustainability. "
    "Goal: grow Instagram followers by 20% and drive weekday foot traffic in 90 days."
)


def is_ollama() -> bool:
    return LLM_MODEL.startswith("ollama")


def ollama_reachable(timeout: float = 2.0) -> bool:
    """True if the configured Ollama server answers. Cheap enough to call from
    the API's /config endpoint so the UI can warn before a run is queued."""
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(
            f"{OLLAMA_BASE_URL.rstrip('/')}/api/tags", timeout=timeout
        ) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def check() -> list[str]:
    """Return a list of setup problems (empty list = all good)."""
    problems = []
    if LLM_MODEL.startswith("groq/") and (
        not GROQ_API_KEY or GROQ_API_KEY.startswith("gsk_your_free_key")
    ):
        problems.append("GROQ_API_KEY is not set (needed for groq/ models)")
    if LLM_MODEL.startswith("anthropic/") and not ANTHROPIC_API_KEY:
        problems.append("ANTHROPIC_API_KEY is not set (needed for Claude models)")
    if LLM_MODEL.startswith("openai/") and not OPENAI_API_KEY:
        problems.append("OPENAI_API_KEY is not set (needed for openai/ models)")
    # Every agent call fails silently if the local server isn't up, which shows
    # up much later as an unparseable dossier. Catch it here instead.
    if is_ollama() and not ollama_reachable():
        problems.append(
            f"Ollama is not reachable at {OLLAMA_BASE_URL} — start it "
            f"(`ollama serve` + `ollama pull {LLM_MODEL.split('/')[-1]}`) "
            f"or set LLM_MODEL in .env to a cloud model"
        )
    if not DATABASE_URL:
        problems.append("DATABASE_URL is not set")
    return problems
