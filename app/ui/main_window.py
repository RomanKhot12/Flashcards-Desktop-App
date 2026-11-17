# Главное окно приложения: список колод, таблица карточек и поиск.

from pathlib import Path

from PyQt6 import uic
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHeaderView,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QTableWidgetItem,
)

from app.exceptions import FlashcardsError
from app.ui.card_dialog import CardDialog


# Главное окно: управление колодами и карточками
class MainWindow(QMainWindow):
    def __init__(self, repo):
        super().__init__()
        self.repo = repo

        # Загружаем разметку окна, созданную для Qt Designer
        ui_path = Path(__file__).resolve().parent / "main_window.ui"
        uic.loadUi(str(ui_path), self)

        self.setup_tables()
        self.connect_signals()
        self.refresh_decks()

    # Настраиваем выделение строк, запрет прямого редактирования ячеек и ширину столбцов
    def setup_tables(self):
        for table in (self.decksTable, self.cardsTable):
            table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            table.verticalHeader().setVisible(False)

        decks_header = self.decksTable.horizontalHeader()
        decks_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        decks_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        decks_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        cards_header = self.cardsTable.horizontalHeader()
        cards_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        cards_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        cards_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        cards_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        cards_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

    # Подключаем кнопки и поля к обработчикам
    def connect_signals(self):
        self.decksTable.itemSelectionChanged.connect(self.on_deck_selected)
        self.searchInput.textChanged.connect(self.on_search_changed)

        self.createDeckButton.clicked.connect(self.on_create_deck)
        self.renameDeckButton.clicked.connect(self.on_rename_deck)
        self.deleteDeckButton.clicked.connect(self.on_delete_deck)

        self.createCardButton.clicked.connect(self.on_create_card)
        self.editCardButton.clicked.connect(self.on_edit_card)
        self.deleteCardButton.clicked.connect(self.on_delete_card)

    # --- Получение текущих выбранных элементов ---

    def get_selected_id(self, table):
        selected_rows = table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        row_index = selected_rows[0].row()
        item = table.item(row_index, 0)
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def get_selected_deck_name(self):
        selected_rows = self.decksTable.selectionModel().selectedRows()
        if not selected_rows:
            return ""
        item = self.decksTable.item(selected_rows[0].row(), 0)
        if item is None:
            return ""
        return item.text()

    # --- Обновление таблиц ---

    def refresh_decks(self, select_deck_id=None):
        if select_deck_id is None:
            select_deck_id = self.get_selected_id(self.decksTable)

        decks = self.repo.list_decks()
        self.decksTable.setRowCount(len(decks))

        row_to_select = -1
        for row_idx, deck in enumerate(decks):
            name_item = QTableWidgetItem(deck.name)
            name_item.setData(Qt.ItemDataRole.UserRole, deck.id)

            total_item = QTableWidgetItem(str(deck.total_cards))
            due_item = QTableWidgetItem(str(deck.due_cards))

            self.decksTable.setItem(row_idx, 0, name_item)
            self.decksTable.setItem(row_idx, 1, total_item)
            self.decksTable.setItem(row_idx, 2, due_item)

            if deck.id == select_deck_id:
                row_to_select = row_idx

        if row_to_select >= 0:
            self.decksTable.selectRow(row_to_select)
        elif len(decks) > 0:
            self.decksTable.selectRow(0)
        self.refresh_cards()

    def on_deck_selected(self):
        self.refresh_cards()

    def on_search_changed(self, text):
        self.refresh_cards()

    def refresh_cards(self):
        deck_id = self.get_selected_id(self.decksTable)
        if deck_id is None:
            self.cardsTable.setRowCount(0)
            return

        query = self.searchInput.text()
        cards = self.repo.get_cards_by_deck(deck_id, search_query=query)
        self.cardsTable.setRowCount(len(cards))

        for row_idx, card in enumerate(cards):
            front_item = QTableWidgetItem(card.front_text)
            front_item.setData(Qt.ItemDataRole.UserRole, card.id)

            back_item = QTableWidgetItem(card.back_text)
            images_item = QTableWidgetItem(self.format_images_label(card))
            box_item = QTableWidgetItem(str(card.box))

            date_text = ""
            if card.next_review_date is not None:
                date_text = card.next_review_date.isoformat()
            date_item = QTableWidgetItem(date_text)

            self.cardsTable.setItem(row_idx, 0, front_item)
            self.cardsTable.setItem(row_idx, 1, back_item)
            self.cardsTable.setItem(row_idx, 2, images_item)
            self.cardsTable.setItem(row_idx, 3, box_item)
            self.cardsTable.setItem(row_idx, 4, date_item)

    def format_images_label(self, card):
        parts = []
        if card.front_image:
            parts.append("Лицо")
        if card.back_image:
            parts.append("Оборот")
        if not parts:
            return "Нет"
        return ", ".join(parts)

    # --- Действия с колодами ---

    def on_create_deck(self):
        name, ok = QInputDialog.getText(self, "Новая колода", "Название колоды:")
        if not ok:
            return
        try:
            deck = self.repo.create_deck(name)
        except FlashcardsError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        self.refresh_decks(select_deck_id=deck.id)

    def on_rename_deck(self):
        deck_id = self.get_selected_id(self.decksTable)
        if deck_id is None:
            QMessageBox.information(self, "Внимание", "Сначала выберите колоду.")
            return

        current_name = self.get_selected_deck_name()
        new_name, ok = QInputDialog.getText(
            self, "Переименование колоды", "Новое название:", text=current_name
        )
        if not ok:
            return

        try:
            self.repo.rename_deck(deck_id, new_name)
        except FlashcardsError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        self.refresh_decks(select_deck_id=deck_id)

    def on_delete_deck(self):
        deck_id = self.get_selected_id(self.decksTable)
        if deck_id is None:
            QMessageBox.information(self, "Внимание", "Сначала выберите колоду.")
            return

        deck_name = self.get_selected_deck_name()
        answer = QMessageBox.question(
            self,
            "Подтверждение удаления",
            f"Удалить колоду «{deck_name}» вместе со всеми её карточками?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            self.repo.delete_deck(deck_id)
        except FlashcardsError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        self.refresh_decks()

    # --- Действия с карточками ---

    def on_create_card(self):
        deck_id = self.get_selected_id(self.decksTable)
        if deck_id is None:
            QMessageBox.information(self, "Внимание", "Сначала выберите или создайте колоду.")
            return

        dialog = CardDialog(parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            self.repo.create_card(
                deck_id=deck_id,
                front_text=dialog.get_front_text(),
                back_text=dialog.get_back_text(),
            )
        except FlashcardsError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        self.refresh_decks(select_deck_id=deck_id)

    def on_edit_card(self):
        deck_id = self.get_selected_id(self.decksTable)
        card_id = self.get_selected_id(self.cardsTable)
        if deck_id is None or card_id is None:
            QMessageBox.information(self, "Внимание", "Сначала выберите карточку.")
            return

        cards = self.repo.get_cards_by_deck(deck_id)
        selected_card = None
        for card in cards:
            if card.id == card_id:
                selected_card = card
                break

        if selected_card is None:
            return

        dialog = CardDialog(card=selected_card, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            self.repo.update_card(
                card_id=card_id,
                front_text=dialog.get_front_text(),
                back_text=dialog.get_back_text(),
            )
        except FlashcardsError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        self.refresh_cards()

    def on_delete_card(self):
        deck_id = self.get_selected_id(self.decksTable)
        card_id = self.get_selected_id(self.cardsTable)
        if deck_id is None or card_id is None:
            QMessageBox.information(self, "Внимание", "Сначала выберите карточку.")
            return

        answer = QMessageBox.question(
            self,
            "Подтверждение удаления",
            "Удалить выбранную карточку?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            self.repo.delete_card(card_id)
        except FlashcardsError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        self.refresh_decks(select_deck_id=deck_id)