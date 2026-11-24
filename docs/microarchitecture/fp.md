# Floating-point execution

The floating-point unit is a co-processor with its own register file, renaming,
and schedulers. On LoongArch it supports single and double precision, fused
multiply-add, and the conversions needed to move values between formats and
between the FPU and the integer registers. Both cores run FP code at a fraction
of their integer throughput, so the shape of an FP loop matters more than the
individual instruction latencies.

## Execution resources

LA664 has four FP/vector pipes. All four can execute 256-bit packed FP adds,
which gives it strong vector FP throughput for a core at this clock. Scalar FP is
more restricted: only two pipes handle scalar FP adds, and scalar FP multiplies
appear to use different pipes from the vector ones. Packed 256-bit multiply and
basic vector integer operations perform at roughly Zen 2 levels. FP add latency
is 3 cycles, and the core can start one FMA per cycle.

LA464 has two 256-bit vector pipes. FP add, multiply, and FMA all take 5 cycles,
and FMA throughput is one per cycle. The two-pipe arrangement is a conservative
LASX implementation, but it is still native 256-bit rather than two 128-bit
halves.

Both cores have 32 FP registers (`$f0` to `$f31`) that alias the low 64 bits of
the LSX registers. That aliasing matters when scalar and vector code are mixed,
and it is covered in [Vector execution](vector.md) only
briefly, so keep it in mind here: a scalar write does not necessarily clear the
upper bits of the vector register that shares the number.

FMA throughput is one per cycle on both cores. That is half of what Zen 2 or
Skylake can do, and it is the number that caps a dot product or a matrix
multiply. Adding more FP pipes did not raise the FMA rate, so the newer core's
advantage is in latency, vector width utilization, and the four pipes for packed
adds rather than in fused multiply-add.

## Dependency chains

FP code is usually limited by a dependency chain rather than by instruction
count. A dot product with a single accumulator turns into a chain of FMAs, and
the chain latency, not the FMA throughput, sets the speed. Unrolling with four
accumulators breaks the chain and lets the core issue one FMA per cycle instead
of one every few cycles; the FMA throughput of one per cycle is still the
ceiling.

The FMA-versus-multiply-and-add choice depends on where the critical path is. If
the chain goes through the product, FMA is shorter than a multiply followed by an
add. If the chain goes through the addend, an FADD can have a shorter latency than the
FMA, and separate operations can be better for that particular chain. When none
of the operands is on the critical path, FMA is still the better choice because
it is one instruction and one pipe slot.

Conversions and moves are part of the chain too. `fcvt.s.d` and `fcvt.d.s`
convert between formats, `ftint.w.d` and `ffint.d.w` convert between floating
point and integer, and `movfr2gr.d` and `movgr2fr.d` move values between the FPU
and the integer registers. The last pair crosses the domain boundary and is
usually the most expensive. Keeping values in FP registers and converting only at
the edges of a routine avoids both the latency and the pipe conflict.

## Division, square root, and estimates

Division and square root are iterative and much slower than add or multiply.
Neither vendor publishes a single latency, because the result depends on the
operands, and the safe assumption is that a divide in an inner loop is a mistake
unless the algorithm needs it.

When the last bits are not required, the usual pattern is an estimate followed by
a Newton iteration. `frsqrte` gives a reciprocal square root estimate on both
cores, and `frecipe` adds a reciprocal estimate on LA664. One or two Newton steps
turn the estimate into a result that is accurate enough for most graphics,
physics, and machine-learning code, and the whole sequence is still cheaper than
a hardware divide.

If the exact result is required, keep the divide out of the loop: compute the
reciprocal once and multiply, or restructure the algorithm so that the division
is amortized. The same applies to square root.

## Denormals, rounding, and FCSR

The rounding mode lives in FCSR and applies to every FP operation. Changing it
inside a loop can serialize the FPU, so set it once at the start of a region and
leave it alone. The default round-to-nearest is the fast path on both cores.

Denormal inputs and results are handled by the hardware. LoongArch does not
provide an x86-style flush-to-zero or denormals-as-zero control, so there is no
switch that makes them free. Whether a denormal costs extra cycles depends on the
operation and the core, and it has to be measured. Code that produces very small
values on purpose, such as audio or certain ML kernels, should either keep the
values in a normal range or accept the cost.

FCSR also holds the exception flags. Reading it with `movfcsr2gr` is not free,
and checking flags after every operation defeats the point of a pipelined FPU.
Check exceptions at the end of a region, not inside the loop.

## What this means for software

Use vector FP where the data allows it. LA664's four 256-bit pipes are the
fastest execution resource in the core, and LA464's two pipes still beat scalar
code. Scalar FP on LA664 is limited to two add pipes and a separate multiply
path, so a scalar-heavy loop leaves most of the FPU idle.

Unroll dot products and similar reductions with several accumulators, but do not
expect more than one FMA per cycle. Keep the number of conversions and
register-crossing moves small, and keep rounding-mode changes out of the loop.

Do not divide inside a loop unless the algorithm requires it. Use `frsqrte`
(and `frecipe` on LA664) with a Newton step when approximate results are
acceptable, and amortize exact division when they are not.

Finally, be careful when mixing scalar and vector code. Writing an `$f` register
updates the low 64 bits of the corresponding vector register, and the core may
have to merge the rest. Choose one width for a hot region, and zero the full
vector width when switching.

## What to measure

Per-instruction latency and throughput are in
[Instruction latency and throughput](../latency-throughput.md). The numbers that
are not published, and that are worth measuring on each core, are the divide and
square root latency over a range of operands, the denormal penalty for add,
multiply, and FMA, the conversion latencies, and the cost of a rounding-mode
change.

## Sources

- [Loongson 3A6000: A Star among Chinese CPUs](https://chipsandcheese.com/p/loongson-3a6000-a-star-among-chinese-cpus)
- [Loongson's 3A5000: China's Best Shot?](https://chipsandcheese.com/p/loongsons-3a5000-chinas-best-shot)
- LoongArch Reference Manual, volumes 1 and 3, for FCSR, conversions, and the FP instruction set.
