# Cache hierarchy

Both cores have the same three-level shape: a private 64 KB L1 instruction cache
and a private 64 KB L1 data cache, a private 256 KB L2, and a shared L3. On the
4-core desktop parts used for most of the measurements below, the L3 is 16 MB
shared by four cores; the server parts package the same cores with a different
L3 topology, described in the L3 section. The differences are in latency,
bandwidth, and how well each level feeds the core. The numbers below are cycles at the 2.5 GHz clock both parts run
at, taken from Chips and Cheese and the LA464/LA664 measurements unless stated
otherwise.

## L1 instruction cache

Both cores use a 64 KB, 4-way L1I, twice the 32 KB that contemporary x86 cores
carry. Neither core has a micro-op cache, so every instruction has to come
through fetch and decode. That makes instruction-side bandwidth more important
than it is on cores that can replay decoded operations from an op cache, and it
makes the size of the L1I more valuable.

On LA464 the L1I feeds an 8-wide fetch and a 4-wide decode. Branch targets come
from a 96-entry, fully associative BTB; when a branch misses it, the core
discovers the branch only after fetch and decode. A sweep of taken branches puts
the cost at 3 CPI beyond 96 branches, with a second knee at 16384 branches where
the 64 KB L1I is exhausted. There is no second-level BTB. Fetching from L2 is
worse than fetching from L3 on this core, which suggests the L2 path has to
handle instruction cache coherency against the L1D, while an L3 hit can use a
directory. Whatever the cause, code that spills out of the 64 KB L1I runs at a
lower instruction rate, and the large L1I is there to keep that from happening
too often. A NOP-footprint sweep sees a sharp drop once the loop leaves L1I,
which is consistent with no instruction prefetcher.

On LA664 the L1I feeds an 8-wide fetch and a 6-wide decoder. The BTB has 96
fully associative entries, and a miss falls back to fetch and decode from the L1I
rather than to a second-level BTB. A NOP-footprint sweep sees a sharp drop once
the loop leaves L1I, which is what the absence of an instruction prefetcher
would look like; other tests had suggested linear prefetch. The result is a front end
that can sustain about 3 IPC when the code fits in L2, but drops below 2 IPC
when it has to come from L3. The 6-wide decode
only helps while the instruction stream keeps up.

## L1 data cache

Both L1Ds are 64 KB and 4-way, write-back, and virtually indexed but physically
tagged. With 4 ways, the set index fits inside the 16 KB page offset, so the
cache can be indexed before the TLB result is available.

On LA664 the L1D has a 3-cycle load-to-use latency for a pointer chase and 4
cycles for other dependent integer loads; `fld`, `vld`, and `xvld` take 5 cycles.
LoongPerf's load-latency measurements agree with that split. It can serve two
256-bit loads, two 256-bit stores, or one 256-bit load plus one 256-bit store per
cycle; 128-bit accesses can go two loads and two stores in the same cycle. Store forwarding takes 7 cycles
when the load is fully contained in the store and 14 cycles on a partial overlap.
Store forwarding across a 64-byte line boundary fails and costs 15 cycles, and a
misaligned store costs 3.

On LA464 the L1D takes 4 cycles for integer loads and 5 for `fld`, `vld`, and
`xvld`. It can serve two 256-bit loads per cycle, or one load and one store. Store
forwarding is 7 cycles for a contained load and 14 for a partial overlap, but the
overlap check is coarse: accesses that hit the same 8-byte block are serialized
even when they do not really overlap, and the same false dependency appears
across 16 KB pages at the same offset. A misaligned load costs 2 cycles, a misaligned store 10, and a misaligned store
that crosses a 16 KB page 15. Forwarding across a 64-byte line boundary fails and
costs 22 cycles.

## L2

Both cores have a private 256 KB L2. It is the level that decides whether a
working set that does not fit in L1 still runs at a useful speed.

LA464's L2 is 16-way, acts as a victim cache for the L1D, and has a 14-cycle
latency. Its bandwidth is about 21.3 bytes per cycle. The instruction side is the
weak point: fetching code from L2 is slower than fetching it from L3, which is
unusual and suggests the L2 path is paying for coherency work.

LA664 keeps the 256 KB size but cuts the latency to 12 cycles and brings
instruction fetch from L2 up to about 3 IPC. Data bandwidth is in the same range
as LA464, around 21 to 22 bytes per cycle. The smaller latency matters more than
the size here, because 256 KB is not large enough to hold much of a working set
on its own.

## L3

On the 4-core desktop parts the L3 is 16 MB, shared by the four cores of a
cluster, and on LA464 it is a victim cache built from four banks behind a
switch. Its latency is about 40
cycles on LA464, and LA664 brings that down by a couple of cycles. Bandwidth is
where the newer core gains more: LA464 gives a single core about 13.7 bytes per
cycle and just over 10 when all four cores are active, while LA664 gives a single
core 18.7 and still 16.55 with every thread loaded. The all-core number matters
because the L3 is shared, and it was a weak point on LA464.

L3 capacity by part:

| Part | L3 |
| --- | --- |
| 3A5000 | 16 MB |
| 3A6000 | 16 MB |
| 3C5000 | 32 MB |
| 3C5000L | 64 MB, four 3A5000 dies |
| 3C6000/S | 32 MB |
| 3C6000/D | 64 MB |
| 3C6000/Q | 128 MB |

The server parts also have their own L3 behavior. On the 3C5000 the 32 MB L3 is
split into four partitions; the latency rises before the full capacity is
reached, so a core may be closer to some partitions than others. On the
3C6000/S the measured L3 latency is about 48 cycles, against about 65 on the
3C5000, and the footprint knee appears only around 96 MB, which is well past the
32 MB capacity and points at replacement or prefetch behavior rather than raw
capacity. The core-to-core bands on the
[core-to-core latency](core-to-core.md) page may therefore reflect L3 partition
distance on the 3C5000, but the CSV does not label the partitions.
`lscpu -C` can present a different number of instances or a different total
depending on how the firmware describes the hierarchy; the capacities here are
from Loongson's product documentation. The latency and bandwidth numbers earlier
in this section are for the 4-core desktop parts; the server figures are the ones
in this paragraph and the table.

Measured bandwidth with LASX `xvld`/`xvst`, in bytes per cycle:

| Part | L1 read | L1 write | L2 read | L2 write | L3 read | L3 write |
| --- | --- | --- | --- | --- | --- | --- |
| 3C5000 (LA464) | 64 | 32 | 21 | 21 | 12 | 10 |
| 3C6000/S (LA664) | 64 | 64 | 21 | 21 | 18 | 12 |

The L1 write difference is the clearest sign of the newer core: LA664 can write a
full 64 bytes per cycle, while LA464 is limited to 32. L2 bandwidth is the same
on both; the newer core gains at L3, especially on reads.

An L3 miss goes to DRAM. Measured latency is about 144 ns on 3A5000 and 104 ns on
3A6000. Both parts run at 2.5 GHz, so the cycle counts behind those numbers are
roughly 360 and 260. The 3A5000 memory controller was a known weak point; the
3A6000 improves it but does not make DRAM latency low.

## What this means for software

The hierarchy rewards code that fits in L1 or L2 and punishes large working sets.
Pointer chasing gets the 3-cycle case on LA664 and a normal 4-cycle load on
LA464, but the 5-cycle latency of `fld`/`vld`/`xvld` means vector loops should
keep their data in registers and avoid reloading the same line.

Instruction footprint matters on both cores because neither has an op cache.
Hot loops should fit in the 64 KB L1I, and the difference between an L2-resident
loop and an L3-resident loop is large, especially on LA464. Function
inlining and loop unrolling both trade instruction cache for fewer branches, so
they should be measured rather than assumed.

The L2 is small on both cores, and the L3 is shared by four cores. A single
thread can use most of the 16 MB L3, but four active threads each get much less
effective capacity, and the bandwidth per core drops with them. Workloads that
stream through memory should not expect L3 to absorb the stream.

Per-instruction latency and throughput live in
[Instruction latency and throughput](../latency-throughput.md). Cache behavior
under specific access patterns is better measured than guessed; treat the numbers
above as a starting point.
