using EnhancedFileExplorer.Core.Interfaces;

namespace EnhancedFileExplorer.Services.FileOperations.Commands;

/// <summary>
/// Command that executes multiple commands sequentially.
/// Used for bulk operations like multi-select delete, copy, cut.
/// </summary>
public class BulkOperationCommand : ICommand
{
    private readonly List<ICommand> _commands;
    private readonly IUndoRedoManager? _undoRedoManager;
    private DateTime _timestamp;
    private bool _executed;

    public string Description
    {
        get
        {
            if (_commands.Count == 0)
                return "Bulk Operation";
            
            if (_commands.Count == 1)
                return _commands[0].Description;
            
            return $"Bulk Operation ({_commands.Count} items)";
        }
    }

    public DateTime Timestamp => _timestamp;

    public bool CanUndo => _commands.All(c => c.CanUndo);

    public BulkOperationCommand(List<ICommand> commands, IUndoRedoManager? undoRedoManager = null)
    {
        _commands = commands ?? throw new ArgumentNullException(nameof(commands));
        _undoRedoManager = undoRedoManager;
        _timestamp = DateTime.UtcNow;
    }

    public async Task<bool> ExecuteAsync(CancellationToken cancellationToken = default)
    {
        if (_executed)
            return false;

        _timestamp = DateTime.UtcNow;
        var successCount = 0;
        var failedCommands = new List<ICommand>();

        foreach (var command in _commands)
        {
            if (cancellationToken.IsCancellationRequested)
                break;

            try
            {
                // Execute command directly (don't use undo/redo manager to avoid double-stacking)
                var success = await command.ExecuteAsync(cancellationToken);
                if (success)
                {
                    successCount++;
                }
                else
                {
                    failedCommands.Add(command);
                }
            }
            catch
            {
                failedCommands.Add(command);
            }
        }

        _executed = true;

        // If all commands succeeded, we can undo
        // If some failed, we still mark as executed but undo might be partial
        return successCount > 0;
    }

    public async Task<bool> UndoAsync(CancellationToken cancellationToken = default)
    {
        if (!_executed)
            return false;

        // Undo commands in reverse order
        var success = true;
        for (int i = _commands.Count - 1; i >= 0; i--)
        {
            if (cancellationToken.IsCancellationRequested)
                break;

            try
            {
                if (_commands[i].CanUndo)
                {
                    var result = await _commands[i].UndoAsync(cancellationToken);
                    if (!result)
                    {
                        success = false;
                    }
                }
            }
            catch
            {
                success = false;
            }
        }

        _executed = false;
        return success;
    }
}

