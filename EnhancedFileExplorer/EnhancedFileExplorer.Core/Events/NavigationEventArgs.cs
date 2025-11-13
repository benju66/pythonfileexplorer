namespace EnhancedFileExplorer.Core.Events;

/// <summary>
/// Event arguments for navigation changes.
/// </summary>
public class NavigationEventArgs : EventArgs
{
    public string Path { get; }
    public NavigationType NavigationType { get; }

    public NavigationEventArgs(string path, NavigationType navigationType)
    {
        Path = path ?? throw new ArgumentNullException(nameof(path));
        NavigationType = navigationType;
    }
}

public enum NavigationType
{
    NavigateTo,
    NavigateBack,
    NavigateForward,
    NavigateUp
}

