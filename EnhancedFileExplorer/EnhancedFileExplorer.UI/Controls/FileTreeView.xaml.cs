using System.Collections.ObjectModel;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using EnhancedFileExplorer.Core.Interfaces;
using EnhancedFileExplorer.Core.Models;
using EnhancedFileExplorer.Services.ContextMenus;
using EnhancedFileExplorer.Services.FileOperations.Commands;
using EnhancedFileExplorer.UI.Services;
using Microsoft.Extensions.Logging;

namespace EnhancedFileExplorer.UI.Controls;

/// <summary>
/// Custom TreeView control for displaying file system.
/// </summary>
public partial class FileTreeView : UserControl
{
    private IFileSystemService? _fileSystemService;
    private ILogger<FileTreeView>? _logger;
    private IContextMenuProvider? _contextMenuProvider;
    private ContextMenuBuilder? _contextMenuBuilder;
    private IIconService? _iconService;
    private IDragDropHandler? _dragDropHandler;
    private IUndoRedoManager? _undoRedoManager;
    private string _currentPath = string.Empty;
    private ObservableCollection<FileTreeViewModel> _rootItems;
    private readonly Dictionary<string, FileTreeViewModel> _viewModelCache;
    private int _sortColumn = 0; // 0=Name, 1=Size, 2=Modified, 3=Created
    private bool _sortAscending = true;
    
    // Drag state
    private Point _dragStartPoint;
    private bool _isDragging;
    private TreeViewItem? _currentDropTarget; // Track current drop target for visual feedback

    public event EventHandler<string>? PathSelected;
    public event EventHandler<string>? PathDoubleClicked;

    public FileTreeView()
    {
        InitializeComponent();
        _rootItems = new ObservableCollection<FileTreeViewModel>();
        _viewModelCache = new Dictionary<string, FileTreeViewModel>(StringComparer.OrdinalIgnoreCase);
        FileTree.ItemsSource = _rootItems;
        
        // Handle item expanded event for lazy loading
        FileTree.AddHandler(TreeViewItem.ExpandedEvent, new RoutedEventHandler(OnItemExpanded));
        
        // Handle column header clicks for sorting
        if (ColumnHeaders != null)
        {
            ColumnHeaders.ColumnHeaderClicked += OnColumnHeaderClicked;
        }
    }

    public void Initialize(
        IFileSystemService fileSystemService, 
        ILogger<FileTreeView>? logger = null,
        IContextMenuProvider? contextMenuProvider = null,
        ContextMenuBuilder? contextMenuBuilder = null,
        IIconService? iconService = null,
        IDragDropHandler? dragDropHandler = null,
        IUndoRedoManager? undoRedoManager = null)
    {
        _fileSystemService = fileSystemService ?? throw new ArgumentNullException(nameof(fileSystemService));
        _logger = logger;
        _contextMenuProvider = contextMenuProvider;
        _contextMenuBuilder = contextMenuBuilder;
        _iconService = iconService;
        _dragDropHandler = dragDropHandler;
        _undoRedoManager = undoRedoManager;
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
            // Preserve expansion state before clearing
            var expandedPaths = GetExpandedPaths();
            
            var items = await _fileSystemService.GetItemsAsync(path);
            
            await Dispatcher.InvokeAsync(() =>
            {
                _rootItems.Clear();
                _viewModelCache.Clear();
                
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
    /// Preserves expansion state.
    /// </summary>
    public async Task RefreshDirectoryAsync(string path)
    {
        if (string.IsNullOrWhiteSpace(path) || _fileSystemService == null)
            return;

        try
        {
            // Preserve expansion state
            var expandedPaths = GetExpandedPaths();
            
            var items = await _fileSystemService.GetItemsAsync(path);
            
            await Dispatcher.InvokeAsync(() =>
            {
                // Find the ViewModel for this path
                if (_viewModelCache.TryGetValue(path, out var viewModel))
                {
                    // Update children
                    viewModel.Children.Clear();
                    
                    var sortedItems = SortItems(items);
                    foreach (var item in sortedItems)
                    {
                        var childViewModel = CreateViewModel(item);
                        viewModel.Children.Add(childViewModel);
                        _viewModelCache[item.Path] = childViewModel;
                    }
                    
                    viewModel.IsLoaded = true;
                }
                else if (string.Equals(path, _currentPath, StringComparison.OrdinalIgnoreCase))
                {
                    // Refresh root items
                    _rootItems.Clear();
                    var sortedItems = SortItems(items);
                    foreach (var item in sortedItems)
                    {
                        var childViewModel = CreateViewModel(item);
                        _rootItems.Add(childViewModel);
                        _viewModelCache[item.Path] = childViewModel;
                    }
                }
                
                // Restore expansion state
                RestoreExpandedPaths(expandedPaths);
            });

            _logger?.LogInformation("Refreshed directory: {Path} ({Count} items)", path, items.Count());
        }
        catch (Exception ex)
        {
            _logger?.LogError(ex, "Error refreshing directory: {Path}", path);
        }
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
    /// Finds the TreeViewItem for a given ViewModel.
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
        if (e.NewValue is FileTreeViewModel viewModel)
        {
            PathSelected?.Invoke(this, viewModel.Path);
        }
    }

    private void FileTree_MouseDoubleClick(object sender, MouseButtonEventArgs e)
    {
        if (FileTree.SelectedItem is FileTreeViewModel viewModel && viewModel.IsDirectory)
        {
            PathDoubleClicked?.Invoke(this, viewModel.Path);
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

            if (treeViewItem?.DataContext is FileTreeViewModel viewModel)
            {
                selectedPath = viewModel.Path;
                parentPath = System.IO.Path.GetDirectoryName(viewModel.Path);
                isDirectory = viewModel.IsDirectory;
                isFile = !isDirectory;
            }

            var context = new ContextMenuContext
            {
                SelectedPath = selectedPath,
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

    private void FileTree_PreviewMouseLeftButtonDown(object sender, MouseButtonEventArgs e)
    {
        // Store the starting point for drag detection
        _dragStartPoint = e.GetPosition(null);
        _isDragging = false;
    }

    private void FileTree_PreviewMouseMove(object sender, MouseEventArgs e)
    {
        if (_dragDropHandler == null || e.LeftButton != MouseButtonState.Pressed)
            return;

        // Check if mouse has moved enough to start a drag
        var currentPosition = e.GetPosition(null);
        var deltaX = Math.Abs(currentPosition.X - _dragStartPoint.X);
        var deltaY = Math.Abs(currentPosition.Y - _dragStartPoint.Y);

        if (!_isDragging && 
            (deltaX > SystemParameters.MinimumHorizontalDragDistance || 
             deltaY > SystemParameters.MinimumVerticalDragDistance))
        {
            StartDragOperation(e);
        }
    }

    private void StartDragOperation(MouseEventArgs e)
    {
        if (_dragDropHandler == null)
            return;

        // Get selected items
        var selectedItems = GetSelectedViewModels();
        if (selectedItems.Count == 0)
            return;

        var sourcePaths = selectedItems.Select(vm => vm.Path).Where(p => !string.IsNullOrEmpty(p)).ToArray();
        if (sourcePaths.Length == 0)
            return;

        // Validate drag
        var context = new DragDropContext
        {
            SourcePaths = sourcePaths,
            RequestedEffect = DragDropEffect.Move
        };

        var canDrag = _dragDropHandler.CanDrag(context);
        if (!canDrag.IsValid)
            return;

        _isDragging = true;

        // Create drag data
        var dataObject = _dragDropHandler.CreateDragData(sourcePaths, isCut: false);
        if (dataObject is not System.Windows.IDataObject wpfDataObject)
            return;

        // Determine allowed effects
        var allowedEffects = System.Windows.DragDropEffects.Move | System.Windows.DragDropEffects.Copy;

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
            _isDragging = false;
        }
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

        // Find drop target
        var hitTestResult = VisualTreeHelper.HitTest(FileTree, e.GetPosition(FileTree));
        var treeViewItem = FindParent<TreeViewItem>(hitTestResult.VisualHit);
        
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
            FileTree.Cursor = Cursors.No;
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
            FileTree.Cursor = requestedEffect == DragDropEffect.Copy ? Cursors.Cross : Cursors.Hand;
            
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
            FileTree.Cursor = Cursors.No;
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

        // Find drop target
        var hitTestResult = VisualTreeHelper.HitTest(FileTree, e.GetPosition(FileTree));
        var treeViewItem = FindParent<TreeViewItem>(hitTestResult.VisualHit);
        
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
                
                // Refresh only the target directory to show new items, preserving expansion state
                await RefreshDirectoryAsync(targetPath);
                
                // Ensure folder remains expanded after drop (if it was already expanded)
                if (targetViewModel != null && targetViewModel.IsDirectory && treeViewItem != null)
                {
                    // Re-find the viewModel after refresh (it might be a new instance)
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
        FileTree.Cursor = Cursors.Arrow;
        ClearDropTargetVisual();
    }

    /// <summary>
    /// Sets visual feedback for the drop target (highlight border/background).
    /// </summary>
    private void SetDropTargetVisual(TreeViewItem item, bool isCopy)
    {
        // Clear previous target
        if (_currentDropTarget != null && _currentDropTarget != item)
        {
            ClearDropTargetVisual();
        }

        _currentDropTarget = item;

        // Find the Border element (PART_Header wrapper) in the template
        var border = FindVisualChild<Border>(item, "Bd");
        if (border != null)
        {
            // Set visual feedback: light blue background for valid drop target
            // Use a slightly different shade for copy vs move
            var brush = new SolidColorBrush(isCopy 
                ? Color.FromArgb(0x80, 0x00, 0x7A, 0xCC) // Light blue for copy
                : Color.FromArgb(0x80, 0x00, 0x96, 0x00)); // Light green for move
            
            border.Background = brush;
            border.BorderBrush = new SolidColorBrush(isCopy 
                ? Color.FromRgb(0x00, 0x7A, 0xCC) 
                : Color.FromRgb(0x00, 0x96, 0x00));
            border.BorderThickness = new Thickness(2);
        }
    }

    /// <summary>
    /// Clears visual feedback from the current drop target.
    /// </summary>
    private void ClearDropTargetVisual()
    {
        if (_currentDropTarget != null)
        {
            var border = FindVisualChild<Border>(_currentDropTarget, "Bd");
            if (border != null)
            {
                // Reset to default (transparent or selection-based)
                border.Background = Brushes.Transparent;
                border.BorderBrush = Brushes.Transparent;
                border.BorderThickness = new Thickness(0);
            }
            _currentDropTarget = null;
        }
    }

    /// <summary>
    /// Finds a visual child element by name in the visual tree.
    /// </summary>
    private static T? FindVisualChild<T>(DependencyObject parent, string childName) where T : DependencyObject
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

    private List<FileTreeViewModel> GetSelectedViewModels()
    {
        var selected = new List<FileTreeViewModel>();
        
        // Get selected item from TreeView
        if (FileTree.SelectedItem is FileTreeViewModel viewModel)
        {
            selected.Add(viewModel);
        }

        // TODO: Support multi-selection in future phases
        // For now, single selection only

        return selected;
    }

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

