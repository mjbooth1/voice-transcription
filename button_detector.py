"""
Mouse Button Detector
Helps identify which Windows message codes correspond to specific mouse buttons.
Run this script and click various buttons to see their message codes.
"""

from pynput.mouse import Listener as MouseListener

def on_click(x, y, button, pressed):
    """Handle mouse clicks and show button information."""
    if pressed:  # Only show button press, not release
        print(f"Button: {button}")
        print(f"Position: ({x}, {y})")
        print(f"Pressed: {pressed}")
        print("---")

def win32_event_filter(msg, data):
    """Show Windows message codes for mouse events."""
    # Skip mouse movement events to reduce spam
    if msg == 512:  # WM_MOUSEMOVE
        return True
    
    print(f"Windows Message: {msg}")
    
    # Common mouse message codes:
    msg_names = {
        512: "WM_MOUSEMOVE",
        513: "WM_LBUTTONDOWN",
        514: "WM_LBUTTONUP", 
        516: "WM_RBUTTONDOWN",
        517: "WM_RBUTTONUP",
        519: "WM_MBUTTONDOWN", 
        520: "WM_MBUTTONUP",
        522: "WM_MOUSEWHEEL",
        523: "WM_XBUTTONDOWN",
        524: "WM_XBUTTONUP"
    }
    
    msg_name = msg_names.get(msg, f"Unknown ({msg})")
    print(f"Message: {msg} - {msg_name}")
    
    # For XButton events, show which button
    if msg in [523, 524]:  # XBUTTON events
        xbutton = (data.mouseData >> 16) & 0xFFFF
        print(f"XButton: {xbutton} ({'XBUTTON1' if xbutton == 1 else 'XBUTTON2' if xbutton == 2 else 'Unknown'})")
    
    print("="*50)
    return True  # Allow event to continue

def main():
    """Main function to detect mouse buttons."""
    print("Mouse Button Detector")
    print("====================")
    print("Click different mouse buttons to see their codes.")
    print("Focus on finding the button between Forward/Back.")
    print("Press Ctrl+C to stop.")
    print()
    
    # Start mouse listener with event filter
    with MouseListener(
        on_click=on_click,
        win32_event_filter=win32_event_filter,
        suppress=False
    ) as listener:
        try:
            listener.join()
        except KeyboardInterrupt:
            print("\nDetection stopped.")

if __name__ == "__main__":
    main()