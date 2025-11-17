using EnhancedFileExplorer.Core.Interfaces;
using EnhancedFileExplorer.Core.Models;
using EnhancedFileExplorer.Services.FileOperations.Commands;
using Microsoft.Extensions.Logging;

namespace EnhancedFileExplorer.Services.ContextMenus;

/// <summary>
/// Context menu provider for the file tree view.
/// </summary>
public class FileTreeContextMenuProvider : IContextMenuProvider
{
    private readonly IFileOperationService _fileOperationService;
    private readonly IFileSystemService _fileSystemService;
    private readonly IUndoRedoManager _undoRedoManager;
    private readonly IClipboardService _clipboardService;
    private readonly ILogger<FileTreeContextMenuProvider> _logger;

    public FileTreeContextMenuProvider(
        IFileOperationService fileOperationService,
        IFileSystemService fileSystemService,
        IUndoRedoManager undoRedoManager,
        IClipboardService clipboardService,
        ILogger<FileTreeContextMenuProvider> logger)
    {
        _fileOperationService = fileOperationService ?? throw new ArgumentNullException(nameof(fileOperationService));
        _fileSystemService = fileSystemService ?? throw new ArgumentNullException(nameof(fileSystemService));
        _undoRedoManager = undoRedoManager ?? throw new ArgumentNullException(nameof(undoRedoManager));
        _clipboardService = clipboardService ?? throw new ArgumentNullException(nameof(clipboardService));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    public async Task<IEnumerable<MenuAction>> GetMenuActionsAsync(ContextMenuContext context)
    {
        var actions = new List<MenuAction>();

        // Check for multi-select first
        var selectedPaths = context.SelectedPaths?.ToList() ?? new List<string>();
        if (selectedPaths.Count == 0 && context.SelectedPath != null)
        {
            selectedPaths.Add(context.SelectedPath);
        }

        if (selectedPaths.Count > 0)
        {
            // Multi-select or single-select actions
            var isMultiSelect = selectedPaths.Count > 1;
            var firstPath = selectedPaths.First();
            var isDirectory = await _fileSystemService.IsDirectoryAsync(firstPath);
            var displayName = isMultiSelect 
                ? $"{selectedPaths.Count} items" 
                : System.IO.Path.GetFileName(firstPath);

            // Rename action - only for single selection
            if (!isMultiSelect)
            {
                actions.Add(new MenuAction
                {
                    Label = "Rename",
                    CommandFactory = () => CreateRenameCommand(firstPath), // Placeholder - dialog handles actual command
                    ToolTip = $"Rename {displayName}",
                    AdditionalData = new Dictionary<string, object>
                    {
                        { "Path", firstPath },
                        { "IsDirectory", isDirectory }
                    }
                });

                actions.Add(new MenuAction { SeparatorBefore = true });
            }

            // Delete action - supports multi-select
            actions.Add(new MenuAction
            {
                Label = "Delete",
                CommandFactory = () => CreateBulkDeleteCommand(selectedPaths),
                ToolTip = isMultiSelect ? $"Delete {selectedPaths.Count} items" : $"Delete {displayName}"
            });

            // Copy and Cut actions - support multi-select
            actions.Add(new MenuAction { SeparatorBefore = true });
            actions.Add(new MenuAction
            {
                Label = "Copy",
                CommandFactory = () => CreateBulkCopyCommand(selectedPaths),
                ToolTip = isMultiSelect ? $"Copy {selectedPaths.Count} items" : $"Copy {displayName}"
            });

            actions.Add(new MenuAction
            {
                Label = "Cut",
                CommandFactory = () => CreateBulkCutCommand(selectedPaths),
                ToolTip = isMultiSelect ? $"Cut {selectedPaths.Count} items" : $"Cut {displayName}"
            });

            // Paste action if clipboard has files
            if (_clipboardService.HasFiles())
            {
                actions.Add(new MenuAction { SeparatorBefore = true });
                actions.Add(new MenuAction
                {
                    Label = "Paste",
                    CommandFactory = () => CreatePasteCommand(firstPath, isDirectory),
                    ToolTip = "Paste items from clipboard"
                });
            }

            // TODO: Add Pin/Unpin when IPinnedItemService is available
            // if (_pinnedItemService != null)
            // {
            //     actions.Add(new MenuAction { SeparatorBefore = true });
            //     actions.Add(new MenuAction
            //     {
            //         Label = "Pin Item",
            //         CommandFactory = () => new PinItemCommand(_pinnedItemService, context.SelectedPath)
            //     });
            // }
        }
        else if (context.ParentPath != null)
        {
            // Empty space actions (create new)
            actions.Add(new MenuAction
            {
                Label = "New File",
                CommandFactory = () => CreateNewFileCommand(context.ParentPath),
                ToolTip = "Create a new file"
            });

            actions.Add(new MenuAction
            {
                Label = "New Folder",
                CommandFactory = () => CreateNewFolderCommand(context.ParentPath),
                ToolTip = "Create a new folder"
            });

            // Paste action if clipboard has files
            if (_clipboardService.HasFiles())
            {
                actions.Add(new MenuAction { SeparatorBefore = true });
                actions.Add(new MenuAction
                {
                    Label = "Paste",
                    CommandFactory = () => CreatePasteCommand(context.ParentPath, true),
                    ToolTip = "Paste items from clipboard"
                });
            }
        }

        return actions;
    }

    private ICommand CreateRenameCommand(string path)
    {
        // This will be handled by showing a dialog before creating the command
        // The actual command creation happens in the UI layer after dialog returns
        // This is a placeholder - the actual implementation requires UI interaction
        var fileName = System.IO.Path.GetFileName(path);
        var newName = $"{fileName}_renamed";
        return new RenameCommand(_fileOperationService, path, newName);
    }

    private ICommand CreateCopyCommand(string path)
    {
        return new CopyCommand(_clipboardService, path);
    }

    private ICommand CreateCutCommand(string path)
    {
        return new CutCommand(_clipboardService, path);
    }
    
    /// <summary>
    /// Creates a command to copy multiple files/folders.
    /// </summary>
    private ICommand CreateBulkCopyCommand(IEnumerable<string> paths)
    {
        // For now, execute multiple copy commands sequentially
        // TODO: Consider creating a BulkCopyCommand for better undo/redo support
        var commandList = paths.Select(path => (ICommand)new CopyCommand(_clipboardService, path)).ToList();
        return new BulkOperationCommand(commandList, _undoRedoManager);
    }
    
    /// <summary>
    /// Creates a command to cut multiple files/folders.
    /// </summary>
    private ICommand CreateBulkCutCommand(IEnumerable<string> paths)
    {
        // For now, execute multiple cut commands sequentially
        // TODO: Consider creating a BulkCutCommand for better undo/redo support
        var commandList = paths.Select(path => (ICommand)new CutCommand(_clipboardService, path)).ToList();
        return new BulkOperationCommand(commandList, _undoRedoManager);
    }
    
    /// <summary>
    /// Creates a command to delete multiple files/folders.
    /// Note: This method needs to be synchronous for CommandFactory, so we check
    /// directory status synchronously using System.IO.
    /// </summary>
    private ICommand CreateBulkDeleteCommand(IEnumerable<string> paths)
    {
        var commandList = new List<ICommand>();
        foreach (var path in paths)
        {
            // Check if path is a directory synchronously
            var isDirectory = System.IO.Directory.Exists(path) && 
                             !System.IO.File.Exists(path);
            commandList.Add(new DeleteCommand(_fileOperationService, path, isDirectory));
        }
        return new BulkOperationCommand(commandList, _undoRedoManager);
    }

    private ICommand CreatePasteCommand(string destinationPath, bool isDirectory)
    {
        // If destination is a directory, use it directly; otherwise use its parent
        var targetPath = isDirectory ? destinationPath : System.IO.Path.GetDirectoryName(destinationPath) ?? destinationPath;
        return new PasteCommand(_fileOperationService, _clipboardService, _fileSystemService, targetPath);
    }

    private ICommand CreateNewFileCommand(string parentPath)
    {
        var defaultName = "NewFile.txt";
        var counter = 1;
        var fullPath = System.IO.Path.Combine(parentPath, defaultName);
        
        // Find unique name
        while (System.IO.File.Exists(fullPath))
        {
            defaultName = $"NewFile ({counter}).txt";
            fullPath = System.IO.Path.Combine(parentPath, defaultName);
            counter++;
        }

        return new CreateFileCommand(_fileOperationService, parentPath, defaultName);
    }

    private ICommand CreateNewFolderCommand(string parentPath)
    {
        var defaultName = "New Folder";
        var counter = 1;
        var fullPath = System.IO.Path.Combine(parentPath, defaultName);
        
        // Find unique name
        while (System.IO.Directory.Exists(fullPath))
        {
            defaultName = $"New Folder ({counter})";
            fullPath = System.IO.Path.Combine(parentPath, defaultName);
            counter++;
        }

        return new CreateFolderCommand(_fileOperationService, parentPath, defaultName);
    }
}

