using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using EnhancedFileExplorer.Core.Interfaces;
using EnhancedFileExplorer.Infrastructure.FileSystem;
using EnhancedFileExplorer.Infrastructure.Events;
using EnhancedFileExplorer.Infrastructure.Icon;
using EnhancedFileExplorer.Infrastructure.FileSystemWatcher;
using EnhancedFileExplorer.Services.FileOperations;
using EnhancedFileExplorer.Services.UndoRedo;
using EnhancedFileExplorer.Services.Navigation;
using EnhancedFileExplorer.Services.TabManagement;
using EnhancedFileExplorer.Services.ContextMenus;
using EnhancedFileExplorer.UI.Services;

namespace EnhancedFileExplorer;

/// <summary>
/// Bootstrapper for dependency injection and service configuration.
/// </summary>
public static class Bootstrapper
{
    /// <summary>
    /// Configures and returns the service provider.
    /// </summary>
    public static IServiceProvider ConfigureServices()
    {
        var services = new ServiceCollection();

        // Logging
        services.AddLogging(builder =>
        {
            builder.AddDebug();
            builder.SetMinimumLevel(LogLevel.Information);
        });

        // Infrastructure
        services.AddSingleton<IEventAggregator, EventAggregator>();
        services.AddSingleton<IClipboardService, ClipboardService>();
        services.AddSingleton<IIconService, IconService>();
        services.AddSingleton<IFileSystemWatcherService, FileSystemWatcherService>();
        services.AddScoped<IFileSystemService, FileSystemService>();
        
        // Register drag-drop handler
        services.AddScoped<IDragDropHandler, FileTreeDragDropHandler>();

        // Services
        services.AddScoped<IFileOperationService, FileOperationService>();
        services.AddSingleton<IUndoRedoManager, UndoRedoManager>(); // Singleton for app-wide undo/redo
        services.AddScoped<INavigationService, NavigationService>(); // Scoped per tab
        services.AddSingleton<ITabManagerService, TabManagerService>(); // Singleton for tab management

        // Context Menu Services
        // Note: ContextMenuBuilder needs IServiceProvider, so we register it after building the provider
        // We'll use a factory to create it with the service provider
        services.AddSingleton<ContextMenuBuilder>(sp => 
            new ContextMenuBuilder(
                sp.GetRequiredService<IUndoRedoManager>(),
                sp,
                sp.GetRequiredService<ILogger<ContextMenuBuilder>>()));
        services.AddTransient<IContextMenuProvider, FileTreeContextMenuProvider>();

        var serviceProvider = services.BuildServiceProvider();
        return serviceProvider;
    }
}

