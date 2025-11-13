using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using EnhancedFileExplorer.Core.Interfaces;
using EnhancedFileExplorer.Infrastructure.FileSystem;
using EnhancedFileExplorer.Infrastructure.Events;
using EnhancedFileExplorer.Services.FileOperations;
using EnhancedFileExplorer.Services.UndoRedo;
using EnhancedFileExplorer.Services.Navigation;
using EnhancedFileExplorer.Services.TabManagement;

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
        services.AddScoped<IFileSystemService, FileSystemService>();

        // Services
        services.AddScoped<IFileOperationService, FileOperationService>();
        services.AddSingleton<IUndoRedoManager, UndoRedoManager>(); // Singleton for app-wide undo/redo
        services.AddScoped<INavigationService, NavigationService>(); // Scoped per tab
        services.AddSingleton<ITabManagerService, TabManagerService>(); // Singleton for tab management

        return services.BuildServiceProvider();
    }
}

