namespace EnhancedFileExplorer.Core.Interfaces;

/// <summary>
/// Command interface for undo/redo operations.
/// </summary>
public interface ICommand
{
    /// <summary>
    /// Description of the command for display purposes.
    /// </summary>
    string Description { get; }

    /// <summary>
    /// Timestamp when the command was executed.
    /// </summary>
    DateTime Timestamp { get; }

    /// <summary>
    /// Whether this command can be undone.
    /// </summary>
    bool CanUndo { get; }

    /// <summary>
    /// Executes the command.
    /// </summary>
    Task<bool> ExecuteAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Undoes the command.
    /// </summary>
    Task<bool> UndoAsync(CancellationToken cancellationToken = default);
}

