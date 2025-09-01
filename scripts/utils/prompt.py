from prompt_toolkit import prompt as pp
from prompt_toolkit.completion import PathCompleter, WordCompleter
from prompt_toolkit.validation import Validator

def prompt(message: str):
  return pp(message)

def prompt_path(message: str):
  return pp(message, completer=PathCompleter())

def prompt_choices(message: str, choices: list[str]):
  completer = WordCompleter(choices, ignore_case=True)
  
  validator = Validator.from_callable(
    lambda text: text in choices,
    error_message="Invalid choice, please select one from the list.",
    move_cursor_to_end=True 
  )
  
  return pp(message, completer=completer, validator=validator)