# Instruction fetch and decode

The front end turns instruction bytes into macro-ops. It fetches from the L1I,
decodes, renames, and hands work to the schedulers. LoongArch makes the decode
part simpler than x86 because every instruction is 32 bits and 4-byte aligned:
there are no prefixes, no variable-length encodings, and no instruction boundary
to recover after a mispredicted branch. What remains is bandwidth, buffer depth,
and the cost of missing in the instruction cache.

## Fetch and decode

Both cores have a 64 KB, 4-way L1I. That is twice the 32 KB that contemporary x86
cores carry, and it is there for a reason: neither core has a micro-op cache, so
every instruction has to be fetched and decoded every time it executes. There is
no replay of decoded operations, so decode width is a hard ceiling. Both cores
fetch up to 8 instructions per cycle, or 32 bytes per cycle. Chips and Cheese
estimated 24 bytes per cycle from the issue width; the cross-page fetch test
measures 32 on both cores.

LA664 decodes 6 instructions per cycle. With the instruction stream coming from
L2 it can sustain about 3 IPC, which is a large improvement over LA464. From L3
it drops below 2 IPC, so a code footprint that spills out of L2 still costs
throughput. A NOP-footprint sweep sees a sharp drop once the loop leaves L1I,
which is consistent with no instruction prefetcher; other tests had suggested
linear prefetch. Either way, instruction prefetch does not replace a
large BTB when branches are unpredictable.

LA464 decodes 4 instructions per cycle. Fetching code from L2 is slower than
fetching it from L3 on this core, which is unusual and suggests the L2 path is
doing instruction-cache coherency work that the L3 path can avoid. The practical
effect is that code outside the 64 KB L1I runs at a lower instruction rate, and
the large L1I is what keeps the common case fast. The NOP sweep shows the same
sharp drop beyond L1I, suggesting no instruction prefetcher.

The instruction buffer depth is not public. What is observable is the throughput: LA664 holds roughly 3 IPC
while the code fits in L2, and LA464's instruction bandwidth from L2 is its weak
point, so it does not sustain the same rate.

## Rename and dispatch

LA664 renames 6 instructions per cycle into a 256-entry ROB. Two renamer
optimizations are worth knowing. The first is register zeroing: when an
instruction writes zero, the renamer eliminates it instead of sending it to an
ALU. The second is dependent register-to-register moves, which can run at two per
cycle, though moves still occupy an ALU pipe rather than being free. After
rename, three schedulers of 48 entries each hold work for the integer, memory,
and FP/vector pipes.

LA464 renames 4 instructions per cycle into a 128-entry ROB. Its renamer has no
zeroing or move elimination; every instruction that reaches rename goes on to
occupy an execution slot. After rename, three 32-entry queues hold memory,
integer, and vector work.

The zeroing case is easy to see in compiler output. A zeroing instruction such
as `or rD, $r0, $r0` does not consume an ALU slot on LA664. On LA464 the same
instruction still costs a slot, so a hot loop full of zeroing is measurably
cheaper on the newer core.

## No front-end cache

The absence of a micro-op cache is the single most important front-end fact
about both cores. On AMD and Intel cores, a hot loop can run from an op cache and
bypass fetch and decode entirely, which raises throughput above the decode width
and lowers power. Here, decode width is a hard ceiling, and code size translates
directly into decode work.

That changes the usual advice. On a core with an op cache, unrolling a loop can
be free or even helpful because the loop body is replayed from the cache. On
LA464 and LA664, an unrolled loop occupies more decode bandwidth and more L1I
space, and the gain has to come from fewer branches and better scheduling rather
than from the front end. Small hot loops are the natural shape for both cores.

It also makes instruction count a first-order cost. Using one vector instruction
instead of four scalar ones saves decode slots as well as execution slots, and
using a single instruction such as `alsl.d` or `bstrins.d` instead of three
does the same. Code size on LoongArch is proportional to instruction
count, so the two effects point in the same direction.

## What the compiler does

GCC aligns loops to 8 bytes for LA464 and 16 bytes for LA664, and function
entries to 32 and 16 bytes respectively. LLVM 24 uses 32-byte
function and 16-byte loop alignment for both and still carries a TODO for
LA664-specific layout tuning. GCC 17's DFA pipeline description covers LA464 only,
so `-mtune=la664` has no dedicated pipeline model. LLVM has separate LA464 and
LA664 scheduling models; its LA664 model uses six-wide issue, a 256-entry ROB,
a 4-cycle load latency, and an estimated 14-cycle misprediction penalty. Treat
GCC's LA664 scheduling as approximate, and treat LLVM's model as more specific
but still partly estimated.

## What this means for software

Keep the hot loop inside the 64 KB L1I and, if possible, inside L2. On LA664 that
is worth about 3 IPC; on LA464 the drop from L1I to L2 is larger, and the drop
from L2 to L3 is larger still.

Be conservative with inlining and unrolling. Both reduce branch count but increase
the instruction footprint, and with no op cache the footprint is charged at
decode time. Profile-guided layout is more valuable here than on a core with an
op cache, because moving cold code out of the hot region directly buys fetch and
decode bandwidth.

Align hot loops and branch targets. The instruction stream is fixed-width, so a
loop that starts at a fetch-block boundary wastes fewer slots on the first
iteration, and aligning the back edge can keep the loop in one fetch window. The
compiler's alignment flags are the easy way to experiment; padding that pushes
the loop out of L1I is the failure mode to watch for.

For JIT code, write the instructions, then execute `ibar` before jumping into
them. LoongArch keeps the instruction and data caches coherent in hardware, so
`ibar` is the ordering step; `cacop` is not needed for ordinary instruction
fetch.
