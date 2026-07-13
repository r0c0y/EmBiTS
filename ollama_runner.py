import os
import subprocess
import time
import socket
import platform
import threading

_lock = threading.Lock()
_tried = False

def _is_ollama_listening(host="localhost", port=11434) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False

def ensure_ollama_running():
    global _tried
    if _is_ollama_listening():
        return True
    with _lock:
        if _tried:
            return _is_ollama_listening()
        _tried = True
        try:
            sys_type = platform.system()
            if sys_type == "Darwin":
                subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif sys_type == "Windows":
                subprocess.Popen(["ollama", "serve"], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                try:
                    subprocess.Popen(["systemctl", "start", "ollama"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(20):
                time.sleep(0.5)
                if _is_ollama_listening():
                    return True
        except Exception:
            pass
    return False
