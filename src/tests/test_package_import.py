import subprocess
import sys


def test_importing_package_does_not_load_subpackages():
    # `python -m package.config ...` chạy từ shell script nên import package phải nhẹ (không kéo pandas/pyarrow/tools)
    code = "import sys, package; sys.exit(1 if any(m.startswith('package.') for m in sys.modules) else 0)"
    assert subprocess.run([sys.executable, "-c", code]).returncode == 0
