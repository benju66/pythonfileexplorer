using EnhancedFileExplorer.Core.Events;

namespace EnhancedFileExplorer.Core.Interfaces;

/// <summary>
/// Service for navigation operations.
/// </summary>
public interface INavigationService
{
    /// <summary>
    /// Current path being displayed.
    /// </summary>
    string CurrentPath { get; }

    /// <summary>
    /// Whether back navigation is available.
    /// </summary>
    bool CanGoBack { get; }

    /// <summary>
    /// Whether forward navigation is available.
    /// </summary>
    bool CanGoForward { get; }

    /// <summary>
    /// Navigates to the specified path.
    /// </summary>
    Task NavigateToAsync(string path, CancellationToken cancellationToken = default);

    /// <summary>
    /// Navigates back in history.
    /// </summary>
    Task NavigateBackAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Navigates forward in history.
    /// </summary>
    Task NavigateForwardAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Navigates to the parent directory.
    /// </summary>
    Task NavigateUpAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Event raised when navigation occurs.
    /// </summary>
    event EventHandler<NavigationEventArgs>? NavigationChanged;
}

