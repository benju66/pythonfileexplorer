using EnhancedFileExplorer.Core.Events;

namespace EnhancedFileExplorer.Core.Interfaces;

/// <summary>
/// Information about a tab.
/// </summary>
public class TabInfo
{
    public string Id { get; set; } = string.Empty;
    public string Title { get; set; } = string.Empty;
    public string? CurrentPath { get; set; }
    public bool IsActive { get; set; }
}

/// <summary>
/// Service for managing tabs.
/// </summary>
public interface ITabManagerService
{
    /// <summary>
    /// Gets the currently active tab.
    /// </summary>
    TabInfo? GetActiveTab();

    /// <summary>
    /// Gets all tabs.
    /// </summary>
    IEnumerable<TabInfo> GetAllTabs();

    /// <summary>
    /// Creates a new tab.
    /// </summary>
    Task<TabInfo> CreateTabAsync(string? initialPath = null, CancellationToken cancellationToken = default);

    /// <summary>
    /// Closes a tab.
    /// </summary>
    Task CloseTabAsync(string tabId, CancellationToken cancellationToken = default);

    /// <summary>
    /// Activates a tab.
    /// </summary>
    Task ActivateTabAsync(string tabId, CancellationToken cancellationToken = default);

    /// <summary>
    /// Navigates a tab to a specific path.
    /// </summary>
    Task NavigateTabAsync(string tabId, string path, CancellationToken cancellationToken = default);

    /// <summary>
    /// Event raised when active tab changes.
    /// </summary>
    event EventHandler<TabChangedEventArgs>? ActiveTabChanged;

    /// <summary>
    /// Event raised when a tab is created.
    /// </summary>
    event EventHandler<TabEventArgs>? TabCreated;

    /// <summary>
    /// Event raised when a tab is closed.
    /// </summary>
    event EventHandler<TabEventArgs>? TabClosed;

    /// <summary>
    /// Gets the navigation service for a specific tab.
    /// </summary>
    INavigationService? GetNavigationServiceForTab(string tabId);
}

