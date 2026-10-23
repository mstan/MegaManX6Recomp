#ifndef MMX6_DIAGNOSTICS_H
#define MMX6_DIAGNOSTICS_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
enum {
    MMX6_INPUT_STAGE=0, MMX6_INPUT_CONTROLLER_SCENE=1,
    MMX6_INPUT_CONTROLLER_INACTIVE=2, MMX6_INPUT_CONTROLLER_BLOCKED=3,
    MMX6_INPUT_CONTROLLER_PLAYER=4, MMX6_INPUT_INTERACTION=5
};
/* Observe the one actual, final active-high standard-button read. Normal
 * recording returns buttons unchanged. Explicit validated offline replay
 * supplies that ordered consumer's recorded value; a mismatch never returns.
 * Never polls SIO or calls guest code. contaminated marks mailbox input. */
uint16_t mmx6_diagnostics_p2(unsigned consumer,uint16_t buttons,int contaminated);
#ifdef __cplusplus
}
#endif
#endif
