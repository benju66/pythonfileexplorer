using System.Collections;
using System.Collections.ObjectModel;
using System.Collections.Specialized;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Threading;
using EnhancedFileExplorer.Core.Interfaces;
using EnhancedFileExplorer.Core.Events;
using EnhancedFileExplorer.Core.Models;
using EnhancedFileExplorer.Services.ContextMenus;
using EnhancedFileExplorer.Services.FileOperations.Commands;
using EnhancedFileExplorer.UI.Behaviors;
using EnhancedFileExplorer.UI.Helpers;
using EnhancedFileExplorer.UI.Services;
using Microsoft.Extensions.Logging;

namespace EnhancedFileExplorer.UI.Controls;

/// <summary>
/// Custom TreeView control for displaying file system.
/// </summary>
public partial class FileTreeView : UserControl, IFileTreeRefreshTarget
{
    private IFileSystemService? _fileSystemService;
    private ILogger<FileTreeView>? _logger;
    private IContextMenuProvider? _contextMenuProvider;
    private ContextMenuBuilder? _contextMenuBuilder;
    private IIconService? _iconService;
    private IDragDropHandler? _dragDropHandler;
    private IUndoRedoManager? _undoRedoManager;
    private IRefreshCoordinator? _refreshCoordinator;
    private string _currentPath = string.Empty;
    
    // IFileTreeRefreshTarget implementation
    string? IFileTreeRefreshTarget.CurrentPath => _currentPath;
    public string InstanceId { get; } = Guid.NewGuid().ToString();
    private ObservableCollection<FileTreeViewModel> _rootItems;
    private readonly Dictionary<string, FileTreeViewModel> _viewModelCache;
    private int _sortColumn = 0; // 0=Name, 1=Size, 2=Modified, 3=Created
    private bool _sortAscending = true;
    
    // Drag state - drag start point and dragging flag are now managed by MultiSelectBehavior
    private TreeViewItem? _currentDropTarget; // Track current drop target for visual feedback
    private readonly Dictionary<TreeViewItem, Border?> _borderCache = new(); // Cache for Border lookups
    
    // Multi-select state - now managed by MultiSelectBehavior
    private readonly ObservableCollection<FileTreeViewModel> _selectedItems = new();
    
    // Refresh coordination - now handled by RefreshCoordinatorService

    public event EventHandler<string>? PathSelected;
    public event EventHandler<string>? PathDoubleClicked;

    public FileTreeView()
    {
        InitializeComponent();
        _rootItems = new ObservableCollection<FileTreeViewModel>();
        _viewModelCache = new Dictionary<string, FileTreeViewModel>(StringComparer.OrdinalIgnoreCase);
        FileTree.ItemsSource = _rootItems;
        
        // Enable multi-select behavior
        MultiSelectBehavior.SetIsEnabled(FileTree, true);
        MultiSelectBehavior.SetSelectedItems(FileTree, _selectedItems);
        
        // Enable drag source behavior for drag initiation
        DragSourceBehavior.SetIsEnabled(FileTree, true);
        DragSourceBehavior.SetSourceType(FileTree, "FileTree");
        DragSourceBehavior.DragStartRequested += OnDragStartRequested;
        
        // Handle item expanded event for lazy loading
        FileTree.AddHandler(TreeViewItem.ExpandedEvent, new RoutedEventHandler(OnItemExpanded));
        
        // Handle column header clicks for sorting
        if (ColumnHeaders != null)
        {
            ColumnHeaders.ColumnHeaderClicked += OnColumnHeaderClicked;
        }

        // CRITICAL FIX #4: Unsubscribe event handler when control is unloaded to prevent memory leaks
        this.Unloaded += FileTreeView_Unloaded;
    }

    /// <summary>
    /// Handles Unloaded event to clean up event subscriptions and prevent memory leaks.
    /// </summary>
    private void FileTreeView_Unloaded(object sender, RoutedEventArgs e)
    {
        // Unsubscribe from static event to prevent memory leaks
        DragSourceBehavior.DragStartRequested -= OnDragStartRequested;
        
        // Unregister from refresh coordinator
        _refreshCoordinator?.UnregisterTreeView(this);
        
        // Unsubscribe from Unloaded event
        this.Unloaded -= FileTreeView_Unloaded;
    }
    
    // IFileTreeRefreshTarget implementation
    bool IFileTreeRefreshTarget.ShouldRefresh(string path)
    {
        if (string.IsNullOrWhiteSpace(_currentPath) || string.IsNullOrWhiteSpace(path))
            return false;
        
        try
        {
            var normalizedCurrentPath = Path.GetFullPath(_currentPath);
            var normalizedPath = Path.GetFullPath(path);
            
            // Refresh if:
            // 1. Exact match (same directory)
            // 2. Path is parent of CurrentPath (change in parent affects us)
            // Note: We DON'T refresh if path is child - FileSystemWatcher handles that
            return normalizedCurrentPath.Equals(normalizedPath, StringComparison.OrdinalIgnoreCase) ||
                   normalizedCurrentPath.StartsWith(
                       normalizedPath + Path.DirectorySeparatorChar, 
                       StringComparison.OrdinalIgnoreCase);
        }
        catch (Exception ex)
        {
            _logger?.LogWarning(ex, "Error checking if should refresh: {Path}", path);
            return false;
        }
    }
    
    bool IFileTreeRefreshTarget.IsPathLoaded(string path)
    {
        if (string.IsNullOrWhiteSpace(path))
            return false;
        
        try
        {
            var normalizedPath = Path.GetFullPath(path);
            
            // Check if path is current path or in cache
            return _currentPath.Equals(normalizedPath, StringComparison.OrdinalIgnoreCase) ||
                   _viewModelCache.ContainsKey(normalizedPath);
        }
        catch (Exception ex)
        {
            _logger?.LogWarning(ex, "Error checking if path is loaded: {Path}", path);
            return false;
        }
    }
    
    Task IFileTreeRefreshTarget.LoadDirectoryAsync(string path)
    {
        return LoadDirectoryAsync(path);
    }
    
    Task IFileTreeRefreshTarget.RefreshDirectoryAsync(string path, bool preserveState)
    {
        return RefreshDirectoryAsync(path);
    }

    public void Initialize(
        IFileSystemService fileSystemService, 
        ILogger<FileTreeView>? logger = null,
        IContextMenuProvider? contextMenuProvider = null,
        ContextMenuBuilder? contextMenuBuilder = null,
        IIconService? iconService = null,
        IDragDropHandler? dragDropHandler = null,
        IUndoRedoManager? undoRedoManager = null,
        IRefreshCoordinator? refreshCoordinator = null)
    {
        _fileSystemService = fileSystemService ?? throw new ArgumentNullException(nameof(fileSystemService));
        _logger = logger;
        _contextMenuProvider = contextMenuProvider;
        _contextMenuBuilder = contextMenuBuilder;
        _iconService = iconService;
        _dragDropHandler = dragDropHandler;
        _undoRedoManager = undoRedoManager;
        _refreshCoordinator = refreshCoordinator;
        
        // Register with refresh coordinator
        _refreshCoordinator?.RegisterTreeView(this);
    }

    public string CurrentPath
    {
        get => _currentPath;
        set
        {
            _currentPath = value;
            LoadDirectoryAsync(value).ConfigureAwait(false);
        }
    }

    public async Task LoadDirectoryAsync(string path)
    {
        if (string.IsNullOrWhiteSpace(path) || _fileSystemService == null)
            return;

        try
        {
            // Preserve expansion and selection state before clearing
            var expandedPaths = GetExpandedPaths();
            var selectedPaths = GetSelectedPaths();
            
            var items = await _fileSystemService.GetItemsAsync(path);
            
            await Dispatcher.InvokeAsync(() =>
            {
                _rootItems.Clear();
                _viewModelCache.Clear();
                _selectedItems.Clear();
                
                // Sort items based on current sort column
                var sortedItems = SortItems(items);
                
                foreach (var item in sortedItems)
                {
                    var viewModel = CreateViewModel(item);
                    _rootItems.Add(viewModel);
                    _viewModelCache[item.Path] = viewModel;
                }
                
                // Restore expansion state
                RestoreExpandedPaths(expandedPaths);
                
                // Restore selection state
                RestoreSelectedPaths(selectedPaths);
            });

            _logger?.LogInformation("Loaded directory: {Path} ({Count} items)", path, items.Count());
        }
        catch (Exception ex)
        {
            _logger?.LogError(ex, "Error loading directory: {Path}", path);
            MessageBox.Show($"Error loading directory: {ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }


    /// <summary>
    /// Refreshes a specific directory without clearing the entire tree.
    /// Uses incremental updates to prevent flickering and preserve scroll position.
    /// Preserves expansion and selection state.
    /// Note: Debouncing is handled by RefreshCoordinatorService.
    /// </summary>
    public async Task RefreshDirectoryAsync(string path)
    {
        if (string.IsNullOrWhiteSpace(path) || _fileSystemService == null)
            return;

        try
        {

            // Preserve expansion and selection state
            var expandedPaths = GetExpandedPaths();
            var selectedPaths = GetSelectedPaths();
            
            // Preserve scroll position to prevent jumping
            ScrollViewer? scrollViewer = null;
            double scrollOffset = 0;
            // Find ScrollViewer in visual tree (it's typically a child of TreeView)
            for (int i = 0; i < VisualTreeHelper.GetChildrenCount(FileTree); i++)
            {
                var child = VisualTreeHelper.GetChild(FileTree, i);
                if (child is ScrollViewer sv)
                {
                    scrollViewer = sv;
                    scrollOffset = sv.VerticalOffset;
                    break;
                }
                // Check nested children
                scrollViewer = VisualTreeHelperExtensions.FindParent<ScrollViewer>(child);
                if (scrollViewer != null)
                {
                    scrollOffset = scrollViewer.VerticalOffset;
                    break;
                }
            }
            
            var items = await _fileSystemService.GetItemsAsync(path);
            
            await Dispatcher.InvokeAsync(() =>
            {
                // Suppress UI updates during batch operations to prevent flickering
                FileTree.IsEnabled = false;
                try
                {
                    // Find the ViewModel for this path
                    if (_viewModelCache.TryGetValue(path, out var viewModel))
                    {
                        RefreshDirectoryChildrenIncremental(viewModel, items, path);
                    }
                    else if (string.Equals(path, _currentPath, StringComparison.OrdinalIgnoreCase))
                    {
                        RefreshRootItemsIncremental(items);
                    }
                    
                    // Restore expansion state
                    RestoreExpandedPaths(expandedPaths);
                    
                    // Restore selection state
                    RestoreSelectedPaths(selectedPaths);
                }
                finally
                {
                    FileTree.IsEnabled = true;
                    
                    // Restore scroll position after layout completes
                    // Use Loaded priority to ensure layout is complete before restoring scroll
                    Dispatcher.BeginInvoke(new Action(() =>
                    {
                        if (scrollViewer != null)
                        {
                            // Force layout update to ensure accurate scroll restoration
                            FileTree.UpdateLayout();
                            
                            // Restore scroll position
                            if (scrollOffset > 0)
                            {
                                scrollViewer.ScrollToVerticalOffset(scrollOffset);
                            }
                        }
                    }), DispatcherPriority.Loaded);
                }
            }, DispatcherPriority.Normal);

            _logger?.LogInformation("Refreshed directory: {Path} ({Count} items)", path, items.Count());
        }
        catch (Exception ex)
        {
            _logger?.LogError(ex, "Error refreshing directory: {Path}", path);
            throw; // Re-throw so coordinator can handle retry
        }
    }

    /// <summary>
    /// Refreshes directory children using incremental updates to prevent flickering.
    /// Only adds/removes items that actually changed.
    /// </summary>
    private void RefreshDirectoryChildrenIncremental(FileTreeViewModel viewModel, IEnumerable<FileSystemItem> newItems, string parentPath)
    {
        var sortedNewItems = SortItems(newItems).ToList();
        var currentChildren = viewModel.Children.ToList();
        
        // Create dictionaries for efficient lookup
        var currentChildrenByPath = currentChildren
            .Where(c => !string.IsNullOrEmpty(c.Path))
            .ToDictionary(c => c.Path!, StringComparer.OrdinalIgnoreCase);
        
        var newItemsByPath = sortedNewItems
            .ToDictionary(i => i.Path, StringComparer.OrdinalIgnoreCase);
        
        // Find items to remove (exist in current but not in new)
        var itemsToRemove = currentChildrenByPath.Keys
            .Except(newItemsByPath.Keys, StringComparer.OrdinalIgnoreCase)
            .ToList();
        
        // Find items to add (exist in new but not in current)
        var itemsToAdd = newItemsByPath.Keys
            .Except(currentChildrenByPath.Keys, StringComparer.OrdinalIgnoreCase)
            .ToList();
        
        // Remove items that no longer exist
        foreach (var pathToRemove in itemsToRemove)
        {
            if (currentChildrenByPath.TryGetValue(pathToRemove, out var childToRemove))
            {
                // Check if selection can be modified (not during drag)
                if (MultiSelectBehavior.CanModifySelection(FileTree))
                {
                    _selectedItems.Remove(childToRemove);
                    childToRemove.IsSelected = false;
                }
                _viewModelCache.Remove(pathToRemove);
                viewModel.Children.Remove(childToRemove);
            }
        }
        
        // Update existing items and add new items in sorted order
        var insertIndex = 0;
        foreach (var newItem in sortedNewItems)
        {
            if (itemsToAdd.Contains(newItem.Path))
            {
                // New item - create ViewModel and insert at correct position
                var childViewModel = CreateViewModel(newItem);
                
                // Find correct insertion position based on sort order
                while (insertIndex < viewModel.Children.Count)
                {
                    var existingChild = viewModel.Children[insertIndex];
                    var compareResult = CompareViewModelItems(childViewModel, existingChild);
                    if (compareResult <= 0)
                        break;
                    insertIndex++;
                }
                
                viewModel.Children.Insert(insertIndex, childViewModel);
                _viewModelCache[newItem.Path] = childViewModel;
                insertIndex++;
            }
            else if (currentChildrenByPath.ContainsKey(newItem.Path))
            {
                // Existing item - update ViewModel in place to preserve identity
                var existingViewModel = currentChildrenByPath[newItem.Path];
                existingViewModel.UpdateFrom(newItem);
                
                // Update insert index for next new item
                var existingIndex = viewModel.Children.IndexOf(existingViewModel);
                if (existingIndex >= 0)
                    insertIndex = existingIndex + 1;
            }
        }
        
        viewModel.IsLoaded = true;
    }

    /// <summary>
    /// Refreshes root items using incremental updates to prevent flickering.
    /// </summary>
    private void RefreshRootItemsIncremental(IEnumerable<FileSystemItem> newItems)
    {
        var sortedNewItems = SortItems(newItems).ToList();
        
        // Create dictionaries for efficient lookup
        var currentItemsByPath = _rootItems
            .Where(c => !string.IsNullOrEmpty(c.Path))
            .ToDictionary(c => c.Path!, StringComparer.OrdinalIgnoreCase);
        
        var newItemsByPath = sortedNewItems
            .ToDictionary(i => i.Path, StringComparer.OrdinalIgnoreCase);
        
        // Find items to remove
        var itemsToRemove = currentItemsByPath.Keys
            .Except(newItemsByPath.Keys, StringComparer.OrdinalIgnoreCase)
            .ToList();
        
        // Find items to add
        var itemsToAdd = newItemsByPath.Keys
            .Except(currentItemsByPath.Keys, StringComparer.OrdinalIgnoreCase)
            .ToList();
        
        // Remove items that no longer exist
        foreach (var pathToRemove in itemsToRemove)
        {
            if (currentItemsByPath.TryGetValue(pathToRemove, out var itemToRemove))
            {
                // Check if selection can be modified (not during drag)
                if (MultiSelectBehavior.CanModifySelection(FileTree))
                {
                    _selectedItems.Remove(itemToRemove);
                    itemToRemove.IsSelected = false;
                }
                _viewModelCache.Remove(pathToRemove);
                _rootItems.Remove(itemToRemove);
            }
        }
        
        // Update existing items and add new items in sorted order
        var insertIndex = 0;
        foreach (var newItem in sortedNewItems)
        {
            if (itemsToAdd.Contains(newItem.Path))
            {
                // New item - create ViewModel and insert at correct position
                var viewModel = CreateViewModel(newItem);
                
                // Find correct insertion position based on sort order
                while (insertIndex < _rootItems.Count)
                {
                    var existingItem = _rootItems[insertIndex];
                    var compareResult = CompareViewModelItems(viewModel, existingItem);
                    if (compareResult <= 0)
                        break;
                    insertIndex++;
                }
                
                _rootItems.Insert(insertIndex, viewModel);
                _viewModelCache[newItem.Path] = viewModel;
                insertIndex++;
            }
            else if (currentItemsByPath.ContainsKey(newItem.Path))
            {
                // Existing item - update ViewModel in place to preserve identity
                var existingViewModel = currentItemsByPath[newItem.Path];
                existingViewModel.UpdateFrom(newItem);
                
                // Update insert index for next new item
                var existingIndex = _rootItems.IndexOf(existingViewModel);
                if (existingIndex >= 0)
                    insertIndex = existingIndex + 1;
            }
        }
    }

    /// <summary>
    /// Compares two FileTreeViewModel items based on current sort settings.
    /// Returns: negative if item1 < item2, 0 if equal, positive if item1 > item2
    /// </summary>
    private int CompareViewModelItems(FileTreeViewModel item1, FileTreeViewModel item2)
    {
        // Directories first
        if (item1.IsDirectory != item2.IsDirectory)
            return item1.IsDirectory ? -1 : 1;
        
        // Then sort by current column
        int comparison = _sortColumn switch
        {
            0 => string.Compare(item1.Name, item2.Name, StringComparison.OrdinalIgnoreCase), // Name
            1 => item1.Size.CompareTo(item2.Size), // Size
            2 => item1.ModifiedDate.CompareTo(item2.ModifiedDate), // Modified
            3 => item1.CreatedDate.CompareTo(item2.CreatedDate), // Created
            _ => string.Compare(item1.Name, item2.Name, StringComparison.OrdinalIgnoreCase)
        };
        
        return _sortAscending ? comparison : -comparison;
    }

    /// <summary>
    /// Gets all currently expanded directory paths.
    /// </summary>
    private HashSet<string> GetExpandedPaths()
    {
        var expandedPaths = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        
        foreach (var viewModel in _viewModelCache.Values)
        {
            if (viewModel.IsDirectory && viewModel.IsExpanded)
            {
                expandedPaths.Add(viewModel.Path);
            }
        }
        
        return expandedPaths;
    }

    /// <summary>
    /// Restores expansion state for directories that were previously expanded.
    /// </summary>
    private void RestoreExpandedPaths(HashSet<string> expandedPaths)
    {
        foreach (var path in expandedPaths)
        {
            if (_viewModelCache.TryGetValue(path, out var viewModel) && viewModel.IsDirectory)
            {
                viewModel.IsExpanded = true;
                
                // Also find and expand the corresponding TreeViewItem
                var treeViewItem = FindTreeViewItemForViewModel(viewModel);
                if (treeViewItem != null)
                {
                    treeViewItem.IsExpanded = true;
                }
            }
        }
    }
    
    /// <summary>
    /// Gets all currently selected item paths.
    /// </summary>
    private HashSet<string> GetSelectedPaths()
    {
        var selectedPaths = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        
        foreach (var viewModel in _selectedItems.OfType<FileTreeViewModel>())
        {
            if (!string.IsNullOrEmpty(viewModel.Path))
            {
                selectedPaths.Add(viewModel.Path);
            }
        }
        
        return selectedPaths;
    }
    
    /// <summary>
    /// Restores selection state for items that were previously selected.
    /// Uses MultiSelectBehavior's sync mechanism to ensure proper UI updates.
    /// </summary>
    private void RestoreSelectedPaths(HashSet<string> selectedPaths)
    {
        // Prevent selection changes during drag
        if (!MultiSelectBehavior.CanModifySelection(FileTree))
            return;
        
        // Clear selection through the behavior's collection
        _selectedItems.Clear();
        
        // Add items to selection - the behavior will sync UI automatically
        foreach (var path in selectedPaths)
        {
            if (_viewModelCache.TryGetValue(path, out var viewModel))
            {
                _selectedItems.Add(viewModel);
                // ViewModel.IsSelected will be updated by MultiSelectBehavior when it syncs
            }
        }
        
        // Trigger behavior sync to update UI
        // The behavior listens to collection changes, so this should happen automatically
        // But we can also explicitly trigger a sync if needed
        var behavior = MultiSelectBehavior.GetSelectedItems(FileTree);
        if (behavior != null && behavior is INotifyCollectionChanged)
        {
            // Collection change will trigger behavior's OnSelectedItemsCollectionChanged
            // which will sync the UI
        }
    }

    /// <summary>
    /// Finds the TreeViewItem for a given ViewModel.
    /// Uses ItemContainerGenerator for reliable lookup (works with virtualization).
    /// </summary>
    private TreeViewItem? FindTreeViewItemForViewModel(FileTreeViewModel viewModel)
    {
        return FindTreeViewItemRecursive(FileTree, viewModel);
    }

    private TreeViewItem? FindTreeViewItemRecursive(ItemsControl parent, FileTreeViewModel targetViewModel)
    {
        foreach (var item in parent.Items)
        {
            var container = parent.ItemContainerGenerator.ContainerFromItem(item) as TreeViewItem;
            if (container != null)
            {
                if (container.DataContext == targetViewModel)
                {
                    return container;
                }
                
                // Check children recursively
                var found = FindTreeViewItemRecursive(container, targetViewModel);
                if (found != null)
                {
                    return found;
                }
            }
        }
        
        return null;
    }

    private FileTreeViewModel CreateViewModel(FileSystemItem item)
    {
        var viewModel = new FileTreeViewModel(item);
        
        // For directories, add a placeholder child to show expand arrow
        if (item.IsDirectory)
        {
            var placeholder = new FileTreeViewModel(new FileSystemItem 
            { 
                Name = "Loading...", 
                Path = string.Empty,
                IsDirectory = false 
            });
            viewModel.Children.Add(placeholder);
        }
        
        // Load icon asynchronously
        LoadIconForViewModel(viewModel);
        
        return viewModel;
    }

    private async void LoadIconForViewModel(FileTreeViewModel viewModel)
    {
        if (_iconService == null)
            return;

        try
        {
            var iconSource = await _iconService.GetIconAsync(viewModel.Path, viewModel.IsDirectory);
            if (iconSource is ImageSource imageSource)
            {
                await Dispatcher.InvokeAsync(() =>
                {
                    viewModel.Icon = imageSource;
                });
            }
        }
        catch (Exception ex)
        {
            _logger?.LogWarning(ex, "Failed to load icon for: {Path}", viewModel.Path);
        }
    }

    private async void OnItemExpanded(object sender, RoutedEventArgs e)
    {
        if (e.OriginalSource is TreeViewItem treeViewItem && 
            treeViewItem.DataContext is FileTreeViewModel viewModel &&
            viewModel.IsDirectory && 
            !viewModel.IsLoaded)
        {
            await LoadChildrenAsync(viewModel);
        }
    }

    private async Task LoadChildrenAsync(FileTreeViewModel parentViewModel)
    {
        if (_fileSystemService == null || parentViewModel.IsLoaded)
            return;

        try
        {
            // Clear placeholder
            parentViewModel.Children.Clear();

            var items = await _fileSystemService.GetItemsAsync(parentViewModel.Path);
            
            await Dispatcher.InvokeAsync(() =>
            {
                // Sort items based on current sort column
                var sortedItems = SortItems(items);
                
                foreach (var item in sortedItems)
                {
                    var childViewModel = CreateViewModel(item);
                    parentViewModel.Children.Add(childViewModel);
                    _viewModelCache[item.Path] = childViewModel;
                }

                parentViewModel.IsLoaded = true;
            });

            _logger?.LogInformation("Loaded directory children: {Path} ({Count} items)", parentViewModel.Path, items.Count());
        }
        catch (Exception ex)
        {
            _logger?.LogError(ex, "Error loading directory children: {Path}", parentViewModel.Path);
            
            await Dispatcher.InvokeAsync(() =>
            {
                parentViewModel.Children.Clear();
                var errorViewModel = new FileTreeViewModel(new FileSystemItem 
                { 
                    Name = $"Error: {ex.Message}", 
                    Path = string.Empty,
                    IsDirectory = false 
                });
                parentViewModel.Children.Add(errorViewModel);
            });
        }
    }


    private void FileTree_SelectedItemChanged(object sender, RoutedPropertyChangedEventArgs<object> e)
    {
        // For multi-select, selection is handled by MultiSelectBehavior
        // Raise PathSelected for the first selected item
        if (_selectedItems.Count > 0)
        {
            var firstSelected = _selectedItems.First();
            PathSelected?.Invoke(this, firstSelected.Path);
        }
    }

    private void FileTree_MouseDoubleClick(object sender, MouseButtonEventArgs e)
    {
        // Find the item that was actually double-clicked, not just SelectedItem
        var hitTestResult = VisualTreeHelper.HitTest(FileTree, e.GetPosition(FileTree));
        var treeViewItem = FindParent<TreeViewItem>(hitTestResult.VisualHit);
        
        if (treeViewItem?.DataContext is FileTreeViewModel viewModel && viewModel.IsDirectory)
        {
            PathDoubleClicked?.Invoke(this, viewModel.Path);
        }
        else if (_selectedItems.Count > 0)
        {
            // Fallback: use first selected item if click target not found
            var firstSelected = _selectedItems.First();
            if (firstSelected.IsDirectory)
            {
                PathDoubleClicked?.Invoke(this, firstSelected.Path);
            }
        }
    }

    private async void FileTree_MouseRightButtonDown(object sender, MouseButtonEventArgs e)
    {
        if (_contextMenuProvider == null || _contextMenuBuilder == null)
            return;

        try
        {
            // Find the item under the mouse cursor
            var hitTestResult = VisualTreeHelper.HitTest(FileTree, e.GetPosition(FileTree));
            var treeViewItem = FindParent<TreeViewItem>(hitTestResult.VisualHit);
            
            string? selectedPath = null;
            string? parentPath = _currentPath;
            bool isDirectory = false;
            bool isFile = false;
            IEnumerable<string>? selectedPaths = null;

            if (treeViewItem?.DataContext is FileTreeViewModel viewModel)
            {
                // If clicked item is in selection, use multi-select context
                if (_selectedItems.Contains(viewModel) && _selectedItems.Count > 1)
                {
                    selectedPaths = _selectedItems.Select(vm => vm.Path).Where(p => !string.IsNullOrEmpty(p));
                    parentPath = System.IO.Path.GetDirectoryName(viewModel.Path);
                    isDirectory = viewModel.IsDirectory;
                    isFile = !isDirectory;
                }
                else
                {
                    // Single selection or clicked item not selected
                    selectedPath = viewModel.Path;
                    parentPath = System.IO.Path.GetDirectoryName(viewModel.Path);
                    isDirectory = viewModel.IsDirectory;
                    isFile = !isDirectory;
                }
            }
            else if (_selectedItems.Count > 0)
            {
                // Right-click on empty space but we have selections - use multi-select context
                selectedPaths = _selectedItems.Select(vm => vm.Path).Where(p => !string.IsNullOrEmpty(p));
            }

            var context = new ContextMenuContext
            {
                SelectedPath = selectedPath,
                SelectedPaths = selectedPaths,
                ParentPath = parentPath ?? _currentPath,
                IsDirectory = isDirectory,
                IsFile = isFile
            };

            var actions = await _contextMenuProvider.GetMenuActionsAsync(context);
            var menu = _contextMenuBuilder.BuildMenu(actions);
            
            menu.PlacementTarget = FileTree;
            menu.Placement = System.Windows.Controls.Primitives.PlacementMode.MousePoint;
            menu.IsOpen = true;

            e.Handled = true;
        }
        catch (Exception ex)
        {
            _logger?.LogError(ex, "Error showing context menu");
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

    private void OnColumnHeaderClicked(object? sender, int columnIndex)
    {
        // Toggle sort direction if clicking same column, otherwise sort ascending
        if (_sortColumn == columnIndex)
        {
            _sortAscending = !_sortAscending;
        }
        else
        {
            _sortColumn = columnIndex;
            _sortAscending = true;
        }

        // Refresh current view
        if (!string.IsNullOrWhiteSpace(_currentPath))
        {
            LoadDirectoryAsync(_currentPath).ConfigureAwait(false);
        }
    }

    private IEnumerable<FileSystemItem> SortItems(IEnumerable<FileSystemItem> items)
    {
        // Always show directories first, then files
        var directories = items.Where(i => i.IsDirectory);
        var files = items.Where(i => !i.IsDirectory);

        IOrderedEnumerable<FileSystemItem> sortedDirectories;
        IOrderedEnumerable<FileSystemItem> sortedFiles;

        // Sort directories
        sortedDirectories = _sortColumn switch
        {
            0 => _sortAscending 
                ? directories.OrderBy(i => i.Name)
                : directories.OrderByDescending(i => i.Name),
            1 => _sortAscending
                ? directories.OrderBy(i => 0L) // Directories have no size
                : directories.OrderByDescending(i => 0L),
            2 => _sortAscending
                ? directories.OrderBy(i => i.ModifiedDate)
                : directories.OrderByDescending(i => i.ModifiedDate),
            3 => _sortAscending
                ? directories.OrderBy(i => i.CreatedDate)
                : directories.OrderByDescending(i => i.CreatedDate),
            _ => directories.OrderBy(i => i.Name)
        };

        // Sort files
        sortedFiles = _sortColumn switch
        {
            0 => _sortAscending
                ? files.OrderBy(i => i.Name)
                : files.OrderByDescending(i => i.Name),
            1 => _sortAscending
                ? files.OrderBy(i => i.Size)
                : files.OrderByDescending(i => i.Size),
            2 => _sortAscending
                ? files.OrderBy(i => i.ModifiedDate)
                : files.OrderByDescending(i => i.ModifiedDate),
            3 => _sortAscending
                ? files.OrderBy(i => i.CreatedDate)
                : files.OrderByDescending(i => i.CreatedDate),
            _ => files.OrderBy(i => i.Name)
        };

        return sortedDirectories.Concat(sortedFiles);
    }

    #region Drag and Drop

    // PreviewMouseLeftButtonDown is now handled by MultiSelectBehavior
    // PreviewMouseMove and PreviewMouseLeftButtonUp are now handled by DragSourceBehavior
    // Drag initiation logic has been moved to DragSourceBehavior for better separation of concerns

    /// <summary>
    /// Handles drag start requests from DragSourceBehavior.
    /// This method executes the actual DoDragDrop operation.
    /// </summary>
    private void OnDragStartRequested(object? sender, DragStartEventArgs e)
    {
        if (_dragDropHandler == null || e.Source != FileTree)
            return;

        // Use captured mouse position instead of MouseEventArgs (which is now a Point)
        StartDragOperation(e.MousePosition, e.SelectedItems);
    }
    
    // Keyboard navigation and selection are now handled by MultiSelectBehavior

    private void StartDragOperation(Point mousePosition, IReadOnlyList<object> dragSelection)
    {
        if (_dragDropHandler == null)
        {
            // If drag handler is null, end drag that was started by DragSourceBehavior
            MultiSelectBehavior.EndDrag(FileTree);
            return;
        }

        // Convert drag selection to FileTreeViewModel list
        var selectedItems = dragSelection.OfType<FileTreeViewModel>().ToList();
        
        if (selectedItems.Count == 0)
        {
            // No items in snapshot, end drag
            MultiSelectBehavior.EndDrag(FileTree);
            return;
        }

        var sourcePaths = selectedItems.Select(vm => vm.Path).Where(p => !string.IsNullOrEmpty(p)).ToArray();
        if (sourcePaths.Length == 0)
        {
            // No valid paths, end drag
            MultiSelectBehavior.EndDrag(FileTree);
            return;
        }

        // Validate drag
        var context = new DragDropContext
        {
            SourcePaths = sourcePaths,
            RequestedEffect = DragDropEffect.Move
        };

        var canDrag = _dragDropHandler.CanDrag(context);
        if (!canDrag.IsValid)
        {
            // Drag not allowed, end drag
            MultiSelectBehavior.EndDrag(FileTree);
            return;
        }

        // Drag is already started (BeginDrag was called in PreviewMouseMove)
        // Selection is locked and snapshot is taken

        // Create drag data
        var dataObject = _dragDropHandler.CreateDragData(sourcePaths, isCut: false);
        if (dataObject is not System.Windows.IDataObject wpfDataObject)
        {
            MultiSelectBehavior.EndDrag(FileTree);
            return;
        }

        // Determine allowed effects
        var allowedEffects = System.Windows.DragDropEffects.Move | System.Windows.DragDropEffects.Copy;

        // Set cursor once at drag start (don't change during DragOver to prevent flickering)
        FileTree.Cursor = Cursors.Arrow;

        try
        {
            var result = DragDrop.DoDragDrop(FileTree, wpfDataObject, allowedEffects);
            
            // Handle result if needed (e.g., clear cut clipboard)
            if (result == System.Windows.DragDropEffects.Move)
            {
                _logger?.LogInformation("Drag-drop move completed");
            }
            else if (result == System.Windows.DragDropEffects.Copy)
            {
                _logger?.LogInformation("Drag-drop copy completed");
            }
        }
        catch (Exception ex)
        {
            _logger?.LogError(ex, "Error during drag operation");
        }
        finally
        {
            // Always end drag and release selection lock
            MultiSelectBehavior.EndDrag(FileTree);
        }
    }

    private void FileTree_DragEnter(object sender, DragEventArgs e)
    {
        // Initialize drag-and-drop state when drag enters the TreeView
        // This is called before DragOver, so we can set up initial state here
        if (_dragDropHandler == null)
        {
            e.Effects = DragDropEffects.None;
            e.Handled = true;
            return;
        }

        // Extract drag data to validate it's a valid drag operation
        var dragData = _dragDropHandler.ExtractDragData(e.Data);
        if (dragData == null)
        {
            e.Effects = DragDropEffects.None;
            e.Handled = true;
            return;
        }

        // Allow the drag to continue - DragOver will handle detailed validation
        // Set initial effects based on what's being dragged
        e.Effects = DragDropEffects.Move | DragDropEffects.Copy;
        e.Handled = true;
    }

    private void FileTree_DragOver(object sender, DragEventArgs e)
    {
        if (_dragDropHandler == null)
        {
            ClearDropTargetVisual();
            e.Effects = DragDropEffects.None;
            e.Handled = true;
            return;
        }

        // Extract drag data
        var dragData = _dragDropHandler.ExtractDragData(e.Data);
        if (dragData == null)
        {
            ClearDropTargetVisual();
            e.Effects = DragDropEffects.None;
            e.Handled = true;
            return;
        }

        // Find drop target using DropZoneHelper (supports expanded folder children)
        var hitTestResult = VisualTreeHelper.HitTest(FileTree, e.GetPosition(FileTree));
        var mousePosition = e.GetPosition(FileTree);
        var treeViewItem = DropZoneHelper.FindDropTarget(FileTree, hitTestResult?.VisualHit, mousePosition);
        
        string? targetPath = null;
        bool isDirectory = false;
        FileTreeViewModel? viewModel = null;

        if (treeViewItem?.DataContext is FileTreeViewModel vm)
        {
            targetPath = vm.Path;
            isDirectory = vm.IsDirectory;
            viewModel = vm;
        }
        else
        {
            // Dropping on empty space - use current path
            targetPath = _currentPath;
            isDirectory = true;
            treeViewItem = null; // No visual target for empty space
        }

        if (string.IsNullOrWhiteSpace(targetPath) || !isDirectory)
        {
            ClearDropTargetVisual();
            e.Effects = DragDropEffects.None;
            e.Handled = true;
            // Don't change cursor - rely on visual feedback only
            return;
        }

        // Determine requested effect based on keyboard modifiers
        var requestedEffect = (Keyboard.Modifiers & ModifierKeys.Control) == ModifierKeys.Control
            ? DragDropEffect.Copy
            : DragDropEffect.Move;

        // Validate drop
        var context = new DragDropContext
        {
            SourcePaths = dragData.Value.FilePaths,
            TargetPath = targetPath,
            IsDirectory = isDirectory,
            RequestedEffect = requestedEffect,
            IsExternalDrag = dragData.Value.IsExternal
        };

        var canDrop = _dragDropHandler.CanDrop(context);
        
        if (canDrop.IsValid)
        {
            // Convert our DragDropEffect to WPF DragDropEffects
            var wpfEffects = System.Windows.DragDropEffects.None;
            if ((canDrop.AllowedEffects & DragDropEffect.Copy) == DragDropEffect.Copy)
                wpfEffects |= System.Windows.DragDropEffects.Copy;
            if ((canDrop.AllowedEffects & DragDropEffect.Move) == DragDropEffect.Move)
                wpfEffects |= System.Windows.DragDropEffects.Move;
            
            e.Effects = wpfEffects;
            e.Handled = true;
            // Don't change cursor - rely on visual feedback only (prevents flickering)
            
            // Update visual feedback for valid drop target
            if (treeViewItem != null)
            {
                SetDropTargetVisual(treeViewItem, requestedEffect == DragDropEffect.Copy);
                // Don't auto-expand during drag - only visual feedback
            }
        }
        else
        {
            ClearDropTargetVisual();
            e.Effects = System.Windows.DragDropEffects.None;
            e.Handled = true;
            // Don't change cursor - rely on visual feedback only
        }
    }

    private async void FileTree_Drop(object sender, DragEventArgs e)
    {
        if (_dragDropHandler == null || _undoRedoManager == null)
        {
            ClearDropTargetVisual();
            e.Effects = System.Windows.DragDropEffects.None;
            e.Handled = true;
            return;
        }

        FileTree.Cursor = Cursors.Arrow;
        ClearDropTargetVisual();

        // Extract drag data
        var dragData = _dragDropHandler.ExtractDragData(e.Data);
        if (dragData == null)
        {
            e.Effects = System.Windows.DragDropEffects.None;
            e.Handled = true;
            return;
        }

        // Find drop target using DropZoneHelper (supports expanded folder children)
        var hitTestResult = VisualTreeHelper.HitTest(FileTree, e.GetPosition(FileTree));
        var mousePosition = e.GetPosition(FileTree);
        var treeViewItem = DropZoneHelper.FindDropTarget(FileTree, hitTestResult?.VisualHit, mousePosition);
        
        string? targetPath = null;
        bool isDirectory = false;
        FileTreeViewModel? targetViewModel = null;

        if (treeViewItem?.DataContext is FileTreeViewModel viewModel)
        {
            targetPath = viewModel.Path;
            isDirectory = viewModel.IsDirectory;
            targetViewModel = viewModel;
        }
        else
        {
            targetPath = _currentPath;
            isDirectory = true;
        }

        if (string.IsNullOrWhiteSpace(targetPath) || !isDirectory)
        {
            e.Effects = System.Windows.DragDropEffects.None;
            e.Handled = true;
            return;
        }

        // Ensure folder is expanded and stays expanded after drop
        // Only expand if it's already expanded (don't force expansion)
        if (targetViewModel != null && targetViewModel.IsDirectory && treeViewItem != null)
        {
            // If folder is already expanded, keep it expanded
            if (targetViewModel.IsExpanded || treeViewItem.IsExpanded)
            {
                targetViewModel.IsExpanded = true;
                treeViewItem.IsExpanded = true;
            }
        }

        // Determine requested effect
        var requestedEffect = (Keyboard.Modifiers & ModifierKeys.Control) == ModifierKeys.Control
            ? DragDropEffect.Copy
            : DragDropEffect.Move;

        var context = new DragDropContext
        {
            SourcePaths = dragData.Value.FilePaths,
            TargetPath = targetPath,
            IsDirectory = isDirectory,
            RequestedEffect = requestedEffect,
            IsExternalDrag = dragData.Value.IsExternal
        };

        // Validate
        var canDrop = _dragDropHandler.CanDrop(context);
        if (!canDrop.IsValid)
        {
            MessageBox.Show(canDrop.ErrorMessage ?? "Cannot drop here", "Invalid Drop", 
                MessageBoxButton.OK, MessageBoxImage.Warning);
            e.Effects = System.Windows.DragDropEffects.None;
            e.Handled = true;
            return;
        }

        try
        {
            // Use the handler's ExecuteDropAsync method which handles the operation
            // TODO: Refactor to use commands for undo/redo support
            var result = await _dragDropHandler!.ExecuteDropAsync(context, cancellationToken: default);
            
            // Convert requested effect to WPF DragDropEffects
            var wpfEffect = requestedEffect == DragDropEffect.Move 
                ? System.Windows.DragDropEffects.Move 
                : System.Windows.DragDropEffects.Copy;
            
            if (result.IsSuccess)
            {
                e.Effects = wpfEffect;
                e.Handled = true;
                
                // Use refresh coordinator for drag/drop (High priority, immediate)
                var targetRequest = new RefreshRequest(
                    targetPath,
                    RefreshSource.ManualDragDrop,
                    RefreshPriority.High);
                
                await _refreshCoordinator!.RequestRefreshAsync(targetRequest);
                
                // If move operation, also refresh source directory
                if (requestedEffect == DragDropEffect.Move && dragData.Value.FilePaths.Any())
                {
                    var sourcePath = Path.GetDirectoryName(dragData.Value.FilePaths.First());
                    if (!string.IsNullOrWhiteSpace(sourcePath))
                    {
                        var sourceRequest = new RefreshRequest(
                            sourcePath,
                            RefreshSource.ManualDragDrop,
                            RefreshPriority.High);
                        
                        await _refreshCoordinator.RequestRefreshAsync(sourceRequest);
                    }
                }
                
                // Ensure folder remains expanded after drop (if it was already expanded)
                if (targetViewModel != null && targetViewModel.IsDirectory && treeViewItem != null)
                {
                    // Wait briefly for refresh to complete, then re-find the viewModel
                    await Task.Delay(100);
                    
                    if (_viewModelCache.TryGetValue(targetPath, out var refreshedViewModel))
                    {
                        refreshedViewModel.IsExpanded = true;
                        
                        // Find and expand the TreeViewItem
                        var refreshedTreeViewItem = FindTreeViewItemForViewModel(refreshedViewModel);
                        if (refreshedTreeViewItem != null)
                        {
                            refreshedTreeViewItem.IsExpanded = true;
                        }
                    }
                }
                
                _logger?.LogInformation("Drag-drop operation completed: {Operation} {Count} items to {Target}", 
                    requestedEffect == DragDropEffect.Move ? "move" : "copy", 
                    dragData.Value.FilePaths.Count(), targetPath);
            }
            else
            {
                MessageBox.Show(result.ErrorMessage ?? "Operation failed", "Error", 
                    MessageBoxButton.OK, MessageBoxImage.Warning);
                e.Effects = System.Windows.DragDropEffects.None;
                e.Handled = true;
            }
        }
        catch (Exception ex)
        {
            _logger?.LogError(ex, "Error during drop operation");
            MessageBox.Show($"Error during drop operation: {ex.Message}", "Error", 
                MessageBoxButton.OK, MessageBoxImage.Error);
            e.Effects = System.Windows.DragDropEffects.None;
            e.Handled = true;
        }
    }

    private void FileTree_DragLeave(object sender, DragEventArgs e)
    {
        // Restore cursor only when drag leaves (not during DragOver)
        FileTree.Cursor = Cursors.Arrow;
        ClearDropTargetVisual();
    }

    /// <summary>
    /// Sets visual feedback for the drop target using attached property for smooth animations.
    /// Shows background highlight on folder row (Windows File Explorer style).
    /// </summary>
    private void SetDropTargetVisual(TreeViewItem item, bool isCopy)
    {
        // Clear previous target
        if (_currentDropTarget != null && _currentDropTarget != item)
        {
            ClearDropTargetVisual();
        }

        _currentDropTarget = item;

        // Use attached properties to trigger visual state change (animations handled in XAML)
        // Background highlight will show green for move, blue for copy
        DropTargetBehavior.SetIsDropTarget(item, true);
        DropTargetBehavior.SetIsCopyOperation(item, isCopy);
    }

    /// <summary>
    /// Clears visual feedback from the current drop target.
    /// </summary>
    private void ClearDropTargetVisual()
    {
        if (_currentDropTarget != null)
        {
            // Reset attached properties to trigger exit animation
            DropTargetBehavior.SetIsDropTarget(_currentDropTarget, false);
            DropTargetBehavior.SetIsCopyOperation(_currentDropTarget, false);
            _currentDropTarget = null;
        }
    }

    /// <summary>
    /// Finds a visual child element by name in the visual tree (cached for performance).
    /// </summary>
    private T? FindVisualChild<T>(DependencyObject parent, string childName) where T : DependencyObject
    {
        if (parent == null)
            return null;

        // Use cached helper method
        return VisualTreeHelperExtensions.FindVisualChild<T>(parent, childName);
    }

    // Selection methods are now handled by MultiSelectBehavior

    private async Task<string> GenerateUniquePathAsync(string originalPath)
    {
        if (_fileSystemService == null)
            return originalPath;

        if (!await _fileSystemService.ExistsAsync(originalPath))
            return originalPath;

        var directory = System.IO.Path.GetDirectoryName(originalPath) ?? string.Empty;
        var fileName = System.IO.Path.GetFileNameWithoutExtension(originalPath);
        var extension = System.IO.Path.GetExtension(originalPath);
        var isDirectory = await _fileSystemService.IsDirectoryAsync(originalPath);

        int counter = 1;
        string newPath;
        do
        {
            if (isDirectory)
            {
                newPath = System.IO.Path.Combine(directory, $"{fileName} ({counter})");
            }
            else
            {
                newPath = System.IO.Path.Combine(directory, $"{fileName} ({counter}){extension}");
            }
            counter++;
        } while (await _fileSystemService.ExistsAsync(newPath) && counter < 1000);

        return newPath;
    }

    #endregion
}

