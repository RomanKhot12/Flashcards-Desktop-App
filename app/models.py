# Модели данных приложения: колода, карточка и итоги сессии.

from datetime import date


# Колода карточек
class Deck:
    def __init__(self, name, id=None, created_at=None):
        self.id = id
        self.name = name
        self.created_at = created_at


# Краткая информация о колоде для отображения в списке главного окна
class DeckSummary:
    def __init__(self, id, name, total_cards, due_cards, created_at):
        self.id = id
        self.name = name
        self.total_cards = total_cards
        self.due_cards = due_cards
        self.created_at = created_at


# Двусторонняя карточка с текстом и необязательными картинками
class Card:
    def __init__(
        self,
        deck_id,
        front_text="",
        back_text="",
        front_image=None,
        back_image=None,
        box=1,
        next_review_date=None,
        created_at=None,
        id=None,
    ):
        self.id = id
        self.deck_id = deck_id
        self.front_text = front_text
        self.back_text = back_text
        self.front_image = front_image
        self.back_image = back_image
        self.box = box
        self.next_review_date = next_review_date
        self.created_at = created_at

    # Проверяет, пора ли повторять карточку (сравниваем только даты, без времени)
    def is_due(self, on_date=None):
        if self.next_review_date is None:
            return True
        if on_date is not None:
            check_date = on_date
        else:
            check_date = date.today()
        return self.next_review_date <= check_date


# Итоги учебной сессии для показа пользователю в конце обучения
class SessionSummary:
    def __init__(self, initial_cards, completed_cards, know_count, dont_know_count, interrupted):
        self.initial_cards = initial_cards
        self.completed_cards = completed_cards
        self.know_count = know_count
        self.dont_know_count = dont_know_count
        self.interrupted = interrupted