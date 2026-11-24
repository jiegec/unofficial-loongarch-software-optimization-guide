---
hide:
  - navigation
---
# Introduction

This guide collects optimization information for LoongArch software, with the
LA664 and LA464 cores as the two primary targets. It starts with microarchitectural background, then gives each mechanism its own
section and ends with concrete recommendations.

The guide does not try to be a replacement for the LoongArch manuals. It assumes
that the reader can read LoongArch assembly and knows the base integer and
floating-point instruction sets.

## Intended audience

This guide is intended for:

- compiler and assembler developers working on LoongArch back ends,
- runtime, libraries, and kernel developers who tune LoongArch code,
- C, C++, and assembly programmers writing performance-sensitive code.

It assumes familiarity with:

- the LoongArch base ISA (64-bit integer instructions, `$r0`–`$r31`, `$f0`–`$f31`),
- the ABI and the usual calling conventions,
- at least one out-of-order microarchitecture (x86, Arm, RISC-V, or LoongArch),
  so that terms such as register renaming, reorder buffer, and store-to-load
  forwarding need no introduction.

## Scope

The guide covers two cores and the products that use them:

| Core | Products (non-exhaustive) | Notes |
| --- | --- | --- |
| LA664 | Loongson-3A6000, 3C6000 | Out-of-order, SMT-capable, LoongArch V1.1 |
| LA464 | Loongson-3A5000, 3C5000 | Out-of-order, single-thread, LoongArch V1.0 |

Out of scope for now: LA264/LA364E (2K1000LA, 2K2000, 2K3000), LA32/LA32R, the
GS464/GS464E predecessors of LA464, and Loongson's accelerator or GPU units. Some
sections may still be useful for those parts, but no values are claimed for them.

Unless stated otherwise, "the processor" means either LA664 or LA464, and the
software environment is 64-bit Linux with the LP64D ABI.
