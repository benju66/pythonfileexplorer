using EnhancedFileExplorer.Core.Interfaces;

namespace EnhancedFileExplorer.Core.Events;

/// <summary>
/// Event arguments for tab events.
/// </summary>
public class TabEventArgs : EventArgs
{
    public TabInfo Tab { get; }

    public TabEventArgs(TabInfo tab)
    {
        Tab = tab ?? throw new ArgumentNullException(nameof(tab));
    }
}

/// <summary>
/// Event arguments for tab change events.
/// </summary>
public class TabChangedEventArgs : EventArgs
{
    public TabInfo? PreviousTab { get; }
    public TabInfo? CurrentTab { get; }

    public TabChangedEventArgs(TabInfo? previousTab, TabInfo? currentTab)
    {
        PreviousTab = previousTab;
        CurrentTab = currentTab;
    }
}

