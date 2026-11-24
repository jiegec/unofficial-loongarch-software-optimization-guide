# Integer execution

Integer code is most of what a compiler emits, and on LoongArch it is also the
easiest part of the core to reason about: the instructions are simple, the
register file is 32 entries with `$r0` hardwired to zero, and most operations are
single-cycle. The interesting parts are the exceptions: multiply, divide, the
bit-field instructions, and the conditional-select sequences that replace
branches.

## Execution resources

LA664 has four integer ALUs fed by a 48-entry integer scheduler. Two of the ALUs
can execute branch instructions, and two have integer multiply capability.
Rename is 6-wide and the ROB holds 256 entries, so the core can keep a lot of
integer work in flight.

LA464 also has four ALUs, a big step up from the two ALUs of the GS464E it
evolved from. Only one branch can resolve per cycle, and two ALUs can multiply.
Rename is 4-wide and the ROB holds 128 entries. All of the integer pipes share a
single unified scheduler rather than the three separate queues on LA664.

Simple operations such as `add.d`, `and`, `or`, `xor`, `slt`, and the shifts are
single-cycle on both cores. What differs is how many can start per cycle and how
much room the schedulers have to find independent work.

## Multiply and divide

`mul.d` produces the low half of a 64-bit product, `mulh.d` and `mulhu.d` the
signed and unsigned high halves, with `.w` forms for 32-bit results. The two
multiply pipes mean the core can start two independent multiplies per cycle.
LA464's multiply latency is 4 cycles. LA664 has the same two-pipe arrangement; its
latency is not in the public material, so measure it before relying on a number.

Division is the slow case. `div.d` and `mod.d` produce quotient and remainder, and
the operation is iterative, so latency depends on the operand values. Chips and
Cheese measured divide throughput improving from roughly one divide every nine
cycles on LA464 to about one every four cycles on LA664. The latency depends strongly on the divisor's magnitude, which is the usual
behavior for an iterative divider.

Code that divides by a constant should let the compiler turn it into a multiply
and a shift. Code that divides inside a loop should be restructured, or replaced
with a reciprocal estimate and a Newton step when the exact quotient is not
required. The integer divider is the one execution unit where a small algorithmic
change usually beats any instruction-level tweak.

## Bit fields and conditional selects

LoongArch has a full set of bit-manipulation instructions and they are worth
using. `bstrins.d` and `bstrpick.d` insert or extract an arbitrary bit field in one
instruction, `bytepick.d` assembles a value from two registers at byte
granularity, `revb.2h`, `revb.4h`, `revb.2w`, and `revb.d` reverse byte order,
`clz.w`/`clz.d` and `ctz.w`/`ctz.d` count leading and trailing zeros, `crc32.w`
and `crc32.d` accumulate CRC, and `alsl.d` combines a shift with an add. Each of
these replaces a short sequence of shifts, masks, and adds.

Conditional assignment is the other place where instruction selection matters.
`slt` and `sltu` produce a 0 or 1, and `maskeqz`/`masknez` turn that into a
select. A short sequence can replace a branch when the branch is genuinely
unpredictable, and it avoids the front-end cost of a misprediction.
When the branch is predictable, the branch is usually cheaper, so this is a
trade-off to measure.

The `$r0` register is hardwired to zero, which makes zeroing cheap in terms of
register pressure but not necessarily in terms of execution slots. LA664
recognizes zeroing at rename and eliminates it, so `or rD, $r0, $r0` or
`xor rD, rD, rD` does not occupy an ALU. LA464 has no such optimization, and the
instruction takes a slot.

## What this means for software

Keep dependency chains short and give the scheduler independent work. The ROB is twice as large on LA664 and
the scheduler is split into three queues, so a loop that is latency-bound on LA464
may become throughput-bound on LA664, and unrolling that helps one may not help
the other.

Spread work across the pipes. A loop that is all multiplies is limited by the two
multiply pipes no matter how wide the rest of the core is; mixing multiplies with
adds and loads keeps all four ALUs busy. The same applies to branches: only two
of LA664's ALUs can execute them, and LA464 resolves one branch per cycle, so a
branch-heavy loop can leave the other ALUs idle.

Use the bit-field instructions instead of hand-written shift-and-mask sequences.
They reduce instruction count, which matters on cores without a micro-op cache,
and they often have the same single-cycle latency as a plain ALU operation.

Avoid division in hot loops. If the divisor is a constant, the compiler can
strength-reduce it. If it is not, consider a reciprocal or a different algorithm.
The divider's data-dependent latency is the most predictable performance problem
in the integer unit.

## What to measure

Per-instruction latency and throughput are maintained in
[Instruction latency and throughput](../latency-throughput.md), so this page does
not duplicate them. The useful measurements for integer code are the latency of
each operation class, the number of pipes that can accept it, and the throughput
of a mixed stream that resembles the real loop.

Divide deserves its own sweep over operand values, since a single number does not
describe it. Multiply and the bit-field instructions are easier: one latency and
one reciprocal throughput are enough if the measurement is taken on independent
operations.

## Sources

- [Loongson 3A6000: A Star among Chinese CPUs](https://chipsandcheese.com/p/loongson-3a6000-a-star-among-chinese-cpus)
- [Loongson's 3A5000: China's Best Shot?](https://chipsandcheese.com/p/loongsons-3a5000-chinas-best-shot)
- LoongArch Reference Manual, volume 3, for the integer instruction set.
