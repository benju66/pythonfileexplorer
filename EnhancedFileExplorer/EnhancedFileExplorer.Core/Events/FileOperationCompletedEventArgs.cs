namespace EnhancedFileExplorer.Core.Events;

/// <summary>
/// Event arguments for file operation completion events.
/// </summary>
public class FileOperationCompletedEventArgs : EventArgs
{
    /// <summary>
    /// Type of operation that was completed.
    /// </summary>
    public FileOperationType OperationType { get; }

    /// <summary>
    /// Path affected by the operation.
    /// </summary>
    public string Path { get; }

    /// <summary>
    /// Parent directory of the affected path (for refresh purposes).
    /// </summary>
    public string? ParentPath { get; }

    /// <summary>
    /// Whether the operation was successful.
    /// </summary>
    public bool IsSuccess { get; }

    public FileOperationCompletedEventArgs(
        FileOperationType operationType,
        string path,
        string? parentPath,
        bool isSuccess)
    {
        OperationType = operationType;
        Path = path;
        ParentPath = parentPath;
        IsSuccess = isSuccess;
    }
}

/// <summary>
/// Types of file operations.
/// </summary>
public enum FileOperationType
{
    Create,
    Delete,
    Rename,
    Copy,
    Move
}

