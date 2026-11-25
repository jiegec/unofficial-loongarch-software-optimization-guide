# Load-store unit

The load-store unit sits between the execution pipes and the L1 data cache. It
contains the address generators, the load and store queues, the forwarding logic,
and the machinery that keeps memory operations in the right order. On LoongArch
its behavior is shaped by one ISA detail: most loads and stores use a base plus a
12-bit immediate or a base plus an index register, with `ldptr` as the
PC-relative form. There is no scaled
index, so an address like `a[i * 8]` costs an extra instruction before the load
even starts.

## Address generation

LA664 has four address-generation units: two for loads and two for stores. That
lets it start two loads and two scalar stores in the same cycle, and it is a
large improvement over LA464. Its L1D can serve two 256-bit loads, two 256-bit
stores, or one load plus one store per cycle; with 128-bit accesses it can also
do two loads and two stores in the same cycle.

LA464 has two AGUs. Both can be loads, or one can be a load and the other a store,
which means two memory operations per cycle at best and one store per cycle. That
is roughly the level of Neoverse N1 or Zen 1, and well behind the four AGUs on
LA664.

According to LoongPerf, indexed loads (`ldx.*`) and stores (`st.*`) double from
1 to 2 instructions per cycle on LA664 compared with LA464, which is what the
extra AGUs buy.

The addressing forms matter for both. Because there is no scaled index, the
compiler has to turn `p[i]` into a shift or an `alsl.d` plus a load unless it can
strength-reduce the index into a pointer walk. Chips and Cheese measured
GCC-compiled array indexing on LA464 at about 8 cycles of effective L1D latency,
where the 4-cycle load is only half the story and the address arithmetic is the
rest. Writing the loop as a pointer walk, with `addi.d` updating the pointer and
the load using an immediate offset, avoids that.

## Queues and ordering

The load queue holds loads from dispatch until their data arrives, and the store
queue holds stores until they can be written to the cache. LA664 has an 80-entry
load queue and a 64-entry store queue; LA464 has 64 and 48.

The unit executes loads out of order with respect to older stores. A load whose
address is known can issue before an older store whose address is not, which is
the speculative part of memory disambiguation. If it turns out that the load
should have seen the store's data, the load is replayed. The queues also enforce
the architectural ordering rules; `dbar` and the atomics are covered later in
this chapter.

## Store-to-load forwarding

Forwarding lets a load take its data from an older store that has not yet reached
the cache. Both cores do it in 7 cycles when the load is fully contained in the
store, and both pay 14 cycles when the load only partially overlaps the store.
The partial-overlap case usually means the load waits for the store to commit and
write back.

The differences are in the corner cases. LA464 checks forwarding at 8-byte
granularity, so a load and a store that touch the same 8-byte block are
serialized even when they do not really overlap; the same false dependency
appears at the same offset in different 16 KB pages. LA664 removes the large
penalty for a misaligned store, dropping it to 3 cycles. Forwarding across a
64-byte line boundary fails and costs 15 cycles on LA664, against 22 on LA464.
LA464's misaligned store costs 10 cycles, or 15 when it crosses a 16 KB page.

The successful-forwarding rule is strict: the store must cover the load, the
pair must stay inside one cache line, and one load cannot take data from more
than one store. The practical rules follow from this. Keep the store and the load
that consumes it the same size and naturally aligned, and make sure the load is fully contained
in the store. Avoid interleaving stores to different regions that share the same
low address bits, because that is what defeats the forwarding check. Group loads
that follow stores close together, so the scheduler has a chance to forward
before the store retires.

## Unaligned and line-crossing accesses

Scalar unaligned accesses work on both cores, but they are not free. A misaligned
load on LA464 costs 2 cycles, and a misaligned store costs 10, or 15 if it also
crosses a page. LA664 brings the misaligned store down to 3 cycles. Vector
unaligned accesses do not raise an alignment exception, but they may be split
across the memory system and are not guaranteed to be atomic.

An access that crosses a cache line needs two L1D accesses, and one that crosses
a page also needs two TLB lookups. Those penalties are separate from the
misalignment penalty and add to it. Aligning buffers, padding rows, and handling
loop heads and tails separately is the usual way to avoid them.

## What this means for software

Walk pointers instead of computing scaled indices. A pointer increment plus an
immediate-offset load uses the AGU and the ALU more efficiently than a shift plus
an indexed load, and it removes the address arithmetic from the load's latency.

Keep store/load pairs simple. The forwarding rules reward a load that is fully
contained in a same-sized, aligned store, and punish partial overlaps and
low-address aliasing. When a loop stores a value and then loads it back, that pair
should be adjacent and identical in width.

Avoid unaligned and line-crossing accesses in hot loops. The hardware handles
them, but the cost is a second cache access and, on LA464, a large store penalty.
If the data layout forces misalignment, consider padding or a different
decomposition.

Use the full width of the L1D. Two 256-bit accesses per cycle are available on
both cores in the load direction, and LA664 can do two stores as well. A vector
loop that issues four 128-bit accesses wastes half of that.

<!--
## What to measure

Per-instruction latency and throughput are in
[Instruction latency and throughput](../latency-throughput.md). For the LSU
itself, the useful measurements are the load-to-use latency for each destination
class, the forwarding cases (contained, partial, misaligned, line-crossing), the
queue depths, and the cost of an unaligned access for each width.

LoongPerf's load-latency analysis confirms the numbers used elsewhere in this
guide: integer loads are 4 cycles on both cores, `fld`, `vld`, and `xvld` are 5,
and only LA664's base-address forwarding case gets to 3.
-->
