namespace EnhancedFileExplorer.Core.Interfaces;

/// <summary>
/// Service for retrieving and caching file system icons.
/// </summary>
public interface IIconService
{
    /// <summary>
    /// Gets the icon for a file or directory asynchronously.
    /// </summary>
    /// <param name="path">The file or directory path.</param>
    /// <param name="isDirectory">Whether the path is a directory.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>The icon as an object (ImageSource in WPF), or null if unavailable.</returns>
    Task<object?> GetIconAsync(string path, bool isDirectory, CancellationToken cancellationToken = default);

    /// <summary>
    /// Clears the icon cache.
    /// </summary>
    void ClearCache();

    /// <summary>
    /// Gets the cache size.
    /// </summary>
    int CacheSize { get; }
}

