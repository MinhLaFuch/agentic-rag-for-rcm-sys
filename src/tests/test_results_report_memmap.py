"""Run memory-safety regressions in a child process to contain native crashes."""

import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize('closed', [False, True])
def test_formatter_does_not_dereference_mapped_arrays(closed):
    script = '''
from pathlib import Path
import tempfile
import numpy as np
from tests.results_report import fmt

with tempfile.TemporaryDirectory() as temp:
    array = np.lib.format.open_memmap(Path(temp) / 'vectors.npy', mode='w+', dtype='float32', shape=(4, 3))
    array[:] = 12345
    view = np.asarray(array)[1:, ::2]
    if CLOSED:
        array._mmap.close()
    text = fmt({'direct': array, 'ndarray_view': view})
    assert 'mmap=STATE' in text, text
    assert 'contents omitted' in text, text
    assert '12345' not in text, text
    print(text)
    if not CLOSED:
        array._mmap.close()
'''.replace('CLOSED', repr(closed)).replace('STATE', 'closed' if closed else 'open')
    env = os.environ.copy()
    source = str(Path(__file__).resolve().parents[1])
    env['PYTHONPATH'] = source + os.pathsep + env.get('PYTHONPATH', '')
    result = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True,
                            text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
