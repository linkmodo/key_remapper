"""
Build Script for Key Remapper
==============================
Creates a standalone Windows executable using PyInstaller.

Usage:
    python build.py

This will create:
    - dist/KeyRemapper.exe (standalone executable)
"""

import subprocess
import sys
import os
from pathlib import Path

def check_dependencies():
    """Check if required packages are installed"""
    required = ['customtkinter', 'pystray', 'PIL', 'PyInstaller']
    missing = []
    
    for pkg in required:
        try:
            if pkg == 'PIL':
                __import__('PIL')
            elif pkg == 'PyInstaller':
                __import__('PyInstaller')
            else:
                __import__(pkg)
        except ImportError:
            missing.append(pkg)
    
    if missing:
        print(f"Missing packages: {', '.join(missing)}")
        print("Installing from requirements.txt...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])

def build_executable():
    """Build the executable using PyInstaller"""
    
    # Get the directory of this script
    script_dir = Path(__file__).parent
    
    # Main script to compile
    main_script = script_dir / "key_remapper_gui.py"
    
    # Icon file (we'll create a simple one if it doesn't exist)
    icon_path = script_dir / "icon.ico"
    
    # PyInstaller command
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--name=KeyRemapper',
        '--onefile',
        '--windowed',  # No console window
        '--noconfirm',  # Overwrite without asking
        f'--distpath={script_dir / "dist"}',
        f'--workpath={script_dir / "build"}',
        f'--specpath={script_dir}',
        # Include customtkinter
        '--collect-all=customtkinter',
        # Include pystray
        '--collect-all=pystray',
        # Hidden imports
        '--hidden-import=pystray._win32',
        '--hidden-import=PIL._tkinter_finder',
        # Add data files
        f'--add-data={script_dir / "key_remapper.py"};.',
    ]
    
    # Add icon if it exists
    if icon_path.exists():
        cmd.append(f'--icon={icon_path}')
    
    # Add the main script
    cmd.append(str(main_script))
    
    print("=" * 50)
    print("Building Key Remapper Executable")
    print("=" * 50)
    print(f"\nMain script: {main_script}")
    print(f"Output: {script_dir / 'dist' / 'KeyRemapper.exe'}")
    print("\nThis may take a few minutes...\n")
    
    # Run PyInstaller
    result = subprocess.run(cmd, cwd=script_dir)
    
    if result.returncode == 0:
        print("\n" + "=" * 50)
        print("BUILD SUCCESSFUL!")
        print("=" * 50)
        print(f"\nExecutable created at:")
        print(f"  {script_dir / 'dist' / 'KeyRemapper.exe'}")
        print("\nTo run:")
        print("  1. Right-click KeyRemapper.exe")
        print("  2. Select 'Run as administrator'")
        print("\nTip: Create a shortcut and set it to always run as admin.")
    else:
        print("\n" + "=" * 50)
        print("BUILD FAILED!")
        print("=" * 50)
        print("Check the error messages above.")
        return False
    
    return True

def create_icon():
    """Create a simple icon file if PIL is available"""
    try:
        from PIL import Image, ImageDraw
        
        # Create icon at multiple sizes
        sizes = [16, 32, 48, 64, 128, 256]
        images = []
        
        for size in sizes:
            img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Draw a rounded rectangle background
            margin = size // 8
            draw.rounded_rectangle(
                [margin, margin, size - margin, size - margin],
                radius=size // 6,
                fill=(41, 128, 185)  # Nice blue color
            )
            
            # Draw "K" letter
            font_size = size // 2
            text_x = size // 2 - font_size // 4
            text_y = size // 2 - font_size // 2
            draw.text((text_x, text_y), "K", fill="white")
            
            images.append(img)
        
        # Save as ICO
        icon_path = Path(__file__).parent / "icon.ico"
        images[0].save(
            icon_path,
            format='ICO',
            sizes=[(s, s) for s in sizes],
            append_images=images[1:]
        )
        print(f"Created icon: {icon_path}")
        return True
    except Exception as e:
        print(f"Could not create icon: {e}")
        return False

def main():
    """Main build process"""
    print("Key Remapper Build Script")
    print("=" * 50)
    
    # Check and install dependencies
    print("\n[1/3] Checking dependencies...")
    check_dependencies()
    
    # Create icon
    print("\n[2/3] Creating application icon...")
    create_icon()
    
    # Build executable
    print("\n[3/3] Building executable...")
    success = build_executable()
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
