from prompt_toolkit import prompt as pp
from prompt_toolkit.completion import PathCompleter, WordCompleter

def prompt(message: str):
  return pp(message)

def prompt_path(message: str):
  return pp(message, completer=PathCompleter())

def prompt_choices(message: str, choices: list[str]):
  completer = WordCompleter(choices, ignore_case=True)
  return pp(message, completer=completer)