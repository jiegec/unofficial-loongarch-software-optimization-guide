---
hide:
  - toc
---
# Microarchitecture overview

This chapter is the processor model the rest of the guide refers to. It starts at
the front end, follows instructions through execution, and explains what each
mechanism means for software. Most sections begin with the principle behind a
mechanism, then document LA664 and LA464; where the two cores agree, the section
says so. The cache hierarchy and the branch section are organized by mechanism
instead, with the per-core differences inside each topic.

The chapter opens with the instruction set architecture. That section is not a
manual replacement; it collects the register file, instruction formats and
classes, extensions, alignment rules, memory model, and ABI facts that later
sections assume.

The processor block diagram then shows the pipeline as a whole, from fetch and
schedulers to the execution pipes, load-store unit, caches, and retirement, with
the two cores side by side so their structural differences are visible early.

Next come the two sections about memory addressing. Cache hierarchy goes through
the L1 instruction and data caches, L2, and L3: capacity, associativity, line
size, ports, and what each of those means for software.
Address translation covers the TLBs, page-table walkers, page sizes and huge
pages, and the cached and uncached address windows that select memory attributes.

Two sections deal with control flow. Optimizing branching explains direction and
target prediction, the return-address stack, branch density, the cost of a
misprediction, branchless code, and loop alignment. Instruction fetch and decode
picks up where that leaves off: fetch blocks, instruction buffers, decode width
and restrictions, dispatch and retire, front-end caching, and spin loops.

The execution sections describe what actually runs. Integer execution has the ALU
pipes, multiply and divide, shifts and bit-field instructions, conditional
selects, and the port restrictions that decide how many of them can run at once.
Floating-point execution has the FP pipes, FMA, divide and square root,
conversions, denormals and rounding modes, and the trade-off
between FMA and a separate multiply and add. Vector execution (LSX and LASX)
goes through the 128-bit and 256-bit resources, mixing vector widths, and
alignment, and points to the intrinsics guide for instruction-level semantics.
Binary translation execution (LBT) covers the instructions that accelerate x86,
Arm, and MIPS emulation, and what they mean for translator performance.

The memory side of the chapter is split between the load-store unit and data
prefetching. The load-store unit covers load and store queues, store-to-load
forwarding, unaligned accesses, and the addressing modes the ISA provides. Data
prefetching covers the hardware prefetchers and the `preld` software prefetch,
including prefetch distance and cache-pollution trade-offs.

Finally, simultaneous multithreading explains how LA664 shares a core between two
threads, which resources are shared, and why LA464 has no SMT. Core-to-core
latency then shows what a cache-line transfer costs between cores on the 3C5000
and 3C6000/S. Atomics and memory ordering finishes the chapter with LL/SC and
`am*`, `dbar` and `ibar`, and the locking idioms that follow from the memory
model.

LA664 is the newer core: it implements LoongArch V1.1, supports SMT, and its
out-of-order and execution resources are larger than LA464's. LA464 is the older
baseline and implements V1.0 only, so code that must run on both has to treat it
as the reference. Sections call out the differences where they change what
software should do, and say so explicitly when the two cores behave the same.
