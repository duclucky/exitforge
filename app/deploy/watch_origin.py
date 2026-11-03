"""Keep the exact fixed HTTPS origin, or track this deployment's preview URL."""
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import urlsplit

DESTINATION=Path('/opt/exitforge/runtime/public-origin.txt')
FIXED=DESTINATION.with_name('fixed-origin.txt')
PATTERN=re.compile(r'https://[a-z0-9-]+\.trycloudflare\.com\b')


def choose_origin(fixed, logs):
    if fixed.exists():
        origin=fixed.read_text(encoding='utf-8').strip()
        parsed=urlsplit(origin)
        if (parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password
                or parsed.port not in (None,443) or parsed.path or parsed.query or parsed.fragment
                or any(character.isspace() for character in origin)):
            raise ValueError('Invalid fixed HTTPS origin')
        return origin
    urls=PATTERN.findall(logs)
    return urls[-1] if urls else ''


def main():
    while True:
        try:
            logs=''
            if not FIXED.exists():
                result=subprocess.run(['/usr/bin/docker','logs','--tail','100','exitforge-tunnel'],capture_output=True,text=True,timeout=10)
                if result.returncode==0:logs=result.stdout+'\n'+result.stderr
            origin=choose_origin(FIXED,logs)
            if origin:
                current=DESTINATION.read_text().strip() if DESTINATION.exists() else ''
                if current!=origin:
                    temporary=DESTINATION.with_suffix('.tmp');temporary.write_text(origin+'\n',encoding='utf-8')
                    temporary.chmod(0o644);os.replace(temporary,DESTINATION)
                    print('ExitForge HTTPS origin: '+origin,flush=True)
        except (OSError,ValueError,subprocess.SubprocessError):pass
        time.sleep(2)


if __name__=='__main__':main()
