# Автотесты для проверки базы данных, картинок, алгоритма Лейтнера и сессии.

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app.config import MODE_MARATHON, MODE_MIX, MODE_ONE_DECK
from app.database import Database
from app.exceptions import DuplicateError, ImageError, NotFoundError, ValidationError
from app.leitner import calculate_next_review, create_study_session
from app.repositories import FlashcardRepository


class FoundationTestCase(unittest.TestCase):
    def setUp(self):
        # Создаём временную папку, чтобы тесты не затрагивали реальные данные
        self.tmp_dir = tempfile.TemporaryDirectory()
        root = Path(self.tmp_dir.name)

        self.db = Database(root / "flashcards.db")
        self.db.initialize()
        self.images_dir = root / "images"
        self.repo = FlashcardRepository(self.db, self.images_dir)

        # Тестовые файлы-заглушки изображений
        self.sample_png = root / "sample.png"
        self.sample_png.write_bytes(b"fake-png")
        self.sample_jpg = root / "sample.jpg"
        self.sample_jpg.write_bytes(b"fake-jpg")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_deck_crud_and_unicode_uniqueness(self):
        deck = self.repo.create_deck("  Английский: глаголы  ")
        self.assertEqual(deck.name, "Английский: глаголы")

        # Проверка уникальности без учёта регистра для кириллицы
        with self.assertRaises(DuplicateError):
            self.repo.create_deck("английский: глаголы")

        with self.assertRaises(ValidationError):
            self.repo.create_deck("   ")

        renamed = self.repo.rename_deck(deck.id, "Физика")
        self.assertEqual(renamed.name, "Физика")

        decks = self.repo.list_decks()
        self.assertEqual(len(decks), 1)
        self.assertEqual(decks[0].name, "Физика")

    def test_card_images_and_cleanup_on_delete(self):
        deck = self.repo.create_deck("Биология")
        card = self.repo.create_card(
            deck.id,
            front_text="Клетка",
            back_image_path=self.sample_png,
        )
        stored_png = self.images_dir / card.back_image
        self.assertTrue(stored_png.is_file())

        # Заменяем картинку на другую — старый файл должен удалиться с диска
        updated = self.repo.update_card(
            card.id,
            front_text="Ядро",
            back_text="Описание",
            new_back_image=self.sample_jpg,
        )
        self.assertFalse(stored_png.exists())
        stored_jpg = self.images_dir / updated.back_image
        self.assertTrue(stored_jpg.is_file())

        # При удалении колоды удаляются карточки и все их изображения
        self.repo.delete_deck(deck.id)
        self.assertFalse(stored_jpg.exists())
        with self.assertRaises(NotFoundError):
            self.repo.get_deck(deck.id)

    def test_invalid_image_and_unicode_search(self):
        deck = self.repo.create_deck("Слова")
        gif = Path(self.tmp_dir.name) / "anim.gif"
        gif.write_bytes(b"GIF89a")

        with self.assertRaises(ImageError):
            self.repo.create_card(deck.id, "Вопрос", "Ответ", front_image_path=gif)

        self.repo.create_card(deck.id, "Яблоко", "Apple")
        self.repo.create_card(deck.id, "Груша", "Pear")

        found = self.repo.get_cards_by_deck(deck.id, search_query="ябл")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].front_text, "Яблоко")

    def test_leitner_and_study_modes(self):
        today = date(2026, 11, 17)

        # Проверяем расчёт коробок и интервалов
        self.assertEqual(calculate_next_review(1, True, today), (2, today + timedelta(days=1)))
        self.assertEqual(calculate_next_review(4, True, today), (5, today + timedelta(days=14)))
        self.assertEqual(calculate_next_review(5, True, today), (5, today + timedelta(days=14)))
        self.assertEqual(calculate_next_review(4, False, today), (1, today))

        d1 = self.repo.create_deck("Математика")
        d2 = self.repo.create_deck("История")
        c1 = self.repo.create_card(d1.id, "2+2", "4", today=today)
        c2 = self.repo.create_card(d2.id, "1961", "Гагарин", today=today)

        one = create_study_session(self.repo, MODE_ONE_DECK, [d1.id], shuffle=False, today=today)
        self.assertEqual(one.initial_count, 1)

        mix = create_study_session(
            self.repo, MODE_MIX, [d1.id, d2.id], shuffle=False, today=today
        )
        self.assertEqual(mix.initial_count, 2)

        session = create_study_session(self.repo, MODE_MARATHON, shuffle=False, today=today)
        self.assertEqual(session.current_card.id, c1.id)

        # «Не знаю» переносит карточку в конец текущей очереди
        session.answer_dont_know()
        self.assertEqual(session.current_card.id, c2.id)

        session.answer_know()
        self.assertEqual(session.current_card.id, c1.id)

        session.answer_know()
        self.assertTrue(session.is_finished)

        summary = session.get_summary()
        self.assertEqual(summary.know_count, 2)
        self.assertEqual(summary.dont_know_count, 1)
        self.assertEqual(summary.completed_cards, 2)

        # На сегодня все карточки повторены
        empty_today = create_study_session(self.repo, MODE_MARATHON, today=today)
        self.assertTrue(empty_today.is_finished)

        # Завтра обе карточки снова появятся (коробка 2 = +1 день)
        tomorrow = create_study_session(
            self.repo, MODE_MARATHON, today=today + timedelta(days=1)
        )
        self.assertEqual(tomorrow.initial_count, 2)


if __name__ == "__main__":
    unittest.main()