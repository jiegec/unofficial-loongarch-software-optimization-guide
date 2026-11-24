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

Each section has the same three parts:

1. **Principles**: the mechanism, why it matters, and what software can do about
   it. This part is architecture-level and applies to any LoongArch core unless
   stated otherwise.
2. **LA664**: what is documented or measured for LA664, and the resulting
   recommendations.
3. **LA464**: the same for LA464.

Where the two cores behave the same, the sections say so explicitly rather than
repeating the text. Sections that only apply to one core (for example
simultaneous multithreading) are marked as such.

## Acknowledgements

This guide is inspired by AMD's *Software Optimization Guide* series. Thanks to AMD for setting such a good example.

## Disclaimer

This is an unofficial document. It is not affiliated with or endorsed by Loongson
Technology. Microarchitectural details that are not documented by the vendor are
derived from public measurements and may be wrong.
