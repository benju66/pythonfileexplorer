using EnhancedFileExplorer.Core.Events;

namespace EnhancedFileExplorer.Core.Interfaces;

/// <summary>
/// Manages undo/redo operations.
/// </summary>
public interface IUndoRedoManager
{
    /// <summary>
    /// Whether undo is available.
    /// </summary>
    bool CanUndo { get; }

    /// <summary>
    /// Whether redo is available.
    /// </summary>
    bool CanRedo { get; }

    /// <summary>
    /// Maximum number of commands in the undo stack.
    /// </summary>
    int MaxStackSize { get; set; }

    /// <summary>
    /// Executes a command and adds it to the undo stack.
    /// </summary>
    Task ExecuteCommandAsync(ICommand command, CancellationToken cancellationToken = default);

    /// <summary>
    /// Undoes the last command.
    /// </summary>
    Task UndoAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Redoes the last undone command.
    /// </summary>
    Task RedoAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Clears both undo and redo stacks.
    /// </summary>
    void Clear();

    /// <summary>
    /// Event raised when undo/redo state changes.
    /// </summary>
    event EventHandler<UndoRedoStateChangedEventArgs>? StateChanged;
}

