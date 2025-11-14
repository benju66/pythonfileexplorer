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

        if (context.SelectedPath != null)
        {
            // Item-specific actions
            var isDirectory = await _fileSystemService.IsDirectoryAsync(context.SelectedPath);
            var fileName = System.IO.Path.GetFileName(context.SelectedPath);

            // Rename action - special handling with dialog
            actions.Add(new MenuAction
            {
                Label = "Rename",
                CommandFactory = () => CreateRenameCommand(context.SelectedPath), // Placeholder - dialog handles actual command
                ToolTip = $"Rename {fileName}",
                AdditionalData = new Dictionary<string, object>
                {
                    { "Path", context.SelectedPath },
                    { "IsDirectory", isDirectory }
                }
            });

            actions.Add(new MenuAction { SeparatorBefore = true });

            // Delete action
            actions.Add(new MenuAction
            {
                Label = "Delete",
                CommandFactory = () => new DeleteCommand(_fileOperationService, context.SelectedPath, isDirectory),
                ToolTip = $"Delete {fileName}"
            });

            // Copy and Move actions
            actions.Add(new MenuAction { SeparatorBefore = true });
            actions.Add(new MenuAction
            {
                Label = "Copy",
                CommandFactory = () => CreateCopyCommand(context.SelectedPath),
                ToolTip = $"Copy {fileName}"
            });

            actions.Add(new MenuAction
            {
                Label = "Cut",
                CommandFactory = () => CreateCutCommand(context.SelectedPath),
                ToolTip = $"Cut {fileName}"
            });

            // Paste action if clipboard has files
            if (_clipboardService.HasFiles())
            {
                actions.Add(new MenuAction { SeparatorBefore = true });
                actions.Add(new MenuAction
                {
                    Label = "Paste",
                    CommandFactory = () => CreatePasteCommand(context.SelectedPath, isDirectory),
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

