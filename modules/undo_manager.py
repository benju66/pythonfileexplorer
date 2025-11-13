# modules/undo_manager.py
from typing import List

class Command:
    """
    Base class for commands in the undo/redo stack. 
    Each subclass implements how to do() and undo() the operation.
    """
    def do(self):
        raise NotImplementedError

    def undo(self):
        raise NotImplementedError

class UndoManager:
    def __init__(self):
        self._undo_stack: List[Command] = []
        self._redo_stack: List[Command] = []

    def push(self, command: Command):
        """
        Push a new command onto the undo stack and clear the redo stack
        (because once you've pushed a new command, the old 'redo' chain is invalid).
        """
        self._undo_stack.append(command)
        self._redo_stack.clear()
        command.do()

    def undo(self):
        if not self._undo_stack:
            return
        command = self._undo_stack.pop()
        command.undo()
        self._redo_stack.append(command)

    def redo(self):
        if not self._redo_stack:
            return
        command = self._redo_stack.pop()
        command.do()
        self._undo_stack.append(command)

    def can_undo(self):
        return len(self._undo_stack) > 0

    def can_redo(self):
        return len(self._redo_stack) > 0

# Global instance for convenience (optional)
undo_manager = UndoManager()
