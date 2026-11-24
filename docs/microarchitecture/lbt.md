# Binary translation execution (LBT)

LBT is the LoongArch Binary Translation extension. It is a set of instructions
aimed at emulators that translate x86, Arm, or MIPS guest code: hardware support
for flag computation, x87 stack management, Arm predication, and the unaligned
loads and stores that MIPS guests expect. The goal is to remove the
instruction-by-instruction software sequences that a translator would otherwise
emit for every guest instruction.

LBT is an optional extension, and the x86, Arm, and MIPS modes are reported
separately. The cores in this guide implement it, but software that depends on a
particular mode should check the hardware capability bits for that mode rather
than assume the whole extension is present.

## Registers and state

LBT adds five registers that live alongside the floating-point state. Four of
them are scratch registers, `$scr0` to `$scr3`, moved to and from the
general-purpose registers with `movgr2scr` and `movscr2gr`. The fifth, LBT4,
holds the guest flags: the low 32 bits carry the x86 EFLAGS layout, and the high
32 bits carry the x87 stack top pointer.

The flags are the important part. CF, PF, AF, ZF, SF, and OF live in the low half
of LBT4, and Arm's N, Z, C, and V are mapped onto the same bits. Instructions
such as `x86add`, `x86adc`, `x86sub`, `x86sbb`, `x86and`, `x86or`, `x86xor`, and
the x86 shift and rotate family update those flags directly. A translator does
not have to compute the flags in software and does not have to spill them between
guest instructions.

According to LoongPerf, `movgr2scr` runs at 1 IPC on both cores, while
`movscr2gr` runs at 1 IPC on LA664 and 2 IPC on LA464. The emulated arithmetic
is cheap too: `x86add.d` and `armadd.w` both have 2-cycle latency and 0.5 IPC,
and `setx86j` has 1-cycle latency and 1 IPC.

The scratch registers are useful for the host side of the translator. An
emulator can keep a few guest or host values in `$scr0` to `$scr3` across calls,
and the LBT jump instructions use them directly: `jiscr0` jumps to `$scr0` plus an
immediate, and `jiscr1` writes the return address into `$scr0` and jumps to
`$scr1` plus an immediate. That gives the translator a cheap call and indirect
jump path without touching the normal GPRs.

LBT state is part of the thread context. An operating system has to save and
restore the four scratch registers and LBT4 on a context switch, and the
translator should assume that the values do not survive a system call or a signal
unless it saves them itself.

## x86 support

The x86 side is the most complete. The integer instructions cover add, subtract,
add-with-carry, subtract-with-borrow, increment, decrement, multiply, logical
operations, shifts, and rotates, each producing the x86 flags as a side effect.
`setx86j` evaluates an x86 condition against the flags and writes 0 or 1 to a
GPR, which is what a translator needs for `setcc` and for materializing a
condition without a branch. `setx86loope` and `setx86loopne` cover the loop
instructions.

The x87 side uses the high half of LBT4 as the stack top. `x86mftop` and
`x86mttop` read and write TOP, `x86inctop` and `x86dectop` implement the x87
stack push and pop bookkeeping, and `x86settm` and `x86clrtm` enable or disable
the TOP-based remapping of the first eight FPRs. With TM enabled, an x87
instruction that names `st(0)` maps to the FPR selected by TOP, so the translator
does not have to rename registers in software for every x87 operation.

The 80-bit x87 format is split across two FPRs. `fcvt.ld.d` and `fcvt.ud.d`
produce the low 64 bits and the high 16 bits of an extended value from a double,
and `fcvt.d.ld` goes the other way. `x86settag` manipulates the x87 tag word in a
GPR, including the bookkeeping that raises an exception on an invalid tag
transition.

## Arm support

The Arm side reuses the same flag bits and maps Arm's N, Z, C, and V onto SF, ZF,
CF, and OF. The Arm integer, logical, and shift instructions (`armadd`, `armsub`,
`armadc`, `armsbc`, `armand`, `armor`, `armxor`, `armnot`, `armsll`, `armsrl`,
`armsra`, `armrotr`, and their immediate forms) update those flags. `setarmj`
evaluates an Arm condition and writes 0 or 1 to a GPR.

The more interesting feature is that the Arm arithmetic and logical instructions
are predicated. Each one carries an Arm condition code and only executes when the
condition holds, which is exactly what Arm code expects. A translator can map a
predicated Arm instruction to one LBT instruction instead of a branch around the
operation. `armmove` and `armmov` handle the conditional move forms, and `armrrx`
covers the rotate-with-extend used by some addressing and shift idioms.

## MIPS support

The MIPS side is smaller and mostly about unaligned memory. `ldl.w`, `ldl.d`,
`ldr.w`, and `ldr.d` load the left or right part of an unaligned value and merge
it with the destination register, while `stl.w`, `stl.d`, `str.w`, and `str.d`
store the corresponding part. These replace the byte-by-byte sequences that a
MIPS translator would otherwise emit for `lwl`, `lwr`, `swl`, and `swr`.

The generic LBT integer group also helps MIPS and other guests: `adc`, `sbc`,
`rotr`, `rotri`, `rcr`, and `rcri` provide the carry and rotate primitives that
the guest ISAs need, and `addu12i` helps with address materialization.

## Using LBT well

Keep the guest flags in hardware. The fastest flag sequence is the one that never
reads LBT4 into a GPR; `x86mfflag` and `x86mtflag` (and the Arm equivalents) are
there for the cases where the guest code actually inspects the flags, such as
`pushf` or a flag-dependent branch that the translator cannot fold.

Use the predicated Arm instructions and the x86 condition instructions instead of
emitting branches around small operations. A branch in translated code is a
branch on the host, with all the predictor pressure that implies; a predicated
LBT instruction avoids it.

Use the scratch registers for the translator's own state. They are not part of
the guest register file, and keeping the host's loop counters or translation
block pointers there avoids spilling around calls. The `jiscr0` and `jiscr1`
instructions make the indirect jump path cheap as well.

Use the x87 remapping rather than software renaming. With TM enabled and TOP in
LBT4, the FPR indices follow the x87 stack automatically, and the tag word stays
consistent through `x86settag`. This is the difference between a translator that
emits one x87 instruction per guest x87 instruction and one that emits a
sequence of moves.

Keep translation blocks small and branch-light. LBT makes individual guest
instructions cheap, but it does not change the host branch predictor or the
instruction cache. A translator that emits long blocks with many host branches
will still be limited by the front end.

## Limits

LBT accelerates the instruction patterns it covers, not the semantics of the
guest memory model. Emulating a weakly ordered guest on LoongArch still requires
the right barriers around guest atomics, and emulating a strongly ordered guest
may require more barriers than the translator would like. Self-modifying guest
code still needs cache maintenance and `ibar` on the host side.

Floating-point exceptions and rounding are another boundary. The x87
instructions in LBT cover the stack and tag bookkeeping, but the guest's
exception behavior and precision control are still the translator's
responsibility.

## What to measure

LoongPerf covers LBT instructions alongside the base ISA, so the per-instruction
latency and throughput are in [Instruction latency and throughput](../latency-throughput.md).
The measurements that matter for a translator are the cost of a guest flag
update, the cost of a predicated Arm instruction, the x87 stack operations, and
the unaligned MIPS loads and stores. Those are better measured with a small
translator benchmark than with a single-instruction loop, because the dependency
on LBT4 is what usually limits the throughput.
