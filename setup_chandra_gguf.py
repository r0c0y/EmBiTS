#!/usr/bin/env python3
"""Helper to verify Chandra GGUF setup for air-gapped deployment.

Usage:
    python setup_chandra_gguf.py --model /models/chandra-ocr-2/chandra-ocr-2-IQ4_NL.gguf --mmproj /models/chandra-ocr-2/chandra-ocr-2.mmproj-f16.gguf

Environment variables:
    CHANDRA_GGUF_MODEL   path to .gguf model
    CHANDRA_GGUF_MMPROJ  path to .mmproj-f16.gguf
    CHANDRA_GGUF_GPU_LAYERS  -1 for all GPU, 0 for CPU-only
    CHANDRA_GGUF_CTX     context size (default 4096)

Recommended quantizations by hardware:
    IQ3_M  2.49 GB  - minimum RAM 6 GB
    IQ4_XS 2.93 GB  - balanced
    IQ4_NL 3.05 GB  - best quality/size (RECOMMENDED)
    Q6_K   4.08 GB  - best quality, needs 10 GB RAM
"""

import argparse
import os
import sys
import platform

try:
    from llama_cpp import Llama
    HAS_LLAMACPP = True
except ImportError:
    HAS_LLAMACPP = False


def check_system():
    print(f"Platform: {platform.system()} {platform.release()} ({platform.machine()})")
    print(f"Python: {sys.version}")

    # Try to detect GPU
    if platform.system() == "Linux":
        try:
            import subprocess
            result = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print(f"GPU: {result.stdout.strip()}")
            else:
                print("GPU: No NVIDIA GPU detected via nvidia-smi")
        except Exception:
            print("GPU: nvidia-smi not available")
    elif platform.system() == "Windows":
        try:
            import subprocess
            result = subprocess.run(["wmic", "path", "win32_VideoController", "get", "name"], capture_output=True, text=True, timeout=10)
            print(f"GPU: {result.stdout.strip()}")
        except Exception:
            print("GPU: Could not detect GPU")

    # RAM
    try:
        import psutil
        mem = psutil.virtual_memory()
        print(f"RAM: {mem.total / (1024**3):.1f} GB total, {mem.available / (1024**3):.1f} GB available")
    except ImportError:
        print("RAM: install psutil for memory info")
    except Exception as e:
        print(f"RAM: {e}")


def verify_model(model_path, mmproj_path, gpu_layers=-1, n_ctx=4096):
    if not HAS_LLAMACPP:
        print("ERROR: llama-cpp-python is not installed.")
        print("  pip install llama-cpp-python")
        return False

    if not model_path or not os.path.exists(model_path):
        print(f"ERROR: Model not found: {model_path}")
        return False

    print(f"Model: {model_path}")
    print(f"  Size: {os.path.getsize(model_path) / (1024**3):.2f} GB")
    if mmproj_path and os.path.exists(mmproj_path):
        print(f"MMProj: {mmproj_path}")
        print(f"  Size: {os.path.getsize(mmproj_path) / (1024**3):.2f} GB")
    else:
        print(f"MMProj: NOT FOUND ({mmproj_path})")
        print("  WARNING: Multimodal input may not work without mmproj file!")

    print(f"GPU layers: {gpu_layers} (-1 = all layers on GPU)")
    print(f"Context size: {n_ctx}")

    try:
        print("\nLoading model...")
        kwargs = {"model_path": model_path, "n_ctx": n_ctx, "n_gpu_layers": gpu_layers, "verbose": False}
        if mmproj_path and os.path.exists(mmproj_path):
            kwargs["mmproj"] = mmproj_path
        llm = Llama(**kwargs)
        print("SUCCESS: Model loaded successfully!")
        return True
    except Exception as e:
        print(f"FAIL: {e}")
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=os.environ.get("CHANDRA_GGUF_MODEL", ""))
    parser.add_argument("--mmproj", default=os.environ.get("CHANDRA_GGUF_MMPROJ", ""))
    parser.add_argument("--gpu-layers", type=int, default=int(os.environ.get("CHANDRA_GGUF_GPU_LAYERS", "-1")))
    parser.add_argument("--ctx", type=int, default=int(os.environ.get("CHANDRA_GGUF_CTX", "4096")))
    parser.add_argument("--no-test", action="store_true", help="Skip model loading test")
    args = parser.parse_args()

    check_system()
    print()

    if not args.no_test:
        ok = verify_model(args.model, args.mmproj, args.gpu_layers, args.ctx)
        sys.exit(0 if ok else 1)
    else:
        print("Model verification skipped.")


if __name__ == "__main__":
    main()
