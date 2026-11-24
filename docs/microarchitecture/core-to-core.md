# Core-to-core latency

A cache line that moves between cores costs far more than an L1 hit, and the
cost is not uniform across the cores of a server part. The two heatmaps below
plot measurements from
[nviennot/core-to-core-latency](https://github.com/nviennot/core-to-core-latency)
on a 3C5000 and a 3C6000/S.

The tool reports one-way latency as half the round-trip time, in nanoseconds.
Each cell is the median for one ordered pair and is printed in the heatmap; the
diagonal is omitted. The raw matrices are in
[core-to-core-3C5000.csv](core-to-core-3C5000.csv) and
[core-to-core-3C6000S.csv](core-to-core-3C6000S.csv).

| Part | Logical CPUs | Min | Median | Max |
| --- | --- | --- | --- | --- |
| 3C5000 | 16 | 29.2 | 43.8 | 55.5 |
| 3C6000/S | 32 | 20.1 | 29.3 | 36.9 |

All values are nanoseconds. For the 3C6000/S, the table includes SMT sibling
pairs; excluding them changes the median only slightly, to 29.5 ns.

## 3C5000

[![Core-to-core latency matrix for the 3C5000](../assets/images/core-to-core-3c5000.png)](../assets/images/core-to-core-3c5000.png)

The 16 cores span 29 to 56 ns. The matrix is not flat: cores 4 to 7 are
consistently faster to reach than cores 12 to 15, and the four bands of four
cores are visible. All 16 cores are in the same NUMA node, so these bands are
not NUMA boundaries. Within a band, a pair is not faster than a pair across
bands, so they are not local clusters either; the pattern is closer to a fixed
offset per core. The CSV is a core-by-core matrix, but it does not say which
cores share an L3 group, so the page describes the bands without naming the
clusters. What matters for software is the spread: a line transfer
can cost twice as much depending on which core pair is involved.

## 3C6000/S

[![Core-to-core latency matrix for the 3C6000/S](../assets/images/core-to-core-3c6000s.png)](../assets/images/core-to-core-3c6000s.png)

The newer part exposes 32 logical CPUs and spans 20 to 37 ns, with a median of
29 ns. It is both faster and more uniform than the 3C5000: the median is about a
third lower, and the worst pair is below the 3C5000 median. The 32 by 32 grid is
dense, so open the image at full size to read the values cell by cell.

The matrix is not flat: logical CPUs 14 to 15 and 26 to 31 are the fastest to
reach, while 0 to 1 are the slowest, and the four 8-thread blocks have distinct
latency levels. All 32 logical CPUs are in the same NUMA node, so the blocks are
not NUMA boundaries either. The CSV is a core-by-core matrix, but it does not
say which cores share a cluster, so the page describes the blocks without
naming one.

The 3C6000/S has SMT, so its 32 logical CPUs are 16 cores with two threads each:
0 and 1 are siblings, 2 and 3 are siblings, and so on. The 16 sibling pairs all
measure 20.8 to 21.4 ns, and they are same-core transfers rather than
core-to-core hops. Excluding them, the median is 29.5 ns. Most cross-core pairs
are 23 to 37 ns, but a small group also reaches 20 to 22 ns, so a low cell is
not by itself proof of SMT.

## What this means for software

These are the costs that a synchronization operation pays before any lock
algorithm runs. A contended lock or a cache line bouncing between cores is
limited by the transfer time, not by the atomic instruction's own latency. On
the 3C5000 the spread is large enough that which cores share data matters; on
the 3C6000/S the spread is smaller, but a cross-core handoff is still an order of
magnitude above an L1 hit.

Keep shared mutable data on one core when possible, pad hot per-thread state to
a cache line, and avoid designs that hand a line back and forth between cores.
For the atomic and barrier side of the same problem, see
[Atomics and memory ordering](atomics.md).
