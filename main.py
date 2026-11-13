import logging

from dotenv import load_dotenv

# 1. Carrega variáveis do .env para o os.environ
#    (inclui LANGSMITH_TRACING, respeitando a escolha do usuário no .env)
load_dotenv()

# 2. Importa o bot somente depois de carregar as variáveis de ambiente
from src.telegram_bot import rodar_bot


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    print("🚀 Iniciando AI English Coach via Telegram...")
    rodar_bot()
