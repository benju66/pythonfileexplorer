using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Globalization;
using System.Runtime.CompilerServices;
using System.Windows.Media;
using EnhancedFileExplorer.Core.Models;

namespace EnhancedFileExplorer.UI.Controls;

/// <summary>
/// View model for file tree items to support virtualization and data binding.
/// </summary>
public class FileTreeViewModel : INotifyPropertyChanged
{
    private bool _isExpanded;
    private bool _isSelected;
    private bool _isLoaded;
    private ImageSource? _icon;
    private ObservableCollection<FileTreeViewModel>? _children;
    private string? _formattedSize;
    private string? _formattedModifiedDate;
    private string? _formattedCreatedDate;

    public FileSystemItem Item { get; }
    public string Name => Item.Name;
    public string Path => Item.Path;
    public bool IsDirectory => Item.IsDirectory;
    
    // Raw values for sorting
    public long Size => Item.Size;
    public DateTime ModifiedDate => Item.ModifiedDate;
    public DateTime CreatedDate => Item.CreatedDate;

    public ImageSource? Icon
    {
        get => _icon;
        set
        {
            if (_icon != value)
            {
                _icon = value;
                OnPropertyChanged();
            }
        }
    }

    public string FormattedSize
    {
        get
        {
            if (_formattedSize == null)
            {
                _formattedSize = IsDirectory ? "—" : FormatFileSize(Item.Size);
            }
            return _formattedSize;
        }
    }

    public string FormattedModifiedDate
    {
        get
        {
            if (_formattedModifiedDate == null)
            {
                _formattedModifiedDate = Item.ModifiedDate == default 
                    ? "—" 
                    : Item.ModifiedDate.ToString("g", CultureInfo.CurrentCulture);
            }
            return _formattedModifiedDate;
        }
    }

    public string FormattedCreatedDate
    {
        get
        {
            if (_formattedCreatedDate == null)
            {
                _formattedCreatedDate = Item.CreatedDate == default 
                    ? "—" 
                    : Item.CreatedDate.ToString("g", CultureInfo.CurrentCulture);
            }
            return _formattedCreatedDate;
        }
    }

    private static string FormatFileSize(long bytes)
    {
        string[] sizes = { "B", "KB", "MB", "GB", "TB" };
        if (bytes == 0) return "0 B";
        
        int order = 0;
        double size = bytes;
        while (size >= 1024 && order < sizes.Length - 1)
        {
            order++;
            size /= 1024;
        }

        return $"{size:0.##} {sizes[order]}";
    }

    public ObservableCollection<FileTreeViewModel> Children
    {
        get
        {
            if (_children == null)
            {
                _children = new ObservableCollection<FileTreeViewModel>();
            }
            return _children;
        }
    }

    public bool IsExpanded
    {
        get => _isExpanded;
        set
        {
            if (_isExpanded != value)
            {
                _isExpanded = value;
                OnPropertyChanged();
            }
        }
    }

    public bool IsSelected
    {
        get => _isSelected;
        set
        {
            if (_isSelected != value)
            {
                _isSelected = value;
                OnPropertyChanged();
            }
        }
    }

    public bool IsLoaded
    {
        get => _isLoaded;
        set
        {
            if (_isLoaded != value)
            {
                _isLoaded = value;
                OnPropertyChanged();
            }
        }
    }

    public FileTreeViewModel(FileSystemItem item)
    {
        Item = item ?? throw new ArgumentNullException(nameof(item));
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    protected virtual void OnPropertyChanged([CallerMemberName] string? propertyName = null)
    {
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
    }
}

