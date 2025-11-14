using System.Collections.ObjectModel;
using System.ComponentModel;
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

    public FileSystemItem Item { get; }
    public string Name => Item.Name;
    public string Path => Item.Path;
    public bool IsDirectory => Item.IsDirectory;

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

