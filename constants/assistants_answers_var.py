from enum import Enum


class RegistrationQuestions(Enum):
    INDEX_1 = {
        "options": [],
        "is_custom_option_allowed": True,
    }
    INDEX_2 = {
        "options": ["Да", "Нет"],
        "is_custom_option_allowed": False,
    }
    INDEX_3 = {
        "options": [],
        "is_custom_option_allowed": True,
    }
    INDEX_4 = {
        "options": ["Да", "Нет"],
        "is_custom_option_allowed": True,
    }
    INDEX_5 = {
        "options": ["Да", "Нет"],
        "is_custom_option_allowed": True,
    }


class DailySurveyQuestions(Enum):
    INDEX_1 = {
        "options": ["Да", "Нет"],
        "is_custom_option_allowed": False,
    }
    INDEX_2 = {
        "options": [
            "Да, принимал",
            "Нет, не принимал",
        ],
        "is_custom_option_allowed": True,
    }
    INDEX_3 = {
        "options": ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
        "is_custom_option_allowed": False,
    }
    INDEX_4 = {
        "options": [
            "висок",
            "теменная область",
            "бровь",
            "глаз",
            "верхняя челюсть",
            "нижняя челюсть",
            "лоб",
            "затылок",
        ],
        "is_custom_option_allowed": True,
    }
    INDEX_5 = {
        "options": [
            "с одной стороны справа",
            "с одной стороны слева",
            "с двух сторон",
        ],
        "is_custom_option_allowed": True,
    }
    INDEX_6 = {
        "options": [
            "давящая",
            "пульсирующая",
            "сжимающая",
            "ноющая",
            "ощущение прострела",
            "режущая",
            "тупая",
            "пронизывающая",
            "острая",
            "жгучая",
        ],
        "is_custom_option_allowed": True,
    }
