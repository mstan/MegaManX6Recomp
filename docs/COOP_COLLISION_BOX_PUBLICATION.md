# Private collision-box observation

`X6BX`, schema1 at diagnostic offset1C20, publishes the four actual bytes
addressed by cached P2's attack(+50), damage(+54) and body(+68) pointers.
Pointers inside801EA000..801F5000 resolve against the private `zero_overlay`
code/data image, including its final four bytes. They never read the restored
resident X overlay. Pointers in80010000..801EA000 resolve against current native
RAM; null, crossing, unsupported and unavailable-bank pointers report no bytes.

The64-byte block contains magic/schema/size/base tick, three12-byte records
(pointer, origin, four bytes) and12 zero reserved bytes. Origins0/1/2 mean
unavailable/native RAM/private overlay. The writer clears unavailable payloads
and finishes before the existing even publication sequence. It calls no guest
code, projects no bank and changes no gameplay state. Existing base schema1
and FX readers retain their extents. The existing2000-byte allocation bounds
the new end1C60.

`tools/mmx6_coop_collision_boxes.py` requires one complete1C60-byte read,
validates the base seqlock, tick, pointer agreement, origin ranges and reserved
bytes, then returns both published bodies and the box data. The caller supplies
its PID/listener-checked read-only callback. Cached or inactive bodies remain
cached or inactive: source bytes do not establish pose eligibility, contact,
collision mechanics or a gameplay pass. Native actor-pool/camera reads are
separate observations and must not be described as atomic with this block.

The actual-plugin diagnostic fixtures deliberately put different bytes in
resident and private banks, check the last valid private address and a crossing
address, require odd publication during every write, check clearing on loss of
availability, and retain canaries and source/body immutability. The parser tests
reject stale/torn/mismatched blocks and malformed replies. Native qualification
is still required on the newly compiled image.
