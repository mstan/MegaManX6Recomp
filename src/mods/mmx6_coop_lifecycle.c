#include "mmx6_coop_lifecycle.h"
#include <string.h>

void mmx6_coop_lifecycle_init(Mmx6CoopLifecycle *s) {
    memset(s, 0, sizeof *s);
    s->status[0] = s->status[1] = MMX6_COOP_ALIVE;
}
int mmx6_coop_living(const Mmx6CoopLifecycle *s, unsigned p) {
    return p < 2 && (s->status[p] == MMX6_COOP_ALIVE ||
                    s->status[p] == MMX6_COOP_JOINING || s->status[p] == MMX6_COOP_LEAVING);
}
void mmx6_coop_fatal(Mmx6CoopLifecycle *s, unsigned p) {
    if (p > 1 || s->status[p] == MMX6_COOP_FALLEN || s->status[p] == MMX6_COOP_DYING) return;
    s->status[p] = MMX6_COOP_DYING;
    if (!mmx6_coop_living(s, p ^ 1)) s->wipe = (uint8_t)(p+1);
    s->select_frames = 0;
}
void mmx6_coop_lifecycle_respawn(Mmx6CoopLifecycle *s) {
    mmx6_coop_lifecycle_init(s);
}
Mmx6CoopJoinAction mmx6_coop_join_input(Mmx6CoopLifecycle *s,
                                     int select, int gameplay, int safe_landing) {
    int pressed = select && !s->select_previous;
    s->select_previous = (uint8_t)!!select;
    if (!select) { s->select_armed = 1; s->select_frames = 0; }
    if (!gameplay || s->wipe) { s->select_frames = 0; return MMX6_COOP_NO_ACTION; }
    if (s->status[1] == MMX6_COOP_ALIVE && mmx6_coop_living(s, 0)) {
        if (select && s->select_armed && ++s->select_frames >= 90) {
            s->status[1] = MMX6_COOP_LEAVING;
            s->select_frames = s->select_armed = 0;
            return MMX6_COOP_LEAVE;
        }
    } else {
        s->select_frames = 0;
        if (s->status[1] == MMX6_COOP_ABSENT && pressed && safe_landing && mmx6_coop_living(s, 0)) {
            s->status[1] = MMX6_COOP_JOINING;
            s->select_armed = 0;
            return MMX6_COOP_JOIN;
        }
    }
    return MMX6_COOP_NO_ACTION;
}
void mmx6_coop_teleport_done(Mmx6CoopLifecycle *s) {
    if (s->status[1] == MMX6_COOP_LEAVING) s->status[1] = MMX6_COOP_ABSENT;
    else if (s->status[1] == MMX6_COOP_JOINING) s->status[1] = MMX6_COOP_ALIVE;
    s->select_frames = s->select_armed = 0;
}
int32_t mmx6_coop_limit_x(int32_t x, int32_t other, unsigned width) {
    /* X1 allows 224 pixels of separation in a 256-pixel viewport. */
    int64_t limit = (int64_t)width * 7 * 65536 / 8;
    int64_t delta = (int64_t)x - other;
    if (delta > limit) return (int32_t)((int64_t)other + limit);
    if (delta < -limit) return (int32_t)((int64_t)other - limit);
    return x;
}
