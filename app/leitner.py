# Алгоритм интервального повторения (система Лейтнера) и учебная сессия.

import random
from datetime import date, timedelta

from app.config import (
    LEITNER_INTERVALS,
    MAX_BOX,
    MIN_BOX,
    MODE_MARATHON,
    MODE_MIX,
    MODE_ONE_DECK,
)
from app.models import SessionSummary


# Считает новую коробку и дату следующего повторения по правилам Лейтнера
def calculate_next_review(current_box, known, today=None):
    if today is not None:
        base_date = today
    else:
        base_date = date.today()

    if known:
        # Переводим в следующую коробку, но не выше 5-й
        new_box = current_box + 1
        if new_box > MAX_BOX:
            new_box = MAX_BOX
        if new_box < MIN_BOX:
            new_box = MIN_BOX
    else:
        # При ошибке карточка всегда возвращается в 1-ю коробку
        new_box = MIN_BOX

    interval_days = LEITNER_INTERVALS[new_box]
    next_date = base_date + timedelta(days=interval_days)
    return new_box, next_date


# Управляет очередью карточек и статистикой в рамках одной учебной сессии
class StudySession:
    def __init__(self, repo, cards, shuffle=True, today=None):
        self.repo = repo
        self.today = today

        # Копируем список карточек и при необходимости перемешиваем
        self.queue = list(cards)
        if shuffle:
            random.shuffle(self.queue)

        self.initial_cards = len(self.queue)
        self.completed_ids = set()
        self.know_count = 0
        self.dont_know_count = 0

    @property
    def initial_count(self):
        return self.initial_cards

    @property
    def remaining_count(self):
        return len(self.queue)

    @property
    def is_finished(self):
        return len(self.queue) == 0

    @property
    def current_card(self):
        if not self.queue:
            return None
        return self.queue[0]

    # Ответ «Знаю»: обновляем коробку в БД и убираем карточку из текущей очереди
    def answer_know(self):
        card = self.require_current_card()
        new_box, next_date = calculate_next_review(card.box, known=True, today=self.today)

        # Сразу сохраняем прогресс в базу данных (если сессию прервут, прогресс не пропадёт)
        updated = self.save_progress(card, new_box, next_date)

        self.queue.pop(0)
        if updated.id is not None:
            self.completed_ids.add(updated.id)
        self.know_count += 1
        return updated

    # Ответ «Не знаю»: сбрасываем в коробку 1 и ставим карточку в конец очереди
    def answer_dont_know(self):
        card = self.require_current_card()
        new_box, next_date = calculate_next_review(card.box, known=False, today=self.today)

        updated = self.save_progress(card, new_box, next_date)

        self.queue.pop(0)
        self.queue.append(updated)
        self.dont_know_count += 1
        return updated

    # Возвращает итоговую статистику сессии
    def get_summary(self):
        return SessionSummary(
            initial_cards=self.initial_cards,
            completed_cards=len(self.completed_ids),
            know_count=self.know_count,
            dont_know_count=self.dont_know_count,
            interrupted=not self.is_finished,
        )

    def require_current_card(self):
        if not self.queue:
            raise RuntimeError("Учебная сессия уже завершена.")
        return self.queue[0]

    def save_progress(self, card, new_box, next_date):
        if card.id is None:
            raise ValueError("Невозможно сохранить прогресс карточки без id.")
        return self.repo.update_card_progress(card.id, new_box, next_date)


# Создаёт учебную сессию для одного из трёх режимов: одна колода, микс или марафон
def create_study_session(repo, mode, deck_ids=None, due_only=True, shuffle=True, today=None):
    if mode == MODE_ONE_DECK:
        if not deck_ids or len(deck_ids) != 1:
            raise ValueError("Для режима «Одна колода» требуется ровно одна колода.")
        target_decks = deck_ids
    elif mode == MODE_MIX:
        if not deck_ids:
            raise ValueError("Для режима «Микс» нужно выбрать хотя бы одну колоду.")
        target_decks = deck_ids
    elif mode == MODE_MARATHON:
        target_decks = None
    else:
        raise ValueError(f"Неизвестный режим обучения: {mode}")

    cards = repo.get_cards_for_study(deck_ids=target_decks, due_only=due_only, today=today)
    return StudySession(repo=repo, cards=cards, shuffle=shuffle, today=today)