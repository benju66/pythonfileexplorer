using System.Windows;
using System.Windows.Controls;
using EnhancedFileExplorer.Core.Interfaces;
using EnhancedFileExplorer.Core.Models;
using EnhancedFileExplorer.Services.FileOperations.Commands;
using EnhancedFileExplorer.UI.Dialogs;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;

namespace EnhancedFileExplorer.UI.Services;

/// <summary>
/// Service for building WPF context menus from menu actions.
/// </summary>
public class ContextMenuBuilder
{
    private readonly IUndoRedoManager _undoRedoManager;
    private readonly IServiceProvider _serviceProvider;
    private readonly ILogger<ContextMenuBuilder> _logger;

    public ContextMenuBuilder(
        IUndoRedoManager undoRedoManager,
        IServiceProvider serviceProvider,
        ILogger<ContextMenuBuilder> logger)
    {
        _undoRedoManager = undoRedoManager ?? throw new ArgumentNullException(nameof(undoRedoManager));
        _serviceProvider = serviceProvider ?? throw new ArgumentNullException(nameof(serviceProvider));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    /// <summary>
    /// Builds a WPF ContextMenu from a collection of menu actions.
    /// </summary>
    public ContextMenu BuildMenu(IEnumerable<MenuAction> actions)
    {
        var contextMenu = new ContextMenu();

        foreach (var action in actions)
        {
            if (action.SeparatorBefore)
            {
                contextMenu.Items.Add(new Separator());
            }

            var menuItem = new MenuItem
            {
                Header = action.Label,
                Icon = action.Icon as System.Windows.Media.ImageSource,
                IsEnabled = action.IsEnabled,
                ToolTip = action.ToolTip ?? action.Label
            };

            // Create command when clicked
            menuItem.Click += async (s, e) =>
            {
                try
                {
                    // Special handling for rename - show dialog first
                    if (action.Label == "Rename" && action.AdditionalData != null)
                    {
                        var path = action.AdditionalData.GetValueOrDefault("Path") as string;
                        var isDirectory = action.AdditionalData.GetValueOrDefault("IsDirectory") as bool? ?? false;
                        
                        if (path != null)
                        {
                            var dialog = new RenameDialog(path, isDirectory);
                            dialog.Owner = Application.Current.MainWindow;
                            
                            if (dialog.ShowDialog() == true && dialog.NewName != null)
                            {
                                var fileOperationService = _serviceProvider.GetRequiredService<IFileOperationService>();
                                var command = new RenameCommand(fileOperationService, path, dialog.NewName);
                                await _undoRedoManager.ExecuteCommandAsync(command);
                            }
                            return;
                        }
                    }
                    
                    // Standard command execution
                    var standardCommand = action.CommandFactory();
                    await _undoRedoManager.ExecuteCommandAsync(standardCommand);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Error executing menu action: {Label}", action.Label);
                    MessageBox.Show(
                        $"Error executing {action.Label}: {ex.Message}",
                        "Error",
                        MessageBoxButton.OK,
                        MessageBoxImage.Error);
                }
            };

            contextMenu.Items.Add(menuItem);
        }

        return contextMenu;
    }
}

