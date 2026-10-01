#include "mmx6_coop_lifecycle.h"
#include <stdio.h>
#include <stdlib.h>

#define CHECK(x) do { if (!(x)) { fprintf(stderr, "line %d: %s\n", __LINE__, #x); exit(1); } } while (0)
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
    mmx6_coop_join_input(&s,0,1,1);
    CHECK(mmx6_coop_join_input(&s,1,1,1)==MMX6_COOP_JOIN);
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
    puts("co-op lifecycle rules PASS");
    return 0;
}
