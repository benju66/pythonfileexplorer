using System.Windows;
using System.Windows.Controls;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using EnhancedFileExplorer.Core.Interfaces;
using EnhancedFileExplorer.Core.Events;
using EnhancedFileExplorer.Services.TabManagement;
using EnhancedFileExplorer.Services.ContextMenus;
using EnhancedFileExplorer.UI.Services;
using EnhancedFileExplorer.UI.Controls;

namespace EnhancedFileExplorer;

/// <summary>
/// Interaction logic for MainWindow.xaml
/// </summary>
public partial class MainWindow : Window
{
    private readonly IServiceProvider _serviceProvider;
    private readonly ILogger<MainWindow> _logger;
        private readonly ITabManagerService _tabManagerService;
        private readonly IUndoRedoManager _undoRedoManager;
        private readonly IFileSystemService _fileSystemService;
        private readonly IFileSystemWatcherService _fileSystemWatcherService;
        private readonly IRefreshCoordinator _refreshCoordinator;

    public MainWindow(IServiceProvider serviceProvider)
    {
        _serviceProvider = serviceProvider ?? throw new ArgumentNullException(nameof(serviceProvider));
        _logger = serviceProvider.GetRequiredService<ILogger<MainWindow>>();
            _tabManagerService = serviceProvider.GetRequiredService<ITabManagerService>();
            _undoRedoManager = serviceProvider.GetRequiredService<IUndoRedoManager>();
            _fileSystemService = serviceProvider.GetRequiredService<IFileSystemService>();
            _fileSystemWatcherService = serviceProvider.GetRequiredService<IFileSystemWatcherService>();
            _refreshCoordinator = serviceProvider.GetRequiredService<IRefreshCoordinator>();

        InitializeComponent();

        // Subscribe to events
        // Navigation events will be handled per-tab
        _undoRedoManager.StateChanged += OnUndoRedoStateChanged;
        _undoRedoManager.FileOperationCompleted += OnFileOperationCompleted;
        _tabManagerService.ActiveTabChanged += OnActiveTabChanged;
        _tabManagerService.TabCreated += OnTabCreated;
        _tabManagerService.TabClosed += OnTabClosed;
        
        // Subscribe to file system watcher events
        _fileSystemWatcherService.Created += OnFileSystemChanged;
        _fileSystemWatcherService.Deleted += OnFileSystemChanged;
        _fileSystemWatcherService.Renamed += OnFileSystemRenamed;
        _fileSystemWatcherService.Changed += OnFileSystemChanged;
        
        // Start watching the initial directory when a tab is created
        _tabManagerService.TabCreated += (s, e) =>
        {
            if (e.Tab.CurrentPath != null)
            {
                StartWatchingDirectory(e.Tab.CurrentPath);
            }
        };
        
        // Stop watching when a tab is closed
        _tabManagerService.TabClosed += (s, e) =>
        {
            if (e.Tab.CurrentPath != null)
            {
                StopWatchingDirectory(e.Tab.CurrentPath);
            }
        };
        
        // Update watcher when active tab changes
        _tabManagerService.ActiveTabChanged += (s, e) =>
        {
            if (e.PreviousTab?.CurrentPath != null)
            {
                StopWatchingDirectory(e.PreviousTab.CurrentPath);
            }
            if (e.CurrentTab?.CurrentPath != null)
            {
                StartWatchingDirectory(e.CurrentTab.CurrentPath);
            }
        };

        // Create initial tab
        Loaded += async (s, e) =>
        {
            try
            {
                await _tabManagerService.CreateTabAsync(
                    Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments));
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error creating initial tab");
                MessageBox.Show(
                    $"Error creating initial tab: {ex.Message}",
                    "Error",
                    MessageBoxButton.OK,
                    MessageBoxImage.Warning);
            }
        };
    }

    private void OnNavigationChanged(object? sender, NavigationEventArgs e)
    {
        // This will be handled per-tab via TabManagerService
    }

    private void OnUndoRedoStateChanged(object? sender, UndoRedoStateChangedEventArgs e)
    {
        Dispatcher.Invoke(() =>
        {
            UndoButton.IsEnabled = e.CanUndo;
            RedoButton.IsEnabled = e.CanRedo;
        });
    }

    private void OnActiveTabChanged(object? sender, TabChangedEventArgs e)
    {
        Dispatcher.Invoke(() =>
        {
            if (e.CurrentTab != null)
            {
                AddressBar.Text = e.CurrentTab.CurrentPath ?? string.Empty;
                UpdateNavigationButtons();
                
                // Update FileTreeView in active tab
                if (MainTabControl.SelectedItem is TabItem tabItem)
                {
                    if (tabItem.Content is FileTreeView fileTreeView && e.CurrentTab.CurrentPath != null)
                    {
                        fileTreeView.CurrentPath = e.CurrentTab.CurrentPath;
                    }
                }
                
                // Subscribe to navigation changes for this tab
                var navService = _tabManagerService.GetNavigationServiceForTab(e.CurrentTab.Id);
                if (navService != null)
                {
                    navService.NavigationChanged += OnTabNavigationChanged;
                }
            }
            
            // Unsubscribe from previous tab's navigation
            if (e.PreviousTab != null)
            {
                var prevNavService = _tabManagerService.GetNavigationServiceForTab(e.PreviousTab.Id);
                if (prevNavService != null)
                {
                    prevNavService.NavigationChanged -= OnTabNavigationChanged;
                }
            }
        });
    }
    
    private void OnTabNavigationChanged(object? sender, NavigationEventArgs e)
    {
        Dispatcher.Invoke(() =>
        {
            AddressBar.Text = e.Path;
            UpdateNavigationButtons();
            
            // Update FileTreeView
            if (MainTabControl.SelectedItem is TabItem tabItem && tabItem.Content is FileTreeView fileTreeView)
            {
                fileTreeView.CurrentPath = e.Path;
            }
        });
    }

    private void OnTabCreated(object? sender, TabEventArgs e)
    {
        Dispatcher.Invoke(() =>
        {
            var tabItem = new TabItem
            {
                Header = e.Tab.Title,
                Tag = e.Tab.Id,
                Content = CreateTabContent(e.Tab)
            };

            MainTabControl.Items.Add(tabItem);
            MainTabControl.SelectedItem = tabItem;
        });
    }

    private void OnTabClosed(object? sender, TabEventArgs e)
    {
        Dispatcher.Invoke(() =>
        {
            for (int i = MainTabControl.Items.Count - 1; i >= 0; i--)
            {
                if (MainTabControl.Items[i] is TabItem tabItem && tabItem.Tag?.ToString() == e.Tab.Id)
                {
                    MainTabControl.Items.RemoveAt(i);
                    break;
                }
            }
        });
    }

    private UIElement CreateTabContent(TabInfo tab)
    {
        var fileTreeView = new FileTreeView();
        fileTreeView.Initialize(
            _fileSystemService,
            _serviceProvider.GetService<ILogger<FileTreeView>>(),
            _serviceProvider.GetRequiredService<IContextMenuProvider>(),
            _serviceProvider.GetRequiredService<ContextMenuBuilder>(),
            _serviceProvider.GetService<IIconService>(),
            _serviceProvider.GetService<IDragDropHandler>(),
            _undoRedoManager,
            _refreshCoordinator);
        
        fileTreeView.PathDoubleClicked += async (s, path) =>
        {
            try
            {
                var isDirectory = await _fileSystemService.IsDirectoryAsync(path);
                if (isDirectory)
                {
                    await _tabManagerService.NavigateTabAsync(tab.Id, path);
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error navigating to path: {Path}", path);
            }
        };

        // Load initial path
        if (!string.IsNullOrEmpty(tab.CurrentPath))
        {
            fileTreeView.CurrentPath = tab.CurrentPath;
        }

        return fileTreeView;
    }

    private void UpdateNavigationButtons()
    {
        var activeTab = _tabManagerService.GetActiveTab();
        if (activeTab != null)
        {
            var navService = _tabManagerService.GetNavigationServiceForTab(activeTab.Id);
            if (navService != null)
            {
                BackButton.IsEnabled = navService.CanGoBack;
                ForwardButton.IsEnabled = navService.CanGoForward;
                return;
            }
        }
        
        BackButton.IsEnabled = false;
        ForwardButton.IsEnabled = false;
    }

    private async void UpButton_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var activeTab = _tabManagerService.GetActiveTab();
            if (activeTab != null)
            {
                var parentPath = await _fileSystemService.GetParentDirectoryAsync(activeTab.CurrentPath ?? string.Empty);
                if (!string.IsNullOrEmpty(parentPath))
                {
                    await _tabManagerService.NavigateTabAsync(activeTab.Id, parentPath);
                }
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error navigating up");
            MessageBox.Show($"Error navigating up: {ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private async void BackButton_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var activeTab = _tabManagerService.GetActiveTab();
            if (activeTab != null)
            {
                var navService = _tabManagerService.GetNavigationServiceForTab(activeTab.Id);
                if (navService != null)
                {
                    await navService.NavigateBackAsync();
                }
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error navigating back");
            MessageBox.Show($"Error navigating back: {ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private async void ForwardButton_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var activeTab = _tabManagerService.GetActiveTab();
            if (activeTab != null)
            {
                var navService = _tabManagerService.GetNavigationServiceForTab(activeTab.Id);
                if (navService != null)
                {
                    await navService.NavigateForwardAsync();
                }
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error navigating forward");
            MessageBox.Show($"Error navigating forward: {ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private async void RefreshButton_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var activeTab = _tabManagerService.GetActiveTab();
            if (activeTab?.CurrentPath != null)
            {
                // Use refresh coordinator for refresh button (High priority, immediate)
                var request = new RefreshRequest(
                    activeTab.CurrentPath,
                    RefreshSource.UserRefresh,
                    RefreshPriority.High);
                
                await _refreshCoordinator.RequestRefreshAsync(request);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error refreshing");
            MessageBox.Show($"Error refreshing: {ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private async void UndoButton_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            await _undoRedoManager.UndoAsync();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error undoing");
            MessageBox.Show($"Error undoing: {ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private async void RedoButton_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            await _undoRedoManager.RedoAsync();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error redoing");
            MessageBox.Show($"Error redoing: {ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private void AddressBar_KeyDown(object sender, System.Windows.Input.KeyEventArgs e)
    {
        if (e.Key == System.Windows.Input.Key.Enter)
        {
            NavigateToAddressBarPath();
        }
    }

    private async void NavigateToAddressBarPath()
    {
        var path = AddressBar.Text.Trim();
        if (string.IsNullOrWhiteSpace(path))
            return;

        try
        {
            var activeTab = _tabManagerService.GetActiveTab();
            if (activeTab != null)
            {
                await _tabManagerService.NavigateTabAsync(activeTab.Id, path);
            }
            else
            {
                await _tabManagerService.CreateTabAsync(path);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error navigating to path: {Path}", path);
            MessageBox.Show($"Error navigating to path: {ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private async void NewTabButton_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            await _tabManagerService.CreateTabAsync();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error creating new tab");
            MessageBox.Show($"Error creating new tab: {ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private async void MainTabControl_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (MainTabControl.SelectedItem is TabItem tabItem && tabItem.Tag is string tabId)
        {
            try
            {
                await _tabManagerService.ActivateTabAsync(tabId);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error activating tab");
            }
        }
    }

    private void OnFileOperationCompleted(object? sender, FileOperationCompletedEventArgs e)
    {
        if (!e.IsSuccess)
            return;

        // Use refresh coordinator for file operation completed events
        if (!string.IsNullOrWhiteSpace(e.ParentPath))
        {
            var request = new RefreshRequest(
                e.ParentPath,
                RefreshSource.FileOperationCompleted,
                RefreshPriority.Normal);
            
            _refreshCoordinator.RequestRefreshAsync(request);
        }
    }

    private void OnFileSystemChanged(object? sender, FileSystemChangedEventArgs e)
    {
        // Use refresh coordinator for FileSystemWatcher events
        if (!string.IsNullOrWhiteSpace(e.FullPath))
        {
            var directoryPath = System.IO.Path.GetDirectoryName(e.FullPath);
            if (!string.IsNullOrWhiteSpace(directoryPath))
            {
                var request = new RefreshRequest(
                    directoryPath,
                    RefreshSource.FileSystemWatcher,
                    RefreshPriority.Low);
                
                _refreshCoordinator.RequestRefreshAsync(request);
            }
        }
    }

    private void OnFileSystemRenamed(object? sender, FileSystemRenamedEventArgs e)
    {
        // Use refresh coordinator for rename operations
        if (!string.IsNullOrWhiteSpace(e.FullPath))
        {
            var directoryPath = System.IO.Path.GetDirectoryName(e.FullPath);
            if (!string.IsNullOrWhiteSpace(directoryPath))
            {
                var request = new RefreshRequest(
                    directoryPath,
                    RefreshSource.FileSystemWatcher,
                    RefreshPriority.Low);
                
                _refreshCoordinator.RequestRefreshAsync(request);
            }
        }
    }

    private void StartWatchingDirectory(string path)
    {
        try
        {
            _fileSystemWatcherService.WatchDirectory(path, includeSubdirectories: false);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error starting file system watcher for: {Path}", path);
        }
    }

    private void StopWatchingDirectory(string path)
    {
        try
        {
            _fileSystemWatcherService.UnwatchDirectory(path);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error stopping file system watcher for: {Path}", path);
        }
    }
}

