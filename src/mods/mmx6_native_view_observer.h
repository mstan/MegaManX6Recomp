#ifndef MMX6_NATIVE_VIEW_OBSERVER_H
#define MMX6_NATIVE_VIEW_OBSERVER_H
#include "cpu_state.h"
#ifdef __cplusplus
extern "C" {
#endif
/* One optional observer of the existing two private draws. No draw request is
 * issued by the observer. BEGIN/END bracket clear, world, OT and final fade;
 * COMMITTED follows successful SDK pair publication and title restoration.
 * CANCEL follows a refused/aborted whole pair or invalidated title session. */
enum { MMX6_NATIVE_VIEW_BEGIN=1, MMX6_NATIVE_VIEW_END=2, MMX6_NATIVE_PAIR_CANCEL=3, MMX6_NATIVE_PAIR_COMMITTED=4 };
typedef void (*Mmx6NativeViewObserver)(void*,CPUState*,unsigned event,unsigned seat,int complete);
void mmx6_native_coop_set_observer(Mmx6NativeViewObserver observer,void *user);
#ifdef __cplusplus
}
#endif
#endif
