import os
import sys
import time

try:
    import msvcrt
except ImportError:
    msvcrt = None

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_input_with_timeout(prompt: str, timeout_sec: float) -> str:
    """Gets input from standard input with a timeout (Windows only).
    If it times out, returns None.
    """
    if msvcrt is None:
        # Fallback for non-windows: blocking input
        return input(prompt)
    
    print(prompt, end="", flush=True)
    
    start_time = time.time()
    result = ""
    
    while True:
        if msvcrt.kbhit():
            char = msvcrt.getwche()
            if char == '\r' or char == '\n':
                print()
                return result
            elif char == '\b':
                result = result[:-1]
            else:
                result += char
                
        if time.time() - start_time > timeout_sec:
            print("\nTime's up!")
            return None
            
        time.sleep(0.01)

def get_single_keypress_with_timeout(timeout_sec: float) -> str:
    """Wait for a single keystroke for a given duration. Return None if timed out."""
    if msvcrt is None:
        time.sleep(timeout_sec)
        return None
        
    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        if msvcrt.kbhit():
            return msvcrt.getwch()
        time.sleep(0.01)
    return None
