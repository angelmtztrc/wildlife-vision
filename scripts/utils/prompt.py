from prompt_toolkit import prompt as pp
from prompt_toolkit.completion import PathCompleter, WordCompleter
from prompt_toolkit.validation import Validator


def prompt(message: str) -> str:
    """Prompt for free-form text input."""
    return pp(message)


def prompt_path(message: str, only_directories: bool = False) -> str:
    """Prompt for a file path with tab completion."""
    return pp(message, completer=PathCompleter(only_directories=only_directories))


def prompt_choices(
    message: str, choices: list[str], case_sensitive: bool = False
) -> str:
    """Prompt for a choice from a predefined list with validation."""
    completer = WordCompleter(choices, ignore_case=not case_sensitive)

    check_choices = choices if case_sensitive else [c.lower() for c in choices]

    validator = Validator.from_callable(
        lambda text: (text if case_sensitive else text.lower()) in check_choices,
        error_message=f"Invalid choice. Options: {', '.join(choices)}",
        move_cursor_to_end=True,
    )

    return pp(message, completer=completer, validator=validator)
