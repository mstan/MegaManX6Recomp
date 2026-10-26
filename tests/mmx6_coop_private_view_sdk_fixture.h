#ifndef MMX6_COOP_PRIVATE_VIEW_SDK_FIXTURE_H
#define MMX6_COOP_PRIVATE_VIEW_SDK_FIXTURE_H
#include "mod_plugins.h"
#include "cpu_state.h"
/* Explicit unit perimeter, not a GPU/sandbox implementation or render proof.
 * Default shared options and refusal preserve existing fixture semantics. */
typedef int (*Mmx6ViewFixtureTransaction)(CPUState *,PSXModRenderPassFn,void *,uint32_t);
typedef struct {
    const char *local_cameras,*cameras;
    int online,local_port,pair_enabled,busy;
    unsigned pair_calls,view_calls,aspect_calls;
    Mmx6ViewFixtureTransaction transaction;
} Mmx6ViewSdkFixture;
extern Mmx6ViewSdkFixture mmx6_view_sdk;
void mmx6_view_sdk_reset(void);
#endif
