using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using EnhancedFileExplorer.UI.Controls;

namespace EnhancedFileExplorer.UI.Helpers;

/// <summary>
/// Helper class for determining drop zones in TreeView, including expanded folder children.
/// </summary>
public static class DropZoneHelper
{
    private const int MaxTraversalDepth = 10; // Prevent infinite loops

    /// <summary>
    /// Finds the appropriate drop target TreeViewItem for the given hit test result.
    /// If the hit is on a child of an expanded folder, returns the parent folder.
    /// </summary>
    /// <param name="treeView">The TreeView containing the items</param>
    /// <param name="hitTestResult">The visual hit from HitTest</param>
    /// <param name="mousePosition">The mouse position relative to the TreeView</param>
    /// <returns>The TreeViewItem that should receive the drop, or null if none found</returns>
    public static TreeViewItem? FindDropTarget(TreeView treeView, DependencyObject hitTestResult, Point mousePosition)
    {
        if (hitTestResult == null)
            return null;

        // First, try to find a TreeViewItem directly at the hit location
        var directItem = VisualTreeHelperExtensions.FindParent<TreeViewItem>(hitTestResult);
        
        if (directItem?.DataContext is FileTreeViewModel directViewModel)
        {
            // If it's a directory, it's a valid drop target
            if (directViewModel.IsDirectory)
                return directItem;

            // If it's a file, check if we're over an expanded parent folder's children area
            // by checking if the mouse is within the bounds of any expanded parent folder
            var parentFolder = FindExpandedParentFolder(directItem, mousePosition);
            if (parentFolder != null)
                return parentFolder;
        }

        // If no direct item found, check if mouse is over an expanded folder's children area
        return FindExpandedFolderAtPosition(treeView, mousePosition);
    }

    /// <summary>
    /// Finds an expanded parent folder that contains the given item and whose children area
    /// contains the mouse position.
    /// </summary>
    private static TreeViewItem? FindExpandedParentFolder(TreeViewItem item, Point mousePosition)
    {
        var current = VisualTreeHelperExtensions.FindParent<TreeViewItem>(item);
        int depth = 0;

        while (current != null && depth < MaxTraversalDepth)
        {
            if (current.DataContext is FileTreeViewModel viewModel && viewModel.IsDirectory && viewModel.IsExpanded)
            {
                // Check if mouse is within this folder's children area
                if (IsMouseOverChildrenArea(current, mousePosition))
                    return current;
            }

            current = VisualTreeHelperExtensions.FindParent<TreeViewItem>(current);
            depth++;
        }

        return null;
    }

    /// <summary>
    /// Finds an expanded folder at the given mouse position by checking all visible TreeViewItems.
    /// </summary>
    private static TreeViewItem? FindExpandedFolderAtPosition(TreeView treeView, Point mousePosition)
    {
        // Use hit test to find all items at this position
        var hitTestResult = VisualTreeHelper.HitTest(treeView, mousePosition);
        if (hitTestResult == null)
            return null;

        // Walk up the visual tree to find TreeViewItems
        var current = hitTestResult.VisualHit;
        int depth = 0;

        while (current != null && depth < MaxTraversalDepth)
        {
            if (current is TreeViewItem tvi && tvi.DataContext is FileTreeViewModel vm)
            {
                if (vm.IsDirectory)
                {
                    // Check if this folder is expanded and mouse is over its children area
                    if (vm.IsExpanded && IsMouseOverChildrenArea(tvi, mousePosition))
                        return tvi;
                    
                    // Even if not expanded, if mouse is directly over the folder item, it's valid
                    var bounds = new Rect(0, 0, tvi.ActualWidth, tvi.ActualHeight);
                    var relativePosition = mousePosition;
                    var itemPosition = tvi.TransformToAncestor(treeView).Transform(new Point(0, 0));
                    relativePosition.Offset(-itemPosition.X, -itemPosition.Y);
                    
                    if (bounds.Contains(relativePosition))
                        return tvi;
                }
            }

            current = VisualTreeHelper.GetParent(current);
            depth++;
        }

        return null;
    }

    /// <summary>
    /// Checks if the mouse position is over the children area of an expanded TreeViewItem.
    /// </summary>
    private static bool IsMouseOverChildrenArea(TreeViewItem item, Point mousePosition)
    {
        if (!item.IsExpanded)
            return false;

        // Find the ItemsPresenter (where children are rendered)
        var itemsPresenter = VisualTreeHelperExtensions.FindVisualChild<ItemsPresenter>(item, "ItemsHost");
        if (itemsPresenter == null)
            return false;

        // Get the bounds of the ItemsPresenter relative to the TreeView
        var treeView = VisualTreeHelperExtensions.FindParent<TreeView>(item);
        if (treeView == null)
            return false;

        var presenterBounds = itemsPresenter.TransformToAncestor(treeView).TransformBounds(
            new Rect(0, 0, itemsPresenter.ActualWidth, itemsPresenter.ActualHeight));

        return presenterBounds.Contains(mousePosition);
    }
}

