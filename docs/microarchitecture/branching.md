# Optimizing branching

Branches are where the front end makes its bets. Every conditional branch forces
the core to guess a direction before the operands are known, and every taken
branch forces it to guess a target. A correct guess keeps the pipeline full; a
wrong one throws away work and refills the front end from the correct path. The
cost of getting this wrong is usually larger than the cost of the branch
instruction itself.

LoongArch makes one part of this simpler than x86. There are no condition codes:
conditional branches compare two registers directly (`beq`, `bne`, `blt`, `bge`,
`bltu`, `bgeu`, `beqz`, `bnez`), and floating-point branches test one of the
eight FCC registers (`bceqz`, `bcnez`). A compare and a branch are already one
instruction, so there is no compare-and-branch fusion to exploit, and no flag
dependency chain to maintain. The trade-off is that LoongArch code tends to have
a higher fraction of branch instructions than x86 code, which puts more pressure
on the predictor.

## What a branch costs

There are three separate mechanisms, and they fail differently. Direction
prediction decides taken or not taken. Target prediction decides where to fetch
next; direct branches carry their target in the instruction, while `jirl`
branches need a target array. Return prediction uses a return-address stack, and
falls back to the indirect predictor when the stack is empty or confused.

A branch that hits the L1 BTB can be handled without a bubble, including
back-to-back taken branches. A branch that misses the BTB has to wait for the
instruction bytes to arrive and for the target address to be computed. On both
cores that means waiting for the L1I, so a BTB miss turns into an instruction
cache latency problem. A mispredicted branch is worse still: everything younger
than the branch is discarded. The public material does not give the misprediction
penalty, so it has to be measured before it is used in a calculation.

## LA664

LA664 has a 96-entry, fully associative BTB that can sustain taken branches back
to back. When a branch misses it, the core falls back to fetch and decode from
the L1I rather than to a second-level BTB. That makes the L1I size part of the
branch predictor, and it means code that stays in L1I also keeps its branch
targets cheap.

The direction predictor is a large step up from LA464. Chips and Cheese measured
accuracy roughly at Zen 2 level: well ahead of the older core and close to recent
x86 cores, though still behind Zen 3 and later. The structure is not public, and
the indirect-target capacity is not documented either.

The return-address stack holds 16 entries, and only 8 per thread when SMT is
active. That is smaller than LA464's 32, which is surprising, but the core
appears to fall back to the indirect predictor when the stack overflows, and the
measured loss is modest. Deep or
recursive call chains still pay more here than on the older core.

Two of the four integer ALUs can execute branches, and LoongPerf measures
not-taken branches at two per cycle. The 6-wide front end and the large BTB mean
that a hot loop with a modest number of branches is usually limited by something
other than branch throughput.

## LA464

LA464 also has a 96-entry, fully associative BTB, but no second-level BTB. A
branch that misses it is discovered only after fetch and decode. In a sweep of
taken branches, CPI stays at 1 up to 96 branches and then rises to 3; a second
knee at 16384 branches marks the 64 KB L1I limit. Chips and Cheese reported 64
entries, probably because it sampled only powers of two.

The direction predictor appears to trace back to the GS464E tournament design,
with local and global history tables and a selector. On long random history it
performs poorly compared with modern TAGE-style predictors, and Chips and Cheese
measured it well behind LA664. The indirect-target capacity is not documented, so
treat jump-table and virtual-dispatch behavior as something to measure rather
than assume.

The return-address stack has 32 entries, twice LA664's. Only one branch can
resolve per cycle, and the 4-wide front end gives the core less room to recover
from a misprediction. LoongPerf's branch measurements show the same limit: a
not-taken branch retires at one per cycle. A taken branch that fits in the BTB
also costs one cycle, but when the test used 960 static branch sites, far beyond
the 96-entry BTB, the cost rose to three cycles per branch. That is the BTB
capacity limit showing up directly in throughput.

## What the compiler does

The compilers already choose `beqz`/`bnez` and `bceqz`/`bcnez` when one operand is
zero, and they if-convert small selects into `slt` plus `maskeqz`/`masknez`, or
into `fsel` for floating point. A C conditional that selects a value is therefore
often branchless without intrinsics; only a conditional with side effects or a
large body becomes a real branch. LLVM's scheduling models for both cores set
the misprediction penalty to 14 cycles, but they mark it as an estimate. GCC
uses a generic branch cost of 6 instruction-cost units. Neither number replaces
a measurement on the actual core.

## Making branches predictable

The first rule is to give the predictor an easy pattern. Branches that are almost
always taken or almost always not taken are cheap. Branches that depend on data
with no correlation are expensive on both cores, and no amount of BTB capacity
fixes them. Sorting or partitioning the data so that a loop's exit condition is
uniform, or hoisting a condition out of a loop, is often worth more than any
instruction-level trick.

The second rule is to use branchless code when the condition is genuinely
unpredictable. LoongArch has the pieces: `slt` and `sltu` turn a comparison into
a 0/1 value, `maskeqz` and `masknez` turn that value into a select, and `fsel`
does the same for floating point. Three or four ALU instructions are usually
cheaper than a misprediction, but more expensive than a predictable branch, so
this is a trade-off to measure rather than a rule to apply everywhere.

The third rule is to keep branch density low. Merge adjacent conditions, avoid
checking the same invariant inside a loop, and use arithmetic or select sequences
where they are shorter. A loop with fewer branches is easier to predict and gives
the front end more useful work per fetch block.

Switch statements and virtual calls deserve their own attention. A dense jump
table fits the indirect target array and predicts well; a sparse one spreads
targets across many entries and mispredicts. Devirtualizing a hot call site, or
replacing a chain of `if` comparisons with a table, changes the branch mix enough
to be worth a profile run.

Calls and returns are cheap when the nesting is shallow and regular. Inlining a
small leaf function removes both the call and the return and takes pressure off
the return stack, but it also increases code size. On LA664 the return stack is
small, so call-heavy code benefits more from inlining than the same code would on
LA464.

## Layout and alignment

Because a BTB miss costs an L1I access on both cores, branch-heavy code should
stay compact and hot. Profile-guided basic-block ordering and function layout put
the taken path next to its branch and move cold code out of the way. Manual
alignment of hot loops can help, but padding has a cost in instruction footprint,
and an over-aligned loop can push itself out of L1I.

The L1 BTB is 96 fully associative entries on both cores. Code with hundreds of
distinct branches in a hot region will thrash it on either core. Keeping the hot branch
footprint small, rather than the whole binary small, is what matters.

Unrolling reduces the number of branches per iteration, but it also grows the
loop body and the number of BTB entries it occupies. The right amount of
unrolling is a per-core question: LA664 has the larger front end and the second
level BTB, while LA464 has the smaller front end and benefits more from keeping
the loop compact.

<!--
## What to measure

The public material gives predictor capacities and accuracy, not the
misprediction penalty. A small benchmark that alternates a predictable and an
unpredictable branch will give the penalty for each core. The same setup can
measure BTB capacity by sweeping the number of distinct branches, return-stack
depth by nesting calls, and indirect-target capacity by increasing the number of
targets per branch.

Per-instruction latency and throughput for branch instructions are in
[Instruction latency and throughput](../latency-throughput.md). The numbers in
this section come from Chips and Cheese and LoongPerf, listed on the
[home page](../index.md#sources); the structure of the predictors is left unknown
where the vendors have not documented it.
-->
