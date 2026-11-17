# Точка входа для запуска графического интерфейса Flashcards.

import sys

from PyQt6.QtWidgets import QApplication

from app.config import get_db_path, get_images_dir
from app.database import Database
from app.repositories import FlashcardRepository
from app.ui.main_window import MainWindow


def main():
    # Инициализируем локальную базу SQLite (.db) и папку для картинок
    db = Database(get_db_path())
    db.initialize()
    repo = FlashcardRepository(db, get_images_dir())

    app = QApplication(sys.argv)
    window = MainWindow(repo)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())