"""System prompt do agente studio_assistant.

Carrega de arquivo .md configurado via AGENT_PROMPT_FILE, com fallback
inline caso o arquivo não exista.
"""

from pathlib import Path

from gyros_os.shared.config import settings


def load_system_prompt() -> str:
    """Carrega system prompt do arquivo configurado em settings.agent_prompt_file.

    Aplica substituição de placeholders {agent_name} e {studio_name}.
    Fallback: prompt inline se arquivo não existir.
    """
    repo_root = Path(__file__).resolve().parents[5]
    prompt_path = repo_root / "prompts" / f"{settings.agent_prompt_file}.md"

    if prompt_path.exists():
        template = prompt_path.read_text(encoding="utf-8")
    else:
        template = (
            "Voce e {agent_name}, assistente de IA da plataforma {studio_name}. "
            "Use a ferramenta search_kb pra buscar na base de conhecimento "
            "antes de responder."
        )

    return template.replace("{agent_name}", settings.agent_name).replace(
        "{studio_name}", settings.studio_name
    )


STUDIO_SYSTEM_PROMPT = load_system_prompt()
