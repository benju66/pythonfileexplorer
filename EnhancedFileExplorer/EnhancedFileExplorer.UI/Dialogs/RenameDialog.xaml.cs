using System.IO;
using System.Windows;
using System.Windows.Input;

namespace EnhancedFileExplorer.UI.Dialogs;

/// <summary>
/// Dialog for renaming files and folders.
/// </summary>
public partial class RenameDialog : Window
{
    private readonly string _originalPath;
    private readonly string _originalName;
    private readonly bool _isDirectory;

    public string? NewName { get; private set; }

    public RenameDialog(string path, bool isDirectory)
    {
        InitializeComponent();
        
        _originalPath = path ?? throw new ArgumentNullException(nameof(path));
        _originalName = Path.GetFileName(path);
        _isDirectory = isDirectory;
        
        Title = $"Rename {(isDirectory ? "Folder" : "File")}";
        NameTextBox.Text = _originalName;
        NameTextBox.SelectAll();
        NameTextBox.Focus();
    }

    private void NameTextBox_TextChanged(object sender, System.Windows.Controls.TextChangedEventArgs e)
    {
        ValidateInput();
    }

    private void NameTextBox_KeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Enter && OkButton.IsEnabled)
        {
            OkButton_Click(sender, e);
        }
    }

    private void ValidateInput()
    {
        var newName = NameTextBox.Text.Trim();
        var isValid = !string.IsNullOrWhiteSpace(newName) && 
                      newName != _originalName &&
                      IsValidFileName(newName);
        
        OkButton.IsEnabled = isValid;
        
        if (!isValid && !string.IsNullOrWhiteSpace(newName))
        {
            if (newName == _originalName)
            {
                NameTextBox.ToolTip = "Name must be different from the current name";
            }
            else if (!IsValidFileName(newName))
            {
                NameTextBox.ToolTip = "Invalid file name. Cannot contain: < > : \" / \\ | ? *";
            }
        }
        else
        {
            NameTextBox.ToolTip = null;
        }
    }

    private bool IsValidFileName(string fileName)
    {
        if (string.IsNullOrWhiteSpace(fileName))
            return false;

        // Check for invalid characters
        var invalidChars = Path.GetInvalidFileNameChars();
        if (fileName.IndexOfAny(invalidChars) >= 0)
            return false;

        // Check for reserved names (Windows)
        var reservedNames = new[] { "CON", "PRN", "AUX", "NUL", 
            "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
            "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9" };
        
        var nameWithoutExtension = Path.GetFileNameWithoutExtension(fileName).ToUpperInvariant();
        if (reservedNames.Contains(nameWithoutExtension))
            return false;

        return true;
    }

    private void OkButton_Click(object sender, RoutedEventArgs e)
    {
        NewName = NameTextBox.Text.Trim();
        DialogResult = true;
        Close();
    }

    private void CancelButton_Click(object sender, RoutedEventArgs e)
    {
        DialogResult = false;
        Close();
    }
}

