using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using EnhancedFileExplorer.UI.Controls;

namespace EnhancedFileExplorer.UI.Adorners;

/// <summary>
/// Drag adorner for file tree drag operations with badge count display.
/// </summary>
public class FileTreeDragAdorner : DragAdornerBase
{
    private const double BadgeSize = 20;
    private const double BadgeMargin = 4;
    private const double IconSize = 32;

    public FileTreeDragAdorner(UIElement adornedElement, IReadOnlyList<FileTreeViewModel> items)
        : base(adornedElement, CreateVisual(items))
    {
    }

    private static UIElement CreateVisual(IReadOnlyList<FileTreeViewModel> items)
    {
        if (items == null || items.Count == 0)
            throw new ArgumentException("Items cannot be null or empty", nameof(items));

        var grid = new Grid();
        
        // Get icon from first item
        var firstItem = items[0];
        var icon = GetItemIcon(firstItem);
        
        // Create icon image
        var image = new Image
        {
            Source = icon,
            Width = IconSize,
            Height = IconSize,
            Stretch = Stretch.Uniform
        };
        
        grid.Children.Add(image);
        
        // Add badge with count if more than one item
        if (items.Count > 1)
        {
            var badge = CreateBadge(items.Count);
            Grid.SetColumn(badge, 0);
            Grid.SetRow(badge, 0);
            grid.Children.Add(badge);
        }
        
        return grid;
    }

    private static UIElement CreateBadge(int count)
    {
        var border = new Border
        {
            Background = new SolidColorBrush(Color.FromRgb(0, 120, 215)), // Blue badge
            CornerRadius = new CornerRadius(BadgeSize / 2),
            Width = BadgeSize,
            Height = BadgeSize,
            HorizontalAlignment = HorizontalAlignment.Right,
            VerticalAlignment = VerticalAlignment.Top,
            Margin = new Thickness(0, -BadgeMargin, -BadgeMargin, 0)
        };
        
        var textBlock = new TextBlock
        {
            Text = count > 99 ? "99+" : count.ToString(),
            Foreground = Brushes.White,
            FontSize = 10,
            FontWeight = FontWeights.Bold,
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
            TextAlignment = TextAlignment.Center
        };
        
        border.Child = textBlock;
        return border;
    }

    private static ImageSource? GetItemIcon(FileTreeViewModel item)
    {
        // Try to get icon from item's Icon property
        if (item.Icon != null)
            return item.Icon;
        
        // Fallback: create a simple colored rectangle based on item type
        var drawingVisual = new DrawingVisual();
        using (var drawingContext = drawingVisual.RenderOpen())
        {
            var color = item.IsDirectory 
                ? Color.FromRgb(75, 139, 203) // Folder blue
                : Color.FromRgb(200, 200, 200); // Light gray for files
            
            drawingContext.DrawRectangle(
                new SolidColorBrush(color),
                new Pen(new SolidColorBrush(color), 1),
                new Rect(0, 0, IconSize, IconSize));
        }
        
        var bitmap = new RenderTargetBitmap(
            (int)IconSize, (int)IconSize,
            96, 96, PixelFormats.Pbgra32);
        bitmap.Render(drawingVisual);
        
        return bitmap;
    }
}

