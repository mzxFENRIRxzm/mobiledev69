"""Open three persistent, isolated Chrome profiles for local account testing."""
import os
from pathlib import Path
import subprocess


def main():
    project = Path(__file__).resolve().parents[1]
    candidates = [Path(os.environ[key]) / 'Google/Chrome/Application/chrome.exe'
                  for key in ('PROGRAMFILES', 'PROGRAMFILES(X86)', 'LOCALAPPDATA')
                  if key in os.environ]
    chrome = next((candidate for candidate in candidates if candidate.is_file()), None)
    if chrome is None:
        raise SystemExit('Google Chrome was not found.')
    for role in ('Admin', 'Mechanic', 'Customer'):
        profile = project / '.local' / 'browser-profiles' / role
        profile.mkdir(parents=True, exist_ok=True)
        # No shell interpolation, profile copying, or credentials in arguments.
        subprocess.Popen([str(chrome), f'--user-data-dir={profile}',
                          '--no-first-run', '--no-default-browser-check', '--new-window',
                          f'http://localhost:50000/login?profile={role}'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=subprocess.CREATE_NO_WINDOW)
        print(f'Opened isolated {role} profile. Sign in with that account.')
    print('Reuse this command to reopen profiles stored in .local/browser-profiles (Git-ignored).')


if __name__ == '__main__':
    main()
