#ifndef MMX6_COOP_JUMP_AUDIO_H
#define MMX6_COOP_JUMP_AUDIO_H
#include <stddef.h>
#include <stdint.h>

enum { MMX6_JUMP_AUDIO_HEADER_BYTES=8192, MMX6_JUMP_AUDIO_SFX_ID=14,
       MMX6_JUMP_AUDIO_VOICE_ID=15, MMX6_JUMP_AUDIO_SFX_BANK=30,
       MMX6_JUMP_AUDIO_VOICE_BANK=31 };
typedef enum {
    MMX6_JUMP_AUDIO_OK=0, MMX6_JUMP_AUDIO_ARGUMENT, MMX6_JUMP_AUDIO_FORMAT,
    MMX6_JUMP_AUDIO_PROGRAMS, MMX6_JUMP_AUDIO_SAMPLES, MMX6_JUMP_AUDIO_RECORD
} Mmx6JumpAudioReason;
typedef struct {
    uint32_t group,id,bank,bytes,sample_bytes,vab,programs,tones,records,samples;
} Mmx6JumpAudioHeader;

/* Construct native80060214's parsed tables at logical sample base0 without
 * opening a VAB, claiming a transfer gate or submitting/completing DMA.
 * All offsets are relative to the copied preheader. No asset bytes ship.
 * On refusal, neither output span nor descriptor is changed. */
Mmx6JumpAudioReason mmx6_jump_audio_prepare_header(const uint8_t *source,size_t size,
    size_t sample_bytes,unsigned group,uint8_t *parsed,size_t capacity,Mmx6JumpAudioHeader *out);
#endif
