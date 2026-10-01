#ifndef MMX6_COOP_LIFECYCLE_H
#define MMX6_COOP_LIFECYCLE_H
#include <stdint.h>

typedef enum {
    MMX6_COOP_ALIVE, MMX6_COOP_LEAVING, MMX6_COOP_ABSENT,
    MMX6_COOP_JOINING, MMX6_COOP_DYING, MMX6_COOP_FALLEN
} Mmx6CoopStatus;
typedef enum { MMX6_COOP_NO_ACTION, MMX6_COOP_LEAVE, MMX6_COOP_JOIN } Mmx6CoopJoinAction;
typedef struct {
    Mmx6CoopStatus status[2];
    unsigned select_frames;
    uint8_t select_armed, select_previous, wipe; /* wipe = last fallen seat + 1 */
} Mmx6CoopLifecycle;

void mmx6_coop_lifecycle_init(Mmx6CoopLifecycle *s);
int mmx6_coop_living(const Mmx6CoopLifecycle *s, unsigned player);
/* Called on native death entry, before the death animation finishes. */
void mmx6_coop_fatal(Mmx6CoopLifecycle *s, unsigned player);
/* Only a new stage or a team respawn may clear FALLEN. An ordinary door may not. */
void mmx6_coop_lifecycle_respawn(Mmx6CoopLifecycle *s);
Mmx6CoopJoinAction mmx6_coop_join_input(Mmx6CoopLifecycle *s,
                                     int select, int gameplay, int safe_landing);
/* Completion is separate from the request, so native teleport art can finish. */
void mmx6_coop_teleport_done(Mmx6CoopLifecycle *s);
int32_t mmx6_coop_limit_x(int32_t x, int32_t other, unsigned viewport_width);
#endif
