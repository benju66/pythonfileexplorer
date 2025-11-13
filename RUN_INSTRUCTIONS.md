# How to Run Enhanced File Explorer

## Prerequisites
- Python 3.11+ installed
- Virtual environment set up (venv folder exists)

## Quick Start

### 1. Activate Virtual Environment

**Windows PowerShell:**
```powershell
.\venv\Scripts\Activate.ps1
```

**Windows Command Prompt:**
```cmd
venv\Scripts\activate.bat
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

### 2. Install Dependencies (if not already installed)

```bash
pip install -r requirements.txt
```

**Note:** You may need to remove `logging==0.4.9.6` from requirements.txt first, as `logging` is part of Python's standard library.

### 3. Run the Application

```bash
python main.py
```

Or:

```bash
python -m main
```

## Alternative: Run Without Virtual Environment

If you prefer to install dependencies globally (not recommended):

```bash
pip install -r requirements.txt
python main.py
```

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'PyQt6'"
**Solution:** Make sure virtual environment is activated and dependencies are installed:
```bash
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Issue: PowerShell execution policy error
**Solution:** Run PowerShell as Administrator and execute:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Issue: "logging" module error
**Solution:** Remove `logging==0.4.9.6` from requirements.txt (it's part of Python standard library)

## Expected Behavior

When you run the app, you should see:
- A file explorer window opens
- Multiple dockable panels (Pinned, Recent, Preview, etc.)
- Toolbar with navigation buttons
- Tab support for multiple file views

## Keyboard Shortcuts

- `Ctrl+T` - New tab
- `Ctrl+W` - Close tab
- `Ctrl+P` - Toggle Pinned Panel
- `Ctrl+B` - Toggle Bookmarks Panel
- `F5` - Refresh
- `Alt+Up` - Go up one directory
- `Ctrl+,` - Open Settings

See `modules/keyboard_shortcuts.py` for full list.

