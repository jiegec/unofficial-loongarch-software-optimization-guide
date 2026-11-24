# Simultaneous multithreading

Simultaneous multithreading lets two threads share one physical core. When one
thread stalls on a cache miss, a long dependency, or a mispredicted branch, the
other thread can use the idle pipeline slots. It is a throughput optimization,
not a latency optimization: two threads on one core finish more total work than
one thread after the other, but each thread individually runs slower than it
would alone.

LA664 implements SMT with two threads per core. LA464 does not. That single fact
changes how the two cores should be tuned, and it means advice written for one
should not be applied to the other without checking.

## How LA664 shares the core

A 3A6000 has four LA664 cores and exposes eight hardware threads to the operating
system. The two threads share the front end, both L1 caches, the L2, and the
branch prediction structures. The L3 is shared more widely, by the four cores of
a cluster, and that sharing is independent of SMT.

The out-of-order resources are mostly split in half. The ROB, the integer and
vector register files, and the load and store queues are statically partitioned
when the second thread becomes active, so a thread cannot use its sibling's half
while the sibling is running. The schedulers are different: they are watermarked
rather than partitioned, so a thread can use what appears to be around 30 of the
48 entries even when both threads are running. That is a compromise between
fairness and the ability to keep a single thread's scheduler full.

The branch predictor is shared, including the BTB. The return stack is 16 entries
in single-thread mode and 8 per thread when SMT is active. Code with deep or
recursive call chains loses some return prediction when a sibling is running,
which is one reason call-heavy workloads see smaller SMT gains than tight loops.

## What SMT buys

Chips and Cheese measured about a 20% gain on 7-Zip and over 30% on libx264 when
both threads were loaded. AMD's Zen 1 and Zen 2 see 40% or more on the same kind
of test. The smaller gain on LA664 suggests that the single-thread core is
already reasonably good at hiding latency, or that the shared resources become
the bottleneck before the second thread can add much.

The gain is workload-dependent. A compute-bound thread with a long dependency
chain leaves issue slots free for its sibling; two memory-bound threads mostly
compete for the same L1 and L2 bandwidth. The same is true of two threads with
large working sets: each one fits in the caches alone, and together they do not.

## LA464

LA464 has no SMT. Each core runs one thread and all of the ROB, register files,
queues, and schedulers belong to it. There is no partition to shrink, no
watermark to hit, and no sibling to steal cache or predictor state.

The practical consequence is that an LA464 core behaves the same whether the
system is lightly or heavily loaded, apart from memory bandwidth and the shared
L3. Code tuned for LA664's two-thread configuration should be checked again on
LA464, but the tuning knobs that matter there are the single-thread ones.

## Using SMT well

For latency-critical work, keep the sibling idle or disable SMT. A thread that
must meet a deadline does not benefit from sharing a core, and the interference
from a busy sibling can be larger than the gain from using all threads. Pinning
the thread to a core whose sibling is idle is the simplest way to get
single-thread behavior on an SMT-capable part.

For throughput work, co-schedule threads that use different resources. A
memory-bound thread next to a compute-bound thread uses the core better than two
threads of the same kind. The watermarked schedulers help here: the compute-bound
thread can still fill its share of the queue while the memory-bound thread waits.

Watch the shared caches. Two threads share the L1D and L2, so a per-thread
working set that fits comfortably alone may thrash when both are active. If a
thread's performance drops sharply when its sibling starts, the cause is often
the cache, not the execution units.

Avoid false sharing between siblings. The L1 and L2 are shared, so a line written
by one thread and read by the other bounces inside the core rather than across the
chip. It is cheaper than cross-core false sharing, but it still costs, and it is
easy to create when two threads process adjacent elements of an array.

Spin loops are especially harmful under SMT. A spinning thread consumes issue
slots and cache bandwidth that its sibling could use. Backoff, `yield`, or a
short sleep usually improves total throughput even if it makes the spinner
slightly slower.

Address layout can matter for the shared predictor. Two threads running the same
code at the same addresses share BTB and predictor state, while two threads
running different code at different addresses compete for it. Running identical
worker threads is therefore friendlier to the predictor than running different
phases of a pipeline.

## What to measure

Measure single-thread performance with the sibling idle and with the sibling busy.
The difference is the interference cost, and it is the number that decides whether
to disable SMT for a workload.

Measure the SMT speedup separately for a compute-bound, a memory-bound, and a
mixed pair of threads. The 20% and 30% figures above are for two specific
workloads; a different kernel can land anywhere between a small gain and a
slowdown.

Use the operating system's SMT control to run the same benchmark with SMT on and
off. On Linux that is `/sys/devices/system/cpu/smt/control`, and `lscpu` reports
the thread siblings. Pinning with `taskset` or `sched_setaffinity` makes the
sibling relationship explicit.
