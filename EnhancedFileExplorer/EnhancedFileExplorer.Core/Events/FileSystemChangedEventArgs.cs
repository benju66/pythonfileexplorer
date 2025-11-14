namespace EnhancedFileExplorer.Core.Events;

/// <summary>
/// Event arguments for file system change events.
/// </summary>
public class FileSystemChangedEventArgs : EventArgs
{
    public string Path { get; }
    public string? FullPath { get; }
    public WatcherChangeTypes ChangeType { get; }

    public FileSystemChangedEventArgs(string path, string? fullPath, WatcherChangeTypes changeType)
    {
        Path = path ?? throw new ArgumentNullException(nameof(path));
        FullPath = fullPath;
        ChangeType = changeType;
    }
}

/// <summary>
/// Event arguments for file system rename events.
/// </summary>
public class FileSystemRenamedEventArgs : FileSystemChangedEventArgs
{
    public string OldPath { get; }
    public string? OldFullPath { get; }

    public FileSystemRenamedEventArgs(string path, string? fullPath, string oldPath, string? oldFullPath)
        : base(path, fullPath, WatcherChangeTypes.Renamed)
    {
        OldPath = oldPath ?? throw new ArgumentNullException(nameof(oldPath));
        OldFullPath = oldFullPath;
    }
}

