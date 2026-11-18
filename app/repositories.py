# Работа с колодами, карточками, поиском и файлами изображений.

import shutil
import sqlite3
import uuid
from datetime import date, datetime
from pathlib import Path

from app.config import (
    ALLOWED_IMAGE_EXTENSIONS,
    MAX_BOX,
    MAX_CARD_TEXT_LENGTH,
    MAX_DECK_NAME_LENGTH,
    MIN_BOX,
)
from app.exceptions import DuplicateError, ImageError, NotFoundError, ValidationError
from app.models import Card, Deck, DeckSummary


# Хранилище данных: выполняет все операции с БД и картинками
class FlashcardRepository:
    def __init__(self, db, images_dir):
        self.db = db
        self.images_dir = Path(images_dir)
        self.images_dir.mkdir(parents=True, exist_ok=True)

    # Проверка данных

    def check_deck_name(self, name):
        cleaned = name.strip()
        if not cleaned:
            raise ValidationError("Название колоды не может быть пустым.")
        if len(cleaned) > MAX_DECK_NAME_LENGTH:
            raise ValidationError(
                f"Название колоды не должно превышать {MAX_DECK_NAME_LENGTH} символов."
            )
        # casefold() надёжнее lower() при сравнении разных алфавитов
        return cleaned, cleaned.casefold()

    def check_card_side(self, text, has_image, side_label):
        cleaned = text.strip()
        if len(cleaned) > MAX_CARD_TEXT_LENGTH:
            raise ValidationError(
                f"Текст {side_label} стороны не должен превышать {MAX_CARD_TEXT_LENGTH} символов."
            )
        if not cleaned and not has_image:
            raise ValidationError(
                f"{side_label.capitalize()} сторона не может быть пустой: нужен текст или картинка."
            )
        return cleaned

    # Работа с файлами изображений

    # Возвращает полный путь к сохранённой картинке или None
    def get_image_path(self, filename):
        if not filename:
            return None
        return self.images_dir / filename

    # Проверяет формат картинки и копирует её в папку приложения с уникальным именем
    def copy_image(self, source):
        src_path = Path(source)
        if not src_path.is_file():
            raise ImageError(f"Файл изображения не найден: {src_path}")

        ext = src_path.suffix.lower()
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            raise ImageError("Поддерживаются только изображения PNG и JPG/JPEG.")

        self.images_dir.mkdir(parents=True, exist_ok=True)
        # Уникальное имя исключает перезапись файлов с одинаковым названием из разных папок
        unique_name = f"{uuid.uuid4().hex}{ext}"
        dest_path = self.images_dir / unique_name

        try:
            shutil.copy2(src_path, dest_path)
        except OSError as exc:
            raise ImageError(f"Не удалось скопировать изображение: {exc}") from exc

        return unique_name

    # Удаляет файл картинки с диска. Если файл занят, оставляем его: данные в БД уже сохранены
    def delete_image_file(self, filename):
        file_path = self.images_dir / filename
        if file_path.is_file():
            try:
                file_path.unlink()
            except OSError:
                pass

    # Удаляет файлы изображений, если на них больше не ссылается ни одна карточка.
    # Вызывается после сохранения изменений в БД.
    def delete_unused_images(self, filenames):
        conn = self.db.connect()
        try:
            for name in set(filenames):
                if not name:
                    continue
                row = conn.execute(
                    "SELECT 1 FROM cards WHERE front_image = ? OR back_image = ? LIMIT 1",
                    (name, name),
                ).fetchone()
                if row is None:
                    self.delete_image_file(name)
        finally:
            conn.close()

    # Удаляет только что скопированные файлы, если запись в БД завершилась ошибкой
    def cleanup_copied_files(self, filenames):
        for name in filenames:
            self.delete_image_file(name)

    # Преобразование строк БД в модели

    def row_to_deck(self, row):
        return Deck(
            id=row["id"],
            name=row["name"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def row_to_card(self, row):
        return Card(
            id=row["id"],
            deck_id=row["deck_id"],
            front_text=row["front_text"],
            back_text=row["back_text"],
            front_image=row["front_image"],
            back_image=row["back_image"],
            box=row["box"],
            next_review_date=date.fromisoformat(row["next_review_date"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    # Операции с колодами

    # Создаёт новую колоду с проверкой уникальности названия
    def create_deck(self, name):
        cleaned, normalized = self.check_deck_name(name)
        now = datetime.now().isoformat(timespec="seconds")

        conn = self.db.connect()
        try:
            with conn:
                cursor = conn.execute(
                    "INSERT INTO decks (name, name_normalized, created_at) VALUES (?, ?, ?)",
                    (cleaned, normalized, now),
                )
                row = conn.execute(
                    "SELECT * FROM decks WHERE id = ?", (cursor.lastrowid,)
                ).fetchone()
        except sqlite3.IntegrityError as exc:
            raise DuplicateError(f"Колода «{cleaned}» уже существует.") from exc
        finally:
            conn.close()

        return self.row_to_deck(row)

    # Переименовывает существующую колоду
    def rename_deck(self, deck_id, new_name):
        cleaned, normalized = self.check_deck_name(new_name)

        conn = self.db.connect()
        try:
            with conn:
                cursor = conn.execute(
                    "UPDATE decks SET name = ?, name_normalized = ? WHERE id = ?",
                    (cleaned, normalized, deck_id),
                )
                if cursor.rowcount == 0:
                    raise NotFoundError(f"Колода с id={deck_id} не найдена.")
                row = conn.execute("SELECT * FROM decks WHERE id = ?", (deck_id,)).fetchone()
        except sqlite3.IntegrityError as exc:
            raise DuplicateError(f"Колода «{cleaned}» уже существует.") from exc
        finally:
            conn.close()

        return self.row_to_deck(row)

    # Удаляет колоду, все её карточки и связанные файлы изображений
    def delete_deck(self, deck_id):
        conn = self.db.connect()
        try:
            with conn:
                rows = conn.execute(
                    "SELECT front_image, back_image FROM cards WHERE deck_id = ?",
                    (deck_id,),
                ).fetchall()

                # Собираем имена картинок до удаления колоды (карточки удалятся каскадно)
                images_to_check = []
                for row in rows:
                    images_to_check.append(row["front_image"])
                    images_to_check.append(row["back_image"])

                cursor = conn.execute("DELETE FROM decks WHERE id = ?", (deck_id,))
                if cursor.rowcount == 0:
                    raise NotFoundError(f"Колода с id={deck_id} не найдена.")
        finally:
            conn.close()

        self.delete_unused_images(images_to_check)

    # Возвращает колоду по её id
    def get_deck(self, deck_id):
        conn = self.db.connect()
        try:
            row = conn.execute("SELECT * FROM decks WHERE id = ?", (deck_id,)).fetchone()
        finally:
            conn.close()

        if row is None:
            raise NotFoundError(f"Колода с id={deck_id} не найдена.")
        return self.row_to_deck(row)

    # Возвращает список колод с общим числом карточек и числом карточек на сегодня
    def list_decks(self, today=None):
        if today is not None:
            target_date = today.isoformat()
        else:
            target_date = date.today().isoformat()

        query = (
            "SELECT "
            "    d.id, "
            "    d.name, "
            "    d.created_at, "
            "    COUNT(c.id) AS total_cards, "
            "    COALESCE("
            "        SUM(CASE WHEN c.next_review_date <= ? THEN 1 ELSE 0 END), 0"
            "    ) AS due_cards "
            "FROM decks d "
            "LEFT JOIN cards c ON c.deck_id = d.id "
            "GROUP BY d.id "
            "ORDER BY d.name_normalized ASC"
        )
        conn = self.db.connect()
        try:
            rows = conn.execute(query, (target_date,)).fetchall()
        finally:
            conn.close()

        result = []
        for row in rows:
            summary = DeckSummary(
                id=row["id"],
                name=row["name"],
                total_cards=row["total_cards"],
                due_cards=row["due_cards"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            result.append(summary)
        return result

    # Операции с карточками

    # Создаёт карточку в коробке 1 со сроком повторения «сегодня»
    def create_card(
        self,
        deck_id,
        front_text="",
        back_text="",
        front_image_path=None,
        back_image_path=None,
        today=None,
    ):
        has_front_img = front_image_path is not None
        has_back_img = back_image_path is not None
        clean_front = self.check_card_side(front_text, has_front_img, "лицевой")
        clean_back = self.check_card_side(back_text, has_back_img, "оборотной")

        if today is not None:
            review_date = today.isoformat()
        else:
            review_date = date.today().isoformat()
        now = datetime.now().isoformat(timespec="seconds")

        copied_files = []
        try:
            front_img_name = None
            if front_image_path is not None:
                front_img_name = self.copy_image(front_image_path)
                copied_files.append(front_img_name)

            back_img_name = None
            if back_image_path is not None:
                back_img_name = self.copy_image(back_image_path)
                copied_files.append(back_img_name)

            conn = self.db.connect()
            try:
                with conn:
                    deck_exists = conn.execute(
                        "SELECT 1 FROM decks WHERE id = ?", (deck_id,)
                    ).fetchone()
                    if deck_exists is None:
                        raise NotFoundError(f"Колода с id={deck_id} не найдена.")

                    insert_sql = (
                        "INSERT INTO cards ("
                        "    deck_id, front_text, back_text, front_image, back_image, "
                        "    box, next_review_date, created_at"
                        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
                    )
                    cursor = conn.execute(
                        insert_sql,
                        (
                            deck_id,
                            clean_front,
                            clean_back,
                            front_img_name,
                            back_img_name,
                            MIN_BOX,
                            review_date,
                            now,
                        ),
                    )
                    row = conn.execute(
                        "SELECT * FROM cards WHERE id = ?", (cursor.lastrowid,)
                    ).fetchone()
            finally:
                conn.close()
        except Exception:
            # Если при сохранении в БД возникла ошибка, убираем скопированные картинки
            self.cleanup_copied_files(copied_files)
            raise

        return self.row_to_card(row)

    # Обновляет текст и картинки карточки. По умолчанию старые картинки сохраняются.
    def update_card(
        self,
        card_id,
        front_text,
        back_text,
        new_front_image=None,
        remove_front_image=False,
        new_back_image=None,
        remove_back_image=False,
    ):
        conn = self.db.connect()
        try:
            row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
        finally:
            conn.close()

        if row is None:
            raise NotFoundError(f"Карточка с id={card_id} не найдена.")

        existing = self.row_to_card(row)

        # Заранее определяем, останутся ли картинки после редактирования, чтобы проверить стороны
        will_have_front_img = (new_front_image is not None) or (
            existing.front_image is not None and not remove_front_image
        )
        will_have_back_img = (new_back_image is not None) or (
            existing.back_image is not None and not remove_back_image
        )

        clean_front = self.check_card_side(front_text, will_have_front_img, "лицевой")
        clean_back = self.check_card_side(back_text, will_have_back_img, "оборотной")

        copied_files = []
        old_images = []
        try:
            # Определяем новое состояние картинки для лицевой стороны
            if new_front_image is not None:
                front_img_name = self.copy_image(new_front_image)
                copied_files.append(front_img_name)
                old_images.append(existing.front_image)
            elif remove_front_image:
                front_img_name = None
                old_images.append(existing.front_image)
            else:
                front_img_name = existing.front_image

            # Определяем новое состояние картинки для оборотной стороны
            if new_back_image is not None:
                back_img_name = self.copy_image(new_back_image)
                copied_files.append(back_img_name)
                old_images.append(existing.back_image)
            elif remove_back_image:
                back_img_name = None
                old_images.append(existing.back_image)
            else:
                back_img_name = existing.back_image

            conn = self.db.connect()
            try:
                with conn:
                    update_sql = (
                        "UPDATE cards "
                        "SET front_text = ?, back_text = ?, front_image = ?, back_image = ? "
                        "WHERE id = ?"
                    )
                    conn.execute(
                        update_sql,
                        (clean_front, clean_back, front_img_name, back_img_name, card_id),
                    )
                    updated_row = conn.execute(
                        "SELECT * FROM cards WHERE id = ?", (card_id,)
                    ).fetchone()
            finally:
                conn.close()
        except Exception:
            self.cleanup_copied_files(copied_files)
            raise

        # Старые картинки удаляем только после успешного сохранения в БД
        self.delete_unused_images(old_images)
        return self.row_to_card(updated_row)

    # Обновляет номер коробки и дату следующего повторения после ответа пользователя
    def update_card_progress(self, card_id, box, next_review_date):
        if box < MIN_BOX or box > MAX_BOX:
            raise ValidationError(f"Номер коробки должен быть от {MIN_BOX} до {MAX_BOX}.")

        conn = self.db.connect()
        try:
            with conn:
                cursor = conn.execute(
                    "UPDATE cards SET box = ?, next_review_date = ? WHERE id = ?",
                    (box, next_review_date.isoformat(), card_id),
                )
                if cursor.rowcount == 0:
                    raise NotFoundError(f"Карточка с id={card_id} не найдена.")
                row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
        finally:
            conn.close()

        return self.row_to_card(row)

    # Удаляет карточку и неиспользуемые файлы изображений
    def delete_card(self, card_id):
        conn = self.db.connect()
        try:
            with conn:
                row = conn.execute(
                    "SELECT front_image, back_image FROM cards WHERE id = ?", (card_id,)
                ).fetchone()
                if row is None:
                    raise NotFoundError(f"Карточка с id={card_id} не найдена.")

                conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))
        finally:
            conn.close()

        self.delete_unused_images([row["front_image"], row["back_image"]])

    # Возвращает карточки колоды; если задан search_query, фильтрует без учёта регистра
    def get_cards_by_deck(self, deck_id, search_query=""):
        conn = self.db.connect()
        try:
            rows = conn.execute(
                "SELECT * FROM cards WHERE deck_id = ? ORDER BY id ASC", (deck_id,)
            ).fetchall()
        finally:
            conn.close()

        cards = []
        for row in rows:
            cards.append(self.row_to_card(row))

        needle = search_query.strip().casefold()
        if not needle:
            return cards

        # Фильтрация в Python гарантирует корректный поиск по кириллице без учёта регистра
        filtered = []
        for card in cards:
            in_front = needle in card.front_text.casefold()
            in_back = needle in card.back_text.casefold()
            if in_front or in_back:
                filtered.append(card)
        return filtered

    # Выбирает карточки для обучения. Если deck_ids=None, берутся все колоды.
    def get_cards_for_study(self, deck_ids=None, due_only=True, today=None):
        if deck_ids is not None and len(deck_ids) == 0:
            return []

        conditions = []
        params = []

        if deck_ids is not None:
            marks = []
            for _ in deck_ids:
                marks.append("?")
            placeholders = ", ".join(marks)
            conditions.append(f"deck_id IN ({placeholders})")
            params.extend(deck_ids)

        if due_only:
            if today is not None:
                target_date = today.isoformat()
            else:
                target_date = date.today().isoformat()
            conditions.append("next_review_date <= ?")
            params.append(target_date)

        where_sql = ""
        if conditions:
            where_sql = "WHERE " + " AND ".join(conditions)

        query = f"SELECT * FROM cards {where_sql} ORDER BY id ASC"
        conn = self.db.connect()
        try:
            rows = conn.execute(query, params).fetchall()
        finally:
            conn.close()

        result = []
        for row in rows:
            result.append(self.row_to_card(row))
        return result
