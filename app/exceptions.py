# Понятные ошибки приложения, чтобы программа не падала молча.


# Базовая ошибка приложения
class FlashcardsError(Exception):
    pass


# Пользователь ввёл некорректные данные (пустое поле, слишком длинный текст)
class ValidationError(FlashcardsError):
    pass


# Попытка создать колоду с названием, которое уже есть
class DuplicateError(FlashcardsError):
    pass


# Колода или карточка не найдена в базе данных
class NotFoundError(FlashcardsError):
    pass


# Ошибка при проверке или копировании файла изображения
class ImageError(FlashcardsError):
    pass