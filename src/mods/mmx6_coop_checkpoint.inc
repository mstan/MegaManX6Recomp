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
#include "mmx6_coop_host_lab.h"
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
enum { CHECKPOINT_LAB_SUBTANK_NONCE=0x4C535432u }; /* Same native CP2; declared F180 supplies only. */
enum { CHECKPOINT_LAB_AMAZON_NONCE=0x4C434130u }; /* Immutable Amazon CP0 identity. */
enum { CHECKPOINT_LAB_INVESTIGATOR_NONCE=0x4C434132u }; /* Immutable Amazon CP2 identity. */
enum { CHECKPOINT_LAB_BEFORE_DOORS_NONCE=0x4C434431u }; /* Intro CP1 plus declared position bypass. */
enum { CHECKPOINT_LAB_BEFORE_EXPLOSION_NONCE=0x4C454631u }; /* Intro CP1 nearby native explosion setup. */
enum { CHECKPOINT_LAB_RECYCLE_NONCE=0x4C435232u }; /* Original Recycle section1 CP2, no pose bypass. */
enum { CHECKPOINT_LAB_ALTERNATE_NONCE=0x4C414231u }; /* Original alternate20/1 CP1; encounter prerequisites stay native. */
enum { CHECKPOINT_LAB_SIGMA_NONCE=0x4C534731u }; /* Original SecretLab3 section1 CP1; actual Sigma fight/transition stay native. */

enum { CHECKPOINT_LAB_MAGMA_START_NONCE=0x4C484E30u }; /* Original Magma3/0 CP0, no encounter/result writes. */
enum { CHECKPOINT_LAB_HEATNIX_NONCE=0x4C484E37u }; /* Original Magma3/0 CP7, no boss/result writes. */
enum { CHECKPOINT_LAB_TURTLOID_NONCE=0x4C545231u }; /* Original Turtloid6/0 CP1; native rain remains unmodified. */
enum { CHECKPOINT_LAB_PORTAL_NONCE=0x4C525032u }; /* Original Recycle section0 CP2 plus declared approach. */
enum { CHECKPOINT_LAB_NORTHPOLE_NONCE=0x4C4E4933u }; /* Original NorthPole CP3 plus declared approach. */
enum { CHECKPOINT_LAB_DISTANT_PORTAL_NONCE=0x4C525044u }; /* Same native entry, distinct far-primary setup. */

enum { CHECKPOINT_LAB_FALLEN_PORTAL_NONCE=0x4C524631u,
    CHECKPOINT_LAB_FALLEN_GUEST_PORTAL_NONCE=0x4C524632u }; /* Position-only pit approaches; death stays native. */
enum { CHECKPOINT_LAB_REFIGHT_DISTANT_NONCE=0x4C524644u }; /* R21: only guest position/history bypass. */
enum { CHECKPOINT_LAB_WOLFANG_NONCE=0x4C574633u }; /* Original12/0 CP3, no position or encounter writes. */

enum { CHECKPOINT_LAB_FORTRESS_CP3_NONCE=0x4C463933u }; /* Original17/0 CP3; F86 defeat/fresh-stage outcomes stay native. */
enum { CHECKPOINT_LAB_GROUND_NONCE=0x4C475236u }; /* Original12/0 CP6; grant selected equipment after its constructor. */

enum { CHECKPOINT_LAB_REFIGHT_NONCE=0x4C524650u }; /* Original0C/0 CP1, portal approach only. */
enum { CHECKPOINT_LAB_GATE_ENEMY_NONCE=0x4C474531u }; /* Original SecretLab2B CP0, position-only approach. */
typedef struct { unsigned phase,index; uint32_t nonce; unsigned authority; uint32_t placed_world; } Mmx6CheckpointPending;
static Mmx6CheckpointPending checkpoint_pending;
static unsigned checkpoint_lab_option,checkpoint_lab_state,checkpoint_lab_previous;
/* Option24 only: actual Map -> responsive cursor -> ordinary mission -> one
 * repeat. These are prerequisite guards, never native progression fields. */
enum { CHECKPOINT_SEQUENCE_NONE,CHECKPOINT_SEQUENCE_MAP,CHECKPOINT_SEQUENCE_RESPONSIVE,
    CHECKPOINT_SEQUENCE_MISSION,CHECKPOINT_SEQUENCE_USED };
static unsigned checkpoint_sequence_state,checkpoint_sequence_cursor,checkpoint_sequence_release;
static unsigned checkpoint_contact_protection_option;
enum { CHECKPOINT_FATAL_RELEASE, CHECKPOINT_FATAL_ARMED, CHECKPOINT_FATAL_CONSUMED,
    CHECKPOINT_FATAL_SCENE_LOCKED, CHECKPOINT_FATAL_SCENE_WAIT_DEATH, CHECKPOINT_FATAL_SCENE_WAIT_ARRIVAL };
/* Starting-HP storage is declared before diagnostics in the plugin. */
static unsigned checkpoint_earned_weapons_option,checkpoint_earned_weapons_applied,checkpoint_earned_weapons_reason;

static void checkpoint_earned_weapons_diagnostics(void) {
    psx_mod_write_byte(diagnostic+0xC4,(uint8_t)checkpoint_earned_weapons_option);
    psx_mod_write_byte(diagnostic+0xC5,(uint8_t)checkpoint_earned_weapons_applied);
    psx_mod_write_byte(diagnostic+0xC6,(uint8_t)((psx_mod_read_byte(PLAYER+0xC9)==0xFFu?1u:0u)|(p2.body[0xC9]==0xFFu?2u:0u)));
    psx_mod_write_byte(diagnostic+0xC7,(uint8_t)checkpoint_earned_weapons_reason);
}

static unsigned checkpoint_lab_index(void) {
    return (checkpoint_lab_option==1 || checkpoint_lab_option==20)?2:checkpoint_lab_option==2?3:
        checkpoint_lab_option==3?5:(checkpoint_lab_option==4 || checkpoint_lab_option==5)?1:
        checkpoint_lab_option==6?27:(checkpoint_lab_option==7 || checkpoint_lab_option==10 ||
        checkpoint_lab_option==12 || checkpoint_lab_option==13)?23:checkpoint_lab_option==8?32:(checkpoint_lab_option==9 || checkpoint_lab_option==24)?106:checkpoint_lab_option==11?10:checkpoint_lab_option==14?94:(checkpoint_lab_option==15 || checkpoint_lab_option==16)?60:checkpoint_lab_option==17?20:checkpoint_lab_option==18?78:checkpoint_lab_option==19?13:checkpoint_lab_option==21?62:checkpoint_lab_option==22?93:checkpoint_lab_option==23?65:115;
}
static uint32_t checkpoint_lab_nonce(void) {
    return checkpoint_lab_option==20?CHECKPOINT_LAB_SUBTANK_NONCE:checkpoint_lab_option==1?CHECKPOINT_LAB_NONCE:
        checkpoint_lab_option==2?CHECKPOINT_LAB_AMAZON_NONCE:
        checkpoint_lab_option==3?CHECKPOINT_LAB_INVESTIGATOR_NONCE:
        checkpoint_lab_option==4?CHECKPOINT_LAB_BEFORE_DOORS_NONCE:
        checkpoint_lab_option==5?CHECKPOINT_LAB_BEFORE_EXPLOSION_NONCE:
        checkpoint_lab_option==6?CHECKPOINT_LAB_RECYCLE_NONCE:
        checkpoint_lab_option==7?CHECKPOINT_LAB_PORTAL_NONCE:
        checkpoint_lab_option==8?CHECKPOINT_LAB_TURTLOID_NONCE:
        (checkpoint_lab_option==9 || checkpoint_lab_option==24)?CHECKPOINT_LAB_ALTERNATE_NONCE:
        checkpoint_lab_option==10?CHECKPOINT_LAB_DISTANT_PORTAL_NONCE:
        checkpoint_lab_option==11?CHECKPOINT_LAB_NORTHPOLE_NONCE:
        checkpoint_lab_option==12?CHECKPOINT_LAB_FALLEN_PORTAL_NONCE:
        checkpoint_lab_option==13?CHECKPOINT_LAB_FALLEN_GUEST_PORTAL_NONCE:
        checkpoint_lab_option==14?CHECKPOINT_LAB_GATE_ENEMY_NONCE:
        checkpoint_lab_option==15?CHECKPOINT_LAB_REFIGHT_NONCE:
        checkpoint_lab_option==16?CHECKPOINT_LAB_REFIGHT_DISTANT_NONCE:
        checkpoint_lab_option==17?CHECKPOINT_LAB_HEATNIX_NONCE:checkpoint_lab_option==18?CHECKPOINT_LAB_SIGMA_NONCE:checkpoint_lab_option==19?CHECKPOINT_LAB_MAGMA_START_NONCE:checkpoint_lab_option==21?CHECKPOINT_LAB_WOLFANG_NONCE:checkpoint_lab_option==22?CHECKPOINT_LAB_FORTRESS_CP3_NONCE:checkpoint_lab_option==23?CHECKPOINT_LAB_GROUND_NONCE:0;
}

static int checkpoint_lab_authorized(void) {
#ifdef MMX6_COOP_AGREED_CHECKPOINT
    if(checkpoint_lab_index()>=115)return 0;
    if(!psx_mod_netplay_is_active())return 1; /* Same lab candidate's LOCAL lane. */
    PSXHostSelection selected;
    return !psx_netplay_host_profile_failed() && psx_netplay_host_profile_ready() &&
        psx_netplay_host_profile_selection(&selected) &&
        mmx6_coop_lab_selection_matches(&selected);
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
/* Both the existing offline diagnostic9 and the separately authorized LAB
 * boundary invoke this exact original initializer. It copies earned flags and
 * native equipment/form; it does not select attacks or change HP/ammo. */
static int checkpoint_equipment_source(void) {
    return checkpoint_hash(0x8003D718u,0x8003D7ACu)==0xE818BDD7u;
}
static void checkpoint_equipment_native(CPUState *cpu,unsigned mask) {
    psx_mod_write_byte(PLAY+0x60,(uint8_t)mask);
    guest(cpu,0x8003D718u,PLAYER,0);
    enter_zero();guest(cpu,0x8003D718u,PLAYER,0);leave_zero();
}
static int checkpoint_equipment_context(CPUState *cpu) {
    return cpu && !(cpu->gpr[29]&3u) && cpu->gpr[29]>=0x80010000u && cpu->gpr[29]<=0x801FFFECu &&
        !checkpoint_earned_weapons_applied && !scene_owner && !zero_projected &&
        psx_mod_read_byte(PLAY)==10 && !psx_mod_read_byte(PLAY+1) &&
        !psx_mod_read_byte(PLAY+0x38) && psx_mod_read_byte(PLAY+0x5E)==1 &&
        life.status[0]==MMX6_COOP_ALIVE && life.status[1]==MMX6_COOP_ALIVE &&
        !psx_mod_read_byte(PLAYER+2) && p2.body[2]==1 &&
        psx_mod_read_byte(PLAYER+0xE7)==1 && p2.body[0xE7]==5;
}
static int checkpoint_equipment_lab(CPUState *cpu) {
    /* PLAY60 is also native campaign-clear state. Never persist the LAB
     * acquisition mask there or let it alter a later intro/report branch. */
    uint32_t campaign=psx_mod_read_byte(PLAY+0x60);
    STATE_WORDS(restore_campaign,67,&campaign,1);
    if(restore_campaign==UINT32_MAX)return 0;
    checkpoint_equipment_native(cpu,0xFFu);
    /* leave_zero has restored its FF projection before this canonical write.
     * The next enter_zero always captures this restored campaign value. */
    psx_mod_write_byte(PLAY+0x60,(uint8_t)campaign);
    STATE_POP(restore_campaign);
    return !state_track.error;
}
static int checkpoint_contact_source(void) {
    /* Original30ECC's no-contact path returns0 at30EEC/30EF0 and30FB4/30FB8
     * through312C4, before damage/recoil. The replacement never writes a
     * player timer, HP or pose. Authenticate that exact original function. */
    return checkpoint_hash(0x80030ECCu,0x800312DCu)==0xE1B1A427u;
}
static int checkpoint_starting_hp_source(void) {
    /* Original3BE74 loads per-character native full HP PLAY5B+character;
     *3BED8 instead loads saved current PLAY5A. Body5D/5E are health copies.
     * The lab seeds ONLY actual5C after that healthy native handoff. */
    return checkpoint_hash(0x8003BE14u,0x8003BEFCu)==0x8A849D5Du;
}
static int checkpoint_source(const Mmx6Checkpoint *entry) {
    if((checkpoint_starting_hp[0] || checkpoint_starting_hp[1]) && !checkpoint_starting_hp_source())return 0;
    if(checkpoint_earned_weapons_option && !checkpoint_equipment_source())return 0;
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
static unsigned checkpoint_starting_hp_parse(const char *option) {
    if(!strcmp(option,"off"))return 0;
    unsigned value=0;
    if(!*option || (*option=='0' && option[1]))return 33;
    for(const char *c=option;*c;++c) {
        if(*c<'0' || *c>'9')return 33;
        value=value*10u+(unsigned)(*c-'0');if(value>32)return 33;
    }
    return value?value:33;
}
static void checkpoint_reset(void) {
    memset(&checkpoint_pending,0,sizeof checkpoint_pending);
    checkpoint_lab_option=checkpoint_lab_state=checkpoint_lab_previous=0;
    checkpoint_sequence_state=checkpoint_sequence_cursor=checkpoint_sequence_release=0;
    checkpoint_contact_protection_option=0;
    checkpoint_fatal_option=checkpoint_fatal_state=0;
    checkpoint_hatch_stagger_option=checkpoint_hatch_stagger_state=0;
    checkpoint_starting_hp[0]=checkpoint_starting_hp[1]=checkpoint_starting_hp_applied=0;
    checkpoint_earned_weapons_option=checkpoint_earned_weapons_applied=checkpoint_earned_weapons_reason=0;
#ifdef MMX6_COOP_AGREED_CHECKPOINT
    char option[32]; /* Longest named development prerequisite plus NUL. */
    if(psx_mod_option_value("mmx6.local-coop","prototype","lab_checkpoint",option,sizeof option)) {
        if(!strcmp(option,"intro_cp2"))checkpoint_lab_option=1;
        else if(!strcmp(option,"intro_subtank_cp2"))checkpoint_lab_option=20;
        else if(!strcmp(option,"amazon_cp0"))checkpoint_lab_option=2;
        else if(!strcmp(option,"amazon_cp2"))checkpoint_lab_option=3;
        else if(!strcmp(option,"intro_before_doors"))checkpoint_lab_option=4;
        else if(!strcmp(option,"intro_before_explosion"))checkpoint_lab_option=5;
        else if(!strcmp(option,"recycle_cp2"))checkpoint_lab_option=6;
        else if(!strcmp(option,"recycle_portal_cp2"))checkpoint_lab_option=7;
        else if(!strcmp(option,"recycle_distant_cp2"))checkpoint_lab_option=10;
        else if(!strcmp(option,"northpole_ice_cp3"))checkpoint_lab_option=11;
        else if(!strcmp(option,"recycle_fallen_cp2"))checkpoint_lab_option=12;
        else if(!strcmp(option,"recycle_fallen_guest_cp2"))checkpoint_lab_option=13;
        else if(!strcmp(option,"secretlab2b_enemy_cp0"))checkpoint_lab_option=14;
        else if(!strcmp(option,"refight_portal_cp1"))checkpoint_lab_option=15;
        else if(!strcmp(option,"refight_distant_cp1"))checkpoint_lab_option=16;
        else if(!strcmp(option,"refight_wolfang_cp3"))checkpoint_lab_option=21;
        else if(!strcmp(option,"secretlab2a_cp3"))checkpoint_lab_option=22;
        else if(!strcmp(option,"refight_ground_cp6"))checkpoint_lab_option=23;
        else if(!strcmp(option,"heatnix_cp7"))checkpoint_lab_option=17;
        else if(!strcmp(option,"sigma_cp1"))checkpoint_lab_option=18;
        else if(!strcmp(option,"heatnix_cp0"))checkpoint_lab_option=19;
        else if(!strcmp(option,"turtloid_rain_cp1"))checkpoint_lab_option=8;
        else if(!strcmp(option,"alternate_boss_cp1"))checkpoint_lab_option=9;
        else if(!strcmp(option,"alternate_sequence_cp1"))checkpoint_lab_option=24;
        else if(strcmp(option,"off"))failed=1;
    }
    if(psx_mod_option_value("mmx6.local-coop","prototype","lab_earned_weapons",option,sizeof option)) {
        if(!strcmp(option,"all"))checkpoint_earned_weapons_option=1;
        else if(strcmp(option,"off"))failed=1;
    }
    if(psx_mod_option_value("mmx6.local-coop","prototype","lab_fatal",option,sizeof option)) {
        if(!strcmp(option,"p1"))checkpoint_fatal_option=1;
        else if(!strcmp(option,"p2"))checkpoint_fatal_option=2;
        else if(!strcmp(option,"scene_before_release"))checkpoint_fatal_option=3;
        else if(!strcmp(option,"scene_during_arrival"))checkpoint_fatal_option=4;
        else if(!strcmp(option,"capsule_owner_p1"))checkpoint_fatal_option=5;
        else if(!strcmp(option,"boss_admission_p1"))checkpoint_fatal_option=6;
        else if(!strcmp(option,"armor_p1"))checkpoint_fatal_option=7;
        else if(strcmp(option,"off"))failed=1;
    }
    if(psx_mod_option_value("mmx6.local-coop","prototype","lab_hatch_stagger",option,sizeof option)) {
        if(!strcmp(option,"on"))checkpoint_hatch_stagger_option=1;
        else if(strcmp(option,"off"))failed=1;
    }
    if(checkpoint_hatch_stagger_option && (checkpoint_lab_option!=4 || !both_doors ||
       checkpoint_fatal_option || checkpoint_earned_weapons_option))failed=1;
    if(checkpoint_fatal_option && !checkpoint_lab_option)failed=1;
    if((checkpoint_fatal_option==3 || checkpoint_fatal_option==4) && checkpoint_lab_option!=1)failed=1;
    if(checkpoint_fatal_option==5 && checkpoint_lab_option!=7)failed=1;
    if(checkpoint_fatal_option==6 && checkpoint_lab_option!=9)failed=1;
    if(checkpoint_fatal_option==7 && checkpoint_lab_option!=7)failed=1;
    if(checkpoint_lab_option==24 && checkpoint_fatal_option)failed=1;
    if(checkpoint_earned_weapons_option && !checkpoint_lab_option)failed=1;
    if(psx_mod_option_value("mmx6.local-coop","prototype","lab_contact_protection",option,sizeof option)) {
        if(!strcmp(option,"on"))checkpoint_contact_protection_option=1;
        else if(strcmp(option,"off"))failed=1;
    }
    const char *hp_options[]={"lab_starting_hp_p1","lab_starting_hp_p2"};
    for(unsigned seat=0;seat<2;++seat)
        if(psx_mod_option_value("mmx6.local-coop","prototype",hp_options[seat],option,sizeof option)) {
            unsigned hp=checkpoint_starting_hp_parse(option);
            if(hp>32)failed=1;else checkpoint_starting_hp[seat]=hp;
        }
    /* A selected damage prerequisite cannot acquire authority without the
     * existing immutable agreed checkpoint/chord/profile pipeline. */
    if((checkpoint_starting_hp[0] || checkpoint_starting_hp[1]) && !checkpoint_lab_option)failed=1;
    if(checkpoint_fatal_option==5 && (checkpoint_starting_hp[0] || checkpoint_starting_hp[1] ||
       checkpoint_earned_weapons_option))failed=1;
    if(checkpoint_hatch_stagger_option && (checkpoint_starting_hp[0] || checkpoint_starting_hp[1]))failed=1;
    /* Falling readiness deliberately precedes death, while the selected hero
     * is airborne. Do not route this prerequisite through the separate
     * both-grounded HP/equipment completion contract. The Gate enemy setup
     * likewise retains original healthy bodies and disallows these extras. */
    if((checkpoint_lab_option==12 || checkpoint_lab_option==13 || checkpoint_lab_option==14) &&
       (checkpoint_starting_hp[0] || checkpoint_starting_hp[1] || checkpoint_earned_weapons_option))failed=1;
    /* Refight placement still requires original healthy arrivals. The existing
     * earned factory runs only after source/standing completion, below. */
    if((checkpoint_lab_option==15 || checkpoint_lab_option==16 || checkpoint_lab_option==21 || checkpoint_lab_option==23) &&
       (checkpoint_starting_hp[0] || checkpoint_starting_hp[1]))failed=1;
#endif
    if(diagnostic) {
#ifdef MMX6_COOP_AGREED_CHECKPOINT
        psx_mod_write_byte(diagnostic+0xC8,(uint8_t)(checkpoint_fatal_option|(checkpoint_hatch_stagger_option<<6)));
#endif
        if(psx_mod_read_byte(diagnostic+0x50)==8)psx_mod_write_byte(diagnostic+0x50,0);
        for(unsigned i=0xA0;i<0xC4;++i)psx_mod_write_byte(diagnostic+i,0);
        for(unsigned i=0xC4;i<0xC8;++i)psx_mod_write_byte(diagnostic+i,0);
        psx_mod_write_word(diagnostic+0xA0,CHECKPOINT_CAPABILITY);
    }
}
static unsigned checkpoint_lab_generation(void) {
    return checkpoint_lab_option==24 && checkpoint_sequence_state==CHECKPOINT_SEQUENCE_USED?2u:1u;
}
static int checkpoint_lab_receipt_complete(void) {
#ifdef MMX6_COOP_AGREED_CHECKPOINT
    if(checkpoint_pending.phase || checkpoint_lab_state!=CHECKPOINT_LAB_CONSUMED ||
       !diagnostic || !checkpoint_lab_authorized())return 0;
    const Mmx6Checkpoint *entry=&checkpoint_inventory[checkpoint_lab_index()];
    return psx_mod_read_word(diagnostic+0xA0)==CHECKPOINT_CAPABILITY && psx_mod_read_word(diagnostic+0xA4)==checkpoint_lab_generation() &&
        psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_COMPLETE && !psx_mod_read_byte(diagnostic+0xA9) &&
        psx_mod_read_byte(diagnostic+0xAA)==entry->stage && psx_mod_read_byte(diagnostic+0xAB)==entry->section &&
        psx_mod_read_byte(diagnostic+0xAC)==entry->checkpoint &&
        psx_mod_read_word(diagnostic+0xB0)==checkpoint_lab_nonce() && psx_mod_read_word(diagnostic+0xB4)==1 &&
        psx_mod_read_word(diagnostic+0xB8)==entry->record && psx_mod_read_byte(diagnostic+0xBC)==1 &&
        psx_mod_read_byte(diagnostic+0xBD)==CHECKPOINT_AGREED &&
        psx_mod_read_byte(diagnostic+0xBE)==CHECKPOINT_LAB_CONSUMED;
#else
    return 0;
#endif
}
static void checkpoint_sequence_input(CPUState *cpu,uint32_t address,uint32_t instruction) {
#ifdef MMX6_COOP_AGREED_CHECKPOINT
    /* Already emitted native post-decoder site, before its saved-RA load.
     * Observe only; the original instruction and all guest RAM are untouched. */
    if(!cpu || address!=0x80012C44u || instruction!=0x8FBF0010u ||
       checkpoint_lab_option!=24 || checkpoint_sequence_state>=CHECKPOINT_SEQUENCE_MISSION ||
       !ready || !enrolled || failed || inside || stage_call || player_call || ride_call ||
       view_call || private_draw || zero_world || zero_projected ||
       !checkpoint_lab_receipt_complete() || (cpu->gpr[29]&3u) ||
       cpu->gpr[29]<0x80010000u || cpu->gpr[29]>0x801FFFECu)return;
    uint32_t caller=psx_mod_read_word(cpu->gpr[29]+16u);
    if(caller!=0x80012220u && caller!=0x8001A834u && caller!=0x8001AB18u)return;
    if(psx_mod_read_byte(PLAY)==4 && psx_mod_read_byte(PLAY+1)==4 &&
       !psx_mod_read_byte(PLAY+2) && psx_mod_read_byte(PLAY+12)==13 && !psx_mod_read_byte(0x80097424u)) {
        /* Original Map4 EA894 owns PLAY27; PLAY2A is a different UI field. */
        unsigned cursor=psx_mod_read_byte(PLAY+0x27u);
        if(cursor>=24)return;
        if(!checkpoint_sequence_state) {
            checkpoint_sequence_state=CHECKPOINT_SEQUENCE_MAP;checkpoint_sequence_cursor=cursor;
        } else if(checkpoint_sequence_state==CHECKPOINT_SEQUENCE_MAP && cursor!=checkpoint_sequence_cursor)
            checkpoint_sequence_state=CHECKPOINT_SEQUENCE_RESPONSIVE;
    } else if(psx_mod_read_byte(PLAY)!=4 && checkpoint_sequence_state==CHECKPOINT_SEQUENCE_MAP) {
        checkpoint_sequence_state=checkpoint_sequence_cursor=0;
    }
#else
    (void)cpu;(void)address;(void)instruction;
#endif
}
static int checkpoint_lab_completed(void) {
#ifdef MMX6_COOP_AGREED_CHECKPOINT
    if(!checkpoint_lab_receipt_complete())return 0;
    const Mmx6Checkpoint *entry=&checkpoint_inventory[checkpoint_lab_index()];
    return psx_mod_read_byte(PLAY+12)==entry->stage && psx_mod_read_byte(PLAY+13)==entry->section &&
        psx_mod_read_byte(PLAY+0x1D)==entry->checkpoint;
#else
    return 0;
#endif
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
       psx_mod_read_word(diagnostic+0xA0)!=CHECKPOINT_CAPABILITY || psx_mod_read_word(diagnostic+0xA4)!=checkpoint_lab_generation() ||
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
static int checkpoint_before_doors_idle_character(unsigned seat,unsigned character) {
    uint8_t body[sizeof p2.body];
    if(seat)memcpy(body,p2.body,sizeof body);else capture(PLAYER,body,sizeof body);
    const unsigned locks[]={0x7A,0x8E,0xA4,0xCC,0xCD,0xD0,0xD3,0xD4,0xE0};
    for(unsigned i=0;i<sizeof locks/sizeof locks[0];++i)if(body[locks[i]])return 0;
    return character<2 && body[0] && body[2]==character && body[4]==1 && body[5]==2 &&
        body[0x5C]>0 && body[0x5C]<128 && !body[0x14] && !body[0x67] &&
        (body[0x70]&8) && le32(body+0x68)==0x80073D50u+character*4u;
}
static int checkpoint_before_doors_idle(unsigned seat) {
    return checkpoint_before_doors_idle_character(seat,seat);
}
static unsigned checkpoint_starting_hp_mask(void) {
    return (checkpoint_starting_hp[0]?1u:0u)|(checkpoint_starting_hp[1]?2u:0u);
}
static unsigned checkpoint_starting_hp_status(void) {
    return checkpoint_starting_hp_mask()?(checkpoint_starting_hp_applied?2u:1u):0u;
}
static void checkpoint_complete(CPUState *cpu) {
    unsigned mask=checkpoint_starting_hp_mask();
    unsigned hp_pending=mask && !checkpoint_starting_hp_applied;
    unsigned equipment_pending=checkpoint_earned_weapons_option && !checkpoint_earned_weapons_applied;
    if(hp_pending || equipment_pending) {
        if(checkpoint_pending.authority!=CHECKPOINT_AGREED ||
           checkpoint_pending.index!=checkpoint_lab_index() || checkpoint_pending.nonce!=checkpoint_lab_nonce() ||
           checkpoint_lab_state!=CHECKPOINT_LAB_CONSUMED || !checkpoint_lab_authorized() ||
           psx_mod_read_word(diagnostic+0xA4)!=1 || psx_mod_read_word(diagnostic+0xB4)!=1 ||
           psx_mod_read_byte(diagnostic+0xBC)!=1 || psx_mod_read_byte(diagnostic+0xBD)!=CHECKPOINT_AGREED) {
            if(equipment_pending)checkpoint_earned_weapons_reason=CHECKPOINT_FORBIDDEN;
            checkpoint_cancel(CHECKPOINT_FORBIDDEN);return;
        }
        if(!checkpoint_starting_hp_source() || (equipment_pending && !checkpoint_equipment_source())) {
            if(equipment_pending)checkpoint_earned_weapons_reason=CHECKPOINT_SOURCE;
            checkpoint_cancel(CHECKPOINT_SOURCE);return;
        }
        if(!checkpoint_safe_boundary() || !checkpoint_before_doors_idle(0) || !checkpoint_before_doors_idle(1) ||
           (equipment_pending && !checkpoint_equipment_context(cpu)))return;
        uint8_t primary[sizeof p2.body];capture(PLAYER,primary,sizeof primary);
        for(unsigned seat=0;seat<2;++seat) {
            const uint8_t *b=seat?p2.body:primary;
            /* Any configured HP seed still requires native full health.
             * Equipment alone may follow native damage: actual/display HP
             * remain positive (display may lag), max HP stays native full.
             * The original factory must preserve all three health bytes. */
            unsigned full=psx_mod_read_byte(PLAY+0x5Bu+b[2]);
            if(full<32 || full>=128 || b[0x5E]!=full || checkpoint_starting_hp[seat]>full)return;
            if(mask && (b[0x5C]!=full || b[0x5D]!=full))return;
            if(!mask && (!b[0x5C] || b[0x5C]>=128 || !b[0x5D] || b[0x5D]>=128))return;
        }
        /* Original checkpoint initialization has finished; it cannot clobber
         * these native per-body flags. Acquire before the optional HP seed. */
        if(equipment_pending) {
            if(!checkpoint_equipment_lab(cpu)) {
                checkpoint_earned_weapons_reason=CHECKPOINT_PLUGIN_FAILED;
                checkpoint_cancel(CHECKPOINT_PLUGIN_FAILED);return;
            }
            checkpoint_earned_weapons_applied=1;
        }
        if(hp_pending) {
            for(unsigned seat=0;seat<2;++seat)if(checkpoint_starting_hp[seat]) {
                if(seat)p2.body[0x5C]=(uint8_t)checkpoint_starting_hp[seat];
                else psx_mod_write_byte(PLAYER+0x5C,(uint8_t)checkpoint_starting_hp[seat]);
            }
            checkpoint_starting_hp_applied=1;
        }
#ifdef MMX6_COOP_CHECKPOINT_TAINT_API
        psx_session_input_taint_add(PSX_INPUT_TAINT_GAME_MAILBOX);
#endif
    }
    memset(&checkpoint_pending,0,sizeof checkpoint_pending);
    checkpoint_status(CHECKPOINT_COMPLETE,CHECKPOINT_OK);
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
#include "mmx6_coop_before_northpole.inc"
#include "mmx6_coop_gate_enemy.inc"
#include "mmx6_coop_before_refight.inc"
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
    else if(authority==CHECKPOINT_AGREED && checkpoint_lab_option==20 && !separate_subtanks)
        reason=CHECKPOINT_FORBIDDEN;
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
    if(authority==CHECKPOINT_AGREED && checkpoint_lab_option==20) {
        /* Fixed, declared prerequisite before the ORIGINAL 8->9 initializer.
         * Its completion/retention and both native heals remain unmodified.
         * The consumed LAB request is the sole one-shot guard; existing
         * bank storage/serializer owns this state, with no extra latch. */
        subtank_seed();
        psx_mod_write_byte(PLAY+0x6B,psx_mod_read_byte(PLAY+0x6B)|0x10u);
        psx_mod_write_byte(PLAY+0x63,0x90u);
        zero_subtanks[0]=0x88u;
        subtank_found=psx_mod_read_byte(PLAY+0x6B)&0x30u;
    }
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
            if(checkpoint_pending.authority==CHECKPOINT_AGREED &&
               (checkpoint_lab_option==15 || checkpoint_lab_option==16)) {
                uint32_t meta,desc;
                if(checkpoint_starting_hp[0] || checkpoint_starting_hp[1])
                    checkpoint_cancel(CHECKPOINT_FORBIDDEN);
                /* The first mode10 entry still has pristine DAT104 and an
                 * uninitialized native player. Let original world/body and
                 * secondary-mapcopy initialization finish before qualifying
                 * their loaded resources. Placement still requires the full
                 * original arrival, standing feet and camera contract. */
                else if(checkpoint_pending.phase==2 && !checkpoint_refight_standing()) { }
                else if(!checkpoint_source(entry) || !checkpoint_refight_source() ||
                        !checkpoint_refight_assets(&meta,&desc) || !checkpoint_refight_ground(meta,desc) ||
                        (checkpoint_lab_option==16 && !checkpoint_refight_distant_ground(meta,desc))) {
                    checkpoint_refight_refusal(entry);
                    checkpoint_refusal_value("refight-source-assets-corridor",0,entry->record,0,1);
                    checkpoint_cancel(CHECKPOINT_SOURCE);
                } else if(checkpoint_pending.phase==2) {
                    if(checkpoint_refight_original_arrival(meta,desc))checkpoint_refight_place();
                } else if(checkpoint_refight_ready()) {
                    psx_mod_write_byte(diagnostic+0xAD,2);checkpoint_complete(cpu);
                }
            } else if(checkpoint_pending.authority==CHECKPOINT_AGREED && checkpoint_lab_option==14) {
                uint32_t meta,desc;
                if(checkpoint_starting_hp[0] || checkpoint_starting_hp[1] || checkpoint_earned_weapons_option)
                    checkpoint_cancel(CHECKPOINT_FORBIDDEN);
                else if(!checkpoint_source(entry) || !checkpoint_gate_enemy_source() ||
                        !checkpoint_gate_enemy_assets(&meta,&desc) || !checkpoint_gate_enemy_ground(meta,desc)) {
                    checkpoint_refusal_value("gate-enemy-source-assets-corridor",0,entry->record,0,1);
                    checkpoint_cancel(CHECKPOINT_SOURCE);
                } else if(!checkpoint_gate_enemy_inactive())checkpoint_cancel(CHECKPOINT_UNSAFE);
                else if(checkpoint_pending.phase==2) {
                    if(checkpoint_gate_enemy_original_arrival())checkpoint_gate_enemy_place();
                } else if(checkpoint_gate_enemy_ready()) {
                    psx_mod_write_byte(diagnostic+0xAD,2);checkpoint_complete(cpu);
                }
            } else if(checkpoint_pending.authority==CHECKPOINT_AGREED &&
               (checkpoint_lab_option==12 || checkpoint_lab_option==13)) {
                uint32_t meta,desc;
                if(checkpoint_starting_hp[0] || checkpoint_starting_hp[1] || checkpoint_earned_weapons_option)
                    checkpoint_cancel(CHECKPOINT_FORBIDDEN);
                else if(!checkpoint_source(entry) || !checkpoint_fallen_portal_source() ||
                        !checkpoint_portal_assets(&meta,&desc) || !checkpoint_fallen_portal_ground(meta,desc)) {
                    checkpoint_refusal_value("fallen-portal-source-assets-pit",0,entry->record,0,1);
                    checkpoint_cancel(CHECKPOINT_SOURCE);
                } else if(checkpoint_pending.phase==2) {
                    if(checkpoint_fallen_portal_original_arrival())checkpoint_fallen_portal_place();
                } else if(checkpoint_fallen_portal_ready()) {
                    psx_mod_write_byte(diagnostic+0xAD,2);checkpoint_complete(cpu);
                }
            } else if(checkpoint_pending.authority==CHECKPOINT_AGREED && checkpoint_lab_option==11) {
                uint32_t meta,desc;
                if(!checkpoint_source(entry) || !checkpoint_northpole_source() ||
                   !checkpoint_northpole_assets(&meta,&desc) || !checkpoint_northpole_ground(meta,desc)) {
                    checkpoint_refusal_value("northpole-setup-source-assets-ground",0,entry->record,0,1);
                    checkpoint_cancel(CHECKPOINT_SOURCE);
                } else if(checkpoint_pending.phase==2) {
                    if(checkpoint_northpole_original_arrival())checkpoint_northpole_place();
                } else if(checkpoint_northpole_ready()) {
                    psx_mod_write_byte(diagnostic+0xAD,2);checkpoint_complete(cpu);
                }
            } else if(checkpoint_pending.authority==CHECKPOINT_AGREED && (checkpoint_lab_option==7 || checkpoint_lab_option==10)) {
                uint32_t meta,desc;
                if(checkpoint_lab_option==10 && !independent_views)checkpoint_cancel(CHECKPOINT_FORBIDDEN);
                else if(!checkpoint_source(entry) || !checkpoint_portal_source() ||
                   !checkpoint_portal_assets(&meta,&desc) || !checkpoint_portal_ground(meta,desc)) {
                    checkpoint_refusal_value("portal-setup-source-assets-ground",0,entry->record,0,1);
                    checkpoint_cancel(CHECKPOINT_SOURCE);
                } else if(checkpoint_pending.phase==2) {
                    if(checkpoint_portal_original_arrival())checkpoint_portal_place();
                } else if(checkpoint_portal_ready()) {
                    psx_mod_write_byte(diagnostic+0xAD,2);checkpoint_complete(cpu);
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
                    else {psx_mod_write_byte(diagnostic+0xAD,2);checkpoint_complete(cpu);}
                }
            } else {
                checkpoint_complete(cpu);
            }
        } else checkpoint_cancel(CHECKPOINT_ORDER);
    }
    if(psx_mod_read_byte(diagnostic+0x50)!=8)return 0;
    return checkpoint_request(psx_mod_read_byte(diagnostic+0x51),psx_mod_read_byte(diagnostic+0x52),
        psx_mod_read_byte(diagnostic+0x53),psx_mod_read_word(diagnostic+0x54),CHECKPOINT_OFFLINE);
}
/* Original terrain contact uses +70; actor support uses +71 (8002E3C4/8002E658).
 * Native800350F8 clears +71 each body update; it is not a previous-ground copy. */
static int checkpoint_fatal_idle(unsigned seat) {
    uint8_t body[sizeof p2.body];
    if(seat)memcpy(body,p2.body,sizeof body);else capture(PLAYER,body,sizeof body);
    const unsigned locks[]={0x7A,0x8E,0xA4,0xCC,0xCD,0xD0,0xD3,0xD4,0xE0};
    for(unsigned i=0;i<sizeof locks/sizeof locks[0];++i)if(body[locks[i]])return 0;
    return body[0] && body[2]<2 && body[4]==1 && body[5]==2 &&
        !body[0x67] && ((body[0x70]|body[0x71])&8);
}
/* Named F167 prerequisite only. Original51924 admits this in-place capsule
 * scene. A fresh agreed chord may request HP80; native updates must decide
 * whether death is admissible and whether the surviving partner is released. */
static int checkpoint_capsule_fatal_ready(void) {
    if(checkpoint_lab_option!=7 || !checkpoint_lab_completed() || !ready || !enrolled || failed ||
       inside || stage_call || player_call || ride_call || view_call || private_draw || zero_world ||
       zero_projected || scene_call || state_track.count || state_track.error || pause_owner>=0 ||
       clear_phase || life.wipe || arrival_pair || join_phase || both_door_actor ||
       psx_mod_read_byte(PLAY)!=10 || psx_mod_read_byte(PLAY+1) || scene_owner!=1 || scene_phase ||
       psx_mod_read_word(diagnostic+0x74)!=0x80051924u || psx_mod_read_byte(diagnostic+0xAD)!=2 ||
       life.status[0]!=MMX6_COOP_ALIVE || life.status[1]!=MMX6_COOP_ALIVE ||
       !psx_mod_read_byte(PLAYER) || psx_mod_read_byte(PLAYER+2)!=0 || psx_mod_read_byte(PLAYER+4)!=1 ||
       psx_mod_read_byte(PLAYER+5)!=20 || !psx_mod_read_byte(PLAYER+0x5C) || psx_mod_read_byte(PLAYER+0x5C)>=128 ||
       !p2.body[0] || !p2.body[3] || p2.body[4]!=1 || !p2.body[0x5C] || p2.body[0x5C]>=128 ||
       !(psx_mod_read_byte(PLAYER+0xD0) || psx_mod_read_byte(PLAYER+0xD4) || psx_mod_read_byte(PLAYER+0x7A) ||
         psx_mod_read_byte(PLAY+0x10) || psx_mod_read_byte(PLAY+0x1C) || psx_mod_read_byte(0x8008EAFCu)))return 0;
    unsigned capsules=0;
    for(unsigned i=0;i<80;++i) {
        uint32_t a=0x800C1220u+i*0xA4u;
        if((psx_mod_read_byte(a)&1u) && psx_mod_read_byte(a+1)==26 && psx_mod_read_byte(a+2)==4 &&
           psx_mod_read_word(a+0x10)==0x800F2E24u && psx_mod_read_byte(a+4)==1 &&
           psx_mod_read_byte(a+5)==1 && !psx_mod_read_byte(a+6))++capsules;
    }
    return capsules==1;
}
/* F41 prerequisite: the original route-boss HP0 admission, before combat.
 * Original BIN43 800FA0B0/C0 selects NPC53 CLUT7948. The other living hero
 * may already be hidden by the original paired scene; do not require it idle.
 * Only request native fatal HP80. Native death/retry and the next introduction
 * remain outcomes, never fixture writes or calls into the boss controller. */
static int checkpoint_boss_admission_fatal_ready(void) {
    if(checkpoint_lab_option!=9 || !checkpoint_lab_completed() || !ready || !enrolled || failed ||
       inside || stage_call || player_call || ride_call || view_call || private_draw || zero_world ||
       zero_projected || scene_call || state_track.count || state_track.error || pause_owner>=0 ||
       clear_phase || life.wipe || arrival_pair || join_phase || both_door_actor ||
       psx_mod_read_byte(PLAY)!=10 || psx_mod_read_byte(PLAY+1) || scene_owner!=1 || scene_phase>3 ||
       life.status[0]!=MMX6_COOP_ALIVE || life.status[1]!=MMX6_COOP_ALIVE ||
       !psx_mod_read_byte(PLAYER) || psx_mod_read_byte(PLAYER+2)!=0 || psx_mod_read_byte(PLAYER+4)!=1 ||
       psx_mod_read_byte(PLAYER+5)!=20 || !psx_mod_read_byte(PLAYER+0x5C) || psx_mod_read_byte(PLAYER+0x5C)>=128 ||
       !p2.body[0] || (p2.body[4]!=1 && p2.body[4]!=3) || !p2.body[0x5C] || p2.body[0x5C]>=128 ||
       psx_mod_read_word(0x800FA0B0u)!=0x24027948u || psx_mod_read_word(0x800FA0C0u)!=0xA6420042u)return 0;
    uint32_t boss=psx_mod_read_word(PLAY+0x20);
    if(boss<0x8008EF48u || boss>=0x8008EF48u+48u*0x9Cu || (boss-0x8008EF48u)%0x9Cu)return 0;
    return (psx_mod_read_byte(boss)&1u) && psx_mod_read_byte(boss+1)==53 &&
        !psx_mod_read_byte(boss+2) && psx_mod_read_byte(boss+4)==1 && psx_mod_read_byte(boss+5)==2 &&
        !psx_mod_read_byte(boss+0x5C) && psx_mod_read_half(boss+0x42)==0x7948u;
}
/* Fixed F4/F103 reachability only. These are the same original lock/release
 * calls as offline commands5/6, selected and hashed before boot. The existing
 * scene hooks own all phase/beam state; only native fatal HP80 is requested.
 * No caller may manufacture a scene phase, death or successful recovery. */
static void checkpoint_scene_call(CPUState *cpu,uint32_t address) {
    enter_zero();guest(cpu,address,0x14,0x40);leave_zero_context(1);
}
static void checkpoint_scene_fatal_boundary(CPUState *cpu) {
    if(!checkpoint_lab_completed() || !ready || !enrolled || failed || inside || stage_call ||
       player_call || ride_call || view_call || private_draw || zero_world || zero_projected ||
       pause_owner>=0 || clear_phase || life.wipe || psx_mod_read_byte(PLAY)!=10 ||
       psx_mod_read_byte(PLAY+1) || scene_owner!=2) {
        checkpoint_fatal_state=CHECKPOINT_FATAL_CONSUMED;return;
    }
    if(checkpoint_fatal_state==CHECKPOINT_FATAL_SCENE_LOCKED) {
        /* Native outgoing beam must actually retire before either operation. */
        if(scene_phase!=3 || psx_mod_read_byte(PLAYER+4)!=3 ||
           life.status[0]!=MMX6_COOP_ALIVE || life.status[1]!=MMX6_COOP_ALIVE ||
           p2.body[4]!=1 || !p2.body[0x5C] || p2.body[0x5C]>=128)return;
        if(checkpoint_fatal_option==3) {
            p2.body[0x5C]=0x80;checkpoint_fatal_state=CHECKPOINT_FATAL_SCENE_WAIT_DEATH;
        } else {
            checkpoint_scene_call(cpu,0x8003D330u);
            checkpoint_fatal_state=CHECKPOINT_FATAL_SCENE_WAIT_ARRIVAL;
        }
    } else if(checkpoint_fatal_state==CHECKPOINT_FATAL_SCENE_WAIT_DEATH) {
        /* Observe original fatal handling before asking the script to release. */
        if(scene_phase!=3 || p2.body[0x5C] ||
           (life.status[1]!=MMX6_COOP_DYING && life.status[1]!=MMX6_COOP_FALLEN))return;
        checkpoint_scene_call(cpu,0x8003D330u);
        checkpoint_fatal_state=CHECKPOINT_FATAL_CONSUMED;
    } else if(checkpoint_fatal_state==CHECKPOINT_FATAL_SCENE_WAIT_ARRIVAL) {
        if(scene_phase!=4 || life.status[0]!=MMX6_COOP_ALIVE || life.status[1]!=MMX6_COOP_ALIVE ||
           psx_mod_read_byte(PLAYER+4)!=1 || !psx_mod_read_byte(PLAYER+0x5C) ||
           psx_mod_read_byte(PLAYER+0x5C)>=128 || p2.body[4]!=1 ||
           !p2.body[0x5C] || p2.body[0x5C]>=128)return;
        p2.body[0x5C]=0x80;checkpoint_fatal_state=CHECKPOINT_FATAL_CONSUMED;
    }
}
/* Matching F145 prerequisite only, equivalent to offline atomic command4.
 * Native CP2 can already be earned during phase3. Authenticate the immutable
 * completed CP1 receipt, then this exact live first hatch/current CP1-or2. */
static void checkpoint_hatch_stagger_boundary(void) {
#ifdef MMX6_COOP_AGREED_CHECKPOINT
    if(!checkpoint_hatch_stagger_option || checkpoint_hatch_stagger_state || checkpoint_lab_option!=4 ||
       !checkpoint_lab_receipt_complete() || !ready || !enrolled || failed || inside || stage_call ||
       player_call || ride_call || view_call || private_draw || zero_world || zero_projected ||
       state_track.count || state_track.error ||
       pause_owner>=0 || clear_phase || life.wipe || !both_door_traversal_active() || both_door_members!=3 ||
       both_door_origin!=0x800FA2A4u || psx_mod_read_byte(both_door_actor+4)!=1 ||
       psx_mod_read_byte(both_door_actor+5)!=3 || psx_mod_read_byte(PLAY)!=10 || psx_mod_read_byte(PLAY+1) ||
       psx_mod_read_byte(PLAY+12) || psx_mod_read_byte(PLAY+13) ||
       (psx_mod_read_byte(PLAY+0x1D)!=1 && psx_mod_read_byte(PLAY+0x1D)!=2) ||
       psx_mod_read_byte(diagnostic+0xAD)!=2 || psx_mod_read_byte(diagnostic+0xAE)!=1 ||
       life.status[0]!=MMX6_COOP_ALIVE || life.status[1]!=MMX6_COOP_ALIVE ||
       !psx_mod_read_byte(PLAYER) || !p2.body[0] || psx_mod_read_byte(PLAYER+4)!=1 || p2.body[4]!=1 ||
       !psx_mod_read_byte(PLAYER+0x5C) || psx_mod_read_byte(PLAYER+0x5C)>=128 || !p2.body[0x5C] || p2.body[0x5C]>=128 ||
       psx_mod_read_word(PLAYER+0x68) || le32(p2.body+0x68) ||
       (int32_t)psx_mod_read_word(PLAYER+8)<(5768<<16))return;
    psx_session_input_taint_add(PSX_INPUT_TAINT_GAME_MAILBOX);
    put32(p2.body+8,5744u<<16);put32(p2.body+12,394u<<16);
    put32(p2.body+0x18,5744u<<16);put32(p2.body+0x1C,394u<<16);
    checkpoint_hatch_stagger_state=1;
    psx_mod_write_byte(diagnostic+0xC8,(uint8_t)(checkpoint_fatal_option|(checkpoint_fatal_state<<3)|0xC0u));
#endif
}
static int checkpoint_lab_boundary(CPUState *cpu,uint16_t raw) {
#ifdef MMX6_COOP_AGREED_CHECKPOINT
    if(checkpoint_lab_state==CHECKPOINT_LAB_CONSUMED) {
        if(checkpoint_lab_option==24 && checkpoint_sequence_state==CHECKPOINT_SEQUENCE_MISSION) {
            /* A new ordinary mission was observed at the original mode9
             * entry. Unsafe/held edges never become deferred requests. */
            int safe=checkpoint_lab_receipt_complete() && checkpoint_safe_boundary() &&
                psx_mod_read_byte(PLAY+12)==4 && !psx_mod_read_byte(PLAY+13) && !psx_mod_read_byte(PLAY+0x1D) &&
                checkpoint_before_doors_idle(0) && checkpoint_before_doors_idle(1);
            if(!safe || (raw && raw!=6))checkpoint_sequence_release=0;
            else if(!raw)checkpoint_sequence_release=1;
            else if(checkpoint_sequence_release) {
                checkpoint_sequence_release=0;checkpoint_sequence_state=CHECKPOINT_SEQUENCE_USED;
                return checkpoint_request(20,1,1,CHECKPOINT_LAB_ALTERNATE_NONCE,CHECKPOINT_AGREED);
            }
        }
        checkpoint_hatch_stagger_boundary();
        if(!checkpoint_fatal_option || !diagnostic || checkpoint_fatal_state==CHECKPOINT_FATAL_CONSUMED)return 0;
        int armor_only=checkpoint_fatal_option==7;
        int mounted=(checkpoint_fatal_option<=2 || armor_only) &&
            checkpoint_mounted_fatal_ready(armor_only?0:checkpoint_fatal_option-1);
        if((checkpoint_fatal_option==3 || checkpoint_fatal_option==4) && checkpoint_fatal_state>=CHECKPOINT_FATAL_SCENE_LOCKED) {
            checkpoint_scene_fatal_boundary(cpu);
        } else if(!checkpoint_lab_completed() && !mounted)checkpoint_fatal_state=CHECKPOINT_FATAL_RELEASE;
        else if(raw!=6)checkpoint_fatal_state=raw?CHECKPOINT_FATAL_RELEASE:CHECKPOINT_FATAL_ARMED;
        else if(checkpoint_fatal_state==CHECKPOINT_FATAL_ARMED) {
            checkpoint_fatal_state=CHECKPOINT_FATAL_RELEASE; /* Unsafe edges never fire later while held. */
            if(checkpoint_fatal_option==6?checkpoint_boss_admission_fatal_ready():
               checkpoint_fatal_option==5?checkpoint_capsule_fatal_ready():
               armor_only?mounted:
               (mounted || (checkpoint_safe_boundary() && !clear_phase && !join_phase && !arrival_pair &&
                checkpoint_fatal_idle(0) && checkpoint_fatal_idle(1)))) {
                psx_session_input_taint_add(PSX_INPUT_TAINT_GAME_MAILBOX);
                if(checkpoint_fatal_option==3 || checkpoint_fatal_option==4) {
                    checkpoint_scene_call(cpu,0x8003D308u);
                    checkpoint_fatal_state=CHECKPOINT_FATAL_SCENE_LOCKED;
                } else {
                    /* New7 requests only original TYPE1 Armor health. Its
                     * native fuse, D5 release, foot box and landing remain
                     * outcomes; old1..6 fatal meanings are unchanged. */
                    if(!armor_only) {
                        if(checkpoint_fatal_option==1 || checkpoint_fatal_option==5 || checkpoint_fatal_option==6)psx_mod_write_byte(PLAYER+0x5C,0x80);
                        else p2.body[0x5C]=0x80;
                    }
                    if(mounted)psx_mod_write_byte(RIDE+0x5C,0x80);
                    checkpoint_fatal_state=CHECKPOINT_FATAL_CONSUMED;
                }
            }
        }
        /* C8: fatal choice bits0..2, fatal state bits3..5, stagger selected/
         * consumed bits6/7.
         * Existing checkpoint receipt and original chord latch stay untouched. */
        psx_mod_write_byte(diagnostic+0xC8,(uint8_t)(checkpoint_fatal_option|(checkpoint_fatal_state<<3)|(checkpoint_hatch_stagger_option<<6)|(checkpoint_hatch_stagger_state<<7)));
        return 0; /* Original player/world update performs fatal handling. */
    }
    if(!checkpoint_lab_option)return 0;
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
    /* These fixed intro CP2/Recycle/portal/alternate-boss/Wolfang/fortress prerequisites
     * may follow an actual native card Load and Recycle mission arrival. The
     * alternate-boss route keeps its original card-owned encounter selection;
     * the inverse Wolfang check likewise keeps native card-owned weapons.
     * The parent still proves the card and acquired masks. */
    if((origin_stage || origin_section || origin_checkpoint) &&
       !((checkpoint_lab_option==1 || checkpoint_lab_option==6 || checkpoint_lab_option==7 ||
           checkpoint_lab_option==9 || checkpoint_lab_option==24 || checkpoint_lab_option==21 || checkpoint_lab_option==22) &&
         origin_stage==4 && !origin_section && !origin_checkpoint)) {
        checkpoint_status(CHECKPOINT_REJECTED,CHECKPOINT_ORDER);return 0;
    }
    unsigned index=checkpoint_lab_index();
    if(index>=115) {checkpoint_status(CHECKPOINT_REJECTED,CHECKPOINT_UNKNOWN);return 0;}
    const Mmx6Checkpoint *entry=&checkpoint_inventory[index];
    (void)cpu;
    return checkpoint_request(entry->stage,entry->section,entry->checkpoint,
        checkpoint_lab_nonce(),CHECKPOINT_AGREED);
#else
    (void)cpu;(void)raw;return 0;
#endif
}
static void checkpoint_native_entry(CPUState *cpu,uint32_t address) {
    if(checkpoint_lab_option==24 && checkpoint_sequence_state==CHECKPOINT_SEQUENCE_RESPONSIVE &&
       !checkpoint_pending.phase && checkpoint_lab_receipt_complete() && cpu &&
       address==0x8001E1BCu && cpu->gpr[31]==0x8001E720u && cpu->gpr[4]==PLAY &&
       ready && !failed && !inside && !stage_call && !player_call && !ride_call &&
       !view_call && !private_draw && !zero_world && !zero_projected && !state_track.count && !state_track.error &&
       psx_mod_read_byte(PLAY)==9 && psx_mod_read_byte(PLAY+12)==4 &&
       !psx_mod_read_byte(PLAY+13) && !psx_mod_read_byte(PLAY+0x1D)) {
        checkpoint_sequence_state=CHECKPOINT_SEQUENCE_MISSION;checkpoint_sequence_release=0;
    }
    /* Original mode9 entry still has the prior loaded checkpoint CC868.
     * BIN33 FC244..FC2E4 retires the real death child, marks the earned
     * refight and selects oldCP+8. Capture only that living continuation,
     * before the native loader replaces the old module/body context. */
    unsigned old_cp=psx_mod_read_byte(0x800CC868u),cp=psx_mod_read_byte(PLAY+0x1D);
    refight_return_checkpoint=0;
    if(cpu && address==0x8001E1BCu && cpu->gpr[31]==0x8001E720u && cpu->gpr[4]==PLAY &&
       ready && !failed && !inside && !zero_projected && psx_mod_read_byte(PLAY)==9 &&
       psx_mod_read_byte(PLAY+12)==12 && !psx_mod_read_byte(PLAY+13) &&
       old_cp>=2 && old_cp<=9 && cp==old_cp+8 && !life.wipe &&
       life.status[0]==MMX6_COOP_ALIVE && life.status[1]==MMX6_COOP_ALIVE &&
       p2.body[2]==1 && (p2.body[0x5C]&0x7F)) {
        memcpy(returning_body,p2.body,sizeof returning_body);
        refight_return_checkpoint=cp;
        psx_mod_counter_add("mmx6.coop.refight-resources-retained",1);
    }
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
