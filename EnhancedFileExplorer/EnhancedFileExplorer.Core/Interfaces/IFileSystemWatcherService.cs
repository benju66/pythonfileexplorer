using EnhancedFileExplorer.Core.Events;

namespace EnhancedFileExplorer.Core.Interfaces;

/// <summary>
/// Service for monitoring file system changes.
/// </summary>
public interface IFileSystemWatcherService
{
    /// <summary>
    /// Starts watching a directory for changes.
    /// </summary>
    /// <param name="path">The directory path to watch.</param>
    /// <param name="includeSubdirectories">Whether to watch subdirectories.</param>
    void WatchDirectory(string path, bool includeSubdirectories = false);

    /// <summary>
    /// Stops watching a directory.
    /// </summary>
    /// <param name="path">The directory path to stop watching.</param>
    void UnwatchDirectory(string path);

    /// <summary>
    /// Stops watching all directories.
    /// </summary>
    void StopAll();

    /// <summary>
    /// Event raised when a file or directory is created.
    /// </summary>
    event EventHandler<FileSystemChangedEventArgs>? Created;

    /// <summary>
    /// Event raised when a file or directory is deleted.
    /// </summary>
    event EventHandler<FileSystemChangedEventArgs>? Deleted;

    /// <summary>
    /// Event raised when a file or directory is renamed.
    /// </summary>
    event EventHandler<FileSystemRenamedEventArgs>? Renamed;

    /// <summary>
    /// Event raised when a file or directory is changed.
    /// </summary>
    event EventHandler<FileSystemChangedEventArgs>? Changed;
}

