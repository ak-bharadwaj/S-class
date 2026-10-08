import os
import sys
import subprocess

def main():
    print("Starting S-Class v6 Installation...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if sys.platform == "win32":
        install_script = os.path.join(script_dir, "install.ps1")
        if not os.path.exists(install_script):
            print(f"install.ps1 not found at {install_script}")
            sys.exit(1)
        cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", install_script]
    else:
        install_script = os.path.join(script_dir, "install.sh")
        if not os.path.exists(install_script):
            print(f"install.sh not found at {install_script}")
            sys.exit(1)
        cmd = ["bash", install_script]
    
    try:
        subprocess.check_call(cmd)
        print("S-Class installation finished successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Installation failed with exit code {e.returncode}")
        sys.exit(e.returncode)

if __name__ == "__main__":
    main()
