#!/usr/bin/env python3

import os
import subprocess
import sys

def setup_environment():
    """Set up the virtual environment and install dependencies"""
    
    print("Setting up Card Counter environment...")
    
    # Check if we're using uv
    try:
        subprocess.run(["uv", "--version"], check=True, capture_output=True)
        use_uv = True
        print("Using uv for environment setup")
    except (subprocess.CalledProcessError, FileNotFoundError):
        use_uv = False
        print("uv not found, trying pip")
    
    # Create virtual environment
    if use_uv:
        try:
            print("Creating virtual environment with uv...")
            subprocess.run(["uv", "venv"], check=True)
            
            # Install dependencies
            print("Installing dependencies...")
            subprocess.run(["uv", "pip", "install", "-r", "requirements.txt"], check=True)
            
        except subprocess.CalledProcessError as e:
            print(f"Error setting up environment with uv: {e}")
            return False
    else:
        try:
            print("Creating virtual environment with python -m venv...")
            subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
            
            # Install dependencies
            print("Installing dependencies...")
            if os.name == 'nt':  # Windows
                pip_path = os.path.join("venv", "Scripts", "pip")
            else:  # Unix
                pip_path = os.path.join("venv", "bin", "pip")
            
            subprocess.run([pip_path, "install", "-r", "requirements.txt"], check=True)
            
        except subprocess.CalledProcessError as e:
            print(f"Error setting up environment with pip: {e}")
            return False
    
    print("Environment setup complete!")
    print("To activate the virtual environment:")
    if use_uv:
        print("  source .venv/bin/activate  (Linux/Mac)")
        print("  .venv\Scripts\activate     (Windows)")
    else:
        print("  source venv/bin/activate    (Linux/Mac)")
        print("  venv\Scripts\activate      (Windows)")
    
    print("\nTo run the application:")
    print("  python app.py")
    
    return True

if __name__ == "__main__":
    success = setup_environment()
    sys.exit(0 if success else 1)