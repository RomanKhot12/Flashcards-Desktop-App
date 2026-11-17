# Диалог создания и редактирования карточки.

from pathlib import Path

from PyQt6 import uic
from PyQt6.QtWidgets import QDialog


# Окно редактирования текста лицевой и оборотной сторон карточки
class CardDialog(QDialog):
    def __init__(self, card=None, parent=None):
        super().__init__(parent)
        ui_path = Path(__file__).resolve().parent / "card_dialog.ui"
        uic.loadUi(str(ui_path), self)

        if card is None:
            self.setWindowTitle("Новая карточка")
        else:
            self.setWindowTitle("Редактирование карточки")
            self.frontTextEdit.setPlainText(card.front_text)
            self.backTextEdit.setPlainText(card.back_text)

        self.saveButton.clicked.connect(self.accept)
        self.cancelButton.clicked.connect(self.reject)

    # Возвращает введённый пользователем текст лицевой стороны
    def get_front_text(self):
        return self.frontTextEdit.toPlainText()

    # Возвращает введённый пользователем текст оборотной стороны
    def get_back_text(self):
        return self.backTextEdit.toPlainText()