"""Static guard against Streamlit duplicate-element-id errors (which only surface
in the real Streamlit runtime, not the headless stub):
  - no duplicate key= values
  - form_submit_button labels must be unique (it has no `key` parameter)
  - st.button / st.download_button must each have a key OR a unique label
"""
import re, sys
import os as _os, sys as _sys
# The app now imports sibling domain modules; these suites exec it from tests/,
# so the repository root must be importable.
_SEP_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _SEP_ROOT not in _sys.path:
    _sys.path.insert(0, _SEP_ROOT)

from collections import Counter

src = open("apps/_developer_impl.py", encoding="utf-8").read()
ok = True
def check(name, cond, detail=""):
    global ok
    print(("PASS" if cond else "FAIL"), name, ("" if cond else f"-> {detail}"))
    ok = ok and cond

# 1) duplicate key= values
keys = re.findall(r'key=["\']([^"\']+)["\']', src)
dup_keys = {k: n for k, n in Counter(keys).items() if n > 1}
check("no duplicate key= values", not dup_keys, dup_keys)

# 2) form_submit_button labels unique
fsb = re.findall(r'form_submit_button\(\s*"([^"]+)"', src)
dup_fsb = {k: n for k, n in Counter(fsb).items() if n > 1}
check("form_submit_button labels unique", not dup_fsb, dup_fsb)

# 3) st.button without key -> label must be unique among keyless buttons
btn_nokey = [m.group(1) for m in re.finditer(r'st\.button\(\s*"([^"]+)"([^)]*)\)', src)
             if 'key=' not in m.group(2)]
dup_btn = {k: n for k, n in Counter(btn_nokey).items() if n > 1}
check("keyless st.button labels unique", not dup_btn, dup_btn)

# 4) st.download_button without key -> label must be unique among keyless ones
dl_nokey = [m.group(1) for m in re.finditer(r'st\.download_button\(\s*"([^"]+)"([^)]*)\)', src)
            if 'key=' not in m.group(2)]
dup_dl = {k: n for k, n in Counter(dl_nokey).items() if n > 1}
check("keyless st.download_button labels unique", not dup_dl, dup_dl)

print("\nUI KEYS OK" if ok else "\nUI KEYS FAILED")
sys.exit(0 if ok else 1)
