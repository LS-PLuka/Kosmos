"""Stage the old relative layout in a temp directory; test the final standalone HTML."""
from pathlib import Path
import tempfile, shutil, json, hashlib, subprocess, sys
root=Path(__file__).resolve().parents[3]; m=json.loads((root/'approved-manifest.json').read_text())
with tempfile.TemporaryDirectory() as tmp:
 t=Path(tmp)
 for old,item in m.items():
  src=root/item['path']; assert hashlib.sha256(src.read_bytes()).hexdigest()==item['sha256'],old
  dest=t/old;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
 shutil.copy2(root/'tools/motion-lab/index.html',t/'previews/playground-phase-c.html')
 for command in [['node','test-phase-b.js'],['node','test-phase-c.js'],[sys.executable,'test-exports.py'],[sys.executable,'test-exports-c.py'],[sys.executable,'test-lab-c.py'],[sys.executable,'test-lab-c-regression.py']]:
  subprocess.run([command[0],str(t/'source'/command[1])],check=True)
print('All original regression suites passed against final lab.')
