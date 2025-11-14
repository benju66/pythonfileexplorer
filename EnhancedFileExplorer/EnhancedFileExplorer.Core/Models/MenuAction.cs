namespace EnhancedFileExplorer.Core.Models;

/// <summary>
/// Represents a menu action item for context menus.
/// </summary>
public class MenuAction
{
    /// <summary>
    /// Display label for the menu item.
    /// </summary>
    public string Label { get; set; } = string.Empty;

    /// <summary>
    /// Factory function to create the command when the menu item is clicked.
    /// </summary>
    public Func<Interfaces.ICommand> CommandFactory { get; set; } = null!;

    /// <summary>
    /// Optional icon for the menu item (ImageSource in WPF).
    /// </summary>
    public object? Icon { get; set; }

    /// <summary>
    /// Whether the menu item is enabled.
    /// </summary>
    public bool IsEnabled { get; set; } = true;

    /// <summary>
    /// Whether to add a separator before this menu item.
    /// </summary>
    public bool SeparatorBefore { get; set; }

    /// <summary>
    /// Optional tooltip text.
    /// </summary>
    public string? ToolTip { get; set; }

    /// <summary>
    /// Additional data for special handling (e.g., path for rename dialog).
    /// </summary>
    public Dictionary<string, object>? AdditionalData { get; set; }
}

