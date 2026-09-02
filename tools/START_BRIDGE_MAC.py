import sys, os, io
D = os.path.expanduser(
    '~/Library/Application Support/Vectorworks/2026/Plug-ins/VWX-MCP')
if D not in sys.path:
    sys.path.insert(0, D)
_src = os.path.join(D, 'vwx_mcp_bridge.py')
# encoding='utf-8' is required: Vectorworks' embedded Python runs with an ASCII
# locale, so a bare open() dies on the em-dash in the bridge's own docstring
# (UnicodeDecodeError, byte 0xe2 at position 42).
with io.open(_src, encoding='utf-8') as _f:
    _code = _f.read()
_g = {'__file__': _src, '__name__': '__main__'}
exec(compile(_code, _src, 'exec'), _g)
