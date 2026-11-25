#!/usr/bin/env bash
# Boot a Zepp OS device image in the simulator's bundled QEMU.
#
#   ZSIM=<dir>  unpacked simulator .deb (holds opt/simulator/resources/firmware/qemu_linux)
#   ZFW=<dir>   unpacked device image (holds main.elf + norflash.bin)
#   ZRUN=<dir>  work dir: serial.log (the firmware's console) and mon.sock (QEMU monitor)
#
#   tools/boot.sh            headless: screen via cap.py, keys via mon.py; no touch
#   tools/boot.sh window     QEMU window on Xvfb :77 so tap.sh can touch the screen
#
# The firmware listens for the installer on localhost:7833 (install.js, send.js).
# norflash.bin is written to: installed faces and settings persist in it.
set -eu
: "${ZSIM:?}" "${ZFW:?}" "${ZRUN:?}"
Q="$ZSIM/opt/simulator/resources/firmware/qemu_linux"
mkdir -p "$ZRUN/libshim"
# Ubuntu 24.04 ships libaio as libaio.so.1t64; QEMU wants libaio.so.1.
# Also needs: apt-get install -y libvte-2.91-0 libaio1t64
ln -sf /usr/lib/x86_64-linux-gnu/libaio.so.1t64 "$ZRUN/libshim/libaio.so.1"
export LD_LIBRARY_PATH="$ZRUN/libshim:$Q/lib"
display="-display none"
if [ "${1:-}" = window ]; then
  pgrep -f 'Xvfb :77' >/dev/null || { nohup Xvfb :77 -screen 0 800x700x24 >/dev/null 2>&1 & sleep 1; }
  export DISPLAY=:77
  display="-display gtk,show-cursor=on"
fi
cd "$ZRUN"
nohup "$Q/qemu-system-arm" -M mps2-an521 -semihosting \
  -drive file="$ZFW/norflash.bin",bus=0,unit=0,format=raw -kernel "$ZFW/main.elf" \
  -nic user,id=usernet,hostfwd=tcp::7833-:7833,model=lan9118 \
  $display -name zsim -serial file:"$ZRUN/serial.log" \
  -monitor unix:"$ZRUN/mon.sock",server,nowait > "$ZRUN/qemu.out" 2>&1 &
echo "booting; console in $ZRUN/serial.log (ready in ~25 s)"
