/* PRIVATE OFFLINE prerequisite bypass, never retry or progression evidence.
 * Mode8 loads the selected stage and clears CP; only its ordinary mode9 entry
 * may install the requested CP before the original initializer executes. */
#include "mmx6_coop_checkpoint_data.h"
#if defined(__has_include)
#if __has_include("session_input_taint.h")
#include "session_input_taint.h"
#define MMX6_COOP_CHECKPOINT_TAINT_API 1
#endif
#endif
enum { CHECKPOINT_CAPABILITY=0x31504B43u, CHECKPOINT_IDLE=0,
    CHECKPOINT_LOADING=1,CHECKPOINT_INITIALIZING=2,CHECKPOINT_COMPLETE=3,
    CHECKPOINT_FAILED=4,CHECKPOINT_REJECTED=5 };
enum { CHECKPOINT_OK=0,CHECKPOINT_FORBIDDEN=1,CHECKPOINT_UNKNOWN=2,
    CHECKPOINT_NAMESPACE=3,CHECKPOINT_UNSAFE=4,CHECKPOINT_SOURCE=5,
    CHECKPOINT_ORDER=6,CHECKPOINT_CONTEXT=7,CHECKPOINT_PLUGIN_FAILED=8 };
typedef struct { unsigned phase,index; uint32_t nonce; } Mmx6CheckpointPending;
static Mmx6CheckpointPending checkpoint_pending;

static uint32_t checkpoint_hash(uint32_t first,uint32_t end) {
    uint32_t hash=2166136261u;
    for(uint32_t at=first;at<end;++at)hash=(hash^psx_mod_read_byte(at))*16777619u;
    return hash;
}
static int checkpoint_source(const Mmx6Checkpoint *entry) {
    if(psx_mod_read_word(0x8007114C)!=0x8001E914u ||
       psx_mod_read_word(0x80071150)!=0x8001E1BCu ||
       psx_mod_read_word(0x80073300u+(entry->stage*2u+entry->section)*4u)!=entry->table ||
       psx_mod_read_word(entry->table+entry->checkpoint*4u)!=entry->record ||
       checkpoint_hash(entry->record,entry->record+36)!=entry->hash)return 0;
    for(unsigned i=0;i<sizeof checkpoint_code/sizeof checkpoint_code[0];++i)
        if(checkpoint_hash(checkpoint_code[i].first,checkpoint_code[i].end)!=checkpoint_code[i].hash)return 0;
    return 1;
}
static void checkpoint_status(unsigned status,unsigned reason) {
    psx_mod_write_byte(diagnostic+0xA8,(uint8_t)status);
    psx_mod_write_byte(diagnostic+0xA9,(uint8_t)reason);
}
static void checkpoint_cancel(unsigned reason) {
    memset(&checkpoint_pending,0,sizeof checkpoint_pending);
    checkpoint_status(CHECKPOINT_FAILED,reason);
}
static void checkpoint_reset(void) {
    memset(&checkpoint_pending,0,sizeof checkpoint_pending);
    if(diagnostic) {
        if(psx_mod_read_byte(diagnostic+0x50)==8)psx_mod_write_byte(diagnostic+0x50,0);
        for(unsigned i=0xA0;i<0xC0;++i)psx_mod_write_byte(diagnostic+i,0);
        psx_mod_write_word(diagnostic+0xA0,CHECKPOINT_CAPABILITY);
    }
}
static int checkpoint_stage_boundary(CPUState *cpu) {
    (void)cpu;
    if(checkpoint_pending.phase) {
        const Mmx6Checkpoint *entry=&checkpoint_inventory[checkpoint_pending.index];
        if(failed || !diagnostic_mutation_allowed())checkpoint_cancel(failed?CHECKPOINT_PLUGIN_FAILED:CHECKPOINT_FORBIDDEN);
        else if(checkpoint_pending.phase==2 && psx_mod_read_byte(PLAY)==10 &&
                psx_mod_read_byte(PLAY+12)==entry->stage && psx_mod_read_byte(PLAY+13)==entry->section &&
                psx_mod_read_byte(PLAY+0x1D)==entry->checkpoint) {
            memset(&checkpoint_pending,0,sizeof checkpoint_pending);
            checkpoint_status(CHECKPOINT_COMPLETE,CHECKPOINT_OK);
        } else checkpoint_cancel(CHECKPOINT_ORDER);
    }
    if(psx_mod_read_byte(diagnostic+0x50)!=8)return 0;
    unsigned stage=psx_mod_read_byte(diagnostic+0x51),section=psx_mod_read_byte(diagnostic+0x52);
    unsigned cp=psx_mod_read_byte(diagnostic+0x53),reason=CHECKPOINT_OK,index=115;
    uint32_t nonce=psx_mod_read_word(diagnostic+0x54);
    for(unsigned i=0;i<115;++i)if(checkpoint_inventory[i].stage==stage &&
        checkpoint_inventory[i].section==section && checkpoint_inventory[i].checkpoint==cp){index=i;break;}
    const Mmx6Checkpoint *entry=index<115?&checkpoint_inventory[index]:NULL;
    if(!diagnostic_mutation_allowed())reason=CHECKPOINT_FORBIDDEN;
    else if(!entry || !nonce)reason=CHECKPOINT_UNKNOWN;
    else if(!entry->campaign)reason=CHECKPOINT_NAMESPACE;
    else if(!ready || !enrolled || failed || inside || stage_call || player_call || ride_call || view_call || private_draw || zero_world ||
            zero_projected || scene_owner || scene_phase || pause_owner>=0 || zero_menu_loaded ||
            state_track.count || state_track.error || psx_mod_read_byte(PLAY)!=10 ||
            psx_mod_read_byte(PLAY+1) || psx_mod_read_byte(PLAY+0x10) || psx_mod_read_byte(PLAY+0x1C) ||
            psx_mod_read_byte(PLAYER+4)!=1 || p2.body[4]!=1 ||
            !psx_mod_read_byte(PLAYER+0x5C) || psx_mod_read_byte(PLAYER+0x5C)>127 ||
            !p2.body[0x5C] || p2.body[0x5C]>127 ||
            life.status[0]!=MMX6_COOP_ALIVE || life.status[1]!=MMX6_COOP_ALIVE)reason=CHECKPOINT_UNSAFE;
    else if(!checkpoint_source(entry))reason=CHECKPOINT_SOURCE;
    /* Reject before any authoritative game write. These are diagnostic receipts. */
    psx_mod_write_byte(diagnostic+0x50,0);
    psx_mod_write_word(diagnostic+0xA4,psx_mod_read_word(diagnostic+0xA4)+1);
    psx_mod_write_byte(diagnostic+0xAA,(uint8_t)stage);
    psx_mod_write_byte(diagnostic+0xAB,(uint8_t)section);
    psx_mod_write_byte(diagnostic+0xAC,(uint8_t)cp);
    psx_mod_write_word(diagnostic+0xB0,nonce);
    psx_mod_write_word(diagnostic+0xB4,0);
    psx_mod_write_word(diagnostic+0xB8,entry?entry->record:0);
    if(reason) {
        checkpoint_status(CHECKPOINT_REJECTED,reason);
        psx_mod_counter_add("mmx6.coop.debug-fixture-rejected",1);
        return 0;
    }
    checkpoint_pending=(Mmx6CheckpointPending){1,index,nonce};
    checkpoint_status(CHECKPOINT_LOADING,CHECKPOINT_OK);
    psx_mod_write_byte(diagnostic+0xBC,1); /* Sticky until activation; original-input proof is tainted. */
#ifdef MMX6_COOP_CHECKPOINT_TAINT_API
    psx_session_input_taint_add(PSX_INPUT_TAINT_GAME_MAILBOX);
#endif
    psx_mod_write_byte(PLAY+12,(uint8_t)stage);
    psx_mod_write_byte(PLAY+13,(uint8_t)section);
    psx_mod_write_byte(PLAY,8);
    return 1; /* Caller must skip this stale stage's original world pass. */
}
static void checkpoint_native_entry(CPUState *cpu,uint32_t address) {
    if(!checkpoint_pending.phase)return;
    const Mmx6Checkpoint *entry=&checkpoint_inventory[checkpoint_pending.index];
    if(!diagnostic_mutation_allowed() || failed) {
        checkpoint_cancel(failed?CHECKPOINT_PLUGIN_FAILED:CHECKPOINT_FORBIDDEN);return;
    }
    if(checkpoint_pending.phase!=1 || address!=0x8001E1BCu ||
       cpu->gpr[31]!=0x8001E720u || cpu->gpr[4]!=PLAY || inside || stage_call || ride_call || view_call || private_draw ||
       zero_projected || state_track.count || state_track.error || psx_mod_read_byte(PLAY)!=9 ||
       psx_mod_read_byte(PLAY+12)!=entry->stage || psx_mod_read_byte(PLAY+13)!=entry->section ||
       psx_mod_read_byte(PLAY+0x1D)!=0) {checkpoint_cancel(CHECKPOINT_CONTEXT);return;}
    if(!checkpoint_source(entry)){checkpoint_cancel(CHECKPOINT_SOURCE);return;}
    psx_mod_write_byte(PLAY+0x1D,entry->checkpoint);
    checkpoint_pending.phase=2;
    psx_mod_write_word(diagnostic+0xB4,1);
    checkpoint_status(CHECKPOINT_INITIALIZING,CHECKPOINT_OK);
    /* No guest call/replacement: the original mode9 initializer continues once. */
}
