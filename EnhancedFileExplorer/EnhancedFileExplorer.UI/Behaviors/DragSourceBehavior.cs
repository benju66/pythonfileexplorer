using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;

namespace EnhancedFileExplorer.UI.Behaviors;

/// <summary>
/// Event arguments for drag start events.
/// </summary>
public class DragStartEventArgs : EventArgs
{
    /// <summary>
    /// The source TreeView that initiated the drag.
    /// </summary>
    public TreeView Source { get; set; } = null!;

    /// <summary>
    /// The type of drag source (e.g., "FileTree", "Tab", "Window").
    /// </summary>
    public string SourceType { get; set; } = string.Empty;

    /// <summary>
    /// The immutable snapshot of selected items taken when drag began.
    /// </summary>
    public IReadOnlyList<object> SelectedItems { get; set; } = Array.Empty<object>();

    /// <summary>
    /// The mouse event arguments from PreviewMouseMove.
    /// </summary>
    public MouseEventArgs MouseEventArgs { get; set; } = null!;
}

/// <summary>
/// Attached behavior for handling drag initiation in TreeView.
/// Coordinates with MultiSelectBehavior to ensure proper selection state before starting drag.
/// Designed to be extensible for future drag sources (tabs, windows, etc.).
/// </summary>
public static class DragSourceBehavior
{
    #region Attached Properties

    /// <summary>
    /// Gets or sets whether drag source behavior is enabled for the TreeView.
    /// </summary>
    public static readonly DependencyProperty IsEnabledProperty =
        DependencyProperty.RegisterAttached(
            "IsEnabled",
            typeof(bool),
            typeof(DragSourceBehavior),
            new PropertyMetadata(false, OnIsEnabledChanged));

    public static bool GetIsEnabled(TreeView treeView)
    {
        return (bool)treeView.GetValue(IsEnabledProperty);
    }

    public static void SetIsEnabled(TreeView treeView, bool value)
    {
        treeView.SetValue(IsEnabledProperty, value);
    }

    /// <summary>
    /// Gets or sets the source type for this drag source (e.g., "FileTree", "Tab", "Window").
    /// Used for future extensibility and identification.
    /// </summary>
    public static readonly DependencyProperty SourceTypeProperty =
        DependencyProperty.RegisterAttached(
            "SourceType",
            typeof(string),
            typeof(DragSourceBehavior),
            new PropertyMetadata("FileTree"));

    public static string GetSourceType(TreeView treeView)
    {
        return (string)treeView.GetValue(SourceTypeProperty);
    }

    public static void SetSourceType(TreeView treeView, string value)
    {
        treeView.SetValue(SourceTypeProperty, value);
    }

    /// <summary>
    /// Event raised when a drag operation should be started.
    /// FileTreeView (or future drag handlers) can subscribe to this to execute DoDragDrop.
    /// </summary>
    public static event EventHandler<DragStartEventArgs>? DragStartRequested;

    #endregion

    #region Private Fields

    private static readonly DependencyProperty DragSourceStateProperty =
        DependencyProperty.RegisterAttached(
            "DragSourceState",
            typeof(DragSourceState),
            typeof(DragSourceBehavior));

    private static DragSourceState GetDragSourceState(TreeView treeView)
    {
        return (DragSourceState)treeView.GetValue(DragSourceStateProperty);
    }

    private static void SetDragSourceState(TreeView treeView, DragSourceState value)
    {
        treeView.SetValue(DragSourceStateProperty, value);
    }

    #endregion

    #region Event Handlers

    private static void OnIsEnabledChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
    {
        if (d is not TreeView treeView)
            return;

        if ((bool)e.NewValue)
        {
            AttachBehavior(treeView);
        }
        else
        {
            DetachBehavior(treeView);
        }
    }

    #endregion

    #region Behavior Attachment

    private static void AttachBehavior(TreeView treeView)
    {
        var state = new DragSourceState(treeView);
        SetDragSourceState(treeView, state);

        // Attach event handlers
        treeView.PreviewMouseMove += state.OnPreviewMouseMove;
        treeView.PreviewMouseLeftButtonUp += state.OnPreviewMouseLeftButtonUp;
    }

    private static void DetachBehavior(TreeView treeView)
    {
        var state = GetDragSourceState(treeView);
        if (state == null)
            return;

        // Detach event handlers
        treeView.PreviewMouseMove -= state.OnPreviewMouseMove;
        treeView.PreviewMouseLeftButtonUp -= state.OnPreviewMouseLeftButtonUp;

        state.Cleanup();
        SetDragSourceState(treeView, null!);
    }

    #endregion

    #region Drag Source State

    private class DragSourceState
    {
        private readonly TreeView _treeView;

        public DragSourceState(TreeView treeView)
        {
            _treeView = treeView ?? throw new ArgumentNullException(nameof(treeView));
        }

        public void OnPreviewMouseMove(object sender, MouseEventArgs e)
        {
            // Only handle if left button is pressed
            if (e.LeftButton != MouseButtonState.Pressed)
                return;

            // Get drag state from MultiSelectBehavior
            var isDragging = MultiSelectBehavior.GetIsDragging(_treeView);
            var dragStartPoint = MultiSelectBehavior.GetDragStartPoint(_treeView);

            // Don't start drag if already dragging
            if (isDragging)
                return;

            // Check if drag start point is valid (was set on a valid item click)
            if (!dragStartPoint.HasValue)
                return;

            // Get selection state from MultiSelectBehavior
            var selectedItems = MultiSelectBehavior.GetSelectedItems(_treeView);
            if (selectedItems == null || selectedItems.Count == 0)
                return;

            // Use dispatcher to ensure selection is complete (handles async selection updates)
            _treeView.Dispatcher.BeginInvoke(new Action(() =>
            {
                // Double-check selection state after dispatcher delay
                var currentSelectedItems = MultiSelectBehavior.GetSelectedItems(_treeView);
                if (currentSelectedItems == null || currentSelectedItems.Count == 0)
                    return;

                // Check if mouse has moved enough to start a drag
                var currentPosition = e.GetPosition(null);
                var deltaX = Math.Abs(currentPosition.X - dragStartPoint.Value.X);
                var deltaY = Math.Abs(currentPosition.Y - dragStartPoint.Value.Y);

                if (deltaX > SystemParameters.MinimumHorizontalDragDistance ||
                    deltaY > SystemParameters.MinimumVerticalDragDistance)
                {
                    // Begin drag and take snapshot BEFORE starting drag operation
                    MultiSelectBehavior.BeginDrag(_treeView);

                    // Raise event for FileTreeView (or future drag handler) to handle
                    var sourceType = GetSourceType(_treeView);
                    var dragSelection = MultiSelectBehavior.GetDragSelection(_treeView);
                    
                    var args = new DragStartEventArgs
                    {
                        Source = _treeView,
                        SourceType = sourceType,
                        SelectedItems = dragSelection,
                        MouseEventArgs = e
                    };

                    DragStartRequested?.Invoke(_treeView, args);

                    // Mark event as handled to prevent other handlers from interfering
                    e.Handled = true;
                }
            }), System.Windows.Threading.DispatcherPriority.Input);
        }

        public void OnPreviewMouseLeftButtonUp(object sender, MouseButtonEventArgs e)
        {
            // If drag was started but cancelled (mouse released before threshold or drag failed),
            // ensure drag state is cleared
            var isDragging = MultiSelectBehavior.GetIsDragging(_treeView);
            if (isDragging)
            {
                // Drag was in progress but mouse released - end drag
                MultiSelectBehavior.EndDrag(_treeView);
            }
            else
            {
                // If drag didn't start (threshold not reached), reset drag start point
                // This prevents the next mouse move from incorrectly triggering a drag
                var dragStartPoint = MultiSelectBehavior.GetDragStartPoint(_treeView);
                if (dragStartPoint.HasValue)
                {
                    // Reset drag start point to prevent next mouse move from triggering drag
                    MultiSelectBehavior.ResetDragStartPoint(_treeView);
                }
            }
        }

        public void Cleanup()
        {
            // Cleanup if needed
        }
    }

    #endregion
}

