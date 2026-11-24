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
than the branch is discarded. Loongson does not publish the misprediction penalty, so it has to be measured
before it is used in a calculation.

## LA664

LA664 has a 64-entry L1 BTB that can sustain taken branches back to back. When a
branch misses that BTB, the core appears to fall back to the instruction cache
and the branch address calculator rather than to a big decoupled BTB; the
effective second level is a 1K to 4K entry structure tied to the 64 KB L1I. That
makes the L1I size part of the branch predictor, and it means code that stays in
L1I also keeps its branch targets cheap.

The direction predictor is a large step up from LA464. Chips and Cheese measured
accuracy roughly at Zen 2 level: well ahead of the older core and close to recent
x86 cores, though still behind Zen 3 and later. The structure is not public.
There is room for 1024 indirect targets, and a single indirect branch can track
well over 128 of them before it starts to mispredict.

The return-address stack holds 16 entries, and only 8 per thread when SMT is
active. That is smaller than LA464's 32, which is surprising, but the core appears to
fall back to the indirect predictor when the stack overflows, and the measured
loss is modest. Deep or recursive call chains still pay more here than on the older core.

Two of the four integer ALUs can execute branches. The 6-wide front end and the
large BTB mean that a hot loop with a modest number of branches is usually
limited by something other than branch throughput.

## LA464

LA464 also has a 64-entry BTB, but no second-level BTB and no large target array
behind it. A branch that misses the BTB waits for the line to come from the 64 KB
L1I (about 3 cycles) and for the target to be calculated. That is not a large
latency in cycles, but the core runs at 2.5 GHz, so in time it is expensive, and
the predictor cannot follow the instruction stream through an L1I miss.

The direction predictor appears to trace back to the GS464E tournament design,
with local and global history tables and a selector. On long random history it performs
poorly compared with modern TAGE-style predictors, and Chips and Cheese measured
it well behind LA664. Indirect prediction is limited too: about 24 targets per
branch and roughly 512 in total, which is enough for small jump tables and simple
virtual dispatch but not for a large interpreter.

The return-address stack has 32 entries, twice LA664's. Only one branch can
resolve per cycle, and the 4-wide front end gives the core less room to recover
from a misprediction.

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

The L1 BTB is only 64 entries on both cores, though LA664's implicit second level
makes the L1I footprint more forgiving. Code with hundreds of distinct branches
in a hot region will thrash the L1 BTB on either core. Keeping the hot branch
footprint small, rather than the whole binary small, is what matters.

Unrolling reduces the number of branches per iteration, but it also grows the
loop body and the number of BTB entries it occupies. The right amount of
unrolling is a per-core question: LA664 has the larger front end and the second
level BTB, while LA464 has the smaller front end and benefits more from keeping
the loop compact.

## What to measure

The public material gives predictor capacities and accuracy, not the
misprediction penalty. A small benchmark that alternates a predictable and an
unpredictable branch will give the penalty for each core. The same setup can
measure BTB capacity by sweeping the number of distinct branches, return-stack
depth by nesting calls, and indirect-target capacity by increasing the number of
targets per branch.

Per-instruction latency and throughput for branch instructions are in
[Instruction latency and throughput](../latency-throughput.md). The numbers in
this section come from the sources below, with the structure of the predictors
left unknown where the vendors have not documented it.

## Sources

- [Loongson 3A6000: A Star among Chinese CPUs](https://chipsandcheese.com/p/loongson-3a6000-a-star-among-chinese-cpus)
- [Loongson's 3A5000: China's Best Shot?](https://chipsandcheese.com/p/loongsons-3a5000-chinas-best-shot)
- LoongArch Reference Manual, volume 3, for the branch instruction forms.
