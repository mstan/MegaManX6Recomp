#ifndef MMX6_COOP_STATE_TRACK_H
#define MMX6_COOP_STATE_TRACK_H
#include <stdint.h>
#include <string.h>

/* Future-restored callback locals become explicit digest state while guest
 * calls can yield. Digest reads owned copies, including after a watchdog
 * abandons the C stack. Pointers,
 * padding and native word byte order never enter the digest or snapshot. */
enum { MMX6_STATE_FRAMES=64, MMX6_STATE_FRAME_BYTES=8192 };
typedef struct {
    uint32_t tag,bytes,words;
    uint8_t saved[MMX6_STATE_FRAME_BYTES];
} Mmx6StateFrame;
typedef struct {
    Mmx6StateFrame frame[MMX6_STATE_FRAMES];
    unsigned count,error;
} Mmx6StateTrack;
static Mmx6StateTrack state_track;

static unsigned mmx6_state_push(uint32_t tag,const void *source,uint32_t bytes,unsigned words) {
    if (!source || bytes>MMX6_STATE_FRAME_BYTES || (words && bytes%4) ||
        state_track.count==MMX6_STATE_FRAMES || state_track.error) {
        state_track.error=1;return UINT32_MAX;
    }
    unsigned slot=state_track.count++;
    Mmx6StateFrame *f=&state_track.frame[slot];
    f->tag=tag;f->bytes=bytes;f->words=!!words;
    memcpy(f->saved,source,bytes);
    return slot;
}
static int mmx6_state_can_call(void) {
    return !state_track.error;
}
static void mmx6_state_update(unsigned slot,const void *source) {
    if (slot>=state_track.count || !source) {state_track.error=1;return;}
    memcpy(state_track.frame[slot].saved,source,state_track.frame[slot].bytes);
}
static void mmx6_state_pop(unsigned slot) {
    if (slot>=state_track.count || slot+1!=state_track.count) {state_track.error=1;return;}
    state_track.count=slot;
}
#define STATE_BYTES(name,tag,source,size) unsigned name=mmx6_state_push(tag,source,(uint32_t)(size),0)
#define STATE_WORDS(name,tag,source,count) unsigned name=mmx6_state_push(tag,source,(uint32_t)(count)*4u,1)
#define STATE_POP(name) mmx6_state_pop(name)
#define STATE_UPDATE(name,source) mmx6_state_update(name,source)
#endif
