# Address translation

Every load and store uses a virtual address, and the core has to turn it into a
physical one before the cache can be accessed. LoongArch does that with a
multi-level page table and a hardware walker, caches recent translations in a TLB
hierarchy, and also provides a small set of direct-mapped windows that skip
translation entirely. The three mechanisms have very different costs, and the
choice between them is mostly made by the operating system rather than by
application code.

## How translation works

The page table lives in memory, and its shape is a build-time choice: Linux
supports 4 KB, 16 KB, and 64 KB pages, with two, three, or four levels depending
on the combination. A 64-bit build with 16 KB pages defaults to three levels. The base address comes from two
CSRs, `PGDL` and `PGDH`, selected by the top bit of the virtual address. On a
TLB miss, the hardware walker reads the page table entries itself and fills the
TLB. If a level is missing or invalid, the core raises a TLB exception (`TLBL`
for a load, `TLBS` for a store, `TLBM` for a modify) and the kernel handles it.

A TLB entry is written through CSRs as well as by the walker. `TLBEHI` holds the
virtual page number and the ASID, `TLBELO0` and `TLBELO1` hold the physical page
number and permission bits, and `TLBIDX` holds the page size, the index, and the
invalid bit. The privileged instructions are
`tlbsrch` to search, `tlbrd` to read, `tlbwr` to write a random entry, `tlbfill`
to write an indexed entry, and `invtlb` to invalidate entries. User code never
touches them directly; the kernel does.

The ASID field is 10 bits. It lets the kernel keep translations for several
address spaces in the TLB at once, so a context switch does not have to flush the
whole TLB. A process that shares nothing with the previous one still has to be
invalidated, but the common case avoids the flush.

Page sizes are 4 KB, 16 KB, and 64 KB, and `TLBIDX` records the size of each
entry. The kernel's page size is a build-time choice; on the 3A5000 and 3A6000
the kernel uses 16 KB pages. A larger base page means each TLB entry covers more
memory and the walker runs less often, at the cost of more internal fragmentation
for small allocations.

## TLB hierarchy

The TLB is per core. On LA464 it is split into a 64-entry L1 DTLB backed by a
2048-entry L2 TLB, which with 16 KB pages covers 1 MB and 32 MB respectively. A
hit in the L2 TLB costs about 5 to 6 cycles more than a hit in the L1 DTLB. For a
pointer chase that misses the L1 DTLB but hits the L2, that is comparable to an
L1D miss, and it adds up over a large working set.

LA664 keeps a 64-entry L1 DTLB. The L2 TLB size is not public, so the coverage
above should be treated as LA464-specific. What is clear is that the page size
and the TLB entry counts are the numbers that decide whether a workload is
TLB-bound, and a 32 MB cover on LA464 is not much for a large heap or a sparse
matrix.

## Page sizes and huge pages

The 16 KB base page already gives LoongArch more TLB coverage per entry than a
4 KB page does, which is why a 64-entry L1 DTLB covers 1 MB instead of 256 KB.
That helps, but it does not remove the need for huge pages. Linux on LoongArch
supports both transparent huge pages and `hugetlbfs`, and they are the practical
way to raise TLB coverage by orders of magnitude for large arrays, hash tables,
and pointer-heavy data structures.

The trade-offs are the usual ones. A huge page has to be allocated and zeroed as
one unit, so the first touch is more expensive and internal fragmentation grows.
THP may also spend time in `khugepaged` collapsing pages in the background, and
that work is visible if the process is sensitive to latency. For long-running
processes with stable large mappings, pre-faulting and `mlock` keep the page
faults out of the hot path; for short-lived ones, the fault cost may outweigh the
TLB gain.

## Direct-mapped windows

LoongArch has four direct-mapped windows, configured by the `DMW0` to `DMW3`
CSRs. A window maps a fixed range of virtual addresses to physical memory with a
fixed memory access type and privilege level, and needs no page table entry and no
TLB lookup. The kernel uses them for its own mappings: one cached window for
normal kernel memory, one strongly ordered uncached window for I/O, and one
weakly ordered uncached window for write-combining mappings.

The memory access type in a window is the same attribute that a page table entry
can carry: coherent cached, strongly ordered uncached, or weakly ordered
uncached. That attribute is part of the mapping, not part of the instruction, so
the same physical page can be reached through a cached window and an uncached one
at the same time. The two views are not coherent with each other, and software
that mixes them has to manage the ordering and the cache maintenance itself. In
practice, device drivers use the uncached windows and normal code uses paged
mappings, and the two do not overlap.

## What this means for software

The first thing to know is that a big working set can be TLB-bound even when it
fits in the caches. If a loop touches one element per 16 KB page, the TLB
coverage matters more than the cache line size. Huge pages, or a smaller number
of larger allocations, are the usual fix.

The second is that page faults and TLB shootdowns are expensive and easy to
trigger accidentally: `mprotect` churn, growing a heap one page at a time, or
repeatedly mapping and unmapping a buffer all show up as system time and IPIs.
Pre-faulting, reusing buffers, and keeping mappings stable avoid most of it.

The third is alignment. A mapping is page-aligned by definition, but code that
assumes a 4 KB page when the kernel uses 16 KB can be wrong about how much memory
a page actually covers. Allocation sizes and offsets that look fine on x86 may
straddle pages differently here. For huge pages, the alignment requirement is the
huge page size, and an `mmap` that is not aligned to it falls back to normal
pages.

The instruction and CSR names, page sizes, and the direct-mapped windows are
documented in the LoongArch Reference Manual, volumes 1 and 2. The kernel-side
behavior (page size, huge pages, ASID handling) is in the Linux LoongArch port.
Where the TLB entry counts are not public, the page says so rather than guessing.
