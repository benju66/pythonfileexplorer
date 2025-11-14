namespace EnhancedFileExplorer.Core.Models;

/// <summary>
/// Context information for building context menus.
/// </summary>
public class ContextMenuContext
{
    /// <summary>
    /// Path of the selected item (single selection).
    /// </summary>
    public string? SelectedPath { get; set; }

    /// <summary>
    /// Paths of selected items (multiple selection).
    /// </summary>
    public IEnumerable<string>? SelectedPaths { get; set; }

    /// <summary>
    /// Parent directory path (for empty space clicks).
    /// </summary>
    public string? ParentPath { get; set; }

    /// <summary>
    /// Whether the selected item is a directory.
    /// </summary>
    public bool IsDirectory { get; set; }

    /// <summary>
    /// Whether the selected item is a file.
    /// </summary>
    public bool IsFile { get; set; }

    /// <summary>
    /// Whether the selected item is a pinned item (for pinned panel context).
    /// </summary>
    public bool IsPinnedItem { get; set; }

    /// <summary>
    /// Additional context data as key-value pairs.
    /// </summary>
    public Dictionary<string, object> AdditionalData { get; set; } = new();
}

