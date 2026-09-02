#!/usr/bin/env python3
"""Talk to the in-Vectorworks bridge directly over its TCP socket.

The bridge speaks newline-delimited JSON on 127.0.0.1:9878. That is the whole
protocol, so an agent does not need the MCP server (or a Claude Code restart)
to drive a live document — only the bridge dialog open inside Vectorworks.

  vwx_cli.py ping
  vwx_cli.py get_document_info
  vwx_cli.py vs_signature '{"name":"CC_GetCircuitSource"}'
  vwx_cli.py execute_script '{"code":"import vs\nvs.AlrtDialog(\"hi\")"}'

The execute_script parameter is `code`, NOT `script` (commands.py:3905). Passing
`script` is accepted silently, execs an empty body, and returns {"result": null}
— a probe that looks like it ran and found nothing.

Exit codes: 0 ok · 2 bridge unreachable · 3 bridge returned an error.
"""
import json
import socket
import sys

HOST, PORT = '127.0.0.1', 9878


def assert_real_vectorworks():
    """Refuse to talk to anything but Vectorworks itself.

    A test double left listening on this port answers `ping` with a cheerful
    {"status":"ok"} and `get_document_info` with a fabricated document. That is
    indistinguishable from the real bridge at the protocol level, so it is
    checked at the OS level instead: the process holding the port must be
    Vectorworks. This has already happened once — an orphaned fake_bridge2.py
    served a mock document that could have been reported as the user's drawing.
    """
    import subprocess
    try:
        pids = subprocess.run(['lsof', '-nP', f'-iTCP:{PORT}', '-sTCP:LISTEN', '-t'],
                              capture_output=True, text=True, timeout=10).stdout.split()
    except Exception:
        return None                      # lsof unavailable: cannot verify, do not block
    if not pids:
        return None                      # nothing listening: the connect error is clearer
    for pid in pids:
        try:
            cmdline = subprocess.run(['ps', '-o', 'command=', '-p', pid],
                                     capture_output=True, text=True, timeout=10).stdout
        except Exception:
            continue
        if 'Vectorworks' not in cmdline:
            raise RuntimeError(
                f'port {PORT} is held by pid {pid}, which is NOT Vectorworks:\n'
                f'  {cmdline.strip()[:200]}\n'
                'Refusing to run — this would return fabricated data. Kill that '
                'process, then start the bridge inside Vectorworks.')
    return True


def call(cmd, params=None, timeout=180.0, verify=True):
    if verify:
        assert_real_vectorworks()
    s = socket.create_connection((HOST, PORT), timeout=10.0)
    s.settimeout(timeout)
    try:
        s.sendall(json.dumps({'type': cmd, 'params': params or {}}).encode() + b'\n')
        buf = b''
        while b'\n' not in buf:
            chunk = s.recv(65536)
            if not chunk:
                raise ConnectionError('bridge closed the connection')
            buf += chunk
        return json.loads(buf.split(b'\n', 1)[0])
    finally:
        s.close()


def main(argv):
    if len(argv) < 2:
        print(__doc__.strip(), file=sys.stderr)
        return 1
    cmd = argv[1]
    params = json.loads(argv[2]) if len(argv) > 2 else {}
    try:
        result = call(cmd, params)
    except RuntimeError as e:
        print(json.dumps({'error': str(e)}, indent=2), file=sys.stderr)
        return 4
    except (ConnectionRefusedError, OSError) as e:
        print(json.dumps({
            'error': f'bridge unreachable on {HOST}:{PORT} ({e})',
            'fix': 'In Vectorworks: Tools > Plug-ins > Run Script... > '
                   'START_BRIDGE_MAC.py, and leave the dialog open.',
        }, indent=2), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 3 if isinstance(result, dict) and result.get('error') else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
