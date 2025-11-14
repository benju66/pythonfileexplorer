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

    public event EventHandler<string>? PathSelected;
    public event EventHandler<string>? PathDoubleClicked;

    public FileTreeView()
    {
        InitializeComponent();
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
            
            Dispatcher.Invoke(() =>
            {
                FileTree.Items.Clear();
                
                // Show both files and directories, but directories will be expandable
                // Sort: directories first, then files, both alphabetically
                foreach (var item in items.OrderBy(i => i.IsDirectory ? 0 : 1).ThenBy(i => i.Name))
                {
                    var treeItem = CreateTreeViewItem(item);
                    FileTree.Items.Add(treeItem);
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

    private TreeViewItem CreateTreeViewItem(FileSystemItem item)
    {
        var treeItem = new TreeViewItem
        {
            Header = CreateItemHeader(item),
            Tag = item.Path,
            IsExpanded = false
        };

        // For directories, add a placeholder item so the expand arrow appears
        // This will be replaced with actual children when expanded
        if (item.IsDirectory)
        {
            // Add a placeholder to show the expand arrow
            var placeholder = new TreeViewItem { Header = "Loading...", IsEnabled = false };
            treeItem.Items.Add(placeholder);

            // Handle expansion - load children when expanded
            treeItem.Expanded += async (s, e) =>
            {
                var tvItem = s as TreeViewItem;
                if (tvItem != null)
                {
                    // Check if we need to load children (only if placeholder is still there)
                    if (tvItem.Items.Count == 1 && tvItem.Items[0] is TreeViewItem firstChild && 
                        firstChild.Header is string header && header == "Loading...")
                    {
                        await LoadDirectoryChildrenAsync(tvItem, item.Path);
                    }
                }
            };
        }

        return treeItem;
    }

    private StackPanel CreateItemHeader(FileSystemItem item)
    {
        var panel = new StackPanel { Orientation = Orientation.Horizontal };
        
        // Icon
        var icon = new Image
        {
            Width = 16,
            Height = 16,
            Margin = new Thickness(0, 0, 5, 0)
        };
        
        // Load icon asynchronously
        LoadIconAsync(item, icon);
        panel.Children.Add(icon);

        // Name
        var textBlock = new TextBlock { Text = item.Name };
        panel.Children.Add(textBlock);

        return panel;
    }

    private async void LoadIconAsync(FileSystemItem item, Image icon)
    {
        if (_iconService == null)
            return;

        try
        {
            var iconSource = await _iconService.GetIconAsync(item.Path, item.IsDirectory);
            if (iconSource is ImageSource imageSource)
            {
                Dispatcher.Invoke(() =>
                {
                    icon.Source = imageSource;
                });
            }
        }
        catch (Exception ex)
        {
            _logger?.LogWarning(ex, "Failed to load icon for: {Path}", item.Path);
        }
    }

    private async Task LoadDirectoryChildrenAsync(TreeViewItem parentItem, string path)
    {
        if (_fileSystemService == null)
            return;

        try
        {
            // Show loading indicator
            Dispatcher.Invoke(() =>
            {
                parentItem.Items.Clear();
                var loadingItem = new TreeViewItem { Header = "Loading...", IsEnabled = false };
                parentItem.Items.Add(loadingItem);
            });

            var items = await _fileSystemService.GetItemsAsync(path);
            
            Dispatcher.Invoke(() =>
            {
                parentItem.Items.Clear();
                
                // Show both directories and files in the tree
                // Sort: directories first, then files, both alphabetically
                var sortedItems = items.OrderBy(i => i.IsDirectory ? 0 : 1).ThenBy(i => i.Name);
                
                foreach (var item in sortedItems)
                {
                    var treeItem = CreateTreeViewItem(item);
                    parentItem.Items.Add(treeItem);
                }

                // If no children, add a message
                if (!sortedItems.Any())
                {
                    var emptyItem = new TreeViewItem { Header = "(empty)", IsEnabled = false };
                    parentItem.Items.Add(emptyItem);
                }
            });

            _logger?.LogInformation("Loaded directory children: {Path} ({Count} items)", path, items.Count());
        }
        catch (Exception ex)
        {
            _logger?.LogError(ex, "Error loading directory children: {Path}", path);
            
            Dispatcher.Invoke(() =>
            {
                parentItem.Items.Clear();
                var errorItem = new TreeViewItem { Header = $"Error: {ex.Message}", IsEnabled = false };
                parentItem.Items.Add(errorItem);
            });
        }
    }

    private void FileTree_SelectedItemChanged(object sender, RoutedPropertyChangedEventArgs<object> e)
    {
        if (FileTree.SelectedItem is TreeViewItem item && item.Tag is string path)
        {
            PathSelected?.Invoke(this, path);
        }
    }

    private void FileTree_MouseDoubleClick(object sender, MouseButtonEventArgs e)
    {
        if (FileTree.SelectedItem is TreeViewItem item && item.Tag is string path)
        {
            // Check if it's a directory synchronously first
            if (System.IO.Directory.Exists(path))
            {
                PathDoubleClicked?.Invoke(this, path);
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

            if (treeViewItem != null && treeViewItem.Tag is string path)
            {
                selectedPath = path;
                parentPath = System.IO.Path.GetDirectoryName(path);
                
                if (_fileSystemService != null)
                {
                    isDirectory = await _fileSystemService.IsDirectoryAsync(path);
                    isFile = !isDirectory;
                }
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

