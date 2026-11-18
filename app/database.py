# Подключение к локальной базе SQLite и создание таблиц.

import sqlite3
from pathlib import Path

# Поле name_normalized хранит название в нижнем регистре (.casefold()),
# чтобы уникальность работала и для кириллицы (встроенный NOCASE в SQLite её не учитывает).
SCHEMA_SQL = (
    "CREATE TABLE IF NOT EXISTS decks (\n"
    "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "    name TEXT NOT NULL,\n"
    "    name_normalized TEXT NOT NULL UNIQUE,\n"
    "    created_at TEXT NOT NULL\n"
    ");\n"
    "CREATE TABLE IF NOT EXISTS cards (\n"
    "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "    deck_id INTEGER NOT NULL,\n"
    "    front_text TEXT NOT NULL DEFAULT '',\n"
    "    back_text TEXT NOT NULL DEFAULT '',\n"
    "    front_image TEXT,\n"
    "    back_image TEXT,\n"
    "    box INTEGER NOT NULL DEFAULT 1 CHECK (box BETWEEN 1 AND 5),\n"
    "    next_review_date TEXT NOT NULL,\n"
    "    created_at TEXT NOT NULL,\n"
    "    FOREIGN KEY (deck_id) REFERENCES decks(id) ON DELETE CASCADE\n"
    ");\n"
    "CREATE INDEX IF NOT EXISTS idx_cards_deck_id ON cards(deck_id);\n"
    "CREATE INDEX IF NOT EXISTS idx_cards_next_review ON cards(next_review_date);\n"
)


# Отвечает за подключение к SQLite и первичную настройку таблиц
class Database:
    def __init__(self, db_path):
        self.db_path = Path(db_path)

    # Открывает соединение с БД и включает каскадное удаление (foreign_keys).
    # Соединение нужно закрывать через conn.close(): with conn его не закрывает.
    def connect(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # В SQLite внешние ключи выключены по умолчанию — включаем при каждом подключении
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    # Создаёт таблицы и индексы, если база ещё пустая
    def initialize(self):
        conn = self.connect()
        try:
            with conn:
                conn.executescript(SCHEMA_SQL)
        finally:
            conn.close()
