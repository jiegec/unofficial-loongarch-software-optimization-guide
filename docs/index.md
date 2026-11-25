---
hide:
  - navigation
---
# Unofficial LoongArch Software Optimization Guide

An unofficial guide to making LoongArch software run faster. It covers two
out-of-order cores:

- **LA664**: the core used by the Loongson-3A6000 and 3C6000 families.
- **LA464**: the core used by the Loongson-3A5000 and 3C5000 families.

The guide is written for compiler, assembler, and runtime developers, and for anyone
writing performance-sensitive C, C++, or assembly for LoongArch.

## How the guide is organized

Most sections follow the same pattern. They start with the mechanism and what
software can do about it, then look at how LA664 and LA464 implement it. Where the
two cores behave the same, the section says so rather than repeating the text, and
sections that apply to only one core, such as simultaneous multithreading, are
marked as such.

A few sections are organized differently. The cache hierarchy has a subsection
per level, the branch section separates prediction from layout, and the ISA
section ends with a direct comparison of the two cores. The pattern is a default,
not a straitjacket.

## Sources

The guide draws on six sets of material.

**Chips and Cheese** publishes the microbenchmark articles behind most of the
core-level numbers:

- [Loongson 3A6000: A Star among Chinese CPUs](https://chipsandcheese.com/p/loongson-3a6000-a-star-among-chinese-cpus)
- [Loongson's 3A5000: China's Best Shot?](https://chipsandcheese.com/p/loongsons-3a5000-chinas-best-shot)

**Microarchitecture measurements** for LA464 and LA664 are in the
[LA464 notes](https://github.com/jiegec/blog-source/blob/master/docs/blog/posts/hardware/loongson-la464.md)
and [LA664 notes](https://github.com/jiegec/blog-source/blob/master/docs/blog/posts/hardware/loongson-la664.md).
They supply the fetch width, BTB, queue, TLB, and forwarding numbers used above.

**Official documentation** covers the architecture and the products:

- [LoongArch Documentation](https://loongson.github.io/LoongArch-Documentation/),
  which hosts the LoongArch Reference Manual: volume 1 (basic architecture),
  volume 2 (vector extensions), and volume 3 (virtualization and binary
  translation extensions).
- Loongson 3A5000/3A6000 and 3C5000/3C6000 product documentation.
- The Linux kernel's LoongArch port, for privileged details and barrier
  encodings that the manuals leave to the operating system.

**LoongPerf** holds the instruction-level measurements:

- [Instruction table](https://jia.je/LoongPerf/table.html)
- [Analysis](https://jia.je/LoongPerf/analysis/)
- [Methodology](https://jia.je/LoongPerf/methodology/)

**Unofficial LoongArch Intrinsics Guide** documents the vector and LBT
instructions at intrinsic level:

- [Guide](https://jia.je/unofficial-loongarch-intrinsics-guide/)
- [LBT Basics](https://jia.je/unofficial-loongarch-intrinsics-guide/lbt_basics/)

**Core-to-core latency** measurements come from
[nviennot/core-to-core-latency](https://github.com/nviennot/core-to-core-latency);
the raw matrices are linked from [the core-to-core page](microarchitecture/core-to-core.md).

Where a core-level description and an instruction-level measurement disagree,
the measurement is used, and the disagreement is noted on the page.

## Acknowledgements

This guide is inspired by AMD's *Software Optimization Guide* series. Thanks to
AMD for setting such a good example.

## Disclaimer

This is an unofficial document. It is not affiliated with or endorsed by Loongson
Technology. Microarchitectural details that are not documented by the vendor are
derived from public measurements and may be wrong.
