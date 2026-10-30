#include "mmx6_coop_lifecycle.h"
#include <stdio.h>
#include <stdlib.h>

#define CHECK(x) do { if (!(x)) { fprintf(stderr, "line %d: %s\n", __LINE__, #x); exit(1); } } while (0)

static void depart(Mmx6CoopLifecycle *s) {
    mmx6_coop_lifecycle_init(s);
    CHECK(mmx6_coop_join_input(s,0,1,1)==MMX6_COOP_NO_ACTION);
    for (unsigned n=0;n<89;++n) CHECK(mmx6_coop_join_input(s,1,1,1)==MMX6_COOP_NO_ACTION);
    CHECK(mmx6_coop_join_input(s,1,1,1)==MMX6_COOP_LEAVE);
    CHECK(s->status[1]==MMX6_COOP_LEAVING);
    mmx6_coop_teleport_done(s);
    CHECK(s->status[1]==MMX6_COOP_ABSENT);
}

static void queued_rejoin(void) {
    Mmx6CoopLifecycle s;
    depart(&s);
    CHECK(mmx6_coop_join_input(&s,0,1,0)==MMX6_COOP_NO_ACTION);
    CHECK(mmx6_coop_join_input(&s,1,1,0)==MMX6_COOP_NO_ACTION);
    /* One real request while X is airborne survives release and waits for
     * native safe ground. Requiring a second button press loses that request. */
    for (unsigned n=0;n<10;++n) CHECK(mmx6_coop_join_input(&s,0,1,0)==MMX6_COOP_NO_ACTION);
    CHECK(mmx6_coop_join_input(&s,0,1,1)==MMX6_COOP_JOIN);
    CHECK(s.status[1]==MMX6_COOP_JOINING);
    CHECK(mmx6_coop_join_input(&s,0,1,1)==MMX6_COOP_NO_ACTION);
    mmx6_coop_teleport_done(&s);
    CHECK(s.status[1]==MMX6_COOP_ALIVE);

    depart(&s);
    CHECK(mmx6_coop_join_input(&s,0,1,0)==MMX6_COOP_NO_ACTION);
    CHECK(mmx6_coop_join_input(&s,1,1,0)==MMX6_COOP_NO_ACTION);
    /* A pre-existing request waits through a temporary native scene. Input
     * during the scene cannot execute an arrival, even at a safe location. */
    CHECK(mmx6_coop_join_input(&s,0,0,1)==MMX6_COOP_NO_ACTION);
    CHECK(mmx6_coop_join_input(&s,0,1,1)==MMX6_COOP_JOIN);

    depart(&s);
    CHECK(mmx6_coop_join_input(&s,0,1,0)==MMX6_COOP_NO_ACTION);
    CHECK(mmx6_coop_join_input(&s,1,1,0)==MMX6_COOP_NO_ACTION);
    mmx6_coop_fatal(&s,0);
    CHECK(s.wipe==1);
    CHECK(mmx6_coop_join_input(&s,0,1,1)==MMX6_COOP_NO_ACTION);
    CHECK(s.status[1]==MMX6_COOP_ABSENT);
    mmx6_coop_lifecycle_respawn(&s);
    CHECK(mmx6_coop_join_input(&s,0,1,1)==MMX6_COOP_NO_ACTION);
    CHECK(s.status[1]==MMX6_COOP_ALIVE);
}

static void blocked_input_edges(void) {
    Mmx6CoopLifecycle s;
    depart(&s);
    CHECK(mmx6_coop_join_input(&s,0,1,1)==MMX6_COOP_NO_ACTION);
    /* A Select edge first seen during a menu/scene is consumed there. It
     * must not become a fabricated ordinary-gameplay rejoin on resume. */
    CHECK(mmx6_coop_join_input(&s,1,0,1)==MMX6_COOP_NO_ACTION);
    CHECK(mmx6_coop_join_input(&s,1,1,1)==MMX6_COOP_NO_ACTION);
    CHECK(s.status[1]==MMX6_COOP_ABSENT);
    /* Releasing in the blocked interval updates history too, allowing the
     * next genuine gameplay press without requiring an extra release. */
    CHECK(mmx6_coop_join_input(&s,0,0,1)==MMX6_COOP_NO_ACTION);
    CHECK(mmx6_coop_join_input(&s,1,1,1)==MMX6_COOP_JOIN);

    mmx6_coop_lifecycle_respawn(&s);
    CHECK(mmx6_coop_join_input(&s,0,1,1)==MMX6_COOP_NO_ACTION);
    for (unsigned n=0;n<89;++n) CHECK(mmx6_coop_join_input(&s,1,1,1)==MMX6_COOP_NO_ACTION);
    CHECK(mmx6_coop_join_input(&s,1,0,1)==MMX6_COOP_NO_ACTION);
    for (unsigned n=0;n<89;++n) CHECK(mmx6_coop_join_input(&s,1,1,1)==MMX6_COOP_NO_ACTION);
    CHECK(mmx6_coop_join_input(&s,1,1,1)==MMX6_COOP_LEAVE);
}

static void rejoin_during_departure(void) {
    Mmx6CoopLifecycle s;
    mmx6_coop_lifecycle_init(&s);
    CHECK(mmx6_coop_join_input(&s,0,1,1)==MMX6_COOP_NO_ACTION);
    for (unsigned n=0;n<89;++n) CHECK(mmx6_coop_join_input(&s,1,1,1)==MMX6_COOP_NO_ACTION);
    CHECK(mmx6_coop_join_input(&s,1,1,1)==MMX6_COOP_LEAVE);
    /* Holding the original departure press never requests an immediate return. */
    for (unsigned n=0;n<10;++n) CHECK(mmx6_coop_join_input(&s,1,1,1)==MMX6_COOP_NO_ACTION);
    CHECK(mmx6_coop_join_input(&s,0,1,1)==MMX6_COOP_NO_ACTION);
    CHECK(mmx6_coop_join_input(&s,1,1,1)==MMX6_COOP_NO_ACTION);
    CHECK(s.status[1]==MMX6_COOP_LEAVING);
    mmx6_coop_teleport_done(&s);
    CHECK(s.status[1]==MMX6_COOP_ABSENT);
    /* A duplicate outgoing completion must not cancel that accepted request. */
    mmx6_coop_teleport_done(&s);
    CHECK(mmx6_coop_join_input(&s,1,1,1)==MMX6_COOP_JOIN);
    CHECK(mmx6_coop_join_input(&s,1,1,1)==MMX6_COOP_NO_ACTION);
    mmx6_coop_teleport_done(&s);
    CHECK(s.status[1]==MMX6_COOP_ALIVE);
    for (unsigned n=0;n<100;++n) CHECK(mmx6_coop_join_input(&s,1,1,1)==MMX6_COOP_NO_ACTION);
}

static void voluntary_absence_across_native_checkpoint(void) {
    Mmx6CoopLifecycle s;
    depart(&s);
    /* Original held departure input is not a new rejoin after loading. */
    mmx6_coop_lifecycle_checkpoint(&s);
    CHECK(s.status[0]==MMX6_COOP_ALIVE && s.status[1]==MMX6_COOP_ABSENT);
    CHECK(mmx6_coop_join_input(&s,1,1,1)==MMX6_COOP_NO_ACTION);
    CHECK(mmx6_coop_join_input(&s,0,1,1)==MMX6_COOP_NO_ACTION);
    CHECK(mmx6_coop_join_input(&s,1,1,1)==MMX6_COOP_JOIN);
    depart(&s);
    CHECK(mmx6_coop_join_input(&s,0,1,0)==MMX6_COOP_NO_ACTION);
    CHECK(mmx6_coop_join_input(&s,1,1,0)==MMX6_COOP_NO_ACTION);
    mmx6_coop_lifecycle_checkpoint(&s);
    CHECK(s.status[1]==MMX6_COOP_ABSENT && s.rejoin_pending);
    CHECK(mmx6_coop_join_input(&s,0,1,1)==MMX6_COOP_JOIN);
    depart(&s);
    mmx6_coop_fatal(&s,0);
    CHECK(s.wipe==1);
    mmx6_coop_lifecycle_checkpoint(&s);
    CHECK(!s.wipe && s.status[0]==MMX6_COOP_ALIVE && s.status[1]==MMX6_COOP_ALIVE);
}

static void death_and_retry_contract(void) {
    Mmx6CoopLifecycle s;
    for (unsigned first=0;first<2;++first) {
        unsigned last=first^1;
        mmx6_coop_lifecycle_init(&s);
        mmx6_coop_fatal(&s,first);
        CHECK(s.status[first]==MMX6_COOP_DYING && !s.wipe);
        CHECK(mmx6_coop_living(&s,last));
        mmx6_coop_fatal(&s,first); /* Native death callbacks may repeat. */
        CHECK(!s.wipe);
        s.status[first]=MMX6_COOP_FALLEN;
        mmx6_coop_fatal(&s,last);
        CHECK(s.wipe==last+1 && s.status[last]==MMX6_COOP_DYING);
        mmx6_coop_fatal(&s,first);
        mmx6_coop_fatal(&s,last);
        CHECK(s.wipe==last+1);
        mmx6_coop_lifecycle_respawn(&s);
        CHECK(!s.wipe && s.status[0]==MMX6_COOP_ALIVE && s.status[1]==MMX6_COOP_ALIVE);
        for (unsigned n=0;n<100;++n) CHECK(mmx6_coop_join_input(&s,1,1,1)==MMX6_COOP_NO_ACTION);
    }
    depart(&s);
    mmx6_coop_fatal(&s,1); /* No native actor exists for a voluntary absence. */
    CHECK(s.status[1]==MMX6_COOP_ABSENT && !s.wipe);
    mmx6_coop_fatal(&s,0);
    CHECK(s.wipe==1);
    mmx6_coop_fatal(&s,1);
    CHECK(s.status[1]==MMX6_COOP_ABSENT && s.wipe==1);
    mmx6_coop_fatal(&s,2);
    CHECK(s.wipe==1);

    /* Both beam directions still count as living until native completion;
     * the plugin's survivor recovery keeps that genuine remaining player. */
    for (unsigned phase=MMX6_COOP_LEAVING;phase<=MMX6_COOP_JOINING;phase+=2) {
        mmx6_coop_lifecycle_init(&s);
        s.status[1]=(Mmx6CoopStatus)phase;
        mmx6_coop_fatal(&s,0);
        CHECK(!s.wipe && mmx6_coop_living(&s,1));
    }
}

int main(void) {
    Mmx6CoopLifecycle s;
    mmx6_coop_lifecycle_init(&s);
    /* Holding Select at boot does not count as a deliberate departure. */
    for (int n=0;n<100;++n) CHECK(mmx6_coop_join_input(&s,1,1,1)==MMX6_COOP_NO_ACTION);
    mmx6_coop_join_input(&s,0,1,1);
    for (int n=0;n<89;++n) CHECK(mmx6_coop_join_input(&s,1,1,1)==MMX6_COOP_NO_ACTION);
    CHECK(mmx6_coop_join_input(&s,1,1,1)==MMX6_COOP_LEAVE);
    CHECK(s.status[1]==MMX6_COOP_LEAVING);
    mmx6_coop_teleport_done(&s);
    CHECK(s.status[1]==MMX6_COOP_ABSENT);
    CHECK(mmx6_coop_join_input(&s,1,1,1)==MMX6_COOP_NO_ACTION);
    mmx6_coop_join_input(&s,0,1,1);
    CHECK(mmx6_coop_join_input(&s,1,1,0)==MMX6_COOP_NO_ACTION);
    CHECK(mmx6_coop_join_input(&s,0,1,1)==MMX6_COOP_JOIN);
    mmx6_coop_teleport_done(&s);
    CHECK(s.status[1]==MMX6_COOP_ALIVE);
    mmx6_coop_join_input(&s,0,1,1);
    for (int n=0;n<60;++n) mmx6_coop_join_input(&s,1,1,1);
    mmx6_coop_join_input(&s,1,0,1); /* Pause/scene breaks consecutive gameplay hold. */
    for (int n=0;n<89;++n) CHECK(mmx6_coop_join_input(&s,1,1,1)==MMX6_COOP_NO_ACTION);
    CHECK(mmx6_coop_join_input(&s,1,1,1)==MMX6_COOP_LEAVE);
    mmx6_coop_lifecycle_respawn(&s);
    mmx6_coop_fatal(&s,0);
    CHECK(!s.wipe && mmx6_coop_living(&s,1));
    mmx6_coop_join_input(&s,0,1,1);
    for (int n=0;n<100;++n) CHECK(mmx6_coop_join_input(&s,1,1,1)==MMX6_COOP_NO_ACTION);
    mmx6_coop_fatal(&s,1);
    CHECK(s.wipe==2);
    mmx6_coop_lifecycle_respawn(&s);
    mmx6_coop_fatal(&s,1);
    s.status[1]=MMX6_COOP_FALLEN;
    mmx6_coop_join_input(&s,0,1,1);
    CHECK(mmx6_coop_join_input(&s,1,1,1)==MMX6_COOP_NO_ACTION);
    CHECK(!s.wipe);
    mmx6_coop_fatal(&s,0);
    CHECK(s.wipe==1);
    mmx6_coop_lifecycle_respawn(&s);
    CHECK(s.status[0]==MMX6_COOP_ALIVE && s.status[1]==MMX6_COOP_ALIVE && !s.wipe);
    CHECK(mmx6_coop_limit_x(600*65536,100*65536,320)==380*65536);
    CHECK(mmx6_coop_limit_x(0,400*65536,320)==120*65536);
    CHECK(mmx6_coop_limit_x(500*65536,100*65536,640)==500*65536);
    queued_rejoin();
    blocked_input_edges();
    rejoin_during_departure();
    voluntary_absence_across_native_checkpoint();
    death_and_retry_contract();
    puts("co-op lifecycle rules PASS");
    return 0;
}
