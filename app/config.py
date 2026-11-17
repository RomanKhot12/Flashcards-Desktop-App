# Настройки и константы приложения Flashcards.

from pathlib import Path

APP_NAME = "Flashcards"
DEFAULT_DATA_DIR = Path.home() / ".flashcards"
DB_FILENAME = "flashcards.db"
IMAGES_DIRNAME = "images"

# Ограничения из ТЗ
MAX_DECK_NAME_LENGTH = 100
MAX_CARD_TEXT_LENGTH = 2000
ALLOWED_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg")

# Режимы обучения
MODE_ONE_DECK = "one_deck"
MODE_MIX = "mix"
MODE_MARATHON = "marathon"

# Система Лейтнера: коробка -> через сколько дней повторять
MIN_BOX = 1
MAX_BOX = 5
LEITNER_INTERVALS = {1: 0, 2: 1, 3: 3, 4: 7, 5: 14}


def get_db_path(data_dir=DEFAULT_DATA_DIR):
    return data_dir / DB_FILENAME


def get_images_dir(data_dir=DEFAULT_DATA_DIR):
    return data_dir / IMAGES_DIRNAME