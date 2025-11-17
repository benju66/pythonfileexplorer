using System.Collections;
using System.Collections.ObjectModel;
using System.Collections.Specialized;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Input;
using System.Windows.Media;
using EnhancedFileExplorer.UI.Controls;

namespace EnhancedFileExplorer.UI.Behaviors;

/// <summary>
/// Attached behavior for enabling multi-select functionality in TreeView.
/// Uses ItemContainerGenerator for reliable TreeViewItem lookup that works with virtualization.
/// </summary>
public static class MultiSelectBehavior
{
    #region Attached Properties

    /// <summary>
    /// Gets or sets whether multi-select is enabled for the TreeView.
    /// </summary>
    public static readonly DependencyProperty IsEnabledProperty =
        DependencyProperty.RegisterAttached(
            "IsEnabled",
            typeof(bool),
            typeof(MultiSelectBehavior),
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
    /// Gets or sets the collection of selected items (ViewModels).
    /// </summary>
    public static readonly DependencyProperty SelectedItemsProperty =
        DependencyProperty.RegisterAttached(
            "SelectedItems",
            typeof(IList),
            typeof(MultiSelectBehavior),
            new PropertyMetadata(null, OnSelectedItemsChanged));

    public static IList? GetSelectedItems(TreeView treeView)
    {
        return (IList?)treeView.GetValue(SelectedItemsProperty);
    }

    public static void SetSelectedItems(TreeView treeView, IList? value)
    {
        treeView.SetValue(SelectedItemsProperty, value);
    }
    
    /// <summary>
    /// Gets or sets whether a TreeViewItem is multi-selected.
    /// This attached property is used for visual state management independent of TreeView's single-selection.
    /// </summary>
    public static readonly DependencyProperty IsMultiSelectedProperty =
        DependencyProperty.RegisterAttached(
            "IsMultiSelected",
            typeof(bool),
            typeof(MultiSelectBehavior),
            new PropertyMetadata(false));

    public static bool GetIsMultiSelected(TreeViewItem treeViewItem)
    {
        return (bool)treeViewItem.GetValue(IsMultiSelectedProperty);
    }

    public static void SetIsMultiSelected(TreeViewItem treeViewItem, bool value)
    {
        treeViewItem.SetValue(IsMultiSelectedProperty, value);
    }
    
    /// <summary>
    /// Gets the drag start point from the behavior's internal state.
    /// Used by FileTreeView for drag detection.
    /// Returns null if drag start point has not been set.
    /// </summary>
    public static Point? GetDragStartPoint(TreeView treeView)
    {
        var state = GetSelectionState(treeView);
        return state?.DragStartPoint;
    }
    
    /// <summary>
    /// Gets whether a drag operation is in progress.
    /// Used by FileTreeView for drag detection.
    /// </summary>
    public static bool GetIsDragging(TreeView treeView)
    {
        var state = GetSelectionState(treeView);
        return state?.IsDragging ?? false;
    }
    
    /// <summary>
    /// Sets whether a drag operation is in progress.
    /// Used by FileTreeView for drag detection.
    /// </summary>
    public static void SetIsDragging(TreeView treeView, bool value)
    {
        var state = GetSelectionState(treeView);
        state?.SetDragging(value);
    }
    
    /// <summary>
    /// Begins a drag operation, taking an immutable snapshot of the current selection.
    /// </summary>
    public static void BeginDrag(TreeView treeView)
    {
        var state = GetSelectionState(treeView);
        state?.BeginDrag();
    }
    
    /// <summary>
    /// Ends a drag operation, releasing the selection lock.
    /// </summary>
    public static void EndDrag(TreeView treeView)
    {
        var state = GetSelectionState(treeView);
        state?.EndDrag();
    }
    
    /// <summary>
    /// Gets the immutable snapshot of selection taken when drag began.
    /// </summary>
    public static IReadOnlyList<object> GetDragSelection(TreeView treeView)
    {
        var state = GetSelectionState(treeView);
        return state?.GetDragSelection() ?? Array.Empty<object>();
    }
    
    /// <summary>
    /// Checks if selection can be modified for the given TreeView.
    /// </summary>
    public static bool CanModifySelection(TreeView treeView)
    {
        var state = GetSelectionState(treeView);
        return state?.CanModifySelection() ?? true;
    }
    
    /// <summary>
    /// Resets the drag start point for the given TreeView.
    /// Used when mouse is released without starting a drag operation.
    /// </summary>
    public static void ResetDragStartPoint(TreeView treeView)
    {
        var state = GetSelectionState(treeView);
        state?.ResetDragStartPoint();
    }

    #endregion

    #region Private Fields

    private static readonly DependencyProperty SelectionStateProperty =
        DependencyProperty.RegisterAttached(
            "SelectionState",
            typeof(SelectionState),
            typeof(MultiSelectBehavior));

    private static SelectionState GetSelectionState(TreeView treeView)
    {
        return (SelectionState)treeView.GetValue(SelectionStateProperty);
    }

    private static void SetSelectionState(TreeView treeView, SelectionState value)
    {
        treeView.SetValue(SelectionStateProperty, value);
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

    private static void OnSelectedItemsChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
    {
        if (d is not TreeView treeView)
            return;

        var state = GetSelectionState(treeView);
        if (state != null)
        {
            // Detach from old collection's CollectionChanged event
            if (e.OldValue is INotifyCollectionChanged oldNotifyCollection)
            {
                oldNotifyCollection.CollectionChanged -= state.OnSelectedItemsCollectionChanged;
            }
            
            // Update the SelectedItems reference
            state.SelectedItems = e.NewValue as IList;
            
            // Attach to new collection's CollectionChanged event
            if (state.SelectedItems is INotifyCollectionChanged newNotifyCollection)
            {
                newNotifyCollection.CollectionChanged += state.OnSelectedItemsCollectionChanged;
            }
            
            // Re-sync UI with the new collection
            state.ResyncSelection();
        }
    }

    #endregion

    #region Behavior Attachment

    private static void AttachBehavior(TreeView treeView)
    {
        var state = new SelectionState(treeView);
        SetSelectionState(treeView, state);

        // Initialize SelectedItems collection if not provided
        if (GetSelectedItems(treeView) == null)
        {
            var selectedItems = new ObservableCollection<object>();
            SetSelectedItems(treeView, selectedItems);
        }

        state.SelectedItems = GetSelectedItems(treeView);

        // Attach event handlers
        treeView.PreviewMouseLeftButtonDown += state.OnPreviewMouseLeftButtonDown;
        treeView.PreviewKeyDown += state.OnPreviewKeyDown;
        treeView.SelectedItemChanged += state.OnSelectedItemChanged;

        // Handle collection changes
        if (state.SelectedItems is INotifyCollectionChanged notifyCollection)
        {
            notifyCollection.CollectionChanged += state.OnSelectedItemsCollectionChanged;
        }
        
        state.Initialize();
    }

    private static void DetachBehavior(TreeView treeView)
    {
        var state = GetSelectionState(treeView);
        if (state == null)
            return;

        // Detach event handlers
        treeView.PreviewMouseLeftButtonDown -= state.OnPreviewMouseLeftButtonDown;
        treeView.PreviewKeyDown -= state.OnPreviewKeyDown;
        treeView.SelectedItemChanged -= state.OnSelectedItemChanged;

        if (state.SelectedItems is INotifyCollectionChanged notifyCollection)
        {
            notifyCollection.CollectionChanged -= state.OnSelectedItemsCollectionChanged;
        }
        
        state.Cleanup();
        SetSelectionState(treeView, null!);
    }

    #endregion

    #region Selection State

    private class SelectionState
    {
        private readonly TreeView _treeView;
        private object? _anchorItem;
        private Point? _dragStartPoint;
        private bool _isDragging;
        private IReadOnlyList<object>? _dragSelectionSnapshot;
        private readonly object _selectionLock = new object();
        
        public IList? SelectedItems { get; set; }
        
        // Expose drag state for FileTreeView integration
        public Point? DragStartPoint => _dragStartPoint;
        public bool IsDragging => _isDragging;
        
        /// <summary>
        /// Begins a drag operation by taking an immutable snapshot of the current selection
        /// and locking selection modifications.
        /// </summary>
        public void BeginDrag()
        {
            lock (_selectionLock)
            {
                _isDragging = true;
                // Take immutable snapshot of current selection
                _dragSelectionSnapshot = SelectedItems?.Cast<object>().ToList().AsReadOnly();
            }
        }
        
        /// <summary>
        /// Ends a drag operation, releasing the selection lock and clearing the snapshot.
        /// </summary>
        public void EndDrag()
        {
            lock (_selectionLock)
            {
                _isDragging = false;
                _dragSelectionSnapshot = null;
            }
        }
        
        /// <summary>
        /// Gets the immutable snapshot of selection taken when drag began.
        /// Returns empty list if no drag is in progress.
        /// </summary>
        public IReadOnlyList<object> GetDragSelection()
        {
            lock (_selectionLock)
            {
                return _dragSelectionSnapshot ?? Array.Empty<object>();
            }
        }
        
        /// <summary>
        /// Checks if selection can be modified (i.e., no drag is in progress).
        /// </summary>
        public bool CanModifySelection()
        {
            lock (_selectionLock)
            {
                return !_isDragging;
            }
        }
        
        /// <summary>
        /// Sets the drag state. For backward compatibility, but prefer BeginDrag/EndDrag.
        /// </summary>
        public void SetDragging(bool value)
        {
            if (value)
                BeginDrag();
            else
                EndDrag();
        }
        
        /// <summary>
        /// Resets the drag start point to null (not set).
        /// </summary>
        public void ResetDragStartPoint()
        {
            _dragStartPoint = null;
        }
        
        /// <summary>
        /// Sets the drag start point. Should only be called when clicking on valid items.
        /// </summary>
        public void SetDragStartPoint(Point point)
        {
            _dragStartPoint = point;
        }

        public SelectionState(TreeView treeView)
        {
            _treeView = treeView ?? throw new ArgumentNullException(nameof(treeView));
        }
        
        public void Initialize()
        {
            // Initial sync of UI with SelectedItems collection
            ClearAllTreeViewItemSelections();
            if (SelectedItems != null)
            {
                // Use Dispatcher to ensure UI is ready
                _treeView.Dispatcher.BeginInvoke(new Action(() =>
                {
                    foreach (var item in SelectedItems.Cast<object>())
                    {
                        UpdateTreeViewItemSelection(item, true);
                    }
                }), System.Windows.Threading.DispatcherPriority.Loaded);
            }
        }
        
        public void Cleanup()
        {
            // Clear all selections on detach
            ClearAllTreeViewItemSelections();
        }
        
        /// <summary>
        /// Re-syncs the UI with the SelectedItems collection.
        /// Called when the SelectedItems collection is changed.
        /// </summary>
        public void ResyncSelection()
        {
            ClearAllTreeViewItemSelections();
            if (SelectedItems != null)
            {
                // Use Dispatcher to ensure UI updates happen correctly
                _treeView.Dispatcher.BeginInvoke(new Action(() =>
                {
                    foreach (var item in SelectedItems.Cast<object>())
                    {
                        UpdateTreeViewItemSelection(item, true);
                    }
                }), System.Windows.Threading.DispatcherPriority.Normal);
            }
        }

        public void OnPreviewMouseLeftButtonDown(object sender, MouseButtonEventArgs e)
        {
            // Reset drag state on new mouse down (only if not already dragging)
            // This handles the case where a new click happens while a drag might be in progress
            if (!_isDragging)
            {
                _isDragging = false; // Already false, but explicit for clarity
            }
            else
            {
                // If already dragging, end the previous drag operation
                EndDrag();
            }
            
            // Check if click is on expander button - allow it to work normally
            if (IsClickOnExpander(e))
            {
                // Reset drag start point for expander clicks
                ResetDragStartPoint();
                return; // Don't handle, let expander work
            }

            // Find clicked TreeViewItem
            var treeViewItem = FindTreeViewItem(e.OriginalSource as DependencyObject);
            if (treeViewItem?.DataContext == null)
            {
                // Empty space click - clear selection and reset drag start point
                ResetDragStartPoint();
                ClearSelection();
                e.Handled = true;
                return;
            }

            // Store clicked item reference for verification after selection
            var clickedItem = treeViewItem.DataContext;
            var mousePosition = e.GetPosition(null);

            // Ensure item is visible before selection (for virtualization)
            treeViewItem.BringIntoView();
            
            // Handle selection FIRST
            HandleSelection(e, clickedItem);
            
            // AFTER selection completes, verify item is selected and set drag start point
            // This fixes the timing issue where drag start point was set before selection completed
            if (SelectedItems != null && SelectedItems.Contains(clickedItem))
            {
                // Item is selected - set drag start point for potential drag operation
                SetDragStartPoint(mousePosition);
            }
            else
            {
                // Item not selected (e.g., Ctrl+Click deselected it, or selection was cleared)
                ResetDragStartPoint();
            }
            
            // Set focus for keyboard navigation
            treeViewItem.Focus();
            
            // DO NOT set e.Handled = true here - we need to allow WPF to capture the mouse
            // for drag-and-drop operations. The event will bubble up, but we've already
            // handled the selection logic. WPF needs the mouse down event to properly
            // initiate drag operations via DoDragDrop().
        }

        public void OnPreviewKeyDown(object sender, KeyEventArgs e)
        {
            // Prevent keyboard selection changes during drag
            if (!CanModifySelection())
                return;
            
            var modifiers = Keyboard.Modifiers;

            if (modifiers == ModifierKeys.Shift)
            {
                if (e.Key == Key.Up || e.Key == Key.Down)
                {
                    ExtendSelectionKeyboard(e.Key == Key.Up);
                    e.Handled = true;
                }
            }
            else if (modifiers == ModifierKeys.Control)
            {
                if (e.Key == Key.A)
                {
                    SelectAllVisible();
                    e.Handled = true;
                }
            }
            else if (e.Key == Key.Escape)
            {
                ClearSelection();
                _anchorItem = null;
                e.Handled = true;
            }
        }

        public void OnSelectedItemChanged(object sender, RoutedPropertyChangedEventArgs<object> e)
        {
            // For multi-select, we handle selection manually
            // TreeView.SelectedItem is read-only, so we can't clear it directly
            // Instead, we ignore this event and manage selection through our own collection
            // The SelectedItemChanged event may fire, but we don't use it for multi-select
            // We prevent conflicts by handling selection in PreviewMouseLeftButtonDown
        }

        public void OnSelectedItemsCollectionChanged(object? sender, NotifyCollectionChangedEventArgs e)
        {
            // Sync TreeViewItem.IsSelected when SelectedItems collection changes externally
            if (SelectedItems == null)
                return;

            // Use Dispatcher to ensure UI updates happen on the correct thread
            _treeView.Dispatcher.BeginInvoke(new Action(() =>
            {
                switch (e.Action)
                {
                    case NotifyCollectionChangedAction.Add:
                        foreach (var item in e.NewItems?.Cast<object>() ?? Enumerable.Empty<object>())
                        {
                            UpdateTreeViewItemSelection(item, true);
                        }
                        break;
                        
                    case NotifyCollectionChangedAction.Remove:
                        foreach (var item in e.OldItems?.Cast<object>() ?? Enumerable.Empty<object>())
                        {
                            UpdateTreeViewItemSelection(item, false);
                        }
                        break;
                        
                    case NotifyCollectionChangedAction.Replace:
                        // Handle replaced items
                        foreach (var item in e.OldItems?.Cast<object>() ?? Enumerable.Empty<object>())
                        {
                            UpdateTreeViewItemSelection(item, false);
                        }
                        foreach (var item in e.NewItems?.Cast<object>() ?? Enumerable.Empty<object>())
                        {
                            UpdateTreeViewItemSelection(item, true);
                        }
                        break;
                        
                    case NotifyCollectionChangedAction.Move:
                        // Move doesn't change selection state, but ensure UI is synced
                        ResyncSelection();
                        break;
                        
                    case NotifyCollectionChangedAction.Reset:
                        // Clear all selections
                        ClearAllTreeViewItemSelections();
                        break;
                }
            }), System.Windows.Threading.DispatcherPriority.Normal);
        }

        #region Selection Logic

        private void HandleSelection(MouseButtonEventArgs e, object clickedItem)
        {
            // Prevent selection changes during drag
            if (!CanModifySelection())
                return;
            
            var modifiers = Keyboard.Modifiers;

            if (modifiers == ModifierKeys.Control)
            {
                // Ctrl+Click: Toggle selection
                ToggleSelection(clickedItem);
                _anchorItem = clickedItem;
            }
            else if (modifiers == ModifierKeys.Shift && _anchorItem != null)
            {
                // Shift+Click: Range selection
                SelectRange(_anchorItem, clickedItem);
            }
            else
            {
                // Normal click: Clear and select single
                ClearSelection();
                AddToSelection(clickedItem);
                _anchorItem = clickedItem;
            }
        }

        private void AddToSelection(object item)
        {
            // Prevent selection changes during drag
            if (!CanModifySelection())
                return;
            
            if (SelectedItems == null || SelectedItems.Contains(item))
                return;

            SelectedItems.Add(item);
            UpdateTreeViewItemSelection(item, true);
        }

        private void RemoveFromSelection(object item)
        {
            // Prevent selection changes during drag
            if (!CanModifySelection())
                return;
            
            if (SelectedItems == null || !SelectedItems.Contains(item))
                return;

            SelectedItems.Remove(item);
            UpdateTreeViewItemSelection(item, false);

            // Update ViewModel if it has IsSelected property
            if (item is FileTreeViewModel viewModel)
            {
                viewModel.IsSelected = false;
            }
        }

        private void ToggleSelection(object item)
        {
            // Prevent selection changes during drag
            if (!CanModifySelection())
                return;
            
            if (SelectedItems == null)
                return;

            if (SelectedItems.Contains(item))
            {
                RemoveFromSelection(item);
            }
            else
            {
                AddToSelection(item);
            }
        }

        private void ClearSelection()
        {
            // Prevent selection changes during drag
            if (!CanModifySelection())
                return;
            
            if (SelectedItems == null)
                return;

            var itemsToRemove = SelectedItems.Cast<object>().ToList();
            foreach (var item in itemsToRemove)
            {
                RemoveFromSelection(item);
            }
            
            _anchorItem = null;
            // Reset drag start point when clearing selection
            ResetDragStartPoint();
        }

        private void SelectRange(object anchorItem, object currentItem)
        {
            // Prevent selection changes during drag
            if (!CanModifySelection())
                return;
            
            var visibleItems = GetVisibleItems();
            var anchorIndex = visibleItems.IndexOf(anchorItem);
            var currentIndex = visibleItems.IndexOf(currentItem);

            if (anchorIndex < 0 || currentIndex < 0)
            {
                ClearSelection();
                AddToSelection(currentItem);
                _anchorItem = currentItem;
                return;
            }

            var start = Math.Min(anchorIndex, currentIndex);
            var end = Math.Max(anchorIndex, currentIndex);

            // Clear selection first
            ClearSelection();

            // Select range
            for (int i = start; i <= end; i++)
            {
                AddToSelection(visibleItems[i]);
            }
        }

        private void ExtendSelectionKeyboard(bool moveUp)
        {
            // Prevent selection changes during drag
            if (!CanModifySelection())
                return;
            
            var visibleItems = GetVisibleItems();
            if (visibleItems.Count == 0)
                return;

            object? currentItem = null;

            // Try to find focused item
            var focusedElement = Keyboard.FocusedElement as FrameworkElement;
            if (focusedElement?.DataContext != null && visibleItems.Contains(focusedElement.DataContext))
            {
                currentItem = focusedElement.DataContext;
            }
            else if (_anchorItem != null && visibleItems.Contains(_anchorItem))
            {
                currentItem = _anchorItem;
            }
            else if (SelectedItems != null && SelectedItems.Count > 0)
            {
                currentItem = SelectedItems.Cast<object>().FirstOrDefault(visibleItems.Contains);
            }

            if (currentItem == null)
            {
                currentItem = moveUp ? visibleItems.Last() : visibleItems.First();
                ClearSelection();
                AddToSelection(currentItem);
                _anchorItem = currentItem;
                return;
            }

            var currentIndex = visibleItems.IndexOf(currentItem);
            if (currentIndex < 0)
                return;

            int newIndex = moveUp
                ? Math.Max(0, currentIndex - 1)
                : Math.Min(visibleItems.Count - 1, currentIndex + 1);

            if (newIndex == currentIndex)
                return;

            var newItem = visibleItems[newIndex];

            if (_anchorItem != null && visibleItems.Contains(_anchorItem))
            {
                SelectRange(_anchorItem, newItem);
            }
            else
            {
                ClearSelection();
                AddToSelection(newItem);
                _anchorItem = newItem;
            }

            // Focus the new item and bring it into view
            var treeViewItem = FindTreeViewItemForItemWithRetry(newItem);
            if (treeViewItem != null)
            {
                treeViewItem.BringIntoView();
                treeViewItem.Focus();
            }
        }

        private void SelectAllVisible()
        {
            // Prevent selection changes during drag
            if (!CanModifySelection())
                return;
            
            var visibleItems = GetVisibleItems();
            ClearSelection();
            foreach (var item in visibleItems)
            {
                AddToSelection(item);
            }
            if (visibleItems.Count > 0)
            {
                _anchorItem = visibleItems.First();
            }
        }

        #endregion

        #region Helper Methods

        private bool IsClickOnExpander(MouseButtonEventArgs e)
        {
            var hitTestResult = VisualTreeHelper.HitTest(_treeView, e.GetPosition(_treeView));
            var hitElement = hitTestResult.VisualHit;

            // Check if clicking on expander button (ToggleButton)
            ToggleButton? expanderButton = null;

            if (hitElement is ToggleButton toggleButton)
            {
                expanderButton = toggleButton;
            }
            else
            {
                expanderButton = FindParent<ToggleButton>(hitElement);
            }

            if (expanderButton != null)
            {
                var parentItem = FindParent<TreeViewItem>(expanderButton);
                if (parentItem != null)
                {
                    // This is the expander button - allow it to work normally
                    return true;
                }
            }

            return false;
        }

        private TreeViewItem? FindTreeViewItem(DependencyObject? element)
        {
            return FindParent<TreeViewItem>(element);
        }

        private TreeViewItem? FindTreeViewItemForItem(object item)
        {
            // Use ItemContainerGenerator for reliable lookup (works with virtualization)
            var container = _treeView.ItemContainerGenerator.ContainerFromItem(item) as TreeViewItem;
            if (container != null)
                return container;

            // If container not found, check if generator is ready
            if (_treeView.ItemContainerGenerator.Status != System.Windows.Controls.Primitives.GeneratorStatus.ContainersGenerated)
            {
                // Generator not ready - try to wait for it
                // This can happen with virtualization
                return null;
            }

            // Fallback: search recursively through visible items
            return FindTreeViewItemRecursive(_treeView, item);
        }
        
        private TreeViewItem? FindTreeViewItemForItemWithRetry(object item, int maxRetries = 3)
        {
            // First try immediate lookup
            var container = FindTreeViewItemForItem(item);
            if (container != null)
                return container;
            
            // If not found and generator is ready, try bringing item into view
            if (_treeView.ItemContainerGenerator.Status == System.Windows.Controls.Primitives.GeneratorStatus.ContainersGenerated)
            {
                // Try to find the item in the Items collection and bring it into view
                var itemsControl = _treeView as ItemsControl;
                if (itemsControl != null)
                {
                    var index = itemsControl.Items.IndexOf(item);
                    if (index >= 0)
                    {
                        var containerAtIndex = _treeView.ItemContainerGenerator.ContainerFromIndex(index) as TreeViewItem;
                        if (containerAtIndex != null)
                        {
                            containerAtIndex.BringIntoView();
                            // Update layout to ensure container is generated
                            _treeView.UpdateLayout();
                            // Try again after bringing into view
                            container = FindTreeViewItemForItem(item);
                            if (container != null)
                                return container;
                        }
                    }
                }
            }
            
            // If still not found, try recursive search as fallback
            return FindTreeViewItemRecursive(_treeView, item);
        }

        private TreeViewItem? FindTreeViewItemRecursive(ItemsControl parent, object item)
        {
            foreach (var childItem in parent.Items)
            {
                var container = parent.ItemContainerGenerator.ContainerFromItem(childItem) as TreeViewItem;
                if (container != null)
                {
                    if (container.DataContext == item)
                        return container;

                    var found = FindTreeViewItemRecursive(container, item);
                    if (found != null)
                        return found;
                }
            }

            return null;
        }

        private void UpdateTreeViewItemSelection(object item, bool isSelected)
        {
            var treeViewItem = FindTreeViewItemForItemWithRetry(item);
            if (treeViewItem != null)
            {
                // Use attached property for multi-select visual state (independent of TreeView's single-selection)
                SetIsMultiSelected(treeViewItem, isSelected);
                
                // Update ViewModel IsSelected property for backward compatibility (if needed elsewhere)
                if (item is FileTreeViewModel viewModel)
                {
                    viewModel.IsSelected = isSelected;
                }
                
                // Bring item into view if selecting (for virtualization)
                if (isSelected)
                {
                    treeViewItem.BringIntoView();
                }
            }
            else if (isSelected)
            {
                // If container not found but we're trying to select, update ViewModel anyway
                // The UI will sync when the container is generated
                if (item is FileTreeViewModel viewModel)
                {
                    viewModel.IsSelected = true;
                }
            }
        }

        private void ClearAllTreeViewItemSelections()
        {
            ClearTreeViewItemSelectionsRecursive(_treeView);
        }

        private void ClearTreeViewItemSelectionsRecursive(ItemsControl parent)
        {
            foreach (var childItem in parent.Items)
            {
                var container = parent.ItemContainerGenerator.ContainerFromItem(childItem) as TreeViewItem;
                if (container != null)
                {
                    // Clear attached property instead of TreeViewItem.IsSelected
                    SetIsMultiSelected(container, false);
                    ClearTreeViewItemSelectionsRecursive(container);
                }
            }
        }

        private List<object> GetVisibleItems()
        {
            var visible = new List<object>();
            CollectVisibleItems(_treeView.Items, visible);
            return visible;
        }

        private void CollectVisibleItems(IEnumerable items, List<object> result)
        {
            foreach (var item in items)
            {
                result.Add(item);

                // If item has children (hierarchical), collect them if expanded
                if (item is FileTreeViewModel viewModel && viewModel.IsDirectory && viewModel.IsExpanded)
                {
                    CollectVisibleItems(viewModel.Children, result);
                }
            }
        }

        private static T? FindParent<T>(DependencyObject? child) where T : DependencyObject
        {
            var parent = VisualTreeHelper.GetParent(child);

            if (parent == null)
                return null;

            if (parent is T parentOfType)
                return parentOfType;

            return FindParent<T>(parent);
        }

        #endregion
    }

    #endregion
}

