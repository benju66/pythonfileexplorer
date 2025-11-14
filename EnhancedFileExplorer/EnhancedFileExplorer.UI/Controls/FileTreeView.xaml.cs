using System.Collections.ObjectModel;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using EnhancedFileExplorer.Core.Interfaces;
using EnhancedFileExplorer.Core.Models;
using EnhancedFileExplorer.Services.ContextMenus;
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
    private string _currentPath = string.Empty;
    private ObservableCollection<FileTreeViewModel> _rootItems;
    private readonly Dictionary<string, FileTreeViewModel> _viewModelCache;

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
    }

    public void Initialize(
        IFileSystemService fileSystemService, 
        ILogger<FileTreeView>? logger = null,
        IContextMenuProvider? contextMenuProvider = null,
        ContextMenuBuilder? contextMenuBuilder = null,
        IIconService? iconService = null)
    {
        _fileSystemService = fileSystemService ?? throw new ArgumentNullException(nameof(fileSystemService));
        _logger = logger;
        _contextMenuProvider = contextMenuProvider;
        _contextMenuBuilder = contextMenuBuilder;
        _iconService = iconService;
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
            var items = await _fileSystemService.GetItemsAsync(path);
            
            await Dispatcher.InvokeAsync(() =>
            {
                _rootItems.Clear();
                _viewModelCache.Clear();
                
                // Show both files and directories, but directories will be expandable
                // Sort: directories first, then files, both alphabetically
                foreach (var item in items.OrderBy(i => i.IsDirectory ? 0 : 1).ThenBy(i => i.Name))
                {
                    var viewModel = CreateViewModel(item);
                    _rootItems.Add(viewModel);
                    _viewModelCache[item.Path] = viewModel;
                }
            });

            _logger?.LogInformation("Loaded directory: {Path} ({Count} items)", path, items.Count());
        }
        catch (Exception ex)
        {
            _logger?.LogError(ex, "Error loading directory: {Path}", path);
            MessageBox.Show($"Error loading directory: {ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
        }
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
                var sortedItems = items.OrderBy(i => i.IsDirectory ? 0 : 1).ThenBy(i => i.Name);
                
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
}

