using System.Windows;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;

namespace EnhancedFileExplorer;

/// <summary>
/// Interaction logic for App.xaml
/// </summary>
public partial class App : Application
{
    private IServiceProvider? _serviceProvider;

    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

        try
        {
            // Configure dependency injection
            _serviceProvider = Bootstrapper.ConfigureServices();

            // Get logger
            var logger = _serviceProvider.GetRequiredService<ILogger<App>>();
            logger.LogInformation("Application starting...");

            // Create and show main window
            var mainWindow = new MainWindow(_serviceProvider);
            mainWindow.Show();
        }
        catch (Exception ex)
        {
            // Show error dialog if startup fails
            MessageBox.Show(
                $"Failed to start application:\n\n{ex.Message}\n\n{ex.StackTrace}",
                "Startup Error",
                MessageBoxButton.OK,
                MessageBoxImage.Error);
            
            // Log to debug output
            System.Diagnostics.Debug.WriteLine($"Startup error: {ex}");
            
            // Shutdown the application
            Shutdown();
        }
    }

    protected override void OnExit(ExitEventArgs e)
    {
        var logger = _serviceProvider?.GetService<ILogger<App>>();
        logger?.LogInformation("Application shutting down...");

        base.OnExit(e);
    }
}

