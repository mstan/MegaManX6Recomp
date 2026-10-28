/* PRIVATE prerequisite bypass, never retry or progression evidence.
 * Mode8 loads the selected stage and clears CP; only its ordinary mode9 entry
 * may install the requested CP before the original initializer executes. */
#include "mmx6_coop_checkpoint_data.h"
#include "mmx6_coop_before_doors_data.h"
#include "mmx6_coop_before_explosion_data.h"
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
enum { CHECKPOINT_LAB_AMAZON_NONCE=0x4C434130u }; /* Immutable Amazon CP0 identity. */
enum { CHECKPOINT_LAB_INVESTIGATOR_NONCE=0x4C434132u }; /* Immutable Amazon CP2 identity. */
enum { CHECKPOINT_LAB_BEFORE_DOORS_NONCE=0x4C434431u }; /* Intro CP1 plus declared position bypass. */
enum { CHECKPOINT_LAB_BEFORE_EXPLOSION_NONCE=0x4C454631u }; /* Intro CP1 nearby native explosion setup. */
enum { CHECKPOINT_LAB_RECYCLE_NONCE=0x4C435232u }; /* Original Recycle section1 CP2, no pose bypass. */
enum { CHECKPOINT_LAB_PORTAL_NONCE=0x4C525032u }; /* Original Recycle section0 CP2 plus declared approach. */
typedef struct { unsigned phase,index; uint32_t nonce; unsigned authority; uint32_t placed_world; } Mmx6CheckpointPending;
static Mmx6CheckpointPending checkpoint_pending;
static unsigned checkpoint_lab_option,checkpoint_lab_state,checkpoint_lab_previous;
static unsigned checkpoint_contact_protection_option;

static unsigned checkpoint_lab_index(void) {
    return checkpoint_lab_option==1?2:checkpoint_lab_option==2?3:
        checkpoint_lab_option==3?5:(checkpoint_lab_option==4 || checkpoint_lab_option==5)?1:
        checkpoint_lab_option==6?27:checkpoint_lab_option==7?23:115;
}
static uint32_t checkpoint_lab_nonce(void) {
    return checkpoint_lab_option==1?CHECKPOINT_LAB_NONCE:
        checkpoint_lab_option==2?CHECKPOINT_LAB_AMAZON_NONCE:
        checkpoint_lab_option==3?CHECKPOINT_LAB_INVESTIGATOR_NONCE:
        checkpoint_lab_option==4?CHECKPOINT_LAB_BEFORE_DOORS_NONCE:
        checkpoint_lab_option==5?CHECKPOINT_LAB_BEFORE_EXPLOSION_NONCE:
        checkpoint_lab_option==6?CHECKPOINT_LAB_RECYCLE_NONCE:
        checkpoint_lab_option==7?CHECKPOINT_LAB_PORTAL_NONCE:0;
}

static int checkpoint_lab_authorized(void) {
#ifdef MMX6_COOP_AGREED_CHECKPOINT
    if(checkpoint_lab_index()>=115)return 0;
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
static int checkpoint_contact_source(void) {
    /* Original30ECC's no-contact path returns0 at30EEC/30EF0 and30FB4/30FB8
     * through312C4, before damage/recoil. The replacement never writes a
     * player timer, HP or pose. Authenticate that exact original function. */
    return checkpoint_hash(0x80030ECCu,0x800312DCu)==0xE1B1A427u;
}
static int checkpoint_source(const Mmx6Checkpoint *entry) {
    if(checkpoint_contact_protection_option && !checkpoint_contact_source())return 0;
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
    checkpoint_contact_protection_option=0;
#ifdef MMX6_COOP_AGREED_CHECKPOINT
    char option[24];
    if(psx_mod_option_value("mmx6.local-coop","prototype","lab_checkpoint",option,sizeof option)) {
        if(!strcmp(option,"intro_cp2"))checkpoint_lab_option=1;
        else if(!strcmp(option,"amazon_cp0"))checkpoint_lab_option=2;
        else if(!strcmp(option,"amazon_cp2"))checkpoint_lab_option=3;
        else if(!strcmp(option,"intro_before_doors"))checkpoint_lab_option=4;
        else if(!strcmp(option,"intro_before_explosion"))checkpoint_lab_option=5;
        else if(!strcmp(option,"recycle_cp2"))checkpoint_lab_option=6;
        else if(!strcmp(option,"recycle_portal_cp2"))checkpoint_lab_option=7;
        else if(strcmp(option,"off"))failed=1;
    }
    if(psx_mod_option_value("mmx6.local-coop","prototype","lab_contact_protection",option,sizeof option)) {
        if(!strcmp(option,"on"))checkpoint_contact_protection_option=1;
        else if(strcmp(option,"off"))failed=1;
    }
#endif
    if(diagnostic) {
        if(psx_mod_read_byte(diagnostic+0x50)==8)psx_mod_write_byte(diagnostic+0x50,0);
        for(unsigned i=0xA0;i<0xC0;++i)psx_mod_write_byte(diagnostic+i,0);
        psx_mod_write_word(diagnostic+0xA0,CHECKPOINT_CAPABILITY);
    }
}
/* Derived authorization only: no new latch, guest body write or live setting
 * switch. Keep P1 covered when P2 voluntarily leaves/joins; a real fall still
 * uses the untouched native terrain/death paths. Rendering is never authority. */
static unsigned checkpoint_contact_protection_mask(void) {
#ifdef MMX6_COOP_AGREED_CHECKPOINT
    if(!checkpoint_contact_protection_option || checkpoint_pending.phase ||
       checkpoint_lab_state!=CHECKPOINT_LAB_CONSUMED || !checkpoint_lab_authorized() ||
       !ready || !enrolled || failed || private_draw || view_call || !diagnostic ||
       scene_owner || scene_phase || clear_phase || pause_owner>=0 || zero_menu_loaded ||
       psx_mod_read_byte(PLAY)!=10 || psx_mod_read_byte(PLAY+1) ||
       psx_mod_read_byte(PLAY+0x10) || psx_mod_read_byte(PLAY+0x1C))return 0;
    const Mmx6Checkpoint *entry=&checkpoint_inventory[checkpoint_lab_index()];
    if(psx_mod_read_byte(PLAY+12)!=entry->stage || psx_mod_read_byte(PLAY+13)!=entry->section ||
       psx_mod_read_byte(PLAY+0x1D)!=entry->checkpoint ||
       psx_mod_read_word(diagnostic+0xA0)!=CHECKPOINT_CAPABILITY || psx_mod_read_word(diagnostic+0xA4)!=1 ||
       psx_mod_read_byte(diagnostic+0xA8)!=CHECKPOINT_COMPLETE || psx_mod_read_byte(diagnostic+0xA9) ||
       psx_mod_read_byte(diagnostic+0xAA)!=entry->stage || psx_mod_read_byte(diagnostic+0xAB)!=entry->section ||
       psx_mod_read_byte(diagnostic+0xAC)!=entry->checkpoint ||
       psx_mod_read_word(diagnostic+0xB0)!=checkpoint_lab_nonce() || psx_mod_read_word(diagnostic+0xB4)!=1 ||
       psx_mod_read_word(diagnostic+0xB8)!=entry->record || psx_mod_read_byte(diagnostic+0xBC)!=1 ||
       psx_mod_read_byte(diagnostic+0xBD)!=CHECKPOINT_AGREED ||
       psx_mod_read_byte(diagnostic+0xBE)!=CHECKPOINT_LAB_CONSUMED)return 0;
    unsigned mask=0;
    for(unsigned seat=0;seat<2;++seat)
        if(life.status[seat]==MMX6_COOP_ALIVE || life.status[seat]==MMX6_COOP_LEAVING ||
           life.status[seat]==MMX6_COOP_JOINING)mask|=1u<<seat;
    return mask;
#else
    return 0;
#endif
}
static unsigned checkpoint_contact_protection_status(void) {
    unsigned mask=checkpoint_contact_protection_mask();
    /* AF: bit0 selected; bit1 active; bits2/3 protected P1/P2. */
    return (checkpoint_contact_protection_option?1u:0u) | (mask?2u:0u) | (mask<<2);
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
/* These named lab bypasses skip only the route to the original door/explosion.
 * Native CP1 initialization and arrival finish first. No action/HP/ground,
 * checkpoint2, door command, allocation flag or outcome is manufactured. */
static int checkpoint_before_doors_idle(unsigned seat) {
    uint8_t body[sizeof p2.body];
    if(seat)memcpy(body,p2.body,sizeof body);else capture(PLAYER,body,sizeof body);
    const unsigned locks[]={0x7A,0x8E,0xA4,0xCC,0xCD,0xD0,0xD3,0xD4,0xE0};
    for(unsigned i=0;i<sizeof locks/sizeof locks[0];++i)if(body[locks[i]])return 0;
    return body[0] && body[2]==seat && body[4]==1 && body[5]==2 &&
        body[0x5C]>0 && body[0x5C]<128 && !body[0x14] && !body[0x67] &&
        (body[0x70]&8) && le32(body+0x68)==0x80073D50u+seat*4u;
}
static int checkpoint_before_doors_source(void) {
    for(unsigned i=0;i<sizeof before_doors_code/sizeof before_doors_code[0];++i)
        if(checkpoint_hash(before_doors_code[i].first,before_doors_code[i].end)!=before_doors_code[i].hash)return 0;
    /* Only the original allocator's bit0 may have changed on this placement. */
    return (psx_mod_read_word(0x800FA2A4u)&0xFFFFFFFEu)==0x04020800u &&
        psx_mod_read_word(0x800FA2A8u)==0x01801670u &&
        psx_mod_read_word(0x80078DC8u)==0x20100000u &&
        psx_mod_read_word(0x800FA7B4u)==0x80050DFCu;
}
static uint32_t checkpoint_before_explosion_placement_word(void) {
    /* Original29F38 calls29E7C at2A12C before allocation. For this low-nibble0
     * placement,29EF8 changes lifetime byte3 from0 to10, except difficulty3
     * takes29E9C's no-change admission. Before our one-shot scan no lifetime
     * transition is authorized; after it only that exact native value is. */
    return checkpoint_pending.phase==3 && psx_mod_read_byte(PLAY+0x68)!=3 ?
        0x10010000u:0x00010000u;
}
static int checkpoint_before_explosion_source(void) {
    for(unsigned i=0;i<sizeof before_explosion_code/sizeof before_explosion_code[0];++i)
        if(checkpoint_hash(before_explosion_code[i].first,before_explosion_code[i].end)!=before_explosion_code[i].hash)return 0;
    /* Bit0 is the original allocator's flag; lifetime byte3 is phase-bound. */
    return (psx_mod_read_word(0x800FA384u)&0xFFFFFFFEu)==checkpoint_before_explosion_placement_word() &&
        psx_mod_read_word(0x800FA388u)==0x02E01240u;
}
static int checkpoint_before_doors_assets(uint32_t *meta,uint32_t *desc) {
    *meta=psx_mod_read_word(0x1F800008u);*desc=psx_mod_read_word(0x1F80000Cu);
    return psx_mod_read_word(0x1F800004u)==BEFORE_DOORS_LAYOUT &&
        psx_mod_read_half(0x800CD338u)==0x061Au && psx_mod_read_half(0x8008EC10u)==156 &&
        *meta>=0x80010000u && *meta<=0x80200000u-BEFORE_DOORS_META_SIZE &&
        *desc>=0x80010000u && *desc<=0x80200000u-BEFORE_DOORS_DESC_SIZE &&
        checkpoint_hash(BEFORE_DOORS_LAYOUT,BEFORE_DOORS_LAYOUT+BEFORE_DOORS_LAYOUT_SIZE)==0x7DA6B2C4u &&
        checkpoint_hash(*meta,*meta+BEFORE_DOORS_META_SIZE)==0x3D839D18u &&
        checkpoint_hash(*desc,*desc+BEFORE_DOORS_DESC_SIZE)==0x92A8E80Du;
}
static int checkpoint_before_doors_tile(uint32_t meta,uint32_t desc,unsigned x,unsigned y) {
    unsigned cell=psx_mod_read_byte(BEFORE_DOORS_LAYOUT+(y>>8)*26u+(x>>8));
    if(!cell)return 0;
    unsigned at=cell*512u+((y>>4)&15u)*32u+((x>>4)&15u)*2u;
    if(at+2u>BEFORE_DOORS_META_SIZE)return -1;
    unsigned tile=psx_mod_read_half(meta+at)&0x3FFFu;
    if(tile*4u+4u>BEFORE_DOORS_DESC_SIZE)return -1;
    unsigned code=psx_mod_read_byte(desc+tile*4u);return code==0x3B?0x38:(int)code;
}
static int checkpoint_before_doors_ground(uint32_t meta,uint32_t desc) {
    /* Complete source/live standing envelopes, not a three-probe shortcut. */
    for(unsigned seat=0;seat<2;++seat) {
        unsigned x=5692u+seat*24u;
        for(unsigned px=x-11u;px<x+11u;++px) {
            if(checkpoint_before_doors_tile(meta,desc,px,416)!=0x38)return 0;
            for(unsigned py=378;py<416;++py)
                if(checkpoint_before_doors_tile(meta,desc,px,py))return 0;
        }
    }
    return 1;
}
static int checkpoint_before_explosion_ground(uint32_t meta,uint32_t desc) {
    for(unsigned seat=0;seat<2;++seat) {
        unsigned x=4736u+seat*24u;
        for(unsigned px=x-11u;px<x+11u;++px) {
            if(checkpoint_before_doors_tile(meta,desc,px,864)!=0x38)return 0;
            for(unsigned py=826;py<864;++py)
                if(checkpoint_before_doors_tile(meta,desc,px,py))return 0;
        }
    }
    return 1;
}
static void checkpoint_position_place(CPUState *cpu) {
    const int explosion=checkpoint_lab_option==5;
    for(unsigned seat=0;seat<2;++seat) {
        uint32_t x=((explosion?4736u:5692u)+seat*24u)<<16,y=((explosion?843u:395u)-seat)<<16;
        if(seat) {put32(p2.body+8,x);put32(p2.body+0x18,x);put32(p2.body+12,y);put32(p2.body+0x1C,y);}
        else {psx_mod_write_word(PLAYER+8,x);psx_mod_write_word(PLAYER+0x18,x);
              psx_mod_write_word(PLAYER+12,y);psx_mod_write_word(PLAYER+0x1C,y);}
    }
    const uint32_t cam=0x800971F8u;
    psx_mod_write_word(cam+8,(explosion?4576u:5424u)<<16);psx_mod_write_word(cam+0x14,(explosion?4576u:5424u)<<16);
    psx_mod_write_word(cam+12,(explosion?704u:256u)<<16);psx_mod_write_word(cam+0x18,(explosion?704u:256u)<<16);
    const unsigned offsets[]={0x1C,0x1E,0x20,0x22,0x24,0x26,0x28,0x2A};
    const uint16_t doors[]={5424,5008,256,256,5424,5008,256,256};
    const uint16_t nearby[]={5120,1968,704,704,5120,1968,704,704};
    const uint16_t *values=explosion?nearby:doors;
    for(unsigned i=0;i<8;++i)psx_mod_write_half(cam+offsets[i],values[i]);
    psx_mod_write_byte(cam+0x47,2); /* Original 5211C authored camera controls. */
    for(unsigned layer=0;layer<3;++layer)psx_mod_write_byte(cam+layer*0x54u+0x4C,1);
#ifdef MMX6_COOP_MODERN_STATE
    independent_invalidate();
#endif
    checkpoint_pending.phase=3;checkpoint_pending.placed_world=psx_mod_read_word(PLAY+0x90);
    psx_mod_write_byte(diagnostic+0xAD,1);
    psx_mod_write_byte(diagnostic+0xAE,1);
    /* Literal primary-window call of 2A3E8..2A434. Calling its whole wrapper
     * here would ALSO rerun 2A438's unconditional secondary controller list,
     * already installed by original CP1 initialization. Preserve all five
     * original native arguments and the caller's stack/register contents. */
    uint32_t stack=cpu->gpr[29]+0x10u;
    uint32_t saved[4]={cpu->gpr[6],cpu->gpr[7],stack,psx_mod_read_word(stack)};
    STATE_WORDS(restore_checkpoint_scan,64,saved,4);
    cpu->gpr[6]=explosion?656:208;cpu->gpr[7]=explosion?992:544;psx_mod_write_word(stack,0);
    guest(cpu,0x80029F38u,explosion?4528:5376,explosion?4944:5792);
    cpu->gpr[6]=saved[0];cpu->gpr[7]=saved[1];psx_mod_write_word(stack,saved[3]);
    STATE_POP(restore_checkpoint_scan);
}
static int checkpoint_before_doors_ready(void) {
    if((uint32_t)(psx_mod_read_word(PLAY+0x90)-checkpoint_pending.placed_world)<2u ||
       !checkpoint_safe_boundary() || !checkpoint_before_doors_idle(0) || !checkpoint_before_doors_idle(1) ||
       psx_mod_read_word(PLAYER+8)!=(5692u<<16) || psx_mod_read_word(PLAYER+12)!=(395u<<16) ||
       le32(p2.body+8)!=(5716u<<16) || le32(p2.body+12)!=(394u<<16))return 0;
    for(uint32_t a=0x800C1220u;a<0x800C4560u;a+=0xA4u)
        if((psx_mod_read_byte(a)&1u) && psx_mod_read_byte(a+1)==8 &&
           psx_mod_read_byte(a+2)==2 && psx_mod_read_byte(a+4)==1 && !psx_mod_read_byte(a+5) &&
           psx_mod_read_word(a+0x10)==0x800FA2A4u &&
           psx_mod_read_half(a+10)==5744 && psx_mod_read_half(a+14)==384 &&
           psx_mod_read_word(a+0x68)==0x80078DC8u)return 1;
    return 0;
}
static int checkpoint_before_explosion_ready(void) {
    if((uint32_t)(psx_mod_read_word(PLAY+0x90)-checkpoint_pending.placed_world)<2u ||
       !checkpoint_safe_boundary() || !checkpoint_before_doors_idle(0) || !checkpoint_before_doors_idle(1) ||
       psx_mod_read_word(PLAYER+8)!=(4736u<<16) || psx_mod_read_word(PLAYER+12)!=(843u<<16) ||
       le32(p2.body+8)!=(4760u<<16) || le32(p2.body+12)!=(842u<<16))return 0;
    /* Category0 native pool, stride9C. Require original init and waiting
     * action, not merely an allocated header or an already-earned impact. */
    for(uint32_t a=0x8008EF48u;a<0x80090C88u;a+=0x9Cu)
        if((psx_mod_read_byte(a)&1u) && !psx_mod_read_byte(a+1) &&
           psx_mod_read_byte(a+2)==1 && psx_mod_read_byte(a+4)==1 &&
           psx_mod_read_byte(a+5)==2 && psx_mod_read_byte(a+6)==1 &&
           !psx_mod_read_byte(a+0x14) && psx_mod_read_word(a+0x10)==0x800FA384u &&
           psx_mod_read_word(a+8)==(4672u<<16) && psx_mod_read_word(a+12)==(736u<<16) &&
           psx_mod_read_word(a+0x30)==0x800FAA34u && psx_mod_read_word(a+0x68)==0x800FA99Cu &&
           psx_mod_read_half(a+0x7C)>0 && psx_mod_read_half(a+0x7C)<=90 &&
           psx_mod_read_half(a+0x80)==736 && psx_mod_read_byte(a+0x82)==1)return 1;
    return 0;
}
/* Refusal-only LAB witness. Recheck after the unchanged predicate failed;
 * never move the validation boundary, relax a guard or write guest state. */
#ifndef MMX6_CHECKPOINT_REFUSAL_LOG
#define MMX6_CHECKPOINT_REFUSAL_LOG(...) fprintf(stderr,__VA_ARGS__)
#endif
static void checkpoint_refusal_value(const char *guard,unsigned index,uint32_t address,uint32_t actual,uint32_t expected) {
#ifdef MMX6_COOP_AGREED_CHECKPOINT
    MMX6_CHECKPOINT_REFUSAL_LOG("[mmx6 checkpoint refusal] %s[%u] phase=%u index=%u address=0x%08X actual=0x%08X expected=0x%08X\n",
        guard,index,checkpoint_pending.phase,checkpoint_pending.index,address,actual,expected);
#else
    (void)guard;(void)index;(void)address;(void)actual;(void)expected;
#endif
}
static void checkpoint_source_refusal(const Mmx6Checkpoint *entry) {
#ifdef MMX6_COOP_AGREED_CHECKPOINT
    if(checkpoint_contact_protection_option && !checkpoint_contact_source()) {
        checkpoint_refusal_value("contact-no-damage-source-hash",0,0x80030ECCu,
            checkpoint_hash(0x80030ECCu,0x800312DCu),0xE1B1A427u);return;
    }
    const uint32_t addresses[]={0x8007114Cu,0x80071150u,
        0x80073300u+(entry->stage*2u+entry->section)*4u,entry->table+entry->checkpoint*4u};
    const uint32_t expected[]={0x8001E914u,0x8001E1BCu,entry->table,entry->record};
    for(unsigned i=0;i<4;++i) {
        uint32_t actual=psx_mod_read_word(addresses[i]);
        if(actual!=expected[i]) {checkpoint_refusal_value("checkpoint-pointer",i,addresses[i],actual,expected[i]);return;}
    }
    uint32_t actual=checkpoint_hash(entry->record,entry->record+36);
    if(actual!=entry->hash) {checkpoint_refusal_value("checkpoint-record-hash",0,entry->record,actual,entry->hash);return;}
    for(unsigned i=0;i<sizeof checkpoint_code/sizeof checkpoint_code[0];++i) {
        actual=checkpoint_hash(checkpoint_code[i].first,checkpoint_code[i].end);
        if(actual!=checkpoint_code[i].hash) {checkpoint_refusal_value("checkpoint-code-hash",i,checkpoint_code[i].first,actual,checkpoint_code[i].hash);return;}
    }
    checkpoint_refusal_value("checkpoint-source-recheck-clean",0,entry->record,actual,actual);
#else
    (void)entry;
#endif
}
static void checkpoint_explosion_source_refusal(void) {
#ifdef MMX6_COOP_AGREED_CHECKPOINT
    for(unsigned i=0;i<sizeof before_explosion_code/sizeof before_explosion_code[0];++i) {
        uint32_t actual=checkpoint_hash(before_explosion_code[i].first,before_explosion_code[i].end);
        if(actual!=before_explosion_code[i].hash) {checkpoint_refusal_value("explosion-code-hash",i,before_explosion_code[i].first,actual,before_explosion_code[i].hash);return;}
    }
    uint32_t actual=psx_mod_read_word(0x800FA384u);
    uint32_t expected=checkpoint_before_explosion_placement_word();
    if((actual&0xFFFFFFFEu)!=expected) {checkpoint_refusal_value("explosion-placement-word0-mask-FFFFFFFE",0,0x800FA384u,actual,expected);return;}
    actual=psx_mod_read_word(0x800FA388u);
    if(actual!=0x02E01240u) {checkpoint_refusal_value("explosion-placement-word1",1,0x800FA388u,actual,0x02E01240u);return;}
    checkpoint_refusal_value("explosion-source-recheck-clean",0,0x800FA384u,actual,actual);
#endif
}
static void checkpoint_resources_refusal(void) {
#ifdef MMX6_COOP_AGREED_CHECKPOINT
    uint32_t meta=psx_mod_read_word(0x1F800008u),desc=psx_mod_read_word(0x1F80000Cu);
    uint32_t actual=psx_mod_read_word(0x1F800004u);
    if(actual!=BEFORE_DOORS_LAYOUT) {checkpoint_refusal_value("post-ready-layout-pointer",0,0x1F800004u,actual,BEFORE_DOORS_LAYOUT);return;}
    actual=psx_mod_read_half(0x800CD338u);
    if(actual!=0x061Au) {checkpoint_refusal_value("post-ready-dimensions",0,0x800CD338u,actual,0x061Au);return;}
    actual=psx_mod_read_half(0x8008EC10u);
    if(actual!=156) {checkpoint_refusal_value("post-ready-stride",0,0x8008EC10u,actual,156);return;}
    if(meta<0x80010000u) {checkpoint_refusal_value("post-ready-meta-lower-bound",0,0x1F800008u,meta,0x80010000u);return;}
    if(meta>0x80200000u-BEFORE_DOORS_META_SIZE) {checkpoint_refusal_value("post-ready-meta-upper-bound",0,0x1F800008u,meta,0x80200000u-BEFORE_DOORS_META_SIZE);return;}
    if(desc<0x80010000u) {checkpoint_refusal_value("post-ready-desc-lower-bound",0,0x1F80000Cu,desc,0x80010000u);return;}
    if(desc>0x80200000u-BEFORE_DOORS_DESC_SIZE) {checkpoint_refusal_value("post-ready-desc-upper-bound",0,0x1F80000Cu,desc,0x80200000u-BEFORE_DOORS_DESC_SIZE);return;}
    const uint32_t starts[]={BEFORE_DOORS_LAYOUT,meta,desc};
    const uint32_t sizes[]={BEFORE_DOORS_LAYOUT_SIZE,BEFORE_DOORS_META_SIZE,BEFORE_DOORS_DESC_SIZE};
    const uint32_t expected[]={0x7DA6B2C4u,0x3D839D18u,0x92A8E80Du};
    for(unsigned i=0;i<3;++i) {
        actual=checkpoint_hash(starts[i],starts[i]+sizes[i]);
        if(actual!=expected[i]) {checkpoint_refusal_value("post-ready-resource-hash-layout-meta-desc",i,starts[i],actual,expected[i]);return;}
    }
    checkpoint_refusal_value("post-ready-resources-recheck-clean",0,BEFORE_DOORS_LAYOUT,actual,actual);
#endif
}
static void checkpoint_ground_refusal(uint32_t meta,uint32_t desc,int explosion) {
#ifdef MMX6_COOP_AGREED_CHECKPOINT
    unsigned floor=explosion?864u:416u,top=explosion?826u:378u;
    for(unsigned seat=0;seat<2;++seat)for(unsigned x=(explosion?4736u:5692u)+seat*24u-11u;
        x<(explosion?4736u:5692u)+seat*24u+11u;++x) {
        int code=checkpoint_before_doors_tile(meta,desc,x,floor);
        if(code!=0x38) {checkpoint_refusal_value("post-ready-foot-worldXY",seat,(floor<<16)|x,(uint32_t)code,0x38);return;}
        for(unsigned y=top;y<floor;++y) {
            code=checkpoint_before_doors_tile(meta,desc,x,y);
            if(code) {checkpoint_refusal_value("post-ready-body-worldXY",seat,(y<<16)|x,(uint32_t)code,0);return;}
        }
    }
    checkpoint_refusal_value("post-ready-ground-recheck-clean",0,0,0,0);
#else
    (void)meta;(void)desc;(void)explosion;
#endif
}
#include "mmx6_coop_before_portal.inc"
static int checkpoint_request(unsigned stage,unsigned section,unsigned cp,uint32_t nonce,unsigned authority) {
    unsigned reason=CHECKPOINT_OK,index=115;
    for(unsigned i=0;i<115;++i)if(checkpoint_inventory[i].stage==stage &&
        checkpoint_inventory[i].section==section && checkpoint_inventory[i].checkpoint==cp){index=i;break;}
    const Mmx6Checkpoint *entry=index<115?&checkpoint_inventory[index]:NULL;
    if(!checkpoint_request_authorized(authority))reason=CHECKPOINT_FORBIDDEN;
    else if(!entry || !nonce)reason=CHECKPOINT_UNKNOWN;
    else if(!entry->campaign)reason=CHECKPOINT_NAMESPACE;
    else if(!checkpoint_safe_boundary())reason=CHECKPOINT_UNSAFE;
    else if(authority==CHECKPOINT_AGREED &&
        (index!=checkpoint_lab_index() || nonce!=checkpoint_lab_nonce()))reason=CHECKPOINT_UNKNOWN;
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
    psx_mod_write_byte(diagnostic+0xAD,0);psx_mod_write_byte(diagnostic+0xAE,0);
    psx_mod_write_byte(diagnostic+0xBD,(uint8_t)authority);
    psx_mod_write_byte(diagnostic+0xBE,(uint8_t)checkpoint_lab_state);
    psx_mod_write_byte(diagnostic+0xBF,(uint8_t)checkpoint_lab_previous);
    if(reason) {
        checkpoint_status(CHECKPOINT_REJECTED,reason);
        psx_mod_counter_add("mmx6.coop.debug-fixture-rejected",1);
        return 0;
    }
    checkpoint_pending=(Mmx6CheckpointPending){1,index,nonce,authority,0};
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
    if(checkpoint_pending.phase) {
        const Mmx6Checkpoint *entry=&checkpoint_inventory[checkpoint_pending.index];
        if(failed || !checkpoint_request_authorized(checkpoint_pending.authority))checkpoint_cancel(failed?CHECKPOINT_PLUGIN_FAILED:CHECKPOINT_FORBIDDEN);
        else if((checkpoint_pending.phase==2 || checkpoint_pending.phase==3) && psx_mod_read_byte(PLAY)==10 &&
                psx_mod_read_byte(PLAY+12)==entry->stage && psx_mod_read_byte(PLAY+13)==entry->section &&
                psx_mod_read_byte(PLAY+0x1D)==entry->checkpoint) {
            if(checkpoint_pending.authority==CHECKPOINT_AGREED && checkpoint_lab_option==7) {
                uint32_t meta,desc;
                if(!checkpoint_source(entry) || !checkpoint_portal_source() ||
                   !checkpoint_portal_assets(&meta,&desc) || !checkpoint_portal_ground(meta,desc)) {
                    checkpoint_refusal_value("portal-setup-source-assets-ground",0,entry->record,0,1);
                    checkpoint_cancel(CHECKPOINT_SOURCE);
                } else if(checkpoint_pending.phase==2) {
                    if(checkpoint_portal_original_arrival())checkpoint_portal_place();
                } else if(checkpoint_portal_ready()) {
                    psx_mod_write_byte(diagnostic+0xAD,2);memset(&checkpoint_pending,0,sizeof checkpoint_pending);
                    checkpoint_status(CHECKPOINT_COMPLETE,CHECKPOINT_OK);
                }
            } else if(checkpoint_pending.authority==CHECKPOINT_AGREED &&
               (checkpoint_lab_option==4 || checkpoint_lab_option==5)) {
                const int explosion=checkpoint_lab_option==5;
                uint32_t meta,desc;
                if(!checkpoint_source(entry)) {checkpoint_source_refusal(entry);checkpoint_cancel(CHECKPOINT_SOURCE);}
                else if(!(explosion?checkpoint_before_explosion_source():checkpoint_before_doors_source())) {
                    if(explosion)checkpoint_explosion_source_refusal();
                    else checkpoint_refusal_value("before-doors-source",0,0,0,0);
                    checkpoint_cancel(CHECKPOINT_SOURCE);
                }
                else if(checkpoint_pending.phase==2) {
                    if(checkpoint_safe_boundary() && checkpoint_before_doors_idle(0) && checkpoint_before_doors_idle(1) &&
                       !(cpu->gpr[29]&3u) && cpu->gpr[29]>=0x80010000u && cpu->gpr[29]<=0x801FFFECu &&
                       checkpoint_before_doors_assets(&meta,&desc) &&
                       (explosion?checkpoint_before_explosion_ground(meta,desc):checkpoint_before_doors_ground(meta,desc)))
                        checkpoint_position_place(cpu);
                } else if(explosion?checkpoint_before_explosion_ready():checkpoint_before_doors_ready()) {
                    if(!checkpoint_before_doors_assets(&meta,&desc)) {checkpoint_resources_refusal();checkpoint_cancel(CHECKPOINT_SOURCE);}
                    else if(!(explosion?checkpoint_before_explosion_ground(meta,desc):checkpoint_before_doors_ground(meta,desc))) {
                        checkpoint_ground_refusal(meta,desc,explosion);checkpoint_cancel(CHECKPOINT_SOURCE);
                    }
                    else {psx_mod_write_byte(diagnostic+0xAD,2);memset(&checkpoint_pending,0,sizeof checkpoint_pending);
                          checkpoint_status(CHECKPOINT_COMPLETE,CHECKPOINT_OK);}
                }
            } else {
                memset(&checkpoint_pending,0,sizeof checkpoint_pending);
                checkpoint_status(CHECKPOINT_COMPLETE,CHECKPOINT_OK);
            }
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
    unsigned origin_stage=psx_mod_read_byte(PLAY+12),origin_section=psx_mod_read_byte(PLAY+13);
    unsigned origin_checkpoint=psx_mod_read_byte(PLAY+0x1D);
    /* The named Recycle prerequisite may follow an actual native card Load
     * and mission arrival. Only its fixed destination gains this origin;
     * the parent still proves the approved card and acquired body masks. */
    if((origin_stage || origin_section || origin_checkpoint) &&
       !(checkpoint_lab_option==6 && origin_stage==4 && !origin_section && !origin_checkpoint)) {
        checkpoint_status(CHECKPOINT_REJECTED,CHECKPOINT_ORDER);return 0;
    }
    unsigned index=checkpoint_lab_index();
    if(index>=115) {checkpoint_status(CHECKPOINT_REJECTED,CHECKPOINT_UNKNOWN);return 0;}
    const Mmx6Checkpoint *entry=&checkpoint_inventory[index];
    return checkpoint_request(entry->stage,entry->section,entry->checkpoint,
        checkpoint_lab_nonce(),CHECKPOINT_AGREED);
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
    if(!checkpoint_source(entry)){checkpoint_source_refusal(entry);checkpoint_cancel(CHECKPOINT_SOURCE);return;}
    psx_mod_write_byte(PLAY+0x1D,entry->checkpoint);
    checkpoint_pending.phase=2;
    psx_mod_write_word(diagnostic+0xB4,1);
    checkpoint_status(CHECKPOINT_INITIALIZING,CHECKPOINT_OK);
    /* No guest call/replacement: the original mode9 initializer continues once. */
}
