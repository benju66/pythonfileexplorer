# Enhanced File Explorer

A high-performance Windows file management application built with WPF and .NET 9.

## Features

- Multi-tab interface
- Undo/redo system
- File operations (copy, move, delete, rename, create)
- Navigation with history
- Pinned items
- Recent items
- Bookmarks
- Custom metadata (colors, tags)
- Search functionality
- Split view
- And more...

## Requirements

- .NET 9 SDK
- Windows 10/11
- Visual Studio 2022 or later (recommended)

## Building

```bash
dotnet build EnhancedFileExplorer.sln
```

## Running

```bash
dotnet run --project EnhancedFileExplorer/EnhancedFileExplorer.csproj
```

## Project Structure

- `EnhancedFileExplorer.Core` - Core interfaces and models
- `EnhancedFileExplorer.Infrastructure` - Infrastructure implementations
- `EnhancedFileExplorer.Data` - Data access layer
- `EnhancedFileExplorer.Services` - Business logic services
- `EnhancedFileExplorer.UI` - UI components
- `EnhancedFileExplorer` - Main application

## Status

🚧 **In Development** - Phase 1: Foundation

