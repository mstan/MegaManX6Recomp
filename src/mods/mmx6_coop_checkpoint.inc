/* PRIVATE prerequisite bypass, never retry or progression evidence.
 * Mode8 loads the selected stage and clears CP; only its ordinary mode9 entry
 * may install the requested CP before the original initializer executes. */
#include "mmx6_coop_checkpoint_data.h"
#if defined(__has_include)
#if __has_include("session_input_taint.h")
#include "session_input_taint.h"
#define MMX6_COOP_CHECKPOINT_TAINT_API 1
#endif
#endif
#if defined(MMX6_ENABLE_LOOPBACK_HOST_LAB) && MMX6_ENABLE_LOOPBACK_HOST_LAB && !defined(PSX_NO_DEBUG_TOOLS) && defined(MMX6_COOP_CHECKPOINT_TAINT_API) && defined(PSX_MOD_NETPLAY_SETTINGS_LOADING_API) && PSX_MOD_NETPLAY_SETTINGS_LOADING_API >= 1 && defined(PSX_MOD_NETPLAY_HOST_CATALOG_API) && PSX_MOD_NETPLAY_HOST_CATALOG_API >= 2
#include "psx_netplay.h"
#include "mmx6_coop_host_lab_contract.h"
#define MMX6_COOP_AGREED_CHECKPOINT 1
#endif
enum { CHECKPOINT_CAPABILITY=0x31504B43u, CHECKPOINT_IDLE=0,
    CHECKPOINT_LOADING=1,CHECKPOINT_INITIALIZING=2,CHECKPOINT_COMPLETE=3,
    CHECKPOINT_FAILED=4,CHECKPOINT_REJECTED=5 };
enum { CHECKPOINT_OK=0,CHECKPOINT_FORBIDDEN=1,CHECKPOINT_UNKNOWN=2,
    CHECKPOINT_NAMESPACE=3,CHECKPOINT_UNSAFE=4,CHECKPOINT_SOURCE=5,
    CHECKPOINT_ORDER=6,CHECKPOINT_CONTEXT=7,CHECKPOINT_PLUGIN_FAILED=8 };
enum { CHECKPOINT_OFFLINE=0,CHECKPOINT_AGREED=1,
    CHECKPOINT_LAB_WAITING=0,CHECKPOINT_LAB_ARMED=1,CHECKPOINT_LAB_CONSUMED=2 };
enum { CHECKPOINT_LAB_NONCE=0x4C435032u }; /* Immutable intro CP2 request identity. */
typedef struct { unsigned phase,index; uint32_t nonce; unsigned authority; } Mmx6CheckpointPending;
static Mmx6CheckpointPending checkpoint_pending;
static unsigned checkpoint_lab_option,checkpoint_lab_state,checkpoint_lab_previous;

static int checkpoint_lab_authorized(void) {
#ifdef MMX6_COOP_AGREED_CHECKPOINT
    if(!checkpoint_lab_option)return 0;
    if(!psx_mod_netplay_is_active())return 1; /* Same lab candidate's LOCAL lane. */
    PSXHostSelection selected;
    const uint8_t expected[32]=MMX6_HOST_LAB_QUALIFICATION_BYTES;
    return !psx_netplay_host_profile_failed() && psx_netplay_host_profile_ready() &&
        psx_netplay_host_profile_selection(&selected) &&
        !strcmp(selected.profile,MMX6_HOST_LAB_PROFILE) && selected.revision==MMX6_HOST_LAB_REVISION &&
        selected.flags==PSX_HOST_PROFILE_DIRECT_LOOPBACK &&
        !memcmp(selected.qualification,expected,sizeof expected);
#else
    return 0;
#endif
}
static int checkpoint_request_authorized(unsigned authority) {
    if(authority==CHECKPOINT_OFFLINE)return diagnostic_mutation_allowed();
    return authority==CHECKPOINT_AGREED && checkpoint_lab_state==CHECKPOINT_LAB_CONSUMED &&
        checkpoint_lab_authorized();
}

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
    checkpoint_lab_option=checkpoint_lab_state=checkpoint_lab_previous=0;
#ifdef MMX6_COOP_AGREED_CHECKPOINT
    char option[24];
    if(psx_mod_option_value("mmx6.local-coop","prototype","lab_checkpoint",option,sizeof option)) {
        if(!strcmp(option,"intro_cp2"))checkpoint_lab_option=1;
        else if(strcmp(option,"off"))failed=1;
    }
#endif
    if(diagnostic) {
        if(psx_mod_read_byte(diagnostic+0x50)==8)psx_mod_write_byte(diagnostic+0x50,0);
        for(unsigned i=0xA0;i<0xC0;++i)psx_mod_write_byte(diagnostic+i,0);
        psx_mod_write_word(diagnostic+0xA0,CHECKPOINT_CAPABILITY);
    }
}
static int checkpoint_safe_boundary(void) {
    return ready && enrolled && !failed && !inside && !stage_call && !player_call && !ride_call && !view_call && !private_draw && !zero_world &&
        !zero_projected && !scene_owner && !scene_phase && pause_owner<0 && !zero_menu_loaded &&
        !state_track.count && !state_track.error && psx_mod_read_byte(PLAY)==10 &&
        !psx_mod_read_byte(PLAY+1) && !psx_mod_read_byte(PLAY+0x10) && !psx_mod_read_byte(PLAY+0x1C) &&
        psx_mod_read_byte(PLAYER+4)==1 && p2.body[4]==1 &&
        psx_mod_read_byte(PLAYER+0x5C)>0 && psx_mod_read_byte(PLAYER+0x5C)<128 &&
        p2.body[0x5C]>0 && p2.body[0x5C]<128 &&
        life.status[0]==MMX6_COOP_ALIVE && life.status[1]==MMX6_COOP_ALIVE;
}
static int checkpoint_request(unsigned stage,unsigned section,unsigned cp,uint32_t nonce,unsigned authority) {
    unsigned reason=CHECKPOINT_OK,index=115;
    for(unsigned i=0;i<115;++i)if(checkpoint_inventory[i].stage==stage &&
        checkpoint_inventory[i].section==section && checkpoint_inventory[i].checkpoint==cp){index=i;break;}
    const Mmx6Checkpoint *entry=index<115?&checkpoint_inventory[index]:NULL;
    if(!checkpoint_request_authorized(authority))reason=CHECKPOINT_FORBIDDEN;
    else if(!entry || !nonce)reason=CHECKPOINT_UNKNOWN;
    else if(!entry->campaign)reason=CHECKPOINT_NAMESPACE;
    else if(!checkpoint_safe_boundary())reason=CHECKPOINT_UNSAFE;
    else if(authority==CHECKPOINT_AGREED && (index!=2 || nonce!=CHECKPOINT_LAB_NONCE))reason=CHECKPOINT_UNKNOWN;
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
    psx_mod_write_byte(diagnostic+0xBD,(uint8_t)authority);
    psx_mod_write_byte(diagnostic+0xBE,(uint8_t)checkpoint_lab_state);
    psx_mod_write_byte(diagnostic+0xBF,(uint8_t)checkpoint_lab_previous);
    if(reason) {
        checkpoint_status(CHECKPOINT_REJECTED,reason);
        psx_mod_counter_add("mmx6.coop.debug-fixture-rejected",1);
        return 0;
    }
    checkpoint_pending=(Mmx6CheckpointPending){1,index,nonce,authority};
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
static int checkpoint_stage_boundary(CPUState *cpu) {
    (void)cpu;
    if(checkpoint_pending.phase) {
        const Mmx6Checkpoint *entry=&checkpoint_inventory[checkpoint_pending.index];
        if(failed || !checkpoint_request_authorized(checkpoint_pending.authority))checkpoint_cancel(failed?CHECKPOINT_PLUGIN_FAILED:CHECKPOINT_FORBIDDEN);
        else if(checkpoint_pending.phase==2 && psx_mod_read_byte(PLAY)==10 &&
                psx_mod_read_byte(PLAY+12)==entry->stage && psx_mod_read_byte(PLAY+13)==entry->section &&
                psx_mod_read_byte(PLAY+0x1D)==entry->checkpoint) {
            memset(&checkpoint_pending,0,sizeof checkpoint_pending);
            checkpoint_status(CHECKPOINT_COMPLETE,CHECKPOINT_OK);
        } else checkpoint_cancel(CHECKPOINT_ORDER);
    }
    if(psx_mod_read_byte(diagnostic+0x50)!=8)return 0;
    return checkpoint_request(psx_mod_read_byte(diagnostic+0x51),psx_mod_read_byte(diagnostic+0x52),
        psx_mod_read_byte(diagnostic+0x53),psx_mod_read_word(diagnostic+0x54),CHECKPOINT_OFFLINE);
}
static int checkpoint_lab_boundary(uint16_t raw) {
#ifdef MMX6_COOP_AGREED_CHECKPOINT
    if(!checkpoint_lab_option || checkpoint_lab_state==CHECKPOINT_LAB_CONSUMED)return 0;
    unsigned chord=raw==0x0006u;
    if(chord && !checkpoint_lab_previous)checkpoint_lab_state=CHECKPOINT_LAB_ARMED;
    checkpoint_lab_previous=chord;
    psx_mod_write_byte(diagnostic+0xBE,(uint8_t)checkpoint_lab_state);
    psx_mod_write_byte(diagnostic+0xBF,(uint8_t)checkpoint_lab_previous);
    if(checkpoint_lab_state!=CHECKPOINT_LAB_ARMED)return 0;
    /* The accepted chord follows the parent's normal movement/jump baseline.
     * Wait through transient menu/air/guest callback states; never sample SIO
     * again or issue a unilateral mailbox write to request this prerequisite. */
    if(!checkpoint_safe_boundary() || !psx_mod_read_byte(PLAYER) || !p2.body[0] ||
        psx_mod_read_byte(PLAYER+5)!=2 || p2.body[5]!=2 ||
        psx_mod_read_byte(PLAYER+0x67) || p2.body[0x67] || !(psx_mod_read_byte(PLAYER+0x70)&8) || !(p2.body[0x70]&8))return 0;
    checkpoint_lab_state=CHECKPOINT_LAB_CONSUMED;
    psx_mod_write_byte(diagnostic+0xBE,(uint8_t)checkpoint_lab_state);
    if(psx_mod_read_byte(PLAY+12) || psx_mod_read_byte(PLAY+13) || psx_mod_read_byte(PLAY+0x1D)) {
        checkpoint_status(CHECKPOINT_REJECTED,CHECKPOINT_ORDER);return 0;
    }
    return checkpoint_request(0,0,2,CHECKPOINT_LAB_NONCE,CHECKPOINT_AGREED);
#else
    (void)raw;return 0;
#endif
}
static void checkpoint_native_entry(CPUState *cpu,uint32_t address) {
    if(!checkpoint_pending.phase)return;
    const Mmx6Checkpoint *entry=&checkpoint_inventory[checkpoint_pending.index];
    if(!checkpoint_request_authorized(checkpoint_pending.authority) || failed) {
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
