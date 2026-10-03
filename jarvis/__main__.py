from jarvis.core.config import get_settings
from jarvis.core.conversation import Conversation
from jarvis.core.logging import setup_logging
from jarvis.llm.client import OllamaClient
from jarvis.llm.system_prompt import build_system_prompt
from jarvis.tools import ToolRunner, default_registry
from jarvis.ui.cli import confirm_in_terminal, run_cli


def main() -> None:
    settings = get_settings()
    logger = setup_logging(settings)
    logger.info(
        "Jarvis starting (model=%s, personality=%s)", settings.ollama_model, settings.personality
    )
    client = OllamaClient(settings.ollama_model)
    runner = ToolRunner(default_registry, confirm=confirm_in_terminal)
    conversation = Conversation(client.chat, build_system_prompt(settings.personality), runner)
    run_cli(conversation)


if __name__ == "__main__":
    main()
