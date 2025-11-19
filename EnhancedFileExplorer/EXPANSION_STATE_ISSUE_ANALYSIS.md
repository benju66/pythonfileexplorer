# Expansion State Collapse Issue - Analysis & Solution

## Problem

Expanded folders briefly collapse and then reopen during refresh operations. This causes visual flickering.

## Root Cause Analysis

### Current Implementation

1. **XAML Binding (Line 32):**
   ```xml
   <Setter Property="IsExpanded" Value="{Binding IsExpanded, Mode=TwoWay}"/>
   ```
   - Two-way binding between `TreeViewItem.IsExpanded` ↔ `ViewModel.IsExpanded`

2. **RefreshDirectoryAsync (Lines 254-298):**
   - Calls `GetExpandedPaths()` - **METHOD DOES NOT EXIST**
   - Calls `RestoreExpandedPaths()` - **METHOD DOES NOT EXIST**
   - These methods are referenced but never implemented!

3. **RefreshDirectoryChildrenIncremental (Lines 339-415):**
   - Modifies `viewModel.Children` collection (adds/removes items)
   - When collection changes, WPF TreeView may recreate TreeViewItems
   - New TreeViewItems start with `IsExpanded = false` by default
   - Two-way binding causes `ViewModel.IsExpanded = false` immediately
   - Then restoration tries to fix it, but timing is wrong

### The Problem Flow

```
1. Refresh starts
2. GetExpandedPaths() called → DOESN'T EXIST (no-op or exception)
3. RefreshDirectoryChildrenIncremental modifies Children collection
4. WPF creates new TreeViewItems for changed items
5. New TreeViewItems start with IsExpanded=false
6. Two-way binding sets ViewModel.IsExpanded=false
7. RestoreExpandedPaths() called → DOESN'T EXIST (no-op)
8. Result: Folders collapse briefly, then ViewModel.IsExpanded might be restored later
```

## Solution Options

### Option A: Implement Missing Methods + Timing Fix (RECOMMENDED)

**Approach:**
1. Implement `GetExpandedPaths()` to capture expansion state from ViewModels
2. Implement `RestoreExpandedPaths()` to restore expansion state
3. Ensure restoration happens AFTER TreeViewItems are created
4. Use `UpdateLayout()` and proper Dispatcher priority

**Pros:**
- Fixes the immediate issue
- Preserves existing architecture
- Minimal code changes

**Cons:**
- Still relies on timing (UpdateLayout + Dispatcher priority)
- May have edge cases with virtualization

**Confidence:** 90%

### Option B: Preserve Expansion During Collection Changes

**Approach:**
1. Before modifying Children collection, capture expansion state
2. Set ViewModel.IsExpanded BEFORE TreeViewItem is created
3. Use one-way binding (ViewModel → TreeViewItem) during refresh
4. Temporarily disable two-way binding updates

**Pros:**
- More robust - doesn't rely on timing
- Prevents collapse from happening at all

**Cons:**
- More complex - need to manage binding state
- May interfere with user interactions during refresh

**Confidence:** 85%

### Option C: Use ItemContainerGenerator + Visual Tree Traversal

**Approach:**
1. Use `ItemContainerGenerator` to find TreeViewItems
2. Directly set `TreeViewItem.IsExpanded` after collection changes
3. Use `UpdateLayout()` to ensure TreeViewItems exist
4. Traverse visual tree to find all TreeViewItems

**Pros:**
- Direct control over TreeViewItem state
- Works regardless of binding

**Cons:**
- More complex visual tree traversal
- Performance overhead
- May not work well with virtualization

**Confidence:** 80%

## Recommended Solution: Option A + Enhancements

### Implementation Strategy

1. **Implement GetExpandedPaths():**
   ```csharp
   private HashSet<string> GetExpandedPaths()
   {
       var expandedPaths = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
       CollectExpandedPaths(_rootItems, expandedPaths);
       return expandedPaths;
   }
   
   private void CollectExpandedPaths(IEnumerable<FileTreeViewModel> items, HashSet<string> expandedPaths)
   {
       foreach (var item in items)
       {
           if (item.IsExpanded && item.IsDirectory)
           {
               expandedPaths.Add(item.Path);
               CollectExpandedPaths(item.Children, expandedPaths);
           }
       }
   }
   ```

2. **Implement RestoreExpandedPaths():**
   ```csharp
   private void RestoreExpandedPaths(HashSet<string> expandedPaths)
   {
       // First, restore ViewModel.IsExpanded (binding will handle TreeViewItem)
       RestoreViewModelExpansion(_rootItems, expandedPaths);
       
       // Then ensure TreeViewItems are updated after layout
       Dispatcher.BeginInvoke(() =>
       {
           FileTree.UpdateLayout();
           RestoreTreeViewItemExpansion(FileTree, expandedPaths);
       }, DispatcherPriority.Loaded);
   }
   
   private void RestoreViewModelExpansion(IEnumerable<FileTreeViewModel> items, HashSet<string> expandedPaths)
   {
       foreach (var item in items)
       {
           if (item.IsDirectory)
           {
               item.IsExpanded = expandedPaths.Contains(item.Path);
               if (item.IsExpanded)
               {
                   RestoreViewModelExpansion(item.Children, expandedPaths);
               }
           }
       }
   }
   
   private void RestoreTreeViewItemExpansion(ItemsControl parent, HashSet<string> expandedPaths)
   {
       var generator = parent.ItemContainerGenerator;
       foreach (var item in parent.Items)
       {
           if (item is FileTreeViewModel viewModel && viewModel.IsDirectory)
           {
               var container = generator.ContainerFromItem(item) as TreeViewItem;
               if (container != null)
               {
                   var shouldBeExpanded = expandedPaths.Contains(viewModel.Path);
                   if (container.IsExpanded != shouldBeExpanded)
                   {
                       container.IsExpanded = shouldBeExpanded;
                   }
                   
                   // Recursively restore children
                   if (container.IsExpanded)
                   {
                       RestoreTreeViewItemExpansion(container, expandedPaths);
                   }
               }
           }
       }
   }
   ```

3. **Enhance RefreshDirectoryAsync:**
   - Capture expansion state BEFORE modifying collection
   - Restore ViewModel.IsExpanded IMMEDIATELY after collection changes
   - Use Dispatcher.BeginInvoke with Loaded priority for TreeViewItem restoration

### Key Improvements

1. **Capture Before Modification:** Get expansion state before `RefreshDirectoryChildrenIncremental` runs
2. **Restore ViewModel First:** Set `ViewModel.IsExpanded` immediately (binding handles TreeViewItem)
3. **Double-Check TreeViewItems:** Use `ItemContainerGenerator` to verify TreeViewItem state after layout
4. **Proper Timing:** Use `UpdateLayout()` + `DispatcherPriority.Loaded` to ensure TreeViewItems exist

### Alternative: Prevent Binding Updates During Refresh

If Option A still has timing issues, we can:

1. Temporarily disable PropertyChanged notifications for IsExpanded during refresh
2. Set all ViewModel.IsExpanded values
3. Re-enable notifications
4. Force binding update

This prevents the two-way binding from collapsing items during refresh.

## Testing Strategy

1. **Test Case 1:** Expand multiple nested folders, trigger refresh
   - Expected: All folders remain expanded, no flickering

2. **Test Case 2:** Expand folders, add new items to expanded folder
   - Expected: Folder stays expanded, new items appear

3. **Test Case 3:** Expand folders, remove items from expanded folder
   - Expected: Folder stays expanded, removed items disappear

4. **Test Case 4:** Rapid refreshes (FileSystemWatcher rapid-fire)
   - Expected: Expansion state preserved throughout

5. **Test Case 5:** Virtualized TreeView (many items)
   - Expected: Expansion state preserved even for off-screen items

## Confidence Assessment

- **Option A (Recommended):** 90% - Should work well with proper timing
- **Option B:** 85% - More robust but more complex
- **Option C:** 80% - Works but performance concerns

## Recommendation

**Implement Option A** with the following enhancements:
1. Implement missing `GetExpandedPaths()` and `RestoreExpandedPaths()` methods
2. Capture expansion state BEFORE collection modifications
3. Restore ViewModel.IsExpanded IMMEDIATELY after collection changes
4. Use `UpdateLayout()` + `DispatcherPriority.Loaded` for TreeViewItem verification
5. Add fallback: If TreeViewItem state doesn't match ViewModel, force update

This provides the best balance of simplicity, reliability, and performance.

