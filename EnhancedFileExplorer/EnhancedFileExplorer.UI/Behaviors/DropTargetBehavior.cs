using System.Windows;
using System.Windows.Controls;

namespace EnhancedFileExplorer.UI.Behaviors;

/// <summary>
/// Attached behavior for marking TreeViewItems as drop targets.
/// Used to trigger visual state changes for smooth animations.
/// </summary>
public static class DropTargetBehavior
{
    /// <summary>
    /// Gets or sets whether the TreeViewItem is a drop target.
    /// </summary>
    public static readonly DependencyProperty IsDropTargetProperty =
        DependencyProperty.RegisterAttached(
            "IsDropTarget",
            typeof(bool),
            typeof(DropTargetBehavior),
            new PropertyMetadata(false));

    public static bool GetIsDropTarget(TreeViewItem item)
    {
        return (bool)item.GetValue(IsDropTargetProperty);
    }

    public static void SetIsDropTarget(TreeViewItem item, bool value)
    {
        item.SetValue(IsDropTargetProperty, value);
    }
}

