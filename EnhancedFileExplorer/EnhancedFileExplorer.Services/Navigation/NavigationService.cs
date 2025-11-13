using EnhancedFileExplorer.Core.Interfaces;
using EnhancedFileExplorer.Core.Events;
using Microsoft.Extensions.Logging;

namespace EnhancedFileExplorer.Services.Navigation;

/// <summary>
/// Service for navigation operations with history management.
/// </summary>
public class NavigationService : INavigationService
{
    private readonly IFileSystemService _fileSystemService;
    private readonly ILogger<NavigationService> _logger;
    private readonly Stack<string> _backStack = new();
    private readonly Stack<string> _forwardStack = new();
    private string _currentPath = string.Empty;
    private readonly object _lock = new();

    public string CurrentPath
    {
        get
        {
            lock (_lock)
            {
                return _currentPath;
            }
        }
        private set
        {
            lock (_lock)
            {
                _currentPath = value;
            }
        }
    }

    public bool CanGoBack
    {
        get
        {
            lock (_lock)
            {
                return _backStack.Count > 0;
            }
        }
    }

    public bool CanGoForward
    {
        get
        {
            lock (_lock)
            {
                return _forwardStack.Count > 0;
            }
        }
    }

    public event EventHandler<NavigationEventArgs>? NavigationChanged;

    public NavigationService(
        IFileSystemService fileSystemService,
        ILogger<NavigationService> logger)
    {
        _fileSystemService = fileSystemService ?? throw new ArgumentNullException(nameof(fileSystemService));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    public async Task NavigateToAsync(string path, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(path))
            throw new ArgumentException("Path cannot be null or empty.", nameof(path));

        var exists = await _fileSystemService.ExistsAsync(path, cancellationToken);
        if (!exists)
            throw new DirectoryNotFoundException($"Path does not exist: {path}");

        var isDirectory = await _fileSystemService.IsDirectoryAsync(path, cancellationToken);
        if (!isDirectory)
            throw new ArgumentException("Path must be a directory.", nameof(path));

        lock (_lock)
        {
            // If we have a current path, add it to back stack
            if (!string.IsNullOrEmpty(_currentPath))
            {
                _backStack.Push(_currentPath);
            }

            // Clear forward stack when navigating to new location
            _forwardStack.Clear();

            _currentPath = path;
        }

        RaiseNavigationChanged(path, NavigationType.NavigateTo);
        _logger.LogInformation("Navigated to: {Path}", path);
    }

    public async Task NavigateBackAsync(CancellationToken cancellationToken = default)
    {
        string? previousPath = null;

        lock (_lock)
        {
            if (_backStack.Count == 0)
            {
                _logger.LogWarning("Cannot navigate back: back stack is empty");
                return;
            }

            previousPath = _backStack.Pop();
            if (!string.IsNullOrEmpty(_currentPath))
            {
                _forwardStack.Push(_currentPath);
            }
            _currentPath = previousPath;
        }

        if (previousPath != null)
        {
            var exists = await _fileSystemService.ExistsAsync(previousPath, cancellationToken);
            if (!exists)
            {
                _logger.LogWarning("Previous path no longer exists: {Path}", previousPath);
                // Try to navigate back again
                await NavigateBackAsync(cancellationToken);
                return;
            }

            RaiseNavigationChanged(previousPath, NavigationType.NavigateBack);
            _logger.LogInformation("Navigated back to: {Path}", previousPath);
        }
    }

    public async Task NavigateForwardAsync(CancellationToken cancellationToken = default)
    {
        string? nextPath = null;

        lock (_lock)
        {
            if (_forwardStack.Count == 0)
            {
                _logger.LogWarning("Cannot navigate forward: forward stack is empty");
                return;
            }

            nextPath = _forwardStack.Pop();
            if (!string.IsNullOrEmpty(_currentPath))
            {
                _backStack.Push(_currentPath);
            }
            _currentPath = nextPath;
        }

        if (nextPath != null)
        {
            var exists = await _fileSystemService.ExistsAsync(nextPath, cancellationToken);
            if (!exists)
            {
                _logger.LogWarning("Next path no longer exists: {Path}", nextPath);
                // Try to navigate forward again
                await NavigateForwardAsync(cancellationToken);
                return;
            }

            RaiseNavigationChanged(nextPath, NavigationType.NavigateForward);
            _logger.LogInformation("Navigated forward to: {Path}", nextPath);
        }
    }

    public async Task NavigateUpAsync(CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrEmpty(CurrentPath))
            return;

        var parentPath = await _fileSystemService.GetParentDirectoryAsync(CurrentPath, cancellationToken);
        if (string.IsNullOrEmpty(parentPath))
            return;

        var exists = await _fileSystemService.ExistsAsync(parentPath, cancellationToken);
        if (!exists)
        {
            _logger.LogWarning("Parent directory does not exist: {Path}", parentPath);
            return;
        }

        await NavigateToAsync(parentPath, cancellationToken);
        // Override navigation type to indicate "up"
        RaiseNavigationChanged(parentPath, NavigationType.NavigateUp);
    }

    private void RaiseNavigationChanged(string path, NavigationType navigationType)
    {
        NavigationChanged?.Invoke(this, new NavigationEventArgs(path, navigationType));
    }
}

