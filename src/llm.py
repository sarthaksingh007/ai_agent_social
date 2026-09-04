"""CrewAI LLM wiring. Role-aware: each agent can run on a different model
(config.AGENT_MODELS), with provider resolved from the model-string prefix.

Supported prefixes: ollama_chat/ (local), openai/, anthropic/, groq/.
"""
import litellm
from crewai import LLM

from src import config


class _ReasoningLLM(LLM):
    """OpenAI reasoning-family models (gpt-5*, o1/o3/o4*) reject `max_tokens`,
    custom temperature and `stop` — but CrewAI 0.86 hardcodes max_tokens in
    LLM.call(). Override call() to speak their API directly."""

    def call(self, messages, callbacks=None):  # noqa: D102
        response = litellm.completion(
            model=self.model,
            messages=messages,
            max_completion_tokens=self.max_completion_tokens,
            api_key=self.api_key,
            num_retries=5,
            stream=False,
        )
        return response["choices"][0]["message"]["content"]


def _resolve_model(role: str | None) -> str:
    if role and role in config.AGENT_MODELS:
        return config.AGENT_MODELS[role]
    return config.LLM_MODEL


def get_llm(temperature: float = 0.4, max_tokens: int = 2048,
            role: str | None = None) -> LLM:
    """Return a configured LLM for an agent role (or the default model).

    Lower temperature (~0.2-0.4) keeps structured/JSON output stable, which
    matters because every agent hands off a validated Pydantic object.
    """
    model = _resolve_model(role)

    if model.startswith("ollama"):
        return LLM(
            model=model,
            base_url=config.OLLAMA_BASE_URL,
            api_base=config.OLLAMA_BASE_URL,  # litellm's Ollama provider key
            temperature=temperature,
            max_tokens=max_tokens,
        )

    key = ""
    if model.startswith("openai/"):
        key = config.OPENAI_API_KEY
    elif model.startswith("anthropic/"):
        key = config.ANTHROPIC_API_KEY
    elif model.startswith("groq/"):
        key = config.GROQ_API_KEY

    # OpenAI reasoning-family models need the subclass (see _ReasoningLLM).
    name = model.split("/")[-1]
    if name.startswith(("gpt-5", "o1", "o3", "o4")):
        return _ReasoningLLM(
            model=model,
            api_key=key or None,
            max_completion_tokens=max(max_tokens, 4096),  # room for reasoning
        )

    return LLM(
        model=model,
        api_key=key or None,
        temperature=temperature,
        max_tokens=max_tokens,
        num_retries=5,
    )
