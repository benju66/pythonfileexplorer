using EnhancedFileExplorer.Core.Interfaces;
using EnhancedFileExplorer.Core.Events;
using Microsoft.Extensions.Logging;

namespace EnhancedFileExplorer.Services.UndoRedo;

/// <summary>
/// Manages undo/redo operations using command pattern.
/// </summary>
public class UndoRedoManager : IUndoRedoManager
{
    private readonly Stack<ICommand> _undoStack = new();
    private readonly Stack<ICommand> _redoStack = new();
    private readonly ILogger<UndoRedoManager> _logger;
    private readonly object _lock = new();

    public bool CanUndo
    {
        get
        {
            lock (_lock)
            {
                return _undoStack.Count > 0;
            }
        }
    }

    public bool CanRedo
    {
        get
        {
            lock (_lock)
            {
                return _redoStack.Count > 0;
            }
        }
    }

    public int MaxStackSize { get; set; } = 100;

    public event EventHandler<UndoRedoStateChangedEventArgs>? StateChanged;
    public event EventHandler<FileOperationCompletedEventArgs>? FileOperationCompleted;

    public UndoRedoManager(ILogger<UndoRedoManager> logger)
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    public async Task ExecuteCommandAsync(ICommand command, CancellationToken cancellationToken = default)
    {
        if (command == null)
            throw new ArgumentNullException(nameof(command));

        try
        {
            var success = await command.ExecuteAsync(cancellationToken);
            if (success)
            {
                lock (_lock)
                {
                    _undoStack.Push(command);
                    
                    // Limit stack size
                    if (_undoStack.Count > MaxStackSize)
                    {
                        // Remove oldest commands (bottom of stack)
                        var temp = new Stack<ICommand>();
                        while (_undoStack.Count > MaxStackSize - 1)
                        {
                            temp.Push(_undoStack.Pop());
                        }
                        _undoStack.Clear();
                        while (temp.Count > 0)
                        {
                            _undoStack.Push(temp.Pop());
                        }
                    }

                    // Clear redo stack when new command is executed
                    _redoStack.Clear();
                }

                RaiseStateChanged();
                RaiseFileOperationCompleted(command);
                _logger.LogInformation("Command executed: {Description}", command.Description);
            }
            else
            {
                _logger.LogWarning("Command execution failed: {Description}", command.Description);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error executing command: {Description}", command.Description);
            throw;
        }
    }

    public async Task UndoAsync(CancellationToken cancellationToken = default)
    {
        ICommand? command = null;

        lock (_lock)
        {
            if (_undoStack.Count == 0)
            {
                _logger.LogWarning("Cannot undo: undo stack is empty");
                return;
            }

            command = _undoStack.Pop();
        }

        if (command != null && command.CanUndo)
        {
            try
            {
                var success = await command.UndoAsync(cancellationToken);
                if (success)
                {
                    lock (_lock)
                    {
                        _redoStack.Push(command);
                    }

                    RaiseStateChanged();
                    _logger.LogInformation("Command undone: {Description}", command.Description);
                }
                else
                {
                    _logger.LogWarning("Command undo failed: {Description}", command.Description);
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error undoing command: {Description}", command.Description);
                throw;
            }
        }
    }

    public async Task RedoAsync(CancellationToken cancellationToken = default)
    {
        ICommand? command = null;

        lock (_lock)
        {
            if (_redoStack.Count == 0)
            {
                _logger.LogWarning("Cannot redo: redo stack is empty");
                return;
            }

            command = _redoStack.Pop();
        }

        if (command != null)
        {
            try
            {
                var success = await command.ExecuteAsync(cancellationToken);
                if (success)
                {
                    lock (_lock)
                    {
                        _undoStack.Push(command);
                    }

                    RaiseStateChanged();
                    _logger.LogInformation("Command redone: {Description}", command.Description);
                }
                else
                {
                    _logger.LogWarning("Command redo failed: {Description}", command.Description);
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error redoing command: {Description}", command.Description);
                throw;
            }
        }
    }

    public void Clear()
    {
        lock (_lock)
        {
            _undoStack.Clear();
            _redoStack.Clear();
        }

        RaiseStateChanged();
        _logger.LogInformation("Undo/redo stacks cleared");
    }

    private void RaiseStateChanged()
    {
        StateChanged?.Invoke(this, new UndoRedoStateChangedEventArgs(CanUndo, CanRedo));
    }

    private void RaiseFileOperationCompleted(ICommand command)
    {
        // Determine operation type and path from command
        FileOperationType operationType;
        string? path = null;
        string? parentPath = null;

        // Use reflection or type checking to determine command type
        var commandType = command.GetType().Name;
        
        if (commandType.Contains("CreateFile"))
        {
            operationType = FileOperationType.Create;
            // Try to get path from command using reflection
            var pathProperty = command.GetType().GetProperty("CreatedPath");
            if (pathProperty != null)
            {
                path = pathProperty.GetValue(command) as string;
            }
            else
            {
                var pathField = command.GetType().GetField("_createdPath", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
                if (pathField != null)
                {
                    path = pathField.GetValue(command) as string;
                }
            }
            parentPath = path != null ? System.IO.Path.GetDirectoryName(path) : null;
        }
        else if (commandType.Contains("CreateFolder"))
        {
            operationType = FileOperationType.Create;
            var pathProperty = command.GetType().GetProperty("CreatedPath");
            if (pathProperty != null)
            {
                path = pathProperty.GetValue(command) as string;
            }
            else
            {
                var pathField = command.GetType().GetField("_createdPath", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
                if (pathField != null)
                {
                    path = pathField.GetValue(command) as string;
                }
            }
            parentPath = path != null ? System.IO.Path.GetDirectoryName(path) : null;
        }
        else if (commandType.Contains("Delete"))
        {
            operationType = FileOperationType.Delete;
            var pathProperty = command.GetType().GetProperty("Path");
            if (pathProperty != null)
            {
                path = pathProperty.GetValue(command) as string;
            }
            else
            {
                var pathField = command.GetType().GetField("_path", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
                if (pathField != null)
                {
                    path = pathField.GetValue(command) as string;
                }
            }
            parentPath = path != null ? System.IO.Path.GetDirectoryName(path) : null;
        }
        else if (commandType.Contains("Rename"))
        {
            operationType = FileOperationType.Rename;
            var oldPathProperty = command.GetType().GetProperty("OldPath");
            if (oldPathProperty != null)
            {
                path = oldPathProperty.GetValue(command) as string;
            }
            else
            {
                var oldPathField = command.GetType().GetField("_oldPath", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
                if (oldPathField != null)
                {
                    path = oldPathField.GetValue(command) as string;
                }
                else
                {
                    var newPathProperty = command.GetType().GetProperty("NewPath");
                    if (newPathProperty != null)
                    {
                        path = newPathProperty.GetValue(command) as string;
                    }
                    else
                    {
                        var newPathField = command.GetType().GetField("_newPath", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
                        if (newPathField != null)
                        {
                            path = newPathField.GetValue(command) as string;
                        }
                    }
                }
            }
            parentPath = path != null ? System.IO.Path.GetDirectoryName(path) : null;
        }
        else if (commandType.Contains("Copy"))
        {
            operationType = FileOperationType.Copy;
        }
        else if (commandType.Contains("Move"))
        {
            operationType = FileOperationType.Move;
        }
        else
        {
            // Unknown command type - don't raise event
            return;
        }

        if (path != null)
        {
            FileOperationCompleted?.Invoke(this, new FileOperationCompletedEventArgs(
                operationType,
                path,
                parentPath,
                true));
        }
    }
}

