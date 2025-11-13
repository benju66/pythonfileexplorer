using EnhancedFileExplorer.Core.Interfaces;
using EnhancedFileExplorer.Core.Events;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;

namespace EnhancedFileExplorer.Services.TabManagement;

/// <summary>
/// Service for managing tabs.
/// </summary>
public class TabManagerService : ITabManagerService, ITabNavigationService
{
    private readonly IServiceProvider _serviceProvider;
    private readonly ILogger<TabManagerService> _logger;
    private readonly Dictionary<string, TabInfo> _tabs = new();
    private readonly Dictionary<string, INavigationService> _tabNavigationServices = new();
    private readonly Dictionary<string, IServiceScope> _tabScopes = new();
    private string? _activeTabId;
    private readonly object _lock = new();

    public event EventHandler<TabChangedEventArgs>? ActiveTabChanged;
    public event EventHandler<TabEventArgs>? TabCreated;
    public event EventHandler<TabEventArgs>? TabClosed;

    public TabManagerService(
        IServiceProvider serviceProvider,
        ILogger<TabManagerService> logger)
    {
        _serviceProvider = serviceProvider ?? throw new ArgumentNullException(nameof(serviceProvider));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    private INavigationService GetOrCreateNavigationService(string tabId)
    {
        lock (_lock)
        {
            if (!_tabNavigationServices.ContainsKey(tabId))
            {
                var scope = _serviceProvider.CreateScope();
                var navService = scope.ServiceProvider.GetRequiredService<INavigationService>();
                _tabNavigationServices[tabId] = navService;
                _tabScopes[tabId] = scope;
            }
            return _tabNavigationServices[tabId];
        }
    }

    public TabInfo? GetActiveTab()
    {
        lock (_lock)
        {
            if (_activeTabId == null || !_tabs.ContainsKey(_activeTabId))
                return null;

            return _tabs[_activeTabId];
        }
    }

    public IEnumerable<TabInfo> GetAllTabs()
    {
        lock (_lock)
        {
            return _tabs.Values.ToList();
        }
    }

    public async Task<TabInfo> CreateTabAsync(string? initialPath = null, CancellationToken cancellationToken = default)
    {
        var tabId = Guid.NewGuid().ToString();
        var tab = new TabInfo
        {
            Id = tabId,
            Title = "New Tab",
            CurrentPath = initialPath ?? Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
            IsActive = false
        };

        lock (_lock)
        {
            _tabs[tabId] = tab;
        }

        // Create navigation service for this tab
        GetOrCreateNavigationService(tabId);

        // Navigate to initial path if provided
        if (!string.IsNullOrEmpty(initialPath))
        {
            try
            {
                await NavigateTabAsync(tabId, initialPath, cancellationToken);
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Failed to navigate to initial path: {Path}", initialPath);
            }
        }

        TabCreated?.Invoke(this, new TabEventArgs(tab));
        _logger.LogInformation("Created tab: {TabId}", tabId);

        // Activate the new tab
        await ActivateTabAsync(tabId, cancellationToken);

        return tab;
    }

    public async Task CloseTabAsync(string tabId, CancellationToken cancellationToken = default)
    {
        TabInfo? tab = null;
        string? nextActiveTabId = null;

        lock (_lock)
        {
            if (!_tabs.ContainsKey(tabId))
            {
                _logger.LogWarning("Tab not found: {TabId}", tabId);
                return;
            }

            tab = _tabs[tabId];
            _tabs.Remove(tabId);
            
            // Clean up navigation service and scope
            if (_tabScopes.TryGetValue(tabId, out var scope))
            {
                scope.Dispose();
                _tabScopes.Remove(tabId);
            }
            _tabNavigationServices.Remove(tabId);

            // If this was the active tab, activate another one
            if (_activeTabId == tabId)
            {
                _activeTabId = null;
                nextActiveTabId = _tabs.Keys.FirstOrDefault();
            }
        }

        if (tab != null)
        {
            TabClosed?.Invoke(this, new TabEventArgs(tab));
            _logger.LogInformation("Closed tab: {TabId}", tabId);
        }

        // Activate next tab if needed
        if (nextActiveTabId != null)
        {
            await ActivateTabAsync(nextActiveTabId, cancellationToken);
        }
    }

    public async Task ActivateTabAsync(string tabId, CancellationToken cancellationToken = default)
    {
        TabInfo? previousTab = null;
        TabInfo? currentTab = null;

        lock (_lock)
        {
            if (!_tabs.ContainsKey(tabId))
            {
                _logger.LogWarning("Tab not found: {TabId}", tabId);
                return;
            }

            // Get previous active tab
            if (_activeTabId != null && _tabs.ContainsKey(_activeTabId))
            {
                previousTab = _tabs[_activeTabId];
                previousTab.IsActive = false;
            }

            // Set new active tab
            _activeTabId = tabId;
            currentTab = _tabs[tabId];
            currentTab.IsActive = true;
        }

        // Navigate to the tab's current path using tab's navigation service
        if (currentTab?.CurrentPath != null)
        {
            try
            {
                var navService = GetOrCreateNavigationService(tabId);
                await navService.NavigateToAsync(currentTab.CurrentPath, cancellationToken);
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Failed to navigate to tab path: {Path}", currentTab.CurrentPath);
            }
        }

        ActiveTabChanged?.Invoke(this, new TabChangedEventArgs(previousTab, currentTab));
        _logger.LogInformation("Activated tab: {TabId}", tabId);
    }

    public async Task NavigateTabAsync(string tabId, string path, CancellationToken cancellationToken = default)
    {
        TabInfo? tab = null;

        lock (_lock)
        {
            if (!_tabs.ContainsKey(tabId))
            {
                _logger.LogWarning("Tab not found: {TabId}", tabId);
                return;
            }

            tab = _tabs[tabId];
        }

        if (tab != null)
        {
            try
            {
                var navService = GetOrCreateNavigationService(tabId);
                await navService.NavigateToAsync(path, cancellationToken);
                tab.CurrentPath = path;
                tab.Title = System.IO.Path.GetFileName(path) ?? "New Tab";

                _logger.LogInformation("Navigated tab {TabId} to: {Path}", tabId, path);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to navigate tab {TabId} to {Path}", tabId, path);
                throw;
            }
        }
    }

    public INavigationService? GetNavigationServiceForTab(string tabId)
    {
        lock (_lock)
        {
            return _tabNavigationServices.TryGetValue(tabId, out var navService) ? navService : null;
        }
    }
}

