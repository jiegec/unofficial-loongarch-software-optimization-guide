# Floating-point execution

The floating-point unit is a co-processor with its own register file, renaming,
and schedulers. On LoongArch it supports single and double precision, fused
multiply-add, and the conversions needed to move values between formats and
between the FPU and the integer registers. Both cores run FP code at a fraction
of their integer throughput, so the shape of an FP loop matters more than the
individual instruction latencies.

## Execution resources

LA664 has four FP/vector pipes. All four can execute 256-bit packed FP adds,
and LoongPerf measures scalar `fadd.d` and `fsub.d` at 4 IPC, twice LA464's 2.
Scalar `fmul.d` and `fmadd.d` run at 2 IPC. Packed 256-bit multiply and basic
vector integer operations perform at roughly Zen 2 levels. FP add latency is 3
cycles.

LA464 has two 256-bit vector pipes. FP add, multiply, and FMA all take 5 cycles,
and LoongPerf measures scalar FP ALU operations at 2 IPC and FMA at 2 IPC. The
two-pipe arrangement is a conservative LASX implementation, but it is still native
256-bit rather than two 128-bit halves.

Both cores have 32 FP registers (`$f0` to `$f31`) that alias the low 64 bits of
the LSX registers. That aliasing matters when scalar and vector code are mixed,
and it is covered in [Vector execution](vector.md) only
briefly, so keep it in mind here: a scalar write does not necessarily clear the
upper bits of the vector register that shares the number.

LoongPerf measures FMA throughput at two per cycle on both cores, so the FMA
rate did not change with the newer core. Chips and Cheese reports one per cycle;
the independent-lane measurement is used here. The gain over LA464 is in latency,
in scalar add and subtract throughput, and in the four pipes for packed adds
rather than in fused multiply-add.

## Dependency chains

FP code is usually limited by a dependency chain rather than by instruction
count. A dot product with a single accumulator turns into a chain of FMAs, and
the chain latency, not the FMA throughput, sets the speed. Unrolling with four
accumulators breaks the chain and lets the core issue two FMAs per cycle instead
of one every few cycles; two per cycle is still the ceiling.

According to LoongPerf, `fmul.d` and `fmadd.d` have 5-cycle latency on both
cores. The scalar conversions are cheap: `fcvt.d.s` and `fcvt.s.d` take 2 cycles,
while `ftint.w.d` and `ffint.d.w` take 4. Moving between the FPU and the integer
registers costs 2 cycles in either direction (`movfr2gr.d`, `movgr2fr.d`), and
`fsel` is 1 cycle on both cores. `fcmp.ceq.d` is 1 cycle on LA664 and 2 on LA464.
FCC moves are much cheaper on LA664: LoongPerf puts `movcf2gr` at 2 cycles
against 7 on LA464, and `movgr2cf` at 2 against 15.

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
LoongPerf fits the unit as a digit-at-a-time datapath that retires four mantissa
bits per cycle. For double precision, an inexact `fdiv.d` takes 23 cycles and an
inexact `fsqrt.d` takes 36. Single precision is 16 and 22. Exact results,
zero, infinity, and NaN short-circuit the unit and finish in 8 to 11 cycles, and
a subnormal operand adds one digit time. The divider and square root behave the
same on LA464 and LA664, so the numbers are not a reason to prefer one core for
this code.

The vector forms follow the scalar unit for 64-bit lanes: `vfdiv.d` is 23 cycles,
and `vfsqrt.d` is 36. Single precision is the odd case, because the vector unit
makes two passes for it: `vfdiv.s` is 27 cycles, slower than the scalar 16. A
single-precision vector divide is not a throughput win over scalar unless the
lane count is high enough to pay for the extra passes.

When the last bits are not required, the usual pattern is an estimate followed by
a Newton iteration. LoongPerf measures `frsqrte.d` and `frecipe.d` at 5 cycles on LA664. One or two Newton steps, each
a few FMA operations, turn the estimate into a result that is accurate enough for
most graphics, physics, and machine-learning code, and the whole sequence is still
well under the 23 cycles of a hardware divide.

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
expect more than two FMAs per cycle. Keep the number of conversions and
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
[Instruction latency and throughput](../latency-throughput.md), and LoongPerf
covers the divide and square root classes. The remaining unknowns are the
denormal penalty for add, multiply, and FMA, the conversion latencies, and the
cost of a rounding-mode change.
