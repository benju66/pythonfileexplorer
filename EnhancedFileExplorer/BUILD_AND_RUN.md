# How to Build and Run Enhanced File Explorer

## Prerequisites

1. **.NET 9 SDK** - Download from [Microsoft](https://dotnet.microsoft.com/download/dotnet/9.0)
   - Verify installation: `dotnet --version` (should show 9.x.x)

2. **Windows 10/11** - Required for WPF applications

3. **Visual Studio 2022** (Optional but recommended)
   - Community Edition is free
   - Or use Visual Studio Code with C# extension

## Quick Start (Command Line)

### 1. Navigate to Solution Directory

```powershell
cd EnhancedFileExplorer
```

### 2. Restore Dependencies

```powershell
dotnet restore EnhancedFileExplorer.sln
```

### 3. Build the Solution

```powershell
dotnet build EnhancedFileExplorer.sln
```

Or build in Release mode:

```powershell
dotnet build EnhancedFileExplorer.sln -c Release
```

### 4. Run the Application

```powershell
dotnet run --project EnhancedFileExplorer/EnhancedFileExplorer.csproj
```

Or run the built executable:

```powershell
cd EnhancedFileExplorer\EnhancedFileExplorer\bin\Debug\net9.0-windows
.\EnhancedFileExplorer.exe
```

## Using Visual Studio

### 1. Open Solution

1. Open Visual Studio 2022
2. File → Open → Project/Solution
3. Navigate to `EnhancedFileExplorer` folder
4. Select `EnhancedFileExplorer.sln`

### 2. Restore and Build

- Visual Studio will automatically restore packages when you open the solution
- Press `Ctrl+Shift+B` or Build → Build Solution

### 3. Run

- Press `F5` to run with debugging
- Press `Ctrl+F5` to run without debugging

## Troubleshooting

### Issue: "NETSDK1045: The current .NET SDK does not support targeting .NET 9.0"

**Solution:** Install .NET 9 SDK from [Microsoft](https://dotnet.microsoft.com/download/dotnet/9.0)

### Issue: "The project file cannot be opened"

**Solution:** Make sure you're using Visual Studio 2022 or later, or .NET 9 SDK

### Issue: "Package restore failed"

**Solution:** 
```powershell
dotnet nuget locals all --clear
dotnet restore EnhancedFileExplorer.sln
```

### Issue: "Cannot find namespace 'EnhancedFileExplorer'"

**Solution:** Rebuild the solution:
```powershell
dotnet clean EnhancedFileExplorer.sln
dotnet build EnhancedFileExplorer.sln
```

### Issue: Application crashes on startup

**Check:**
1. Look at the console output for error messages
2. Check Windows Event Viewer for .NET errors
3. Verify all dependencies are installed

## Expected Behavior

When you run the application, you should see:

1. **Main Window** opens with:
   - Toolbar at the top (Up, Back, Forward, Refresh, Undo, Redo buttons)
   - Address bar
   - New Tab button
   - Tab control with one initial tab

2. **File Tree** displays:
   - Files and folders from your Documents folder (default)
   - Can expand folders by clicking
   - Can double-click folders to navigate

3. **Navigation**:
   - Click folders to navigate
   - Use toolbar buttons for navigation
   - Type path in address bar and press Enter

## Development Tips

### Hot Reload (Visual Studio)

- Make changes to XAML or code
- Press `Ctrl+Alt+Q` to apply changes without restarting

### Debugging

- Set breakpoints in code
- Use Debug → Windows → Output to see log messages
- Check Debug output for application logs

### View Logs

- Logs are written to Debug output window in Visual Studio
- Check the Output window (View → Output) for log messages

## Project Structure Reference

```
EnhancedFileExplorer/
├── EnhancedFileExplorer.sln          # Solution file
├── EnhancedFileExplorer/             # Main application
│   ├── App.xaml                      # Application definition
│   ├── MainWindow.xaml               # Main window UI
│   └── Bootstrapper.cs               # DI configuration
├── EnhancedFileExplorer.Core/        # Core interfaces/models
├── EnhancedFileExplorer.Infrastructure/  # Infrastructure implementations
├── EnhancedFileExplorer.Services/   # Business logic services
└── EnhancedFileExplorer.UI/         # UI components
```

## Next Steps After Running

1. **Test Navigation**:
   - Click on folders in the tree
   - Use Back/Forward buttons
   - Try address bar navigation

2. **Test Tabs**:
   - Click "+" button to create new tab
   - Switch between tabs
   - Close tabs

3. **Report Issues**:
   - Note any errors or unexpected behavior
   - Check console output for error messages

---

**Note:** This is Phase 1 - Foundation. File operations (create, delete, rename) will be added in the next phase with context menus.

