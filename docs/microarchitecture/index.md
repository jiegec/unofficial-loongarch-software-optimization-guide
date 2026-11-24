# Microarchitecture

This chapter is the processor model that the rest of the guide refers to. It
walks through the core from the structures that feed it to the structures that
retire its results, and explains what each mechanism means for software. Every
section starts with the principle behind a mechanism, then documents LA664 and
LA464 separately, and says so when the two cores behave the same.

The chapter opens with the instruction set architecture: the register file,
instruction formats and classes, optional extensions, alignment rules, the memory
model, and the ABI facts that every later section assumes. It is the ISA-level
subset that shows up in optimization decisions, not a replacement for the
LoongArch manuals.

The processor block diagram then draws the pipeline as a whole — front end,
schedulers, integer, floating-point and vector pipes, load-store unit, caches, and
retire path — and puts the two cores side by side so that their structural
differences are visible before the details arrive.

Cache hierarchy describes the L1 instruction and data caches, L2, and L3: capacity,
associativity, line size, ports, replacement policy, and the software consequences
of each. Address translation covers the TLBs, the page-table walkers, page sizes
and huge pages, and the cached and uncached address windows that select memory
attributes.

Optimizing branching is about the front end's control-flow decisions: direction
and target prediction, the return-address stack, branch density, the cost of a
misprediction, branchless code, and loop alignment. Instruction fetch and decode
continues through the same part of the core: fetch blocks, instruction buffers,
decode width and restrictions, dispatch and retire, front-end caching, and the
behavior of spin loops.

The execution sections cover where the work happens. Integer execution describes
the ALU and address-generation pipes, multiply and divide, shifts and bit-field
instructions, conditional selects, and the port restrictions that decide how many
of them can run at once. Floating-point execution covers the floating-point pipes,
FMA, divide and square root, conversions, denormals and rounding modes, and when
FMA is preferable to a separate multiply and add. Vector execution (LSX and LASX)
covers the 128-bit and 256-bit execution resources, mixing vector widths, and
alignment, and points at the intrinsics guide for instruction-level semantics.
Binary translation execution (LBT) covers the instructions used to accelerate
x86, Arm, and MIPS emulation, and what they mean for translator performance.

The memory side of the chapter is split between the load-store unit and data
prefetching. The load-store unit covers load and store queues, store-to-load
forwarding, unaligned accesses, and the addressing modes the ISA provides. Data
prefetching covers the hardware prefetchers and the `preld` software prefetch,
including prefetch distance and cache-pollution trade-offs.

Finally, simultaneous multithreading explains how LA664 shares a core between two
threads and which resources are shared, and why LA464 has no SMT. Atomics and
memory ordering covers the LL/SC and `am*` instructions, `dbar` and `ibar`, and
the locking idioms that follow from the memory model.

LA664 is the newer core: it implements LoongArch V1.1, supports SMT, and its
out-of-order and execution resources are larger than LA464's. LA464 is the older
baseline and implements V1.0 only, so code that must run on both has to treat it as
the reference. Sections call out the differences
where they change what software should do, and say so explicitly when the two
cores behave the same.
