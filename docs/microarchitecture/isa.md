# Instruction set architecture

This section collects the parts of the LoongArch instruction set that the rest of
the guide assumes: the register file, instruction formats and classes, extensions,
alignment rules, and the memory model. It is not a replacement for the ISA
manuals; it is the subset that shows up in optimization decisions.

## Registers

LoongArch 64-bit has:

| Resource | Notes |
| --- | --- |
| 32 general-purpose registers, `$r0`–`$r31` | 64-bit; `$r0` is hardwired to zero |
| 32 floating-point registers, `$f0`–`$f31` | 64-bit |
| 32 vector registers | LSX `$v0`–`$v31`, 128-bit; LASX `$x0`–`$x31`, 256-bit |
| 8 floating-point condition codes | `$fcc0`–`$fcc7` |

The register files overlap: a floating-point register is the low 64 bits of an
LSX register, and an LSX register is the low 128 bits of the corresponding LASX
register.

Outside LBT, there is no integer condition-code register and no
general-purpose flags. Integer branches compare two registers directly; floating-point branches
test an FCC. This removes the x86-style flag dependency, but it also means there is
no compare-and-branch fusion to exploit: the compare and the branch are already one
instruction.

LBT adds its own architectural state. It provides four 64-bit scratch registers,
`$scr0`–`$scr3`, which software moves to and from the general-purpose registers
with `movgr2scr` and `movscr2gr`. Emulators use them to hold guest registers, and
`jiscr0`/`jiscr1` use them as alternate branch targets. A fifth register, LBT4,
holds the x86 EFLAGS in its low 32 bits and the x87 FTOP in its high 32 bits, so
that LBT's flag operations and condition helpers (`setx86j`, `setarmj`, …) can
work on it directly. This state is part of the thread context, so an operating
system has to save and restore it on a context switch.

## Instruction formats

Every instruction is 32 bits wide and 4-byte aligned. There are no prefixes and no
variable-length encodings, so instruction boundaries follow from the address
alone. A fetch block always ends on an instruction boundary, and code size is
proportional to instruction count.

Loads and stores have two main addressing forms:

- base plus a signed 12-bit immediate, for example `ld.d $a0, $sp, 16`;
- base plus an index register, for example `ldx.d $a0, $a1, $a2`.

A third form, `ldptr.w` and `ldptr.d`, is PC-relative and is what the compiler
uses for globals. There is no scaled-index addressing and no
base-plus-index-plus-displacement form. A scaled address such as `a[i * 8]` needs a separate shift or an `alsl.d`
before the load. Branches are PC-relative (`b`, `bl`, `beq`, `bne`, `blt`, …) or
register-indirect (`jirl`), which is how calls through a pointer and function
returns work. PC-relative data addresses use `pcalau12i` plus an immediate; large
constants are built with `lu12i.w` and `ori`, adding `lu32i.d` and `lu52i.d` for
64-bit values.

## Instruction classes

The integer instructions cover arithmetic and logic (`add.d`, `sub.d`, `and`,
`or`, `xor`, `slt`), shifts (`slli.d`, `srli.d`, `rotri.d`), and bit-field and byte
manipulation (`bstrins.d`, `bstrpick.d`, `bytepick.d`, `revb.2h`, `revb.4h`,
`revb.2w`, `revb.d`). Bit-field insert and extract and the rotates are single
instructions, so they beat the equivalent shift-and-mask sequences; the byte
reversal instructions are the cheapest way to convert endianness.

Multiply and divide have their own instructions. `mul.d` produces the low half of
the product, `mulh.d` and `mulhu.d` the signed and unsigned high halves, and
`div.d` and `mod.d` the quotient and remainder. Multiply is pipelined; divide is
iterative, and code that divides by a constant should let the compiler turn it
into a multiply and shift.

Control flow comes in three shapes. Conditional branches (`beq`, `bne`, `blt`,
`bge`, `bltu`, `bgeu`, `beqz`, `bnez`) compare registers directly and do not read
or write flags. Floating-point branches (`bceqz`, `bcnez`) test one of the
floating-point condition codes. Unconditional control flow uses PC-relative `b`
and `bl` for direct jumps and calls, and `jirl` for register-indirect jumps, calls
through a pointer, and returns.

Loads and stores use `ld.d`/`st.d` with a base plus immediate offset,
`ldx.d`/`stx.d` with a base plus index register, or the PC-relative `ldptr.d`. There is
no scaled index. Atomics require natural alignment; ordinary loads and stores may
be unaligned on cores that implement the UAL capability (see Alignment). Atomics come in two
families: the reservation-based `ll.w`/`sc.w` and `ll.d`/`sc.d` pairs, and the
single-instruction `amadd.d`, `amswap.d`, `amand.d`, `amor.d`, `amxor.d`,
`ammax.d`, and `ammin.d`.

Floating point has `fadd.d`, `fsub.d`, `fmul.d`, `fdiv.d`, `fmadd.d`, and
`fsqrt.d`, plus the single-precision forms. Comparisons such as
`fcmp.ceq.d` and `fcmp.clt.d` write a floating-point condition code rather than a
general-purpose register; `fsel` selects a value without branching, and
`movfr2gr.d` and `movgr2fr.d` move values between the FPU and the integer
registers. `fcvt.s.d` and `fcvt.d.s` convert between formats, while `ftint.w.d`
and `ffint.d.w` convert between floating point and integer representations. Vector
instructions follow the same pattern at 128 bits (`vadd.w`, `vld`, `vst`,
`vbitsel.v`, `vshuf.b`) or 256 bits (`xvadd.w`, `xvld`, `xvst`).

System and maintenance instructions are the last group: `dbar` and `ibar` order
memory and instruction fetch, `cacop` performs cache maintenance, `cpucfg`
reports the CPU's features, and `idle` suspends the core.

A few instructions exist mainly to build branchless sequences. `slt` and `sltu`
turn a comparison into a 0/1 value; `maskeqz` and `masknez` use it to select
between two values, and `fsel` does the same for floating point. They are the
alternative to a conditional branch.

## Extensions

LoongArch is defined as a base ISA plus optional extensions. The base is the
64-bit V1.0 instruction set. The optional extensions are LSX (128-bit vectors),
LASX (256-bit vectors), LBT (binary translation instructions, used to accelerate
x86, Arm, and MIPS emulation), and LVZ (virtualization).

LoongArch V1.1 is a later revision of the ISA rather than a separate extension: it
adds instructions such as quadword atomics, reciprocal estimates, and
memory-ordering variants. LA664 implements V1.1, while LA464 implements the V1.0
version only. A V1.1 instruction therefore runs on LA664 but is an illegal
instruction on LA464, so portable binaries should be built for LA464 and use a
dispatched V1.1 path only where the newer instruction actually pays for itself.

The instruction-level semantics of LSX, LASX, and LBT operations are documented
in the [intrinsics guide](https://jia.je/unofficial-loongarch-intrinsics-guide),
which also gives pseudo-code for each intrinsic.

## Alignment

Instruction alignment is fixed: every instruction is 32 bits and 4-byte aligned,
so branch targets and the PC are 4-byte aligned. A misaligned instruction address
is an error.

Data alignment is not fixed by the base ISA. LoongArch defines an optional
unaligned-access capability, reported by the UAL bit of `cpucfg` (CPUCFG1 bit 20).
When UAL is present, ordinary scalar and vector loads and stores may use unaligned
addresses and the hardware handles them. When it is absent, a misaligned access
raises an alignment exception (ALE), which the kernel either emulates in software
or turns into a signal.

The Loongson-3 processors based on LoongArch, including LA464 and LA664, report
UAL, so ordinary unaligned accesses work on both cores. Two caveats remain.
Atomics and `ll`/`sc` require natural alignment, and a misaligned atomic access
raises ALE. And an unaligned vector access is not guaranteed to be atomic or
ordered: the vector manual states that the vector load and store instructions do
not raise alignment exceptions, but also that an unaligned access may be split
across the memory system.

Portable code cannot assume UAL. Some LoongArch cores, such as LA264 in the
2K1000LA, do not implement it, so software that must run everywhere should check
the capability at run time or avoid unaligned accesses altogether. Even where UAL
is present, aligned accesses remain preferable: they avoid cache-line and page
splits, and they keep the atomicity guarantees that unaligned accesses give up.

For source code, the practical rule is unchanged: do not type-pun through a
narrower pointer. Use `memcpy`, read serialization formats field by field, and
align vector buffers when laying out data structures.

## Memory model and address spaces

LoongArch has a weakly ordered memory model: loads and stores to different
addresses may be observed out of order by other cores. `dbar` orders data
accesses, and `ibar` orders instruction fetches with respect to prior stores.
`ll`/`sc` operate on a reservation and must be retried when `sc` fails.

Addresses come in two flavors. Normal memory is mapped through the page tables,
with the usual TLB hierarchy. LoongArch also provides direct-mapped windows
(DMW): a small number of windows that map a range of physical memory with a fixed
memory access type (cached, strongly ordered uncached, or weakly ordered uncached)
without using a page table. Device registers are accessed through an uncached or
weakly ordered uncached window, so that a read reaches the device and a store is
not held in a cache.

I/O is coherent on the Loongson systems supported by Linux: device DMA sees stores
to cached memory, so DMA buffers are ordinary cached memory and the kernel
performs no cache maintenance for them. The instruction and data caches are kept
coherent by hardware as well, so after writing code it is enough to execute
`ibar` to avoid fetching stale instructions. `cacop` is the cache-maintenance
instruction, used for cache management and error handling rather than to make
ordinary data visible.

## ABI

The 64-bit ABI used by Linux is LP64D, which passes floating-point values in
floating-point registers. In the common case:

- integer arguments go in `$a0`–`$a7`, floating-point arguments in `$fa0`–`$fa7`;
- integer results are returned in `$a0` and `$a1`, floating-point results in
  `$fa0` and `$fa1`;
- `$s0`–`$s8`, `$sp`, `$fp`, and `$ra` are callee-saved;
- `$tp` points at thread-local storage;
- the stack is 16-byte aligned.

The exact rules for aggregate arguments and for vector values are in the ABI
specification; the guide only relies on the register roles above.

## What differs between the two cores

Both cores implement the same ISA family, so the material in this section applies
to both. They differ in which optional instructions are implemented and in how the
core executes them, not in what the instructions mean.

LA664 is the newer core. It implements LoongArch V1.1, adds SMT, and has more
out-of-order and execution resources. LA464 is the older baseline and implements
V1.0 only, so V1.1 instructions are illegal on it. Code that has to run everywhere
should be compiled for LA464, with V1.1 instructions confined to a dispatched
path.

The following sections split the microarchitectural details per core when the
mechanism differs, and say so when the two cores behave the same.
