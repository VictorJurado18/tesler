"""Write dragshift.__version__ into the Windows exe metadata (installer/version_info.txt)."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dragshift import __version__ as v  # noqa: E402

nums = [int(n) for n in re.findall(r"\d+", v)[:3]] + [0, 0, 0]
p = Path(__file__).with_name("version_info.txt")
s = p.read_text(encoding="utf-8")
s = re.sub(r"\(\d+, \d+, \d+, 0\)", "({}, {}, {}, 0)".format(*nums[:3]), s)
s = re.sub(r"'(FileVersion|ProductVersion)', '[^']*'", lambda m: f"'{m.group(1)}', '{v}'", s)
p.write_text(s, encoding="utf-8")
print(v)
