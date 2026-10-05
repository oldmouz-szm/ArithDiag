"""Read-only memory guard and sampled process-group RSS for Linux/WSL."""
import subprocess
from pathlib import Path
PS=Path("/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")
def available(timeout=5):
    if PS.is_file():
        p=subprocess.run([str(PS),"-NoProfile","-NonInteractive","-Command",
            "[Console]::Write((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory)"],
            capture_output=True,text=True,timeout=timeout)
        if p.returncode:raise RuntimeError("Windows host memory query failed")
        return int(p.stdout.strip())/1024**2
    for row in Path("/proc/meminfo").read_text().splitlines():
        if row.startswith("MemAvailable:"):return int(row.split()[1])/1024**2
    raise RuntimeError("Available memory could not be determined")
def group_rss(pgid):
    total=0
    for path in Path("/proc").iterdir():
        if not path.name.isdecimal():continue
        try:
            stat=(path/"stat").read_text().rsplit(")",1)[1].split()
            if int(stat[2])!=pgid:continue
            for row in (path/"status").read_text().splitlines():
                if row.startswith("VmRSS:"):total+=int(row.split()[1])/1024;break
        except (FileNotFoundError,ProcessLookupError,PermissionError):pass
    return total
