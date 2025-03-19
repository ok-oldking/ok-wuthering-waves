# if __name__ == '__main__':
#     from config import config
#     from ok import OK
#
#     config = config
#     config['debug'] = True
#     config['ocr']['lib'] = 'paddleocr'
#     ok = OK(config)
#     ok.start()
import glob
import os
from win32com.client import Dispatch


def create_shortcut(exe_path, shortcut_name, description=None, target_path=None, arguments=None):
    """
    Creates a shortcut in the Start Menu for the given executable.

    Args:
        exe_path: The full path to the executable file.
        shortcut_name: The name of the shortcut (without the .lnk extension).
        target_path:  Optional. The full path to the Start Menu location.
                          If None, uses the current user's Start Menu.
    """
    if not exe_path:
        cwd = os.getcwd()
        pattern = os.path.join(cwd, "ok*.exe")  # Construct the search pattern

        # Use glob to find files matching the pattern (case-insensitive)
        matching_files = glob.glob(pattern.lower()) + glob.glob(pattern.upper())  # search both cases

        for filename in glob.glob(pattern):
            matching_files.append(filename)

        if matching_files:
            # Return the first matching file
            exe_path = matching_files[0]

    if not os.path.exists(exe_path):
        return False

    if not os.path.isabs(exe_path):
        exe_path = os.path.abspath(exe_path)

    if target_path is None:
        target_path = os.path.join(os.path.expandvars("%AppData%"), "Microsoft", "Windows", "Start Menu",
                                   "Programs")

    if not os.path.exists(target_path):
        return False

    shortcut_path = os.path.join(target_path, f"{shortcut_name}.lnk")

    try:
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortcut(shortcut_path)
        shortcut.TargetPath = exe_path
        if arguments is not None:
            shortcut.Arguments = arguments
        shortcut.WorkingDirectory = os.path.dirname(exe_path)
        shortcut.Description = description if description else shortcut_name
        shortcut.IconLocation = exe_path
        shortcut.save()

        print(f"Shortcut created at: {shortcut_path} {exe_path}")

    except Exception as e:
        print(f"Error creating shortcut: {e}")
        return False
    return True


def create_shortcut_with_unicode(shortcut_path, exe_path, shortcut_name, description=None, arguments=None):
    shell = Dispatch('WScript.Shell')
    shortcut = shell.CreateShortcut(shortcut_path)
    shortcut.TargetPath = exe_path
    shortcut.WorkingDirectory = os.path.dirname(exe_path)
    shortcut.Description = description if description else shortcut_name
    if arguments is not None:
        shortcut.Arguments = arguments
    shortcut.IconLocation = exe_path

    # Ensure Unicode characters are handled
    shortcut_name = str(shortcut_name)
    shortcut.Description = str(description) if description else shortcut_name

    shortcut.save()


if __name__ == "__main__":
    # Example usage:
    exe_path = r"ok-ww.exe"  # Replace with your actual executable path
    shortcut_name = "ok-ww中文"  # Replace with your desired shortcut name
    create_shortcut_with_unicode(None, shortcut_name,
                                 arguments="-t -1 -e")  # Creates shortcut in current user's Start Menu

    # To create in the All Users Start Menu (requires admin privileges):
    # all_users_start_menu = r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs"
    # create_shortcut(exe_path, shortcut_name, all_users_start_menu)
