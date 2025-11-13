namespace EnhancedFileExplorer.Core.Interfaces;

/// <summary>
/// Extension to ITabManagerService to provide navigation service access per tab.
/// </summary>
public interface ITabNavigationService
{
    /// <summary>
    /// Gets the navigation service for a specific tab.
    /// </summary>
    INavigationService? GetNavigationServiceForTab(string tabId);
}

