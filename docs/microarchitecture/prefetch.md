# Data prefetching

Prefetching moves data closer to the core before it is needed. It trades memory
bandwidth and cache capacity for lower latency, and it can hurt: a prefetch that
brings in a line that is never used evicts something useful and consumes
bandwidth. On LoongArch the software side is a single instruction, `preld`, and
the hardware side is much less documented than on x86.

## Hardware prefetchers

LA464 has an L2 prefetch engine: a sequential 16-line test shows lines beyond
the demand line arriving in L2. The public documentation does not describe its
stream or stride detectors, and the LA664 data prefetcher has not been measured
here. That does not mean there is none; it means the behavior has to be measured
rather than assumed.

What is safe to say is that both cores fill a 64-byte line on a miss and that
sequential, unit-stride access is the pattern any prefetcher is built for. If a
loop walks an array forward, the hardware is likely to help. If it walks a linked
list in random order, no hardware prefetcher can predict the next address, and
software prefetching is the only option.

A stride sweep is the way to find out what the hardware does. Time a loop that
reads with strides of 1, 2, 4, 8, and so on, at sizes that fit in L1D, L2, and
L3, and compare with a version that touches every line. A prefetcher shows up as
a stride range where the loop is faster than the no-prefetch baseline. The same
sweep with a large random permutation shows whether prefetching hurts when the
pattern is unpredictable.

Instruction prefetch has not been demonstrated. A NOP-footprint sweep sees a
sharp drop once the loop leaves L1I, which is what the absence of an
instruction prefetcher would look like. Other tests had suggested some linear
prefetch, but they do not prove it exists. A branchy interpreter should not rely
on instruction prefetch, which is one reason the instruction cache footprint
matters so much. It is not a reason to add data prefetches.

## Software prefetch: preld

`preld hint, rj, si12` prefetches the line containing `rj + si12`. `preldx` does
the same with a register offset. The hint field selects the kind of prefetch and
is implementation-defined beyond the values the compiler uses. GCC emits
`preld 0` for a read prefetch and `preld 8` for a write prefetch, which is the
mapping `__builtin_prefetch(addr, rw, locality)` uses; the locality argument has
no separate encoding in the compiler's output, so it should not be relied on.

According to LoongPerf, `preld` and `preldx` both issue at one per cycle on
LA664 and LA464, so each prefetch costs an instruction slot even when the line
is already in cache.

The instruction is a hint. A core may ignore it, and it may be dropped when the
line cannot be prefetched. That makes it safe to sprinkle in code, but it also
means a prefetch that does nothing is invisible unless the code is measured.

The useful parameter is distance. A prefetch has to be issued far enough ahead to
cover the miss latency, but not so far ahead that the line is evicted before use.
At 2.5 GHz, an L3 hit on the 4-core desktop parts is about 40 cycles, an L2 hit
12 to 14, and a DRAM access about 260 cycles on LA664 and 360 on LA464. The
server parts are slower: the measured L3 latency is about 48 cycles on the
3C6000/S and 65 on the 3C5000. If a loop takes 20 cycles per
iteration, a DRAM-bound load needs to be prefetched roughly 13 to 18 iterations
ahead. That is the calculation to start from, and then to tune by measurement.

Prefetch one line per instruction, not one element. A 64-byte line covers 16
32-bit elements or 8 64-bit ones, so a loop that prefetches every element is
issuing 8 to 16 times more prefetches than it needs. Prefetching every second or
fourth iteration is usually enough for a unit-stride loop.

Do not prefetch across a page boundary unless the next page is known to be
mapped. A prefetch to an unmapped page may be dropped or may cost a page walk,
and either way it is not helping. For a loop that runs to the end of an array,
stop prefetching a few iterations before the end, or prefetch only within the
current page.

## Prefetching and cache pollution

Prefetching is most useful when the data is used once and the latency is on the
critical path. It is least useful when the data is already in cache, when it will
be reused many times, or when the access pattern is random.

A prefetch that misses in L3 and goes to DRAM consumes bandwidth that another
thread could use, and it can evict a line that a different loop was about to
reuse. On a four-core part with a shared 16 MB L3, that interference is real. A
workload that is already bandwidth-bound usually gets slower when prefetches are
added, not faster.

The other pollution case is prefetching too far ahead. A line that arrives 100
iterations early may be evicted before it is used, and the prefetch has then
cost bandwidth for nothing. This is why the distance has to be tuned to the
working set, not just to the miss latency.

## What the compiler does

GCC enables `-fprefetch-loop-arrays` at `-O3` and models four simultaneous
prefetches; LLVM's TTI asks for a prefetch distance of 200 iterations and enables write
prefetching. Both lower `__builtin_prefetch` to `preld 0` for reads and `preld 8`
for writes; the locality argument is not encoded separately. Check the generated
`preld` before adding manual prefetches, because `-O3` may already have inserted
them.

## What this means for software

Use `__builtin_prefetch` rather than hand-written `preld` unless there is a
reason to control the hint. The compiler knows the address form and will pick
`preld` or `preldx` as appropriate.

Start with the loops that are latency-bound and have a predictable address
pattern: pointer chasing through a linked structure, a loop over a large array
that misses L3, or a streaming store. Add a prefetch at the calculated distance,
measure, and adjust. If the loop is already bandwidth-bound or the data fits in
L2, the prefetch is more likely to hurt than help.

For pointer chasing, prefetching several nodes ahead is often the only way to
hide the dependent misses. The addresses are not known until the previous node is
loaded, so the prefetch has to be issued speculatively or the structure has to be
changed to expose more parallelism.

For streaming stores, the write hint tells the core that the line will be
overwritten. Whether that avoids a read-for-ownership depends on the core and is
worth measuring; on a write-once stream it can be a large win.

## Measuring prefetch behavior

The hardware prefetcher behavior is unknown, so measure it with stride and
stream sweeps before writing software prefetches. For `preld` itself, measure the
hint mapping (which level is filled, whether a write hint changes the state), the
distance that minimizes time for a DRAM-bound loop, and the slowdown when the
same prefetches are added to a bandwidth-bound loop.

Per-instruction latency and throughput for `preld` and `preldx` are in
[Instruction latency and throughput](../latency-throughput.md).
