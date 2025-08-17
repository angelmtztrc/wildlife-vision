from prompt_toolkit import prompt as pp
from prompt_toolkit.completion import PathCompleter, WordCompleter

def prompt(message):
  return pp(message, completer=WordCompleter())

def prompt_path(message):
  return pp(message, completer=PathCompleter())