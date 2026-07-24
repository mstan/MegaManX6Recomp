# Converting static patches to native PSXRecomp mods

This guide describes how to convert an existing patcher, patched image, ROM
hack, or collection of game tweaks into independently configurable `.psxmod`
features. It is intentionally adversarial: a conversion is not considered
complete merely because a patched image boots or a byte diff can be reproduced.

The conversion target is a deterministic runtime plan applied over a verified,
immutable stock disc. Patched images are development oracles. They are never
runtime inputs, compatibility fallbacks, or ownership maps.

## Invariants

A native conversion must preserve these rules:

- The player selects only a supported stock BIN/CUE.
- The stock image is never modified.
- A package is an installation, provenance, version, and trust boundary.
- A feature is one independently understandable user-facing behavior.
- Enabling one feature never silently enables, disables, or reconfigures
  another feature.
- Disabling a feature removes only that feature's operations.
- Disabled is the stock behavior. Do not add a one-choice option whose only
  purpose is to name the enabled behavior.
- Mutually exclusive values of one concept are options inside one feature.
- Runtime cost scales with enabled operations, not possible configurations.
- Every operation is guarded against the exact supported stock revision.
- Every changed byte has one reviewed owner.
- Operation order is not an implicit override mechanism.
- Whole-image diffs and raw patcher offsets are evidence, not runtime
  ownership.
- Derived images and patcher-specific base images never ship as runtime
  fallbacks.

Fail closed when any invariant cannot be demonstrated.

## Required provenance

Record the following before analyzing a feature:

- stock game identifier, region, revision, BIN SHA-256, and CUE or track layout;
- upstream mod or patcher name, version, source revision, and license;
- hashes of the patcher, source data, base patches, and replacement assets;
- the exact profile or command used to produce each oracle;
- converter source revision and command line;
- all explicit random seeds and normalized option values; and
- hashes of every oracle and generated package.

Do not rely on an analyst's checkout-local default paths, an ambient
environment variable, or an unrecorded GUI state. A build with the same package
ID and version must be byte-for-byte reproducible from the recorded inputs.

If source assets cannot legally be redistributed, generate the package locally
from user-supplied inputs and document that restriction. Do not hide copied
game data inside a conversion report or test fixture.

## Define the feature before diffing it

Start with the user-facing concept, not the patcher's file layout.

A good feature has:

- a stable package-local ID;
- a name and description understandable without patcher terminology;
- one independent enabled state;
- a stable category;
- explicit option types, domains, defaults, and bounds; and
- a statement of its visible behavior when enabled and disabled.

Examples:

- `Rockman X6 Title Screen`, as a boolean feature: disabled is stock USA art;
- `Retranslation`, as a boolean feature when there is only one translated
  script;
- `Translation`, with a choice only when two or more non-stock translations
  are actually available;
- `Disable Nightmare Rain`, with a boolean enabled state.

Stock versus one replacement is the feature's disabled/enabled state, not a
dropdown. Two or more replacement variants are mutually exclusive values in
one feature because they control one resource. Title art and a retranslation
are separate features because a player can reasonably enable either, both, or
neither.

Do not expose implementation helpers, common patcher bases, scratch arenas, or
container relocation records as user-facing features. Determine whether each
helper is:

- an operation owned by the feature;
- an identical internal operation shared by multiple features;
- a real dependency on another independently meaningful feature; or
- infrastructure that must become a registered runtime hook or resolver
  primitive.

Never translate a patcher's `PreReq` list into silent feature activation.

## Evidence ladder

Every feature has an evidence level in its conversion report. Only E6 is ready
for release.

### E0: inventory

Capture the upstream option name, values, defaults, dependencies, ordering
rules, input assets, source writes, and expected visible behavior.

E0 is discovery only. It may contain stale, dead, or context-dependent patcher
entries.

### E1: isolated oracle

Produce a deterministic feature-only oracle from known inputs. If the feature
does nothing by itself, record the smallest activating context and why it is
needed.

An E1 raw diff is not an ownership claim. It commonly includes filesystem
metadata, error-correction bytes, a patcher's common base, shared fixes,
relocation scaffolding, or other selected features.

### E2: semantic ownership

Map every proposed changed byte to a stable identity in both stock and the
oracle:

- ISO file and file-relative location;
- container, outer record, subasset index, type, and payload;
- loaded executable and guest address;
- loaded overlay and lifecycle;
- named table field or structure; or
- a registered hook identifier.

Identify direct operations, required helper operations, and explicitly excluded
oracle noise. Any unexplained changed byte or required byte with no owner keeps
the feature below E2.

### E3: native plan

Construct the smallest guarded native operations that reproduce the owned
effect from stock. Materialize the plan offline and prove:

- all stock guards match;
- enabled output matches the semantically owned oracle content;
- disabled output is exactly stock;
- the plan claims no unrelated bytes; and
- no derived disc, VCDIFF, or patched oracle is a runtime payload.

### E4: runtime parity

Exercise the actual runtime path:

- disc requests receive the composed virtual bytes;
- startup writes occur after the target is loaded and before it is consumed;
- changed executable code reaches the supported interpreter, native overlay, or
  registered hook path;
- repeated reads return the same bytes; and
- the visible or behavioral result matches the oracle.

A successful offline materialization is not proof that the game requests the
same data or that a static recomp executes changed code.

### E5: composition

Test the feature with every resource neighbor, dependency, and known combined
oracle. Prove compatible changes compose and incompatible changes produce an
actionable pre-launch diagnostic naming both features and the exact resource.

Do not attempt every theoretical permutation. Derive the matrix from the
semantic ownership and dependency graph, then add representative cross-category
and high-risk combinations.

### E6: release

The archive is deterministic, versioned, schema-valid, installable,
upgrade-tested, and accompanied by its conversion report. All required tests
pass from a clean checkout, provenance is complete, licensing is resolved, and
remaining limitations are explicit.

Use status names such as `inventory`, `candidate`, `reviewed`, and `deferred`
below E6. Do not label a feature `ready` because a raw diff or patched disc
worked once.

## Oracle algebra

Use these names when a patcher applies a common derived base:

- `S`: verified stock image;
- `B`: patcher's common base applied to stock with no requested feature;
- `F`: common base plus exactly the feature under review;
- `G`: another independently reviewed feature; and
- `FG`: common base plus both features.

The useful discovery delta is usually `F - B`, not `F - S`. The latter includes
common-base changes that the feature may not own.

For each proposed operation:

1. Locate the semantic target independently in `S`, `B`, and `F`.
2. Attribute the replacement to upstream source or a reviewed transform.
3. Prove that `F` contains the expected replacement at that semantic identity.
4. Prove that omitted `B - S` bytes are base noise or independently owned.
5. Materialize the native plan over `S` and compare the owned semantic result
   with `F`.
6. Where `FG` exists, prove the composed native plan matches its owned result.

Mode 2 EDC/ECC bytes, timestamps, directory records, padding, and relocation
tables must be classified rather than hand-waved. Raw-sector-only EDC/ECC
differences may be transport regeneration; any user-data mismatch requires an
explanation.

Always include a negative oracle: disabled feature state must follow the stock
read and execution paths without retaining any feature operation.

## Semantic ownership rules

Raw offsets from a patched or base-derived image may move relative to stock.
They are useful for locating a candidate asset, but must never be copied
directly into a stock-targeted manifest.

For each asset:

1. Determine its file and container identity in the oracle.
2. Determine its record, index, type, size, and other stable identifiers.
3. Resolve that identity independently in stock.
4. Validate expected stock bytes and replacement bytes.
5. Calculate the runtime destination from the stock structure.
6. Emit the smallest range that fully owns the change.

For each executable write:

1. Identify the executable or overlay containing it.
2. Translate file-relative location to the correct guest address.
3. Record when it is loaded and when the patched behavior is first used.
4. Decode or otherwise review the expected and replacement instructions.
5. Prove the replacement in the isolated oracle.
6. Use an expected-byte guard at the supported lifecycle point.

Do not emit a whole record merely because rebuilding the record was convenient.
If one same-size subasset changed, own that subasset's payload range. A
whole-record overlay prevents unrelated mods from changing other subassets and
turns an implementation detail into a false conflict.

If a feature grows a subasset or record, changes a container table, or requires
new backing storage, it cannot be independently represented by a fixed private
relocation chosen by the converter. Multiple features will otherwise allocate
the same padding, disagree about table entries or logical extents, and
over-claim reconstructed containers.

Fail closed on growing containers until the runtime has a resolver-owned
allocator or semantic container composer that can:

- combine all enabled subasset changes;
- allocate backing storage once for the complete plan;
- rebuild table and extent metadata deterministically;
- assign ownership diagnostics to the originating features; and
- detect real semantic conflicts before boot.

Apply the same rule to injected code. Fixed scratch addresses and patcher-order
overwrites do not become safe merely because they worked in one derived image.
Use stable registered hooks and an explicit hook-chain policy, or add a
resolver-owned code allocator and relocation model. Otherwise defer the
feature.

## Select the native operation

Choose the narrowest supported primitive:

| Change | Preferred primitive |
|---|---|
| Same-size file or subasset payload | Guarded `disc_user` or `disc_raw` overlay at the stock-derived range |
| Startup data or code in the main executable | Guarded guest-memory write at a proven lifecycle point |
| Repeated or contextual behavior | Stable game-registered hook |
| Direct bounded unsigned scalar | Format-v2 `replace_from` patch using `u8`, `u16le`, or `u32le` |
| Linked MIPS LUI/ORI constant | Format-v3 `mips_lui_ori_u32` transform with a complete instruction-pair guard |
| Related ordered scalars | One feature with a format-v3 `ordered_integer` constraint |
| Independent fields sharing one semantic record | Format-v4 `fields`, with a complete guard and exact owned ranges |
| Bounded integer branch between fixed templates | Format-v4 `when_integer` on separate guarded patches |
| Grown record or container | Resolver-owned semantic container composer; otherwise defer |
| Injected routine or shared scratch use | Registered hook/code allocator with relocation support; otherwise defer |

Large payloads should be file-backed and hash-verified. Disc overlays must be
indexed before launch; do not scan installed features on every CD read. Hooks
must dispatch through stable IDs and should have negligible cost when disabled.
Packages do not load arbitrary native code.

### Bounded integer conversion

Use `replace_from` only when the upstream option is a direct bounded unsigned
scalar. The option declaration owns the range and default; the patch declares
the encoding and exact guarded record:

```toml
format_version = 2

[[option]]
feature = "normal_ground_dash_duration"
id = "frames"
label = "Frames"
type = "integer"
min = 10
max = 100
step = 1
default = 30

[[patch]]
feature = "normal_ground_dash_duration"
target = "main_exe"
address = 2147723944
expected = "1E000224"
replace_from = { option = "frames", encoding = "u16le", offset = 0 }
```

The replacement begins as the complete `expected` byte sequence, then the
encoded field replaces the bytes at `offset`. Guard a complete instruction or
semantic record when possible, even if the value occupies fewer bytes.

Before conversion, prove all of the following:

- the stock/default selection is a no-op;
- minimum, one interior value, and maximum retain exact source closure and
  write topology;
- every emitted payload is exactly the declared unsigned encoding;
- the complete declared range, plus any addend, fits that encoding;
- executable writes map independently to a stock guest address;
- container writes map independently to a stock member or subasset identity;
- the dynamic guard range does not overlap another enabled operation; and
- default, minimum, maximum, malformed, and out-of-range values are tested by
  the real resolver.

Do not use this primitive for bitfields, signed arithmetic, tables,
expressions, code injection, or a value whose valid behavioral range is
unknown. Add a narrower typed primitive or hook for those cases.

For a constant constructed by a linked MIPS LUI/ORI pair, format 3's
`mips_lui_ori_u32` transform is the supported narrow exception. Guard the
complete aligned pair and prove both opcodes and register linkage. The
transform uses raw high/low halves, not signed-ADDIU carry rules. If the source
tool's declared default means “emit no writes,” use `omit_when_default`; do
not normalize asymmetric stock sites merely because the source UI displays
one default value.

Related integer fields with a semantic ordering invariant belong in one
feature and one `ordered_integer` constraint. Choose the option order and
`nondecreasing`/`nonincreasing` direction from the domain, explicitly decide
whether equality is valid, and test defaults plus boundary and invalid vectors.

### Sparse record fields and bounded branches

Use format 4 when several independently configurable values live in one
semantic instruction or data record. Keep the complete stock record in
`expected`, but declare only the bytes the feature owns:

```toml
format_version = 4

[[option]]
feature = "x_saber_timing"
id = "timing_4"
label = "Timing 4"
type = "integer"
min = 1
max = 99
step = 1
default = 3

[[patch]]
feature = "x_saber_timing"
target = "disc_user"
offset = 432554280
expected = "03420132"
fields = [
  { offset = 0, option = "timing_4", encoding = "u8" },
]
```

The guard is compatibility evidence, not ownership. Runtime resolution checks
all four stock bytes before any mutation, while collision detection and
writing claim only byte zero. Another feature may own byte one of the same
record if its complete guard agrees. Do not shrink the guard to avoid a
collision, and do not claim neighboring flags or padding merely because the
source tool rewrites a convenient allocation unit.

Each field must be either non-empty literal bytes or one bounded integer option
from the same feature, using `u8`, `u16le`, `u32le`, or the reviewed linked
MIPS encoding. A checked `addend` can represent narrow relationships such as
`cap + 1` or `opacity - 1`. If the source requires more than that, do not
smuggle an expression language into the manifest.

For one bounded source value that selects different fixed templates, use
separate guarded patches with a typed predicate:

```toml
[[patch]]
feature = "maximum_lives"
target = "main_exe"
address = 2147587968
expected = "CC68000C"
fields = [
  { offset = 0, replace = "00000000" },
]
when_integer = { option = "maximum", op = "gt", value = 9 }
```

`when_integer` supports only `eq`, `ne`, `lt`, `le`, `gt`, and `ge` against a
constant inside the referenced option's bounds. It is resolved before boot and
may be ANDed with existing string conditions. It is not an expression VM or a
per-frame dispatcher.

Adversarial tests for a sparse conversion must include:

- two enabled features owning adjacent fields under the same complete guard;
- a real same-field collision with different replacements;
- failure caused by a changed guard-only byte before any write is applied;
- stock/default per-field no-op elision;
- minimum, interior, maximum, and every bounded branch boundary;
- additive encoding overflow rejection;
- sector-boundary splitting for disc guards; and
- deterministic report entries that distinguish guarded bytes from owned
  bytes.

## Dependencies and collisions

Build a resource ledger for every feature. Each row should record:

- resource key, such as file/record/subasset, guest range, or hook ID;
- direct or helper ownership;
- expected stock hash;
- replacement hash or hook action;
- option condition;
- lifecycle;
- known neighboring features; and
- reviewed composition outcome.

Run interval collision checks across disc and memory ranges and semantic checks
across assets and hooks.

- Identical expected and replacement bytes may be coalesced.
- Disjoint subasset changes may compose even when they share an outer record.
- Different bytes at the same location are a real collision unless represented
  through an explicit composition primitive.
- Package order, patcher order, or “last writer wins” is not composition.
- Enabling one feature must not silently disable another.
- A real incompatibility must name both features and let the user choose.

Some upstream dependencies are implementation closure rather than product
dependencies. A shared initialization write may belong inside each feature and
coalesce. A stable runtime hook may replace a group of ordered patches. A
genuinely meaningful feature dependency must be visible and validated. Record
the decision rather than copying upstream dependency syntax mechanically.

## Required test matrix

At minimum, test:

- supported stock hash and an explicitly rejected unsupported revision;
- feature disabled: no resolved operations and stock behavior;
- feature enabled with every choice or boolean value;
- integer minimum, maximum, default, and invalid values;
- every stock expected-byte or expected-hash guard;
- exact semantic comparison with the isolated oracle;
- actual runtime disc-read, memory-write, or hook path;
- cold boot and repeated launch;
- repeated and cross-sector disc reads for overlays;
- enable, disable, and re-enable persistence;
- every dependency edge;
- every shared-resource edge in the ownership graph;
- known combined oracles;
- at least one unrelated cross-category combination;
- exact collision diagnostics for deliberately incompatible fixtures;
- missing, corrupt, oversized, or hash-mismatched assets;
- deterministic package rebuild and conversion report; and
- install, upgrade, rollback, and removal behavior.

Add feature-specific behavioral tests such as screenshots, menu text, scripted
input, memory traces, save/load, or stage transitions. Byte parity does not
replace behavioral parity, and a screenshot does not replace byte ownership.

For hundreds of features, use the resource graph to select pairwise and
dependency combinations. Add higher-order tests only where a shared hook,
container, initialization path, or upstream exception rule joins three or more
features.

## Deterministic packaging and versioning

Use stable package and feature IDs. Never recycle an ID for a different
concept. Keep option IDs and values stable so saved state survives upgrades.

The package version is an explicit build input, not a converter constant.

- Patch releases fix conversion or packaging without changing the intended
  feature contract.
- Minor releases add backward-compatible features or option values.
- Major releases change IDs, state meaning, target assumptions, or other
  incompatible contracts.

Any payload, operation, target, default, or visible behavior change requires a
new version. The same `(package_id, version)` must never name two different
archives.

The conversion report should include:

- all provenance hashes and normalized selections;
- evidence level per feature;
- semantic ownership ledger;
- direct, helper, and excluded changes;
- operation counts and hashes;
- stock guards;
- dependency and collision results;
- plan fingerprint;
- test results;
- converter revision and explicit seed; and
- final archive hash.

Make ZIP entry ordering, timestamps, compression settings, path casing, and
manifest serialization deterministic. Validate the archive with the same
installer and resolver used by the product.

When installing a newer version, the launcher should clearly offer to replace
or retain the selected old version. It must not leave ambiguous active state.
Rollback may retain an older version, but only one selected version of a
package participates in a launch plan.

## Release and defer gates

Release only when all of the following are true:

- evidence is E6;
- the supported stock target is exact;
- every operation has semantic ownership and a stock guard;
- enabled and disabled behavior is proven;
- all resource-neighbor tests pass;
- the archive is deterministic and schema-valid;
- provenance and licensing are complete; and
- installation and upgrade behavior is verified.

Reject or defer a feature when any of these apply:

- an oracle byte is unexplained or ownership is inferred only from a whole-image
  diff;
- an address was copied from a derived image without stock semantic mapping;
- the feature claims a whole file or record for a smaller change;
- required common-base mutations cannot be separated from the feature;
- composition relies on patch order or silent overrides;
- a grown container has no resolver-owned allocator/composer;
- injected code has no registered hook or relocation infrastructure;
- the target lifecycle is unknown;
- a write is unbounded, unguarded, or targets an unsupported revision;
- the result depends on an unrecorded random seed or environment state;
- source assets, oracle recipe, or redistribution rights are unavailable;
- the feature lacks a negative test or a resource-neighbor test; or
- visible behavior cannot be reproduced through the native runtime path.

Deferral is a successful outcome of an adversarial review. It prevents a
derived-image assumption from becoming permanent runtime architecture.

## Compact MMX6 workflow

MMX6 Tweaks contains hundreds of options, common B01/S02 base changes,
dependencies, reorder rules, file inserts, nested `ROCK_X6.DAT` assets, and
injected behavior. Convert it incrementally:

1. Pin the USA v1.1 stock BIN SHA-256 and record the Tweaks patcher revision.
2. Inventory one human-facing option and its smallest activating dependency
   closure.
3. Produce `B`, feature-only `F`, and useful combined oracles from recorded
   profiles.
4. Diff for discovery, then subtract common-base changes and patcher
   scaffolding.
5. Map each remaining change to stock `ROCK_X6.BIN`, a
   `ROCK_X6.DAT` record/subasset, the main executable, a loaded overlay, or a
   stable behavior hook.
6. Review every Tweaks prerequisite and reorder edge. Classify it as owned
   helper, real dependency, composition rule, or excluded base noise.
7. Emit the narrowest guarded operations and a per-feature ownership ledger.
8. Materialize the plan over stock and compare it semantically with the
   feature-only oracle.
9. Run the stock BIN/CUE with the `.psxmod`, test the visible behavior, and
   verify the actual runtime read or execution path.
10. Test every existing feature that shares a record, byte range, hook, or
    lifecycle, plus any available combined oracle.
11. Mark the feature E6 only after deterministic package, install, upgrade,
    enable, disable, and collision tests pass.

The Rockman title-screen conversion demonstrates why this process matters.
Tweaks' B01-derived image moved `ROCK_X6.DAT` record 107 by `0x40` sectors.
Reusing its raw offsets against stock patched the wrong ranges. The correct
conversion identifies the palette as record `26`, subasset `0`, and the three
title assets as record `107`, subassets `1`, `3`, and `8`; it then resolves
those identities independently in stock and the oracles.

Retranslation also demonstrates a scaling limit. Replacing only owned
same-size subassets is composable. Reconstructing and relocating grown outer
records into fixed `ZNULL.DAT` space is not a general independent-feature
strategy: another growing feature may need the same storage, table entries, or
logical extent. Do not ingest another growing MMX6 feature until allocation and
container reconstruction are resolved for the complete enabled plan.

Recommended ingestion order:

1. same-size, semantically identified tables and assets;
2. narrow guarded scalar or startup writes;
3. self-contained existing-code edits with a proven runtime path;
4. shared behavior converted to stable hooks;
5. growing containers and injected routines only after allocator and relocation
   infrastructure exists.

Do not optimize for the number of converted checkboxes. Optimize for narrow
ownership, reproducible evidence, independent composition, and a runtime
architecture that will still work when the hundredth feature is enabled.
