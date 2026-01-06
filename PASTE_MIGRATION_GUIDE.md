# Migration Guide: Character Typing to Clipboard Paste

This document explains how to migrate from character-by-character typing to clipboard paste for text insertion in the voice transcription hotkey listener.

## Why This Change?

**Problem**: Character-by-character typing (`keyboard_controller.type(text)`) fires keypress events as fast as the system allows (~0-1ms apart). This overwhelms React-based terminal UIs like Claude Code CLI, triggering "maximum update depth exceeded" errors.

**Solution**: Clipboard paste inserts all text as a single operation, triggering just one state update regardless of text length.

## Dependencies Required

Ensure `pyperclip` is installed:
```bash
pip install pyperclip
```

Ensure these imports are at the top of your file:
```python
import pyperclip
import time
from pynput.keyboard import Key
```

## Code Changes

### Step 1: Add the New Paste Method

Add this method to your `GlobalHotkeyListener` class:

```python
def paste_via_clipboard(self, text):
    """Paste text via clipboard (Ctrl+V) instead of typing character-by-character.

    This prevents React-based terminal UIs (like Claude Code CLI) from hitting
    maximum update depth errors caused by rapid individual character inputs.
    """
    try:
        # Save current clipboard content
        original_clipboard = pyperclip.paste()
    except:
        original_clipboard = None

    try:
        # Copy text to clipboard and paste immediately
        pyperclip.copy(text)
        with self.keyboard_controller.pressed(Key.ctrl):
            self.keyboard_controller.tap('v')

    finally:
        # Restore original clipboard after paste completes
        if original_clipboard is not None:
            time.sleep(0.05)  # Brief wait for paste to complete before restoring
            pyperclip.copy(original_clipboard)
```

### Step 2: Replace All `keyboard_controller.type()` Calls

Find and replace all instances of:
```python
self.keyboard_controller.type(text)
```

With:
```python
self.paste_via_clipboard(text)
```

### Locations to Update in `paste_text()` Method

There are 3 places in the `paste_text()` method that need updating:

1. **Normal mode** (~line 462):
   ```python
   # Before:
   self.keyboard_controller.type(text)

   # After:
   self.paste_via_clipboard(text)
   ```

2. **GPT direct mode** (~line 470):
   ```python
   # Before:
   self.keyboard_controller.type(normalized_response)

   # After:
   self.paste_via_clipboard(normalized_response)
   ```

3. **GPT clipboard mode** (~line 489):
   ```python
   # Before:
   self.keyboard_controller.type(normalized_response)

   # After:
   self.paste_via_clipboard(normalized_response)
   ```

## How It Works

1. **Save** current clipboard content
2. **Copy** transcription text to clipboard
3. **Paste** via Ctrl+V (text appears immediately at cursor)
4. **Wait** 50ms for paste to complete
5. **Restore** original clipboard content

The 50ms delay occurs **after** text appears on screen, so it doesn't affect perceived latency. The clipboard restoration is essential for the GPT+clipboard workflow (Shift+Forward) where you reference copied content.

## Notes

- **Clipboard types**: Only text is preserved. If you had an image or file on the clipboard, it will be replaced with text after restoration.
- **Pre-paste delay**: None (paste is immediate after clipboard copy)
- **Post-paste delay**: 50ms (ensures paste completes before clipboard restoration)
