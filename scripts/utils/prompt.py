from prompt_toolkit import prompt as pp
from prompt_toolkit.completion import PathCompleter

def prompt(message):
  return pp(message)

def prompt_path(message):
  return pp(message, completer=PathCompleter())