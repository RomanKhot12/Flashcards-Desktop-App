# Диалог создания и редактирования карточки.

from pathlib import Path

from PyQt6 import uic
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QDialog, QFileDialog

# Размер области превью картинки (такой же задан в card_dialog.ui)
PREVIEW_WIDTH = 200
PREVIEW_HEIGHT = 150

# В диалоге выбора файла показываем только PNG и JPG/JPEG
IMAGE_FILTER = "Изображения (*.png *.jpg *.jpeg)"


# Окно редактирования текста и картинок лицевой и оборотной сторон карточки
class CardDialog(QDialog):
    def __init__(self, card=None, front_image_path=None, back_image_path=None, parent=None):
        super().__init__(parent)
        ui_path = Path(__file__).resolve().parent / "card_dialog.ui"
        uic.loadUi(str(ui_path), self)

        # Новые картинки, выбранные пользователем (путь к исходному файлу)
        self.new_front_image = None
        self.new_back_image = None
        # Пользователь нажал «Убрать картинку»
        self.front_image_removed = False
        self.back_image_removed = False

        if card is None:
            self.setWindowTitle("Новая карточка")
        else:
            self.setWindowTitle("Редактирование карточки")
            self.frontTextEdit.setPlainText(card.front_text)
            self.backTextEdit.setPlainText(card.back_text)

        # Показываем уже сохранённые картинки карточки
        self.show_preview(self.frontImageLabel, front_image_path)
        self.show_preview(self.backImageLabel, back_image_path)
        self.frontRemoveButton.setEnabled(front_image_path is not None)
        self.backRemoveButton.setEnabled(back_image_path is not None)

        self.frontChooseButton.clicked.connect(self.on_choose_front_image)
        self.frontRemoveButton.clicked.connect(self.on_remove_front_image)
        self.backChooseButton.clicked.connect(self.on_choose_back_image)
        self.backRemoveButton.clicked.connect(self.on_remove_back_image)

        self.saveButton.clicked.connect(self.accept)
        self.cancelButton.clicked.connect(self.reject)

    # Открывает диалог выбора файла и возвращает путь или None
    def ask_image_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выберите изображение", "", IMAGE_FILTER)
        if not path:
            return None
        return path

    # Показывает уменьшенную картинку в области превью или поясняющий текст
    def show_preview(self, label, image_path):
        label.setPixmap(QPixmap())

        if image_path is None:
            label.setText("Нет картинки")
            return

        if not Path(image_path).is_file():
            label.setText("Файл картинки не найден")
            return

        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            label.setText("Не удалось открыть картинку")
            return

        scaled = pixmap.scaled(
            PREVIEW_WIDTH,
            PREVIEW_HEIGHT,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        label.setPixmap(scaled)

    # Лицевая сторона

    def on_choose_front_image(self):
        path = self.ask_image_file()
        if path is None:
            return
        self.new_front_image = path
        self.front_image_removed = False
        self.show_preview(self.frontImageLabel, path)
        self.frontRemoveButton.setEnabled(True)

    def on_remove_front_image(self):
        self.new_front_image = None
        self.front_image_removed = True
        self.show_preview(self.frontImageLabel, None)
        self.frontRemoveButton.setEnabled(False)

    # Оборотная сторона

    def on_choose_back_image(self):
        path = self.ask_image_file()
        if path is None:
            return
        self.new_back_image = path
        self.back_image_removed = False
        self.show_preview(self.backImageLabel, path)
        self.backRemoveButton.setEnabled(True)

    def on_remove_back_image(self):
        self.new_back_image = None
        self.back_image_removed = True
        self.show_preview(self.backImageLabel, None)
        self.backRemoveButton.setEnabled(False)

    # Данные, введённые пользователем

    def get_front_text(self):
        return self.frontTextEdit.toPlainText()

    def get_back_text(self):
        return self.backTextEdit.toPlainText()

    # Путь к новой картинке лицевой стороны или None, если её не меняли
    def get_new_front_image(self):
        return self.new_front_image

    def get_new_back_image(self):
        return self.new_back_image

    # True, если картинку лицевой стороны нужно удалить
    def is_front_image_removed(self):
        return self.front_image_removed

    def is_back_image_removed(self):
        return self.back_image_removed
