using EnhancedFileExplorer.Core.Models;

namespace EnhancedFileExplorer.Core.Interfaces;

/// <summary>
/// Service for file system operations.
/// </summary>
public interface IFileSystemService
{
    /// <summary>
    /// Checks if a path exists.
    /// </summary>
    Task<bool> ExistsAsync(string path, CancellationToken cancellationToken = default);

    /// <summary>
    /// Checks if a path is a directory.
    /// </summary>
    Task<bool> IsDirectoryAsync(string path, CancellationToken cancellationToken = default);

    /// <summary>
    /// Gets all items in a directory.
    /// </summary>
    Task<IEnumerable<FileSystemItem>> GetItemsAsync(string directory, CancellationToken cancellationToken = default);

    /// <summary>
    /// Gets information about a specific file or directory.
    /// </summary>
    Task<FileSystemItem> GetItemAsync(string path, CancellationToken cancellationToken = default);

    /// <summary>
    /// Gets the parent directory of a path.
    /// </summary>
    Task<string?> GetParentDirectoryAsync(string path, CancellationToken cancellationToken = default);
}

