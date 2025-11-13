# Enhanced File Explorer - C# Design Specification
## Core Features & Architecture Design

**Version:** 2.0  
**Date:** January 2025  
**Status:** Design Phase  
**Platform:** Windows (WPF + .NET 9)

---

## Executive Summary

This document provides detailed architectural design for core features that must be included in the C# implementation, with emphasis on industry-standard patterns, reliability, and maintainability. This supplements the base C# specification with concrete designs for:

- **Pinned Items System** (Core Feature)
- **Split View** (Core Feature)
- **Recent Items** (Core Feature)
- **Bookmarks** (Standard Feature)
- **Custom Metadata** (Standard Feature)
- **Fuzzy Search** (Standard Feature)

All designs follow SOLID principles, use proven patterns, and prioritize testability and maintainability.

---

## 1. Pinned Items System (Core Feature)

### 1.1 Architecture Overview

**Design Pattern:** Repository Pattern + Observer Pattern  
**Storage:** SQLite (primary) + JSON (backup/export)  
**Scope:** Application-wide (shared across windows)

### 1.2 Core Components

#### 1.2.1 Domain Model

```csharp
public class PinnedItem
{
    public string Id { get; set; }                    // GUID
    public string Path { get; set; }                 // Full file system path
    public string DisplayName { get; set; }           // Custom display name (optional)
    public PinnedItemType Type { get; set; }         // File, Folder, Favorite
    public int DisplayOrder { get; set; }            // Sort order
    public DateTime PinnedDate { get; set; }         // When it was pinned
    public DateTime LastAccessed { get; set; }       // Last access time
    public Dictionary<string, string> Metadata { get; set; }  // Custom metadata
    public bool IsFavorite { get; set; }            // Favorite flag
}

public enum PinnedItemType
{
    File,
    Folder,
    Favorite
}
```

#### 1.2.2 Repository Interface

```csharp
public interface IPinnedItemRepository
{
    Task<IEnumerable<PinnedItem>> GetAllAsync(CancellationToken cancellationToken = default);
    Task<IEnumerable<PinnedItem>> GetByTypeAsync(PinnedItemType type, CancellationToken cancellationToken = default);
    Task<PinnedItem?> GetByIdAsync(string id, CancellationToken cancellationToken = default);
    Task<PinnedItem?> GetByPathAsync(string path, CancellationToken cancellationToken = default);
    Task<PinnedItem> AddAsync(PinnedItem item, CancellationToken cancellationToken = default);
    Task UpdateAsync(PinnedItem item, CancellationToken cancellationToken = default);
    Task DeleteAsync(string id, CancellationToken cancellationToken = default);
    Task ReorderAsync(IEnumerable<string> orderedIds, CancellationToken cancellationToken = default);
    Task<bool> ExistsAsync(string path, CancellationToken cancellationToken = default);
}
```

**Design Rationale:**
- Async/await for non-blocking operations
- CancellationToken support for cancellation
- Nullable return types for clarity
- Separate reorder method for batch operations

#### 1.2.3 Service Layer

```csharp
public interface IPinnedItemService
{
    // Core operations
    Task<PinnedItem> PinItemAsync(string path, CancellationToken cancellationToken = default);
    Task UnpinItemAsync(string path, CancellationToken cancellationToken = default);
    Task<bool> IsPinnedAsync(string path, CancellationToken cancellationToken = default);
    
    // Favorites
    Task SetFavoriteAsync(string path, bool isFavorite, CancellationToken cancellationToken = default);
    Task<IEnumerable<PinnedItem>> GetFavoritesAsync(CancellationToken cancellationToken = default);
    
    // Reordering
    Task ReorderItemsAsync(IEnumerable<string> orderedPaths, CancellationToken cancellationToken = default);
    
    // Validation
    Task<ValidationResult> ValidatePathAsync(string path, CancellationToken cancellationToken = default);
    
    // Events
    event EventHandler<PinnedItemEventArgs> ItemPinned;
    event EventHandler<PinnedItemEventArgs> ItemUnpinned;
    event EventHandler<PinnedItemEventArgs> ItemUpdated;
    event EventHandler<PinnedItemsReorderedEventArgs> ItemsReordered;
}

public class PinnedItemService : IPinnedItemService
{
    private readonly IPinnedItemRepository _repository;
    private readonly IFileSystemService _fileSystemService;
    private readonly ILogger<PinnedItemService> _logger;
    
    public PinnedItemService(
        IPinnedItemRepository repository,
        IFileSystemService fileSystemService,
        ILogger<PinnedItemService> logger)
    {
        _repository = repository ?? throw new ArgumentNullException(nameof(repository));
        _fileSystemService = fileSystemService ?? throw new ArgumentNullException(nameof(fileSystemService));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }
    
    public async Task<PinnedItem> PinItemAsync(string path, CancellationToken cancellationToken = default)
    {
        // Validation
        var validation = await ValidatePathAsync(path, cancellationToken);
        if (!validation.IsValid)
        {
            throw new InvalidOperationException($"Cannot pin item: {validation.ErrorMessage}");
        }
        
        // Check if already pinned
        var existing = await _repository.GetByPathAsync(path, cancellationToken);
        if (existing != null)
        {
            _logger.LogInformation("Item already pinned: {Path}", path);
            return existing;
        }
        
        // Create new pinned item
        var item = new PinnedItem
        {
            Id = Guid.NewGuid().ToString(),
            Path = path,
            DisplayName = Path.GetFileName(path),
            Type = await _fileSystemService.IsDirectoryAsync(path, cancellationToken) 
                ? PinnedItemType.Folder 
                : PinnedItemType.File,
            DisplayOrder = await GetNextDisplayOrderAsync(cancellationToken),
            PinnedDate = DateTime.UtcNow,
            LastAccessed = DateTime.UtcNow,
            Metadata = new Dictionary<string, string>(),
            IsFavorite = false
        };
        
        var result = await _repository.AddAsync(item, cancellationToken);
        
        // Raise event
        ItemPinned?.Invoke(this, new PinnedItemEventArgs(result));
        
        _logger.LogInformation("Item pinned: {Path}", path);
        return result;
    }
    
    // Additional methods...
}
```

**Design Rationale:**
- Service layer encapsulates business logic
- Dependency injection for testability
- Event-driven architecture for UI updates
- Comprehensive logging
- Validation before operations

#### 1.2.4 SQLite Repository Implementation

```csharp
public class SqlitePinnedItemRepository : IPinnedItemRepository
{
    private readonly IDbConnectionFactory _connectionFactory;
    private readonly ILogger<SqlitePinnedItemRepository> _logger;
    
    public SqlitePinnedItemRepository(
        IDbConnectionFactory connectionFactory,
        ILogger<SqlitePinnedItemRepository> logger)
    {
        _connectionFactory = connectionFactory ?? throw new ArgumentNullException(nameof(connectionFactory));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }
    
    public async Task<IEnumerable<PinnedItem>> GetAllAsync(CancellationToken cancellationToken = default)
    {
        const string sql = @"
            SELECT Id, Path, DisplayName, Type, DisplayOrder, 
                   PinnedDate, LastAccessed, Metadata, IsFavorite
            FROM PinnedItems
            ORDER BY DisplayOrder ASC, PinnedDate DESC";
        
        using var connection = await _connectionFactory.CreateConnectionAsync(cancellationToken);
        return await connection.QueryAsync<PinnedItem>(sql, cancellationToken);
    }
    
    // Additional methods with proper error handling and transactions...
}
```

**Database Schema:**
```sql
CREATE TABLE PinnedItems (
    Id TEXT PRIMARY KEY,
    Path TEXT NOT NULL UNIQUE,
    DisplayName TEXT,
    Type INTEGER NOT NULL,
    DisplayOrder INTEGER NOT NULL,
    PinnedDate TEXT NOT NULL,
    LastAccessed TEXT NOT NULL,
    Metadata TEXT,  -- JSON
    IsFavorite INTEGER NOT NULL DEFAULT 0,
    CreatedAt TEXT NOT NULL,
    UpdatedAt TEXT NOT NULL
);

CREATE INDEX IX_PinnedItems_Path ON PinnedItems(Path);
CREATE INDEX IX_PinnedItems_Type ON PinnedItems(Type);
CREATE INDEX IX_PinnedItems_DisplayOrder ON PinnedItems(DisplayOrder);
CREATE INDEX IX_PinnedItems_IsFavorite ON PinnedItems(IsFavorite);
```

**Design Rationale:**
- Proper indexing for performance
- JSON column for flexible metadata
- Timestamps for audit trail
- Unique constraint on path

#### 1.2.5 ViewModel (MVVM)

```csharp
public class PinnedItemsViewModel : ViewModelBase
{
    private readonly IPinnedItemService _pinnedItemService;
    private readonly IEventAggregator _eventAggregator;
    private readonly ObservableCollection<PinnedItemViewModel> _items;
    
    public PinnedItemsViewModel(
        IPinnedItemService pinnedItemService,
        IEventAggregator eventAggregator)
    {
        _pinnedItemService = pinnedItemService ?? throw new ArgumentNullException(nameof(pinnedItemService));
        _eventAggregator = eventAggregator ?? throw new ArgumentNullException(nameof(eventAggregator));
        
        _items = new ObservableCollection<PinnedItemViewModel>();
        Items = new ReadOnlyObservableCollection<PinnedItemViewModel>(_items);
        
        // Commands
        PinItemCommand = new AsyncRelayCommand<string>(PinItemAsync);
        UnpinItemCommand = new AsyncRelayCommand<string>(UnpinItemAsync);
        NavigateToItemCommand = new RelayCommand<PinnedItemViewModel>(NavigateToItem);
        ReorderItemsCommand = new AsyncRelayCommand<IEnumerable<string>>(ReorderItemsAsync);
        
        // Subscribe to events
        _pinnedItemService.ItemPinned += OnItemPinned;
        _pinnedItemService.ItemUnpinned += OnItemUnpinned;
        
        // Load initial data
        LoadItemsAsync().ConfigureAwait(false);
    }
    
    public ReadOnlyObservableCollection<PinnedItemViewModel> Items { get; }
    
    public ICommand PinItemCommand { get; }
    public ICommand UnpinItemCommand { get; }
    public ICommand NavigateToItemCommand { get; }
    public ICommand ReorderItemsCommand { get; }
    
    private async Task PinItemAsync(string path)
    {
        try
        {
            await _pinnedItemService.PinItemAsync(path);
        }
        catch (Exception ex)
        {
            _eventAggregator.Publish(new ErrorMessageEvent(ex.Message));
        }
    }
    
    // Additional methods...
}
```

**Design Rationale:**
- MVVM pattern for testability
- ObservableCollection for UI binding
- Async commands for non-blocking operations
- Event-driven updates
- Error handling with user feedback

### 1.3 UI Component Design

#### 1.3.1 Panel Control

```csharp
public class PinnedItemsPanel : PanelBase
{
    public PinnedItemsPanel()
    {
        InitializeComponent();
    }
    
    protected override void OnViewModelChanged()
    {
        if (DataContext is PinnedItemsViewModel viewModel)
        {
            // Setup bindings
        }
    }
}
```

**XAML Structure:**
- TreeView for hierarchical display (Favorites section, Pinned Items section)
- Drag-and-drop support for reordering
- Context menu for actions
- Icons for file types

### 1.4 Integration Points

1. **File Tree Context Menu**
   - "Pin Item" action
   - "Unpin Item" action (if already pinned)
   - "Add to Favorites" action

2. **Toolbar**
   - Quick access button to toggle panel
   - Keyboard shortcut (Ctrl+P)

3. **Navigation**
   - Click on pinned item navigates to that location
   - Double-click opens in new tab

---

## 2. Split View (Core Feature)

### 2.1 Architecture Overview

**Design Pattern:** Strategy Pattern + Composite Pattern  
**Scope:** Per-tab or per-window

### 2.2 Core Components

#### 2.2.1 Split View Manager

```csharp
public interface ISplitViewManager
{
    bool IsSplitViewActive { get; }
    SplitOrientation Orientation { get; }
    double SplitRatio { get; set; }  // 0.0 to 1.0
    
    Task ActivateSplitViewAsync(SplitOrientation orientation, CancellationToken cancellationToken = default);
    Task DeactivateSplitViewAsync(CancellationToken cancellationToken = default);
    Task SwapViewsAsync(CancellationToken cancellationToken = default);
    Task SynchronizeNavigationAsync(bool enabled, CancellationToken cancellationToken = default);
    
    event EventHandler<SplitViewActivatedEventArgs> SplitViewActivated;
    event EventHandler<SplitViewDeactivatedEventArgs> SplitViewDeactivated;
}

public enum SplitOrientation
{
    Horizontal,  // Side by side
    Vertical     // Top and bottom
}
```

#### 2.2.2 Split View Container

```csharp
public class SplitViewContainer : Control
{
    public static readonly DependencyProperty LeftContentProperty =
        DependencyProperty.Register(nameof(LeftContent), typeof(object), typeof(SplitViewContainer));
    
    public static readonly DependencyProperty RightContentProperty =
        DependencyProperty.Register(nameof(RightContent), typeof(object), typeof(SplitViewContainer));
    
    public static readonly DependencyProperty OrientationProperty =
        DependencyProperty.Register(nameof(Orientation), typeof(Orientation), typeof(SplitViewContainer),
            new PropertyMetadata(Orientation.Horizontal));
    
    public static readonly DependencyProperty SplitRatioProperty =
        DependencyProperty.Register(nameof(SplitRatio), typeof(double), typeof(SplitViewContainer),
            new PropertyMetadata(0.5, OnSplitRatioChanged));
    
    public object LeftContent
    {
        get => GetValue(LeftContentProperty);
        set => SetValue(LeftContentProperty, value);
    }
    
    public object RightContent
    {
        get => GetValue(RightContentProperty);
        set => SetValue(RightContentProperty, value);
    }
    
    public Orientation Orientation
    {
        get => (Orientation)GetValue(OrientationProperty);
        set => SetValue(OrientationProperty, value);
    }
    
    public double SplitRatio
    {
        get => (double)GetValue(SplitRatioProperty);
        set => SetValue(SplitRatioProperty, value);
    }
    
    // Custom control implementation with GridSplitter
}
```

**Design Rationale:**
- Custom control for reusability
- Dependency properties for data binding
- GridSplitter for user-adjustable split
- Supports both orientations

#### 2.2.3 Split View Service

```csharp
public class SplitViewService : ISplitViewManager
{
    private readonly ITabManagerService _tabManagerService;
    private readonly IEventAggregator _eventAggregator;
    private readonly ILogger<SplitViewService> _logger;
    
    private bool _isActive;
    private SplitOrientation _orientation;
    private double _splitRatio = 0.5;
    private bool _synchronizeNavigation;
    
    public SplitViewService(
        ITabManagerService tabManagerService,
        IEventAggregator eventAggregator,
        ILogger<SplitViewService> logger)
    {
        _tabManagerService = tabManagerService ?? throw new ArgumentNullException(nameof(tabManagerService));
        _eventAggregator = eventAggregator ?? throw new ArgumentNullException(nameof(eventAggregator));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }
    
    public bool IsSplitViewActive => _isActive;
    public SplitOrientation Orientation => _orientation;
    public double SplitRatio
    {
        get => _splitRatio;
        set => _splitRatio = Math.Clamp(value, 0.1, 0.9);  // Constrain between 10% and 90%
    }
    
    public async Task ActivateSplitViewAsync(SplitOrientation orientation, CancellationToken cancellationToken = default)
    {
        if (_isActive)
        {
            _logger.LogWarning("Split view already active");
            return;
        }
        
        try
        {
            _orientation = orientation;
            _isActive = true;
            
            // Create second tab manager
            var secondTabManager = await _tabManagerService.CreateTabManagerAsync(cancellationToken);
            
            // Setup synchronization if enabled
            if (_synchronizeNavigation)
            {
                SetupNavigationSynchronization(secondTabManager);
            }
            
            // Raise event
            SplitViewActivated?.Invoke(this, new SplitViewActivatedEventArgs(orientation));
            
            _logger.LogInformation("Split view activated: {Orientation}", orientation);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to activate split view");
            throw;
        }
    }
    
    // Additional methods...
}
```

**Design Rationale:**
- Service layer for business logic
- Event-driven architecture
- Error handling and logging
- Navigation synchronization support

### 2.3 UI Integration

#### 2.3.1 Main Window Integration

```csharp
public class MainWindowViewModel : ViewModelBase
{
    private readonly ISplitViewManager _splitViewManager;
    
    public ICommand ToggleSplitViewCommand { get; }
    public ICommand SwapViewsCommand { get; }
    
    public bool IsSplitViewActive => _splitViewManager.IsSplitViewActive;
    
    private async Task ToggleSplitViewAsync()
    {
        if (_splitViewManager.IsSplitViewActive)
        {
            await _splitViewManager.DeactivateSplitViewAsync();
        }
        else
        {
            await _splitViewManager.ActivateSplitViewAsync(SplitOrientation.Horizontal);
        }
    }
}
```

#### 2.3.2 Context Menu Integration

- "Open in Split View" option for folders
- "Toggle Split View" in View menu
- Keyboard shortcut (Ctrl+\)

### 2.4 State Persistence

```csharp
public class SplitViewState
{
    public bool IsActive { get; set; }
    public SplitOrientation Orientation { get; set; }
    public double SplitRatio { get; set; }
    public bool SynchronizeNavigation { get; set; }
    public string LeftTabPath { get; set; }
    public string RightTabPath { get; set; }
}
```

**Storage:** Part of workspace/session state

---

## 3. Recent Items (Core Feature)

### 3.1 Architecture Overview

**Design Pattern:** Repository Pattern + LRU Cache  
**Storage:** SQLite with automatic cleanup  
**Scope:** Application-wide

### 3.2 Core Components

#### 3.2.1 Domain Model

```csharp
public class RecentItem
{
    public string Id { get; set; }
    public string Path { get; set; }
    public RecentItemType Type { get; set; }
    public DateTime LastAccessed { get; set; }
    public int AccessCount { get; set; }
    public string DisplayName { get; set; }
    public string? ThumbnailPath { get; set; }
}

public enum RecentItemType
{
    File,
    Folder
}
```

#### 3.2.2 Repository Interface

```csharp
public interface IRecentItemRepository
{
    Task<IEnumerable<RecentItem>> GetRecentItemsAsync(
        int count = 20, 
        RecentItemType? type = null,
        CancellationToken cancellationToken = default);
    
    Task AddOrUpdateAsync(string path, CancellationToken cancellationToken = default);
    Task ClearAsync(CancellationToken cancellationToken = default);
    Task CleanupOldItemsAsync(int daysToKeep = 30, CancellationToken cancellationToken = default);
    Task<bool> ExistsAsync(string path, CancellationToken cancellationToken = default);
}
```

#### 3.2.3 Service Layer

```csharp
public interface IRecentItemService
{
    Task RecordAccessAsync(string path, CancellationToken cancellationToken = default);
    Task<IEnumerable<RecentItem>> GetRecentFilesAsync(int count = 20, CancellationToken cancellationToken = default);
    Task<IEnumerable<RecentItem>> GetRecentFoldersAsync(int count = 20, CancellationToken cancellationToken = default);
    Task ClearRecentItemsAsync(CancellationToken cancellationToken = default);
    
    event EventHandler<RecentItemEventArgs> ItemAccessed;
}
```

**Design Rationale:**
- Automatic cleanup of old items
- Separate methods for files and folders
- Event-driven updates
- LRU-style ordering

### 3.3 Integration Points

1. **File Tree Navigation**
   - Record access when navigating to folder
   - Record access when opening file

2. **Recent Items Panel**
   - Display recent files and folders
   - Group by date (Today, Yesterday, This Week, etc.)
   - Click to navigate

3. **Jump List Integration**
   - Windows Jump List for quick access
   - Recent files in taskbar

---

## 4. Bookmarks (Standard Feature)

### 4.1 Architecture Overview

**Design Pattern:** Repository Pattern + Tree Structure  
**Storage:** SQLite with hierarchical support  
**Scope:** Application-wide

### 4.2 Core Components

#### 4.2.1 Domain Model

```csharp
public class Bookmark
{
    public string Id { get; set; }
    public string? ParentId { get; set; }  // For folders
    public string Name { get; set; }
    public string? Path { get; set; }      // Null for folders
    public BookmarkType Type { get; set; }
    public int DisplayOrder { get; set; }
    public DateTime CreatedDate { get; set; }
    public DateTime ModifiedDate { get; set; }
    public List<Bookmark> Children { get; set; } = new();
}

public enum BookmarkType
{
    Folder,  // Bookmark folder (container)
    File,    // File bookmark
    Link     // URL or custom link
}
```

#### 4.2.2 Repository Interface

```csharp
public interface IBookmarkRepository
{
    Task<IEnumerable<Bookmark>> GetRootBookmarksAsync(CancellationToken cancellationToken = default);
    Task<IEnumerable<Bookmark>> GetChildrenAsync(string parentId, CancellationToken cancellationToken = default);
    Task<Bookmark?> GetByIdAsync(string id, CancellationToken cancellationToken = default);
    Task<Bookmark> AddAsync(Bookmark bookmark, CancellationToken cancellationToken = default);
    Task UpdateAsync(Bookmark bookmark, CancellationToken cancellationToken = default);
    Task DeleteAsync(string id, CancellationToken cancellationToken = default);
    Task MoveAsync(string bookmarkId, string? newParentId, CancellationToken cancellationToken = default);
}
```

**Design Rationale:**
- Hierarchical structure for organization
- Support for bookmark folders
- Move operation for reorganization

### 4.3 Service Layer

```csharp
public interface IBookmarkService
{
    Task<Bookmark> CreateBookmarkAsync(string name, string path, string? parentFolderId = null, CancellationToken cancellationToken = default);
    Task<Bookmark> CreateBookmarkFolderAsync(string name, string? parentFolderId = null, CancellationToken cancellationToken = default);
    Task DeleteBookmarkAsync(string id, CancellationToken cancellationToken = default);
    Task MoveBookmarkAsync(string bookmarkId, string? newParentFolderId, CancellationToken cancellationToken = default);
    Task<IEnumerable<Bookmark>> GetBookmarkTreeAsync(CancellationToken cancellationToken = default);
    
    event EventHandler<BookmarkEventArgs> BookmarkCreated;
    event EventHandler<BookmarkEventArgs> BookmarkDeleted;
    event EventHandler<BookmarkMovedEventArgs> BookmarkMoved;
}
```

---

## 5. Custom Metadata (Standard Feature)

### 5.1 Architecture Overview

**Design Pattern:** Repository Pattern + Strategy Pattern  
**Storage:** SQLite with JSON for flexible properties  
**Scope:** Per-file/folder

### 5.2 Core Components

#### 5.2.1 Domain Model

```csharp
public class FileMetadata
{
    public string Path { get; set; }
    public string? Color { get; set; }           // Hex color for text
    public bool IsBold { get; set; }
    public List<string> Tags { get; set; } = new();
    public Dictionary<string, object> CustomProperties { get; set; } = new();
    public DateTime CreatedDate { get; set; }
    public DateTime ModifiedDate { get; set; }
}

public class MetadataProperty
{
    public string Key { get; set; }
    public MetadataPropertyType Type { get; set; }
    public object? Value { get; set; }
}

public enum MetadataPropertyType
{
    String,
    Number,
    Boolean,
    Date,
    Color
}
```

#### 5.2.2 Repository Interface

```csharp
public interface IFileMetadataRepository
{
    Task<FileMetadata?> GetMetadataAsync(string path, CancellationToken cancellationToken = default);
    Task SaveMetadataAsync(FileMetadata metadata, CancellationToken cancellationToken = default);
    Task DeleteMetadataAsync(string path, CancellationToken cancellationToken = default);
    Task<IEnumerable<FileMetadata>> GetByTagAsync(string tag, CancellationToken cancellationToken = default);
    Task<IEnumerable<FileMetadata>> GetByColorAsync(string color, CancellationToken cancellationToken = default);
    Task<bool> HasMetadataAsync(string path, CancellationToken cancellationToken = default);
}
```

#### 5.2.3 Service Layer

```csharp
public interface IFileMetadataService
{
    Task SetColorAsync(string path, string? color, CancellationToken cancellationToken = default);
    Task SetBoldAsync(string path, bool isBold, CancellationToken cancellationToken = default);
    Task AddTagAsync(string path, string tag, CancellationToken cancellationToken = default);
    Task RemoveTagAsync(string path, string tag, CancellationToken cancellationToken = default);
    Task SetCustomPropertyAsync(string path, string key, object value, CancellationToken cancellationToken = default);
    Task<FileMetadata> GetMetadataAsync(string path, CancellationToken cancellationToken = default);
    Task<IEnumerable<string>> SearchByTagAsync(string tag, CancellationToken cancellationToken = default);
    
    event EventHandler<MetadataChangedEventArgs> MetadataChanged;
}
```

### 5.3 Integration with File Tree

- Custom rendering in FileTreeView
- Context menu for metadata operations
- Color picker dialog
- Tag management UI

---

## 6. Fuzzy Search (Standard Feature)

### 6.1 Architecture Overview

**Design Pattern:** Strategy Pattern + Adapter Pattern  
**Storage:** In-memory cache for recent searches  
**Scope:** Per-search operation

### 6.2 Core Components

#### 6.2.1 Search Strategy Interface

```csharp
public interface ISearchStrategy
{
    Task<IEnumerable<SearchResult>> SearchAsync(
        string query,
        SearchOptions options,
        CancellationToken cancellationToken = default);
    
    bool CanHandle(string query, SearchOptions options);
    int Priority { get; }  // Lower = higher priority
}

public class FuzzySearchStrategy : ISearchStrategy
{
    private readonly IFileSystemService _fileSystemService;
    private readonly ILogger<FuzzySearchStrategy> _logger;
    
    public int Priority => 2;  // Fallback after exact search
    
    public bool CanHandle(string query, SearchOptions options)
    {
        return options.EnableFuzzySearch && !string.IsNullOrWhiteSpace(query);
    }
    
    public async Task<IEnumerable<SearchResult>> SearchAsync(
        string query,
        SearchOptions options,
        CancellationToken cancellationToken = default)
    {
        // Use Levenshtein distance or similar algorithm
        // Implement fuzzy matching logic
    }
}
```

#### 6.2.2 Search Service

```csharp
public interface ISearchService
{
    Task<SearchResults> SearchAsync(
        string query,
        SearchOptions options,
        CancellationToken cancellationToken = default);
    
    Task<IEnumerable<SearchResult>> SearchAsync(
        string query,
        string searchPath,
        SearchOptions options,
        CancellationToken cancellationToken = default);
}

public class SearchService : ISearchService
{
    private readonly IEnumerable<ISearchStrategy> _strategies;
    private readonly IWindowsSearchService _windowsSearchService;
    private readonly ILogger<SearchService> _logger;
    
    public SearchService(
        IEnumerable<ISearchStrategy> strategies,
        IWindowsSearchService windowsSearchService,
        ILogger<SearchService> logger)
    {
        _strategies = strategies.OrderBy(s => s.Priority);
        _windowsSearchService = windowsSearchService;
        _logger = logger;
    }
    
    public async Task<SearchResults> SearchAsync(
        string query,
        SearchOptions options,
        CancellationToken cancellationToken = default)
    {
        // Try Windows Search first (if indexed)
        if (options.UseWindowsSearch && await _windowsSearchService.IsIndexedAsync(options.SearchPath, cancellationToken))
        {
            return await _windowsSearchService.SearchAsync(query, options, cancellationToken);
        }
        
        // Fall back to strategy chain
        foreach (var strategy in _strategies)
        {
            if (strategy.CanHandle(query, options))
            {
                var results = await strategy.SearchAsync(query, options, cancellationToken);
                if (results.Any())
                {
                    return new SearchResults(results, strategy.GetType().Name);
                }
            }
        }
        
        return SearchResults.Empty;
    }
}
```

**Design Rationale:**
- Strategy pattern for different search types
- Chain of responsibility for fallback
- Windows Search integration as primary
- Fuzzy search as fallback

### 6.3 Search Options

```csharp
public class SearchOptions
{
    public string SearchPath { get; set; } = string.Empty;
    public bool IncludeSubdirectories { get; set; } = true;
    public bool SearchInFileNames { get; set; } = true;
    public bool SearchInFileContents { get; set; } = false;
    public bool CaseSensitive { get; set; } = false;
    public bool UseWindowsSearch { get; set; } = true;
    public bool EnableFuzzySearch { get; set; } = true;
    public int FuzzyThreshold { get; set; } = 60;  // 0-100
    public IEnumerable<string> FileExtensions { get; set; } = Enumerable.Empty<string>();
    public long? MinFileSize { get; set; }
    public long? MaxFileSize { get; set; }
    public DateTime? ModifiedAfter { get; set; }
    public DateTime? ModifiedBefore { get; set; }
}
```

---

## 7. Common Architectural Patterns

### 7.1 Repository Pattern Implementation

**Base Repository Interface:**
```csharp
public interface IRepository<TEntity, TKey> where TEntity : class
{
    Task<TEntity?> GetByIdAsync(TKey id, CancellationToken cancellationToken = default);
    Task<IEnumerable<TEntity>> GetAllAsync(CancellationToken cancellationToken = default);
    Task<TEntity> AddAsync(TEntity entity, CancellationToken cancellationToken = default);
    Task UpdateAsync(TEntity entity, CancellationToken cancellationToken = default);
    Task DeleteAsync(TKey id, CancellationToken cancellationToken = default);
    Task<bool> ExistsAsync(TKey id, CancellationToken cancellationToken = default);
}
```

**Unit of Work Pattern:**
```csharp
public interface IUnitOfWork : IDisposable
{
    IPinnedItemRepository PinnedItems { get; }
    IRecentItemRepository RecentItems { get; }
    IBookmarkRepository Bookmarks { get; }
    IFileMetadataRepository FileMetadata { get; }
    
    Task<int> SaveChangesAsync(CancellationToken cancellationToken = default);
    Task BeginTransactionAsync(CancellationToken cancellationToken = default);
    Task CommitTransactionAsync(CancellationToken cancellationToken = default);
    Task RollbackTransactionAsync(CancellationToken cancellationToken = default);
}
```

### 7.2 Event Aggregator Pattern

```csharp
public interface IEventAggregator
{
    void Subscribe<T>(Action<T> handler) where T : IEvent;
    void Unsubscribe<T>(Action<T> handler) where T : IEvent;
    void Publish<T>(T eventData) where T : IEvent;
}

public interface IEvent
{
    DateTime Timestamp { get; }
}

// Example events
public class PinnedItemEventArgs : EventArgs, IEvent
{
    public PinnedItem Item { get; }
    public DateTime Timestamp { get; } = DateTime.UtcNow;
    
    public PinnedItemEventArgs(PinnedItem item)
    {
        Item = item ?? throw new ArgumentNullException(nameof(item));
    }
}
```

### 7.3 Dependency Injection Configuration

```csharp
public static class ServiceCollectionExtensions
{
    public static IServiceCollection AddFileExplorerServices(this IServiceCollection services)
    {
        // Repositories
        services.AddScoped<IPinnedItemRepository, SqlitePinnedItemRepository>();
        services.AddScoped<IRecentItemRepository, SqliteRecentItemRepository>();
        services.AddScoped<IBookmarkRepository, SqliteBookmarkRepository>();
        services.AddScoped<IFileMetadataRepository, SqliteFileMetadataRepository>();
        
        // Services
        services.AddScoped<IPinnedItemService, PinnedItemService>();
        services.AddScoped<IRecentItemService, RecentItemService>();
        services.AddScoped<IBookmarkService, BookmarkService>();
        services.AddScoped<IFileMetadataService, FileMetadataService>();
        services.AddScoped<ISplitViewManager, SplitViewService>();
        services.AddScoped<ISearchService, SearchService>();
        
        // Search Strategies
        services.AddScoped<ISearchStrategy, ExactSearchStrategy>();
        services.AddScoped<ISearchStrategy, FuzzySearchStrategy>();
        services.AddScoped<ISearchStrategy, ContentSearchStrategy>();
        
        // Unit of Work
        services.AddScoped<IUnitOfWork, SqliteUnitOfWork>();
        
        // Event Aggregator
        services.AddSingleton<IEventAggregator, EventAggregator>();
        
        return services;
    }
}
```

### 7.4 Error Handling Strategy

```csharp
public class Result<T>
{
    public bool IsSuccess { get; private set; }
    public T? Value { get; private set; }
    public string? ErrorMessage { get; private set; }
    public Exception? Exception { get; private set; }
    
    public static Result<T> Success(T value) => new() { IsSuccess = true, Value = value };
    public static Result<T> Failure(string errorMessage, Exception? exception = null) => 
        new() { IsSuccess = false, ErrorMessage = errorMessage, Exception = exception };
}

// Usage in services
public async Task<Result<PinnedItem>> PinItemAsync(string path, CancellationToken cancellationToken = default)
{
    try
    {
        var validation = await ValidatePathAsync(path, cancellationToken);
        if (!validation.IsValid)
        {
            return Result<PinnedItem>.Failure(validation.ErrorMessage);
        }
        
        var item = await _repository.AddAsync(/* ... */);
        return Result<PinnedItem>.Success(item);
    }
    catch (Exception ex)
    {
        _logger.LogError(ex, "Failed to pin item: {Path}", path);
        return Result<PinnedItem>.Failure("Failed to pin item", ex);
    }
}
```

---

## 8. Database Schema Design

### 8.1 Complete Schema

```sql
-- Pinned Items
CREATE TABLE PinnedItems (
    Id TEXT PRIMARY KEY,
    Path TEXT NOT NULL UNIQUE,
    DisplayName TEXT,
    Type INTEGER NOT NULL,
    DisplayOrder INTEGER NOT NULL,
    PinnedDate TEXT NOT NULL,
    LastAccessed TEXT NOT NULL,
    Metadata TEXT,
    IsFavorite INTEGER NOT NULL DEFAULT 0,
    CreatedAt TEXT NOT NULL,
    UpdatedAt TEXT NOT NULL
);

-- Recent Items
CREATE TABLE RecentItems (
    Id TEXT PRIMARY KEY,
    Path TEXT NOT NULL,
    Type INTEGER NOT NULL,
    LastAccessed TEXT NOT NULL,
    AccessCount INTEGER NOT NULL DEFAULT 1,
    DisplayName TEXT,
    ThumbnailPath TEXT,
    CreatedAt TEXT NOT NULL
);

-- Bookmarks
CREATE TABLE Bookmarks (
    Id TEXT PRIMARY KEY,
    ParentId TEXT,
    Name TEXT NOT NULL,
    Path TEXT,
    Type INTEGER NOT NULL,
    DisplayOrder INTEGER NOT NULL,
    CreatedDate TEXT NOT NULL,
    ModifiedDate TEXT NOT NULL,
    FOREIGN KEY (ParentId) REFERENCES Bookmarks(Id) ON DELETE CASCADE
);

-- File Metadata
CREATE TABLE FileMetadata (
    Path TEXT PRIMARY KEY,
    Color TEXT,
    IsBold INTEGER NOT NULL DEFAULT 0,
    Tags TEXT,  -- JSON array
    CustomProperties TEXT,  -- JSON object
    CreatedDate TEXT NOT NULL,
    ModifiedDate TEXT NOT NULL
);

-- Tags (for quick lookup)
CREATE TABLE Tags (
    Id TEXT PRIMARY KEY,
    Name TEXT NOT NULL UNIQUE,
    Color TEXT,
    CreatedDate TEXT NOT NULL
);

-- File-Tag relationships
CREATE TABLE FileTags (
    FilePath TEXT NOT NULL,
    TagId TEXT NOT NULL,
    PRIMARY KEY (FilePath, TagId),
    FOREIGN KEY (FilePath) REFERENCES FileMetadata(Path) ON DELETE CASCADE,
    FOREIGN KEY (TagId) REFERENCES Tags(Id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX IX_PinnedItems_Path ON PinnedItems(Path);
CREATE INDEX IX_PinnedItems_Type ON PinnedItems(Type);
CREATE INDEX IX_PinnedItems_DisplayOrder ON PinnedItems(DisplayOrder);
CREATE INDEX IX_PinnedItems_IsFavorite ON PinnedItems(IsFavorite);

CREATE INDEX IX_RecentItems_Path ON RecentItems(Path);
CREATE INDEX IX_RecentItems_LastAccessed ON RecentItems(LastAccessed DESC);
CREATE INDEX IX_RecentItems_Type ON RecentItems(Type);

CREATE INDEX IX_Bookmarks_ParentId ON Bookmarks(ParentId);
CREATE INDEX IX_Bookmarks_DisplayOrder ON Bookmarks(DisplayOrder);

CREATE INDEX IX_FileMetadata_Color ON FileMetadata(Color);
CREATE INDEX IX_FileTags_FilePath ON FileTags(FilePath);
CREATE INDEX IX_FileTags_TagId ON FileTags(TagId);
```

### 8.2 Migration Strategy

```csharp
public interface IDatabaseMigrator
{
    Task MigrateAsync(CancellationToken cancellationToken = default);
    Task<bool> NeedsMigrationAsync(CancellationToken cancellationToken = default);
    int GetCurrentVersion();
    int GetTargetVersion();
}

public class SqliteDatabaseMigrator : IDatabaseMigrator
{
    private readonly IDbConnectionFactory _connectionFactory;
    private readonly ILogger<SqliteDatabaseMigrator> _logger;
    
    public async Task MigrateAsync(CancellationToken cancellationToken = default)
    {
        var currentVersion = GetCurrentVersion();
        var targetVersion = GetTargetVersion();
        
        for (int version = currentVersion + 1; version <= targetVersion; version++)
        {
            await ApplyMigrationAsync(version, cancellationToken);
        }
    }
    
    private async Task ApplyMigrationAsync(int version, CancellationToken cancellationToken)
    {
        // Apply migration scripts
        // Update version table
    }
}
```

---

## 9. Testing Strategy

### 9.1 Unit Testing

```csharp
[TestClass]
public class PinnedItemServiceTests
{
    private Mock<IPinnedItemRepository> _repositoryMock;
    private Mock<IFileSystemService> _fileSystemServiceMock;
    private Mock<ILogger<PinnedItemService>> _loggerMock;
    private PinnedItemService _service;
    
    [TestInitialize]
    public void Setup()
    {
        _repositoryMock = new Mock<IPinnedItemRepository>();
        _fileSystemServiceMock = new Mock<IFileSystemService>();
        _loggerMock = new Mock<ILogger<PinnedItemService>>();
        
        _service = new PinnedItemService(
            _repositoryMock.Object,
            _fileSystemServiceMock.Object,
            _loggerMock.Object);
    }
    
    [TestMethod]
    public async Task PinItemAsync_ValidPath_ReturnsPinnedItem()
    {
        // Arrange
        var path = @"C:\Test\Folder";
        _fileSystemServiceMock.Setup(x => x.IsDirectoryAsync(path, It.IsAny<CancellationToken>()))
            .ReturnsAsync(true);
        _repositoryMock.Setup(x => x.GetByPathAsync(path, It.IsAny<CancellationToken>()))
            .ReturnsAsync((PinnedItem?)null);
        
        // Act
        var result = await _service.PinItemAsync(path);
        
        // Assert
        Assert.IsNotNull(result);
        Assert.AreEqual(path, result.Path);
        _repositoryMock.Verify(x => x.AddAsync(It.IsAny<PinnedItem>(), It.IsAny<CancellationToken>()), Times.Once);
    }
}
```

### 9.2 Integration Testing

```csharp
[TestClass]
public class PinnedItemIntegrationTests
{
    private string _testDbPath;
    private IPinnedItemRepository _repository;
    
    [TestInitialize]
    public void Setup()
    {
        _testDbPath = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString() + ".db");
        // Initialize test database
        _repository = new SqlitePinnedItemRepository(/* ... */);
    }
    
    [TestMethod]
    public async Task AddAndRetrieve_WorksCorrectly()
    {
        // Test repository with real database
    }
    
    [TestCleanup]
    public void Cleanup()
    {
        if (File.Exists(_testDbPath))
        {
            File.Delete(_testDbPath);
        }
    }
}
```

---

## 10. Performance Considerations

### 10.1 Caching Strategy

```csharp
public interface ICacheService
{
    Task<T?> GetAsync<T>(string key, CancellationToken cancellationToken = default);
    Task SetAsync<T>(string key, T value, TimeSpan? expiration = null, CancellationToken cancellationToken = default);
    Task RemoveAsync(string key, CancellationToken cancellationToken = default);
    Task ClearAsync(CancellationToken cancellationToken = default);
}

public class MemoryCacheService : ICacheService
{
    private readonly IMemoryCache _memoryCache;
    private readonly ILogger<MemoryCacheService> _logger;
    
    // Implementation with LRU eviction
}
```

### 10.2 Background Processing

```csharp
public interface IBackgroundTaskService
{
    Task EnqueueTaskAsync(Func<CancellationToken, Task> task, CancellationToken cancellationToken = default);
    Task EnqueueTaskAsync<T>(Func<T, CancellationToken, Task> task, T parameter, CancellationToken cancellationToken = default);
}

// Usage for cleanup tasks
public class RecentItemCleanupService : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            await CleanupOldItemsAsync(stoppingToken);
            await Task.Delay(TimeSpan.FromHours(24), stoppingToken);  // Daily cleanup
        }
    }
}
```

---

## 11. Security Considerations

### 11.1 Path Validation

```csharp
public class PathValidator
{
    public ValidationResult ValidatePath(string path, PathValidationOptions options)
    {
        // Check for path traversal
        // Validate against allowed directories
        // Check file system permissions
        // Sanitize input
    }
}
```

### 11.2 SQL Injection Prevention

- Use parameterized queries
- Never concatenate user input into SQL
- Use ORM or query builder

### 11.3 Input Sanitization

```csharp
public static class InputSanitizer
{
    public static string SanitizeFileName(string fileName)
    {
        // Remove invalid characters
        // Prevent path traversal
        // Limit length
    }
    
    public static string SanitizePath(string path)
    {
        // Normalize path
        // Validate against whitelist
        // Prevent traversal
    }
}
```

---

## 12. Summary & Recommendations

### 12.1 Implementation Priority

1. **Phase 1: Core Infrastructure**
   - Repository pattern implementation
   - Database schema and migrations
   - Dependency injection setup
   - Event aggregator

2. **Phase 2: Core Features**
   - Pinned Items System
   - Split View
   - Recent Items

3. **Phase 3: Standard Features**
   - Bookmarks
   - Custom Metadata
   - Fuzzy Search

4. **Phase 4: Integration & Polish**
   - UI components
   - Performance optimization
   - Testing
   - Documentation

### 12.2 Key Design Decisions

✅ **Use Repository Pattern** - Testability and flexibility  
✅ **SQLite for Storage** - Performance and structure  
✅ **Event-Driven Architecture** - Decoupling and responsiveness  
✅ **Dependency Injection** - Testability and maintainability  
✅ **Async/Await Throughout** - Performance and responsiveness  
✅ **Comprehensive Error Handling** - Reliability  
✅ **Structured Logging** - Debugging and monitoring  

### 12.3 Best Practices Applied

- SOLID principles
- DRY (Don't Repeat Yourself)
- Separation of concerns
- Single Responsibility Principle
- Interface segregation
- Dependency inversion
- Test-driven development support
- Comprehensive error handling
- Structured logging

---

**End of Design Specification**

