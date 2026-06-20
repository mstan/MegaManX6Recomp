#!/usr/bin/env python3
"""mdis.py - read live RAM from the recomp/oracle debug server and disassemble MIPS-I.

Usage:
  python tools/mdis.py 0x800EA920 192            # disasm 192 bytes at addr (port 4490)
  python tools/mdis.py --port 4380 0x800EA920 64 # against the oracle
  python tools/mdis.py --hex <hexstring> 0x800EA920   # disasm a hex blob you already have

Covers the MIPS-I subset PSX code uses. Unknown encodings print ".word 0x...".
"""
import socket, sys, json, time

REG = ["zero","at","v0","v1","a0","a1","a2","a3","t0","t1","t2","t3","t4","t5","t6","t7",
       "s0","s1","s2","s3","s4","s5","s6","s7","t8","t9","k0","k1","gp","sp","fp","ra"]

def r(n): return REG[n & 31]

def s16(x):
    x &= 0xffff
    return x - 0x10000 if x & 0x8000 else x

def disasm(word, addr):
    op = (word >> 26) & 0x3f
    rs = (word >> 21) & 0x1f
    rt = (word >> 16) & 0x1f
    rd = (word >> 11) & 0x1f
    sh = (word >> 6) & 0x1f
    fn = word & 0x3f
    imm = word & 0xffff
    simm = s16(imm)
    tgt = (word & 0x3ffffff) << 2
    jaddr = (addr & 0xf0000000) | tgt
    if word == 0:
        return "nop"
    if op == 0:  # SPECIAL
        if fn == 0x00: return f"sll   {r(rd)}, {r(rt)}, {sh}"
        if fn == 0x02: return f"srl   {r(rd)}, {r(rt)}, {sh}"
        if fn == 0x03: return f"sra   {r(rd)}, {r(rt)}, {sh}"
        if fn == 0x04: return f"sllv  {r(rd)}, {r(rt)}, {r(rs)}"
        if fn == 0x06: return f"srlv  {r(rd)}, {r(rt)}, {r(rs)}"
        if fn == 0x07: return f"srav  {r(rd)}, {r(rt)}, {r(rs)}"
        if fn == 0x08: return f"jr    {r(rs)}"
        if fn == 0x09: return f"jalr  {r(rd)}, {r(rs)}" if rd != 31 else f"jalr  {r(rs)}"
        if fn == 0x0c: return "syscall"
        if fn == 0x0d: return "break"
        if fn == 0x10: return f"mfhi  {r(rd)}"
        if fn == 0x11: return f"mthi  {r(rs)}"
        if fn == 0x12: return f"mflo  {r(rd)}"
        if fn == 0x13: return f"mtlo  {r(rs)}"
        if fn == 0x18: return f"mult  {r(rs)}, {r(rt)}"
        if fn == 0x19: return f"multu {r(rs)}, {r(rt)}"
        if fn == 0x1a: return f"div   {r(rs)}, {r(rt)}"
        if fn == 0x1b: return f"divu  {r(rs)}, {r(rt)}"
        if fn == 0x20: return f"add   {r(rd)}, {r(rs)}, {r(rt)}"
        if fn == 0x21: return f"addu  {r(rd)}, {r(rs)}, {r(rt)}"
        if fn == 0x22: return f"sub   {r(rd)}, {r(rs)}, {r(rt)}"
        if fn == 0x23: return f"subu  {r(rd)}, {r(rs)}, {r(rt)}"
        if fn == 0x24: return f"and   {r(rd)}, {r(rs)}, {r(rt)}"
        if fn == 0x25: return f"or    {r(rd)}, {r(rs)}, {r(rt)}"
        if fn == 0x26: return f"xor   {r(rd)}, {r(rs)}, {r(rt)}"
        if fn == 0x27: return f"nor   {r(rd)}, {r(rs)}, {r(rt)}"
        if fn == 0x2a: return f"slt   {r(rd)}, {r(rs)}, {r(rt)}"
        if fn == 0x2b: return f"sltu  {r(rd)}, {r(rs)}, {r(rt)}"
        return f".word 0x{word:08x}  (special fn=0x{fn:02x})"
    if op == 0x01:  # REGIMM
        if rt == 0x00: return f"bltz  {r(rs)}, 0x{addr+4+simm*4:08x}"
        if rt == 0x01: return f"bgez  {r(rs)}, 0x{addr+4+simm*4:08x}"
        if rt == 0x10: return f"bltzal {r(rs)}, 0x{addr+4+simm*4:08x}"
        if rt == 0x11: return f"bgezal {r(rs)}, 0x{addr+4+simm*4:08x}"
        return f".word 0x{word:08x}  (regimm rt=0x{rt:02x})"
    if op == 0x02: return f"j     0x{jaddr:08x}"
    if op == 0x03: return f"jal   0x{jaddr:08x}"
    if op == 0x04: return f"beq   {r(rs)}, {r(rt)}, 0x{addr+4+simm*4:08x}"
    if op == 0x05: return f"bne   {r(rs)}, {r(rt)}, 0x{addr+4+simm*4:08x}"
    if op == 0x06: return f"blez  {r(rs)}, 0x{addr+4+simm*4:08x}"
    if op == 0x07: return f"bgtz  {r(rs)}, 0x{addr+4+simm*4:08x}"
    if op == 0x08: return f"addi  {r(rt)}, {r(rs)}, {simm}"
    if op == 0x09: return f"addiu {r(rt)}, {r(rs)}, {simm}  (0x{imm:04x})"
    if op == 0x0a: return f"slti  {r(rt)}, {r(rs)}, {simm}"
    if op == 0x0b: return f"sltiu {r(rt)}, {r(rs)}, {simm}  (0x{imm:04x})"
    if op == 0x0c: return f"andi  {r(rt)}, {r(rs)}, 0x{imm:04x}"
    if op == 0x0d: return f"ori   {r(rt)}, {r(rs)}, 0x{imm:04x}"
    if op == 0x0e: return f"xori  {r(rt)}, {r(rs)}, 0x{imm:04x}"
    if op == 0x0f: return f"lui   {r(rt)}, 0x{imm:04x}"
    if op == 0x10: return f"cop0  0x{word:08x}"
    if op == 0x12: return f"cop2/gte 0x{word:08x}"
    if op == 0x20: return f"lb    {r(rt)}, {simm}({r(rs)})"
    if op == 0x21: return f"lh    {r(rt)}, {simm}({r(rs)})"
    if op == 0x22: return f"lwl   {r(rt)}, {simm}({r(rs)})"
    if op == 0x23: return f"lw    {r(rt)}, {simm}({r(rs)})"
    if op == 0x24: return f"lbu   {r(rt)}, {simm}({r(rs)})"
    if op == 0x25: return f"lhu   {r(rt)}, {simm}({r(rs)})"
    if op == 0x26: return f"lwr   {r(rt)}, {simm}({r(rs)})"
    if op == 0x28: return f"sb    {r(rt)}, {simm}({r(rs)})"
    if op == 0x29: return f"sh    {r(rt)}, {simm}({r(rs)})"
    if op == 0x2a: return f"swl   {r(rt)}, {simm}({r(rs)})"
    if op == 0x2b: return f"sw    {r(rt)}, {simm}({r(rs)})"
    if op == 0x2e: return f"swr   {r(rt)}, {simm}({r(rs)})"
    if op == 0x32: return f"lwc2  0x{word:08x}"
    if op == 0x3a: return f"swc2  0x{word:08x}"
    return f".word 0x{word:08x}  (op=0x{op:02x})"

def read_ram(port, addr, length):
    s = socket.socket(); s.settimeout(20)
    s.connect(("127.0.0.1", port))
    s.sendall(json.dumps({"cmd":"read_ram","addr":f"0x{addr:08X}","len":length}).encode()+b"\n")
    time.sleep(0.1); buf=b""; s.settimeout(3)
    try:
        while True:
            c=s.recv(65536)
            if not c: break
            buf+=c
            if buf.endswith(b"\n"): break
    except socket.timeout: pass
    s.close()
    for line in reversed(buf.decode(errors="replace").strip().splitlines()):
        try:
            j=json.loads(line)
            if "hex" in j: return bytes.fromhex(j["hex"])
        except Exception: continue
    raise RuntimeError("no hex in reply")

def main():
    args=sys.argv[1:]
    port=4490
    hexblob=None
    if args and args[0]=="--port":
        port=int(args[1]); args=args[2:]
    if args and args[0]=="--hex":
        hexblob=args[1]; args=args[2:]
    addr=int(args[0],0)
    if hexblob is not None:
        data=bytes.fromhex(hexblob)
    else:
        length=int(args[1],0) if len(args)>1 else 128
        data=read_ram(port,addr,length)
    for i in range(0,len(data)-3,4):
        word=int.from_bytes(data[i:i+4],"little")
        a=addr+i
        print(f"  0x{a:08x}: {word:08x}  {disasm(word,a)}")

if __name__=="__main__":
    main()
