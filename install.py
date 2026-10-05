import os
import sys
import subprocess

def main():
    print("Starting S-Class EOS v6 Installation...")
    if sys.platform == "win32":
        cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", "install.ps1"]
    else:
        cmd = ["bash", "install.sh"]
    
    try:
        subprocess.check_call(cmd)
        print("Installation completed successfully in under 60 seconds.")
    except subprocess.CalledProcessError as e:
        print(f"Installation failed with exit code {e.returncode}")
        sys.exit(e.returncode)

if __name__ == "__main__":
    main()
