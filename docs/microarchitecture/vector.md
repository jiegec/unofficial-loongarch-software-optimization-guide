# Vector execution (LSX and LASX)

LoongArch has two vector extensions: LSX with 128-bit registers and LASX with
256-bit registers. Both use 32 architectural vector registers, and both are
exposed as C intrinsics in GCC and LLVM. The register files overlap: the FP
registers are the low 64 bits of the LSX registers, and the LSX registers are the
low 128 bits of the LASX registers.

The vector unit is the widest execution resource in both cores. For dense,
regular data it is also the cheapest way to get work done. For irregular data the
shuffles and the lack of horizontal operations can eat the gain, so vector code
is worth writing where the data layout is under control.

## Execution resources

LA664 has four FP/vector pipes, and all four can execute 256-bit packed FP adds.
Packed 256-bit FP multiply and the basic vector integer operations perform at
roughly Zen 2 levels. FMA throughput is two per cycle on both cores, so the gain
over the older core comes from the extra pipes for adds, compares, and integer
work rather than from a faster FMA.

LA464 has two 256-bit vector pipes. Vector integer adds are single-cycle, and the
core can start two 256-bit vector integer multiplies per cycle, which is a real
strength for integer SIMD. FP add, multiply, and FMA take 5 cycles, and FMA
throughput is two per cycle.

According to LoongPerf, `vadd.w` and `xvadd.w` have 1-cycle latency and reach
4 IPC on LA664, against 2 IPC on LA464. `vmul.w` has 4-cycle latency on both
cores, and `vfmul.d` and `vfmadd.d` take 5. `vfadd` and `vfsub` fall from 5
cycles on LA464 to 3 on LA664.

Both cores implement LASX natively at 256 bits rather than splitting every
operation into two 128-bit halves. An LASX instruction therefore buys the same
work as two LSX instructions without doubling the instruction count, and that
matters on cores without a micro-op cache.

The load/store side keeps up. LA664's L1D can serve two 256-bit accesses per
cycle in any mix of loads and stores, and LA464 can serve two 256-bit loads or one
load plus one store. A vector loop that is limited by L1D bandwidth is therefore
limited by something other than the vector pipes.

## Data types and instruction classes

LSX and LASX support 8-, 16-, 32-, and 64-bit integer elements, plus single and
double precision floating point. The instructions fall into a few groups that
behave differently.

Element-wise arithmetic (`vadd`, `vsub`, `vmul`, `xvadd`, `xvsub`, `xvmul`, and
the FP forms) is the fast path. Saturating forms (`vsadd`, `vssub`, `xvsadd`,
`xvssub`) clamp instead of wrapping and are cheaper than a manual clamp sequence.
Widening and narrowing forms (`vaddwev`, `vaddwod`, `vssran`, `xvaddwev`, and
friends) do the width conversion inside the operation, which is usually better
than widening first and adding later.

Comparisons produce a vector of all-ones or all-zeros masks. There is no mask
register file. The mask is consumed by `vbitsel.v` or by bitwise operations, so a
select is a compare plus a `vbitsel`, not a compare plus a branch. This is the
same branchless idea as the integer select sequences, applied to vectors.

Shuffles and permutations (`vshuf.b`, `vshuf4i`, `vpermi.w`, `vext2xv`,
`xvpickve`, and their LASX forms) have a 1-cycle latency, and LoongPerf measures
`vshuf.b` and `xvshuf.b` at two per cycle on both cores. They are not a throughput
bottleneck by themselves, but they consume issue slots and registers, and a long
chain of shuffles is still a dependency chain. A layout that avoids shuffles is
worth more than a clever shuffle sequence, not because the shuffle unit is slow,
but because the surrounding code gets simpler.

The vector integer divider is a separate unit with a larger fixed cost. LoongPerf
gives 8 to 26 cycles for signed 64-bit elements, 11 to 31 for 32-bit, 17 to 41
for 16-bit, and 29 to 61 for 8-bit, with the range coming from the quotient
width; the unsigned forms are a little wider.
Lanes are processed in parallel, so LSX and LASX have the same latency even
though LASX carries twice as many lanes, and a partly active vector costs less
than a full one. Narrow element divides are the slowest, which is the opposite of
the usual intuition.

There is no horizontal add or horizontal max. Reductions are built from pairwise
operations and a final horizontal step, and their cost is logarithmic in the
lane count plus the horizontal step. Keeping a scalar accumulator for a reduction
inside the loop and doing the horizontal step once at the end is usually faster
than reducing every iteration.

`vldrepl` and `xvldrepl` load one element from memory and broadcast it to every
lane, which is cheaper than a load plus a shuffle. `vldx` and `xvldx` take a
register offset instead of an immediate, which is useful for gather-like patterns
but has the same address-generation cost as any indexed access.

## Memory and alignment

Vector loads and stores are `vld`/`vst` and `xvld`/`xvst`, with indexed forms.
The LoongArch vector manual states that these instructions do not raise
alignment exceptions, so an unaligned vector access works. It can still be split
across the memory system, and the manual notes that an unaligned vector access is
not guaranteed to be atomic or ordered.

For performance, align vector buffers to 32 bytes for LASX and 16 for LSX, or to
the cache line if the data is also streamed. A vector access that crosses a cache
line costs more than an aligned one, and one that crosses a page boundary costs
more still. Handling the head and tail of a loop with scalar or LSX code is
usually cheaper than misaligning the whole loop for a few elements.

The 256-bit load and store bandwidth is real, so a vector loop should use full
width accesses. Loading a vector as four scalar loads and assembling it with
shuffles defeats both the load path and the shuffle units.

## Mixing LSX, LASX, and scalar FP

The overlapping register files create the only subtle correctness and performance
issue in vector code. Writing an `$f` register leaves the upper bits of the
corresponding `$v` and `$x` registers alone, and writing a `$v` register leaves
the upper 128 bits of the `$x` register alone. If the core tracks the upper bits
as dirty, a later wider read or write may need a merge.

The usual rules follow. Pick one width for a hot region and stay with it. Zero the
full width with `vxor.v` or `xvxor.v` when switching between widths or when
clearing a register. Avoid passing values between scalar FP and vector code in
the middle of a loop; do the conversion at the edges.

GCC and LLVM handle these merges when intrinsics are used correctly, but
hand-written assembly has to do it explicitly. The ABI defines how vector
arguments and return values are passed, and the compiler inserts the necessary
merges at function boundaries.

## What this means for software

Use the widest vector that the data allows. LASX is native 256-bit on both cores,
so a 256-bit operation does twice the work of a 128-bit one for the same
instruction count, and the instruction count is what the front end pays for.

Choose a data layout that avoids extra shuffle instructions. Structure-of-arrays layouts, padded
rows, and element sizes that match the operation are worth more than any
instruction-level trick. If a kernel needs a transpose or a wide permutation in
the inner loop, consider changing the layout instead.

Use saturating and widening instructions instead of manual clamp or convert
sequences. They are single instructions and they keep the dependency chain short.

Keep reductions out of the inner loop. Accumulate into a vector, then do one
horizontal step at the end. For FP reductions, several vector accumulators hide
the FMA latency, and the one-FMA-per-cycle limit still applies.

## What to measure

Per-instruction latency and throughput are in
[Instruction latency and throughput](../latency-throughput.md). The vector
numbers worth measuring on each core are the throughput of element-wise add,
multiply, and compare, the throughput and latency of the shuffle group, the
latency of vector loads and stores, and the penalty for an unaligned access.

The instruction-level semantics of LSX, LASX, and LBT operations are documented
in the [Unofficial LoongArch Intrinsics Guide](https://jia.je/unofficial-loongarch-intrinsics-guide),
with pseudo-code for each intrinsic.
