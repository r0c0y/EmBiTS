import os
import subprocess
import time
import socket
import platform

def _is_ollama_listening(host="localhost", port=11434) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False

def ensure_ollama_running():
    if _is_ollama_listening():
        return True
    
    print("Ollama is not running. Attempting to start Ollama server locally...")
    sys_type = platform.system()
    
    try:
        if sys_type == "Darwin":  # macOS
            try:
                # Try opening standard application bundle
                subprocess.Popen(["open", "-a", "Ollama"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif sys_type == "Windows":
            try:
                # Try locating the Ollama user-profile directory launcher
                appdata = os.environ.get("LOCALAPPDATA", "")
                win_path = os.path.join(appdata, "Programs", "Ollama", "Ollama.exe")
                if os.path.exists(win_path):
                    subprocess.Popen([win_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    subprocess.Popen(["ollama", "serve"], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                subprocess.Popen(["ollama", "serve"], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:  # Linux / RHEL
            try:
                # Attempt to use systemctl service if available, else fallback to background CLI serve
                subprocess.Popen(["systemctl", "start", "ollama"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
        # Wait up to 10 seconds for the socket to accept connections
        for _ in range(20):
            time.sleep(0.5)
            if _is_ollama_listening():
                print("Ollama server started successfully.")
                return True
    except Exception as e:
        print(f"Failed to auto-start Ollama: {e}")
        
    print("WARNING: Could not connect to Ollama. Please make sure the Ollama application is launched and running.")
    return False
