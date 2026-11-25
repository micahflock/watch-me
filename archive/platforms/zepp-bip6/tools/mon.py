import socket,sys,time,re
s=socket.socket(socket.AF_UNIX); s.connect(sys.argv[1]); time.sleep(0.2); s.recv(65536)
for c in sys.argv[2:]:
    if c.startswith('sleep '): time.sleep(float(c[6:])); continue
    s.sendall((c+"\n").encode()); time.sleep(0.15); s.recv(65536)
