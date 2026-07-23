# MMX6 trusted mod resolvers

Each source file in this directory owns one game-specific resolver domain and
registers a stable `builtin:<id>` resolver with PSXRecomp's mod-package
manager.

Keep domains independent:

- one source file and package generator per semantic domain;
- no package-supplied native code;
- complete stock guards on every emitted write;
- feature-local selection state only;
- deterministic output independent of feature or package declaration order;
- explicit collision ownership for shared code, tables, or allocations; and
- disabled features emit no operations.

Prefer declarative package operations. A trusted resolver belongs here only
when several independent features must compose into a shared bitfield, table,
routine, allocation, or other semantic record that cannot be represented by
ordinary non-overlapping writes.
