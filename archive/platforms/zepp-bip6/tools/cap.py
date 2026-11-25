# usage: python3 -I cap.py <monsock> <workdir> <out.png>
import socket, sys, time, re, os
import numpy as np
from PIL import Image
sock, wd, out = sys.argv[1:4]
def mon(cmd):
    s = socket.socket(socket.AF_UNIX); s.connect(sock); time.sleep(0.2); s.recv(65536)
    s.sendall((cmd + "\n").encode()); time.sleep(0.8)
    r = s.recv(1 << 20).decode(errors='replace'); s.close(); return re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', r)
regs = mon("xp /8wx 0x50305000")
m = re.search(r'50305010:\s+0x([0-9a-f]+)', regs)
base = int(m.group(1), 16)
fn = 'fbcap.raw'
p = os.path.join(wd, fn)
if os.path.exists(p): os.remove(p)
mon("pmemsave 0x%x %d %s" % (base, 390 * 450 * 2, fn))
for _ in range(20):
    if os.path.exists(p) and os.path.getsize(p) == 390 * 450 * 2: break
    time.sleep(0.2)
a = np.frombuffer(open(p, 'rb').read(), dtype='<u2').reshape(450, 390).astype(np.uint32)
r = ((a >> 11) & 31) * 255 // 31; g = ((a >> 5) & 63) * 255 // 63; b = (a & 31) * 255 // 31
Image.fromarray(np.dstack([r, g, b]).astype(np.uint8)).save(out)
print('saved', out, hex(base))
