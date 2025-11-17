using System.Windows;
using System.Windows.Media;

namespace EnhancedFileExplorer.UI.Helpers;

/// <summary>
/// Extension methods for visual tree operations with performance optimizations.
/// </summary>
public static class VisualTreeHelperExtensions
{
    /// <summary>
    /// Finds the first parent of the specified type in the visual tree.
    /// </summary>
    public static T? FindParent<T>(DependencyObject? child) where T : DependencyObject
    {
        var parent = VisualTreeHelper.GetParent(child);

        if (parent == null)
            return null;

        if (parent is T parentOfType)
            return parentOfType;

        return FindParent<T>(parent);
    }

    /// <summary>
    /// Finds a visual child element by name in the visual tree.
    /// </summary>
    public static T? FindVisualChild<T>(DependencyObject parent, string childName) where T : DependencyObject
    {
        if (parent == null)
            return null;

        for (int i = 0; i < VisualTreeHelper.GetChildrenCount(parent); i++)
        {
            var child = VisualTreeHelper.GetChild(parent, i);
            
            if (child is T t && child is FrameworkElement fe && fe.Name == childName)
                return t;

            var childOfChild = FindVisualChild<T>(child, childName);
            if (childOfChild != null)
                return childOfChild;
        }

        return null;
    }
}

