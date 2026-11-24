# Vector execution (LSX and LASX)

LoongArch has two vector extensions: LSX (128-bit) and LASX (256-bit). Both use
32 architectural vector registers, and both are exposed as C intrinsics in GCC
and LLVM.

The instruction-level reference, covering what each intrinsic does, its operands,
and its pseudo-code, is maintained in the
**[Unofficial LoongArch Intrinsics Guide](https://jia.je/unofficial-loongarch-intrinsics-guide)**:


[Open the Intrinsics Guide](https://jia.je/unofficial-loongarch-intrinsics-guide){ .md-button target="_blank" }

The intrinsics guide covers LSX, LASX, and LBT, with pseudo-code for every
operation. Use it when you need the exact semantics of an instruction or the name
of the intrinsic that maps to it. This guide is about when and why to use a
vector operation; the intrinsics guide is about what the operation computes.
