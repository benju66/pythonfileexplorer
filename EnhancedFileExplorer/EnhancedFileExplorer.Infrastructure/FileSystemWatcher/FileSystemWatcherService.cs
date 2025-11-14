using System.Collections.Concurrent;
using EnhancedFileExplorer.Core.Events;
using EnhancedFileExplorer.Core.Interfaces;
using Microsoft.Extensions.Logging;

namespace EnhancedFileExplorer.Infrastructure.FileSystemWatcher;

/// <summary>
/// Service for monitoring file system changes using System.IO.FileSystemWatcher.
/// </summary>
public class FileSystemWatcherService : IFileSystemWatcherService, IDisposable
{
    private readonly ILogger<FileSystemWatcherService> _logger;
    private readonly ConcurrentDictionary<string, System.IO.FileSystemWatcher> _watchers;
    private readonly object _lock = new();
    private bool _disposed;

    public event EventHandler<FileSystemChangedEventArgs>? Created;
    public event EventHandler<FileSystemChangedEventArgs>? Deleted;
    public event EventHandler<FileSystemRenamedEventArgs>? Renamed;
    public event EventHandler<FileSystemChangedEventArgs>? Changed;

    public FileSystemWatcherService(ILogger<FileSystemWatcherService> logger)
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _watchers = new ConcurrentDictionary<string, System.IO.FileSystemWatcher>(StringComparer.OrdinalIgnoreCase);
    }

    public void WatchDirectory(string path, bool includeSubdirectories = false)
    {
        if (_disposed)
            throw new ObjectDisposedException(nameof(FileSystemWatcherService));

        if (string.IsNullOrWhiteSpace(path))
            throw new ArgumentException("Path cannot be null or empty.", nameof(path));

        if (!System.IO.Directory.Exists(path))
        {
            _logger.LogWarning("Cannot watch non-existent directory: {Path}", path);
            return;
        }

        // Normalize path
        path = System.IO.Path.GetFullPath(path);

        // Check if already watching
        if (_watchers.ContainsKey(path))
        {
            _logger.LogDebug("Already watching directory: {Path}", path);
            return;
        }

        try
        {
            var watcher = new System.IO.FileSystemWatcher(path)
            {
                IncludeSubdirectories = includeSubdirectories,
                NotifyFilter = System.IO.NotifyFilters.FileName
                             | System.IO.NotifyFilters.DirectoryName
                             | System.IO.NotifyFilters.LastWrite
                             | System.IO.NotifyFilters.Size
                             | System.IO.NotifyFilters.CreationTime
            };

            watcher.Created += OnCreated;
            watcher.Deleted += OnDeleted;
            watcher.Renamed += OnRenamed;
            watcher.Changed += OnChanged;
            watcher.Error += OnError;

            watcher.EnableRaisingEvents = true;

            if (_watchers.TryAdd(path, watcher))
            {
                _logger.LogInformation("Started watching directory: {Path} (Subdirectories: {IncludeSubdirectories})", path, includeSubdirectories);
            }
            else
            {
                watcher.Dispose();
                _logger.LogWarning("Failed to add watcher for: {Path}", path);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error creating file system watcher for: {Path}", path);
        }
    }

    public void UnwatchDirectory(string path)
    {
        if (string.IsNullOrWhiteSpace(path))
            return;

        path = System.IO.Path.GetFullPath(path);

        if (_watchers.TryRemove(path, out var watcher))
        {
            try
            {
                watcher.EnableRaisingEvents = false;
                watcher.Created -= OnCreated;
                watcher.Deleted -= OnDeleted;
                watcher.Renamed -= OnRenamed;
                watcher.Changed -= OnChanged;
                watcher.Error -= OnError;
                watcher.Dispose();

                _logger.LogInformation("Stopped watching directory: {Path}", path);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error disposing watcher for: {Path}", path);
            }
        }
    }

    public void StopAll()
    {
        var paths = _watchers.Keys.ToArray();
        foreach (var path in paths)
        {
            UnwatchDirectory(path);
        }
        _logger.LogInformation("Stopped all file system watchers");
    }

    private void OnCreated(object sender, System.IO.FileSystemEventArgs e)
    {
        try
        {
            var args = new FileSystemChangedEventArgs(e.Name ?? string.Empty, e.FullPath, System.IO.WatcherChangeTypes.Created);
            Created?.Invoke(this, args);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error handling Created event for: {Path}", e.FullPath);
        }
    }

    private void OnDeleted(object sender, System.IO.FileSystemEventArgs e)
    {
        try
        {
            var args = new FileSystemChangedEventArgs(e.Name ?? string.Empty, e.FullPath, System.IO.WatcherChangeTypes.Deleted);
            Deleted?.Invoke(this, args);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error handling Deleted event for: {Path}", e.FullPath);
        }
    }

    private void OnRenamed(object sender, System.IO.RenamedEventArgs e)
    {
        try
        {
            var args = new FileSystemRenamedEventArgs(e.Name ?? string.Empty, e.FullPath, e.OldName ?? string.Empty, e.OldFullPath);
            Renamed?.Invoke(this, args);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error handling Renamed event: {OldPath} -> {NewPath}", e.OldFullPath, e.FullPath);
        }
    }

    private void OnChanged(object sender, System.IO.FileSystemEventArgs e)
    {
        try
        {
            var args = new FileSystemChangedEventArgs(e.Name ?? string.Empty, e.FullPath, System.IO.WatcherChangeTypes.Changed);
            Changed?.Invoke(this, args);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error handling Changed event for: {Path}", e.FullPath);
        }
    }

    private void OnError(object sender, System.IO.ErrorEventArgs e)
    {
        _logger.LogError(e.GetException(), "File system watcher error");
    }

    public void Dispose()
    {
        if (_disposed)
            return;

        StopAll();
        _disposed = true;
        _logger.LogInformation("FileSystemWatcherService disposed");
    }
}

