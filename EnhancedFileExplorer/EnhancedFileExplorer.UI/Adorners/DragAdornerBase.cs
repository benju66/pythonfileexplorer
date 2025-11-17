using System.Windows;
using System.Windows.Documents;
using System.Windows.Media;

namespace EnhancedFileExplorer.UI.Adorners;

/// <summary>
/// Base class for drag adorners that display visual feedback during drag operations.
/// Extensible for different drag sources (file tree, tabs, windows, etc.).
/// </summary>
public abstract class DragAdornerBase : Adorner
{
    protected readonly UIElement _child;
    private double _offsetX;
    private double _offsetY;

    protected DragAdornerBase(UIElement adornedElement, UIElement child)
        : base(adornedElement)
    {
        _child = child ?? throw new ArgumentNullException(nameof(child));
        AddVisualChild(_child);
    }

    /// <summary>
    /// Updates the position of the adorner relative to the mouse.
    /// </summary>
    public void UpdatePosition(Point position)
    {
        var adornerLayer = AdornerLayer.GetAdornerLayer(AdornedElement);
        if (adornerLayer == null)
            return;

        var transform = TransformToAncestor(adornerLayer);
        var point = transform.Transform(new Point(0, 0));
        
        _offsetX = position.X - point.X;
        _offsetY = position.Y - point.Y;
        
        InvalidateArrange();
    }

    protected override Size MeasureOverride(Size constraint)
    {
        _child.Measure(constraint);
        return _child.DesiredSize;
    }

    protected override Size ArrangeOverride(Size finalSize)
    {
        _child.Arrange(new Rect(new Point(_offsetX, _offsetY), finalSize));
        return finalSize;
    }

    protected override int VisualChildrenCount => 1;

    protected override Visual GetVisualChild(int index)
    {
        if (index != 0)
            throw new ArgumentOutOfRangeException(nameof(index));
        return _child;
    }

    protected override Geometry? GetLayoutClip(Size layoutSlotSize)
    {
        return null; // Don't clip - allow adorner to extend beyond bounds
    }
}

