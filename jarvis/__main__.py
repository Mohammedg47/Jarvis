from jarvis.core.config import get_settings
from jarvis.core.logging import setup_logging


def main() -> None:
    settings = get_settings()
    logger = setup_logging(settings)
    logger.info(
        "Jarvis starting (model=%s, personality=%s)", settings.ollama_model, settings.personality
    )


if __name__ == "__main__":
    main()
