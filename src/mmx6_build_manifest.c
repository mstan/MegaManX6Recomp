#include "build_manifest.h"
#include "mod_plugins.h"

/* Keep the actual target's compiled manifest present even before a transport
 * envelope consumes it. No guest state, settings or network behavior changes. */
static const char *volatile mmx6_build_manifest_anchor;
PSX_MOD_CONSTRUCTOR(mmx6_embed_build_manifest) {
    mmx6_build_manifest_anchor = psx_compiled_build_manifest_sha256();
}

const char *mmx6_declared_build_manifest_sha256(void) {
    return psx_compiled_build_manifest_sha256();
}
