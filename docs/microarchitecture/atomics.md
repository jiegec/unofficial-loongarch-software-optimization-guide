# Atomics and memory ordering

Atomics are where the core meets the memory system and the other cores. LoongArch
provides two families of atomic operations and a small set of barrier
instructions, and the memory model is weak enough that the barriers are not
optional decoration. The performance of a lock or a lock-free structure depends
on which family is used, how the atomics are aligned, and how much contention
they see.

## The memory model

LoongArch is weakly ordered. Loads and stores to different addresses may be
observed out of order by other cores, and a core may reorder its own accesses as
long as the architecture permits it. The programmer gets ordering from
`dbar`, `ibar`, and the acquire/release forms of the atomic instructions; a plain
`am*` is atomic, not ordered.

`dbar` takes a hint that selects which prior and subsequent accesses are ordered.
The low bits name the four combinations of prior read, prior write, subsequent
read, and subsequent write, and one more bit selects ordering versus completion.
`dbar 0` is the simple barrier used for general memory ordering, `dbar 0x10` is
the ordering barrier Linux uses for SMP, and `dbar 0x700` is a weaker hint for
the read-after-read case in LL/SC loops. The exact encoding is in the ISA manual
and in the kernel's barrier header; the point is that a full barrier is not the
only option.

`ibar` is the instruction barrier. It orders instruction fetch with respect to
prior stores, which is why it appears after code has been written, not around
ordinary data.

## LL/SC

The first family is load-linked and store-conditional: `ll.w` and `sc.w`, `ll.d`
and `sc.d`, and on LA664 `sc.q`, which extends the pair to 16 bytes. `ll` reads a
location and leaves a reservation; `sc` writes only if the reservation is still
valid and reports success in a register.

The reservation can be lost for reasons that have nothing to do with the
program's logic: an interrupt, a context switch, or a store from another core.
A retry loop is therefore mandatory, and under contention the loop can spin for a
long time. `sc` failure is not free, and a naive LL/SC loop under heavy
contention can spend most of its time retrying.

LL/SC is still the right tool when the operation is not one of the built-in
read-modify-write forms, such as a compare-and-swap that also computes something,
or a multi-word update. The reservation-based sequence is also what a compiler
emits for many C11 atomic operations when no single instruction matches.

Cores that report the LLACQ/SCREL feature in CPUCFG2 also have `llacq.w`/`llacq.d`
and `screl.w`/`screl.d`, the acquire and release variants of the pair. They attach
the ordering to the access instead of requiring a separate `dbar`, and LoongPerf
lists them alongside the plain LL/SC forms.

According to LoongPerf, a dependency chain of `amswap.d` takes 13 cycles on
LA664 and 15 on LA464. `ll.d` takes 9.5 cycles from address to result, against 4
for a plain load, because of the reservation bookkeeping. `sc.d` is slightly
worse on LA664: 14 cycles per store-conditional on LA464 and 15 on LA664.

## Atomic read-modify-write

The second family is the `am*` instructions: `amswap`, `amadd`, `amand`, `amor`,
`amxor`, `ammax`, and `ammin`, each in `.w` and `.d` forms. LA664 adds `amcas`,
a compare-and-swap that returns the old value. These are single instructions that
perform the whole operation at the memory system, so there is no retry loop and
no reservation to lose.

That does not make them free. An `am*` instruction still has to acquire the line
in the appropriate coherence state, and under contention the line bounces between
cores. The instruction is atomic, but atomicity is not ordering: if the algorithm
needs acquire or release semantics, a `dbar` is still required at the right
place.

LA464 has the `amswap`/`amadd`/logical/min-max family but not `amcas`, and it does
not have `sc.q`. Code that must run on both cores should use the common subset or
provide a fallback path.

## Barriers

A barrier costs what it costs to make prior operations visible. The cost comes
from draining the store buffer, waiting for acknowledgements, and preventing
later operations from overlapping with earlier ones. `dbar` is cheap when it is
executed once per batch and expensive when it is executed per element.

Use the weakest barrier that is sufficient. A store-release needs to order prior
writes against the release store; a load-acquire needs to order the acquire load
against later reads and writes. The four-bit hint encoding exists so that these
cases can avoid a full barrier when the hardware supports it.

`ibar` is for instruction-stream coherence, not for data. After writing code, run
the data-cache maintenance if the platform requires it, then `ibar`, then jump.
On LoongArch the data and instruction caches are kept coherent in hardware, so
`ibar` is the step that matters for JIT code.

## Locking idioms

A lock word should live on its own cache line. If it shares a line with the data
it protects, every acquire invalidates the data and every data write invalidates
the lock, and the lock becomes a coherence amplifier.

The classic spin pattern is test-and-test-and-set: spin on a plain load of the
lock word, and only attempt the atomic when the load says the lock looks free.
This keeps the line in shared state during the spin and reduces the number of
failed atomics. A pure atomic spin works but generates more coherence traffic.

Backoff matters under contention. After a failed acquire, waiting a short,
randomized time before retrying reduces the thundering herd and lets the owner
finish. Under SMT, a spinning thread also competes with its sibling for issue
slots and cache, so `yield` or a short sleep is often better than a tight spin.

For high contention, a queue lock or a ticket lock scales better than a single
test-and-set word, because each waiter spins on a different location. That is a
general lock-design point, but it matters more here because the core count is
small and the coherence traffic is concentrated.

## What this means for software

Prefer the single-instruction `am*` form when it matches the operation. It avoids
the retry loop, and under contention the difference is large. Use LL/SC when the
operation is not covered, or when the compiler already generates it.

Keep atomic operations naturally aligned. A misaligned atomic raises an alignment
exception, and even the aligned case is slower than a normal load or store. Do
not mix atomic and non-atomic accesses to the same location; the hardware does
not promise anything useful in that case.

Use the language's atomics rather than hand-written barrier sequences. GCC and
LLVM know the LoongArch memory model and will emit the right `dbar` for the
requested ordering. Hand-written `dbar` sequences are easy to get wrong and hard
to review.

Measure under contention. A single-threaded atomic loop measures latency; a lock
benchmark with several threads measures throughput, and the two can point in
opposite directions. The `am*` instruction that wins uncontended may not win when
eight threads are hammering the same line.

## Measuring synchronization costs

Per-instruction latency and throughput are in
[Instruction latency and throughput](../latency-throughput.md). The measurements
that matter for synchronization are the uncontended atomic latency, the
contended throughput for 2, 4, and 8 threads, the SC failure rate under
contention, and the cost of each `dbar` hint.

Cross-core latency is worth measuring separately. The L3 is shared and the
coherence protocol is the same for atomics and ordinary lines, so a value bounced
between two cores has a cost that shows up in every contended operation.
