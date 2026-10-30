/* Original Recycle member6 c7b195e3e3968ebbd6c177cf023e47b35a9a816382c9b54ca157a80b393468f5.
 * Only record18/type1C/subtype1 action1. Deferred native PLAYER reads stay
 * with the admitted scene owner through the existing single world pass.
 * No new persistent state, synthesized transition, or whole-AI double pass. */
#include "psx_sha256.h"
typedef struct { uint32_t first,bytes; const char *sha; } Mmx6PortalCode;
static const Mmx6PortalCode recycle_portal_code[]={
    {0x800EBD80u,0xC1Cu,"649b1982448e991220f590c33c2e63ea0851750ec7a6dd78038f06604738365f"},
    {0x800F38B8u,0x7Cu,"3ddf40bbf8a26b1afbb70e52e7f8630bfbe88bdee0c7ea3a00df5ea5acf5601c"},
    {0x800E9864u,0x14u,"53b05d275b9e87395fd528643ec36cb8907090872218b132cd804162b4ee7f43"},
    {0x8002D654u,0x214u,"39bed2ddf0ab87f9f986d8f51c1fc735557ffbf0949fd4dfd3fc54e928d2168b"},
    {0x80020C40u,0xC4u,"0420ce4f4df1aa2567b932ec9af2524a174f99b07c0b99d85dd6b64646090a97"},
    {0x8003A628u,0x50u,"8448685dacfd99c7da2ffeced5139cfc0611367502fabede5da4ada73dc97df5"},
    {0x8003B870u,0xE4u,"1912ca2068ca612bdd1e3928fe718601dfb551001b07d1349ea682aec6edf5ea"},
    {0x8001EA28u,0x120u,"86465a195f3b5fd7577cfc0595928bd8c278efda3060a607e5547e18dcf8dac4"},
    {0x8001EB48u,0xC4u,"26083b03e74a7d9beffdf0e648cf2fc5dca58979dfba81c79eee7b57e80cb101"},
    {0x8001E914u,0xD8u,"ad4d2d9299a5e871110bde73120cb7410560e1d8e9797143bc3bb474be35b371"},
    {0x8001E9ECu,0x3Cu,"ca34fec0c410c6edafefa2051a70b296396f6a761e4575b235c1160e85d57e47"},
    {0x8001E1BCu,0x170u,"db8d0094d673f5a0f2c89beb097c54bee6f8449c539d9d176f00844af5160b9c"},
    {0x8001E32Cu,0x3B8u,"c532803823d419cf6804de1052208f0e5c9f8fb580ceb203b12de4d4157a6cbb"},
    {0x80042F7Cu,0x2Cu,"71e386a73511afbe127fe413a0403074e0978eb81db558eea22d61711a0043a5"},
    {0x80029E7Cu,0xBCu,"df6eff4115848b712fbc5f13bac169665422de1032a5e9544412af5d56e7da89"},
    {0x8002A254u,0x14u,"9a76756a228e340e960ce17f8dd26714f2dedc0ee4816d9e351f20689bd95587"},
    {0x8002A33Cu,0x70u,"64d048352812e4978ca1ed0fcc3edd590db9311fb7a08ef19a216024f7f980c5"}
};
static int recycle_portal_source(void) {
    static const char hex[]="0123456789abcdef";
    for(unsigned i=0;i<sizeof recycle_portal_code/sizeof recycle_portal_code[0];++i) {
        const Mmx6PortalCode *span=&recycle_portal_code[i];
        psx_sha256_ctx hash;uint8_t buffer[128],digest[32];psx_sha256_init(&hash);
        for(unsigned at=0;at<span->bytes;) {
            unsigned count=span->bytes-at;if(count>sizeof buffer)count=sizeof buffer;
            capture(span->first+at,buffer,count);psx_sha256_update(&hash,buffer,count);at+=count;
        }
        psx_sha256_final(&hash,digest);
        for(unsigned n=0;n<32;++n)
            if(span->sha[n*2]!=hex[digest[n]>>4] || span->sha[n*2+1]!=hex[digest[n]&15])return 0;
    }
    unsigned flags=psx_mod_read_byte(0x800F2B0Cu);
    unsigned state=psx_mod_read_byte(0x800F2B0Fu);
    /* Before allocation, scanner8002A12C calls80029E7C. Category0/high0
     * becomes10h at80029EF8 unless PLAY+68==3 bypasses that state step.
     * Scanner8002A254..264 then ORs1 into byte0. Reset8002A380/384
     * restores byte3's low nibble and byte0's authored70h bits.
     * Accept four complete source-proven words; all other bytes stay exact. */
    return flags<=1 && (state==0 || state==0x10) &&
        psx_mod_read_word(0x8006DC8Cu)==0x800F301Cu &&
        psx_mod_read_word(0x800F308Cu)==0x800EC678u &&
        psx_mod_read_word(0x800F2B0Cu)==(0x00011C00u|flags|(state<<24)) &&
        psx_mod_read_word(0x800F2B10u)==0x06300610u;
}
static int recycle_portal_eligible(unsigned seat) {
    unsigned active=seat?p2.body[0]:psx_mod_read_byte(PLAYER);
    unsigned visible=seat?p2.body[3]:psx_mod_read_byte(PLAYER+3);
    unsigned phase=seat?p2.body[4]:psx_mod_read_byte(PLAYER+4);
    unsigned action=seat?p2.body[5]:psx_mod_read_byte(PLAYER+5);
    unsigned hp=seat?p2.body[0x5C]:psx_mod_read_byte(PLAYER+0x5C);
    unsigned locked=seat?(p2.body[0x7A]|p2.body[0xD0]|p2.body[0xD4]):
        (psx_mod_read_byte(PLAYER+0x7A)|psx_mod_read_byte(PLAYER+0xD0)|psx_mod_read_byte(PLAYER+0xD4));
    return life.status[seat]==MMX6_COOP_ALIVE && active && visible && phase==1 && action>=2 &&
        hp && !(hp&0x80) && !locked && !scene_passenger(seat);
}
static int recycle_portal_contact(CPUState *cpu,uint32_t address) {
    /* Already projected survivor/menu/scene worlds use their native owner.
     * Both living actors are required: a phase0/no-passenger scene could end
     * before the next native portal setup establishes its deferred locks. */
    if(address!=0x800EC780u || cpu->gpr[31]!=0x800EC70Cu || scene_call || inside ||
       zero_world || zero_projected || !stage_call || !ready || !enrolled || failed ||
       scene_owner || scene_phase || psx_mod_read_byte(PLAY)!=0x0A ||
       psx_mod_read_byte(PLAY+1) || psx_mod_read_byte(PLAY+12)!=4 || psx_mod_read_byte(PLAY+13) ||
       psx_mod_read_byte(PLAY+0x0F) || psx_mod_read_byte(PLAY+0x10) ||
       psx_mod_read_byte(PLAY+0x1C) || psx_mod_read_byte(0x80097424u) ||
       psx_mod_read_byte(PLAYER+2) || p2.body[2]!=1 ||
       !recycle_portal_eligible(0) || !recycle_portal_eligible(1))return 0;
    uint32_t actor=cpu->gpr[4];
    if(actor<0x8008EF48u || actor>=0x80090C88u || (actor-0x8008EF48u)%0x9Cu ||
       !(psx_mod_read_byte(actor)&1) || psx_mod_read_byte(actor+1)!=0x1C ||
       psx_mod_read_byte(actor+2)!=1 || psx_mod_read_byte(actor+4)!=1 ||
       psx_mod_read_byte(actor+5)!=1 || psx_mod_read_byte(actor+6) ||
       psx_mod_read_word(actor+0x10)!=0x800F2B0Cu ||
       psx_mod_read_word(actor+0x50)!=0x800F38BCu || psx_mod_read_word(actor+0x54)!=0x800F38C0u ||
       psx_mod_read_word(actor+0x68)!=0x800F38B8u || !recycle_portal_source())return 0;
    uint32_t context[4]={address,actor,0,0};STATE_WORDS(restore_portal,47,context,4);
    scene_call=1;
    /* Original pure geometry first. A simultaneous contact retains P1 priority. */
    if(guest(cpu,0x8002D654u,actor,PLAYER)) {
        scene_call=0;STATE_POP(restore_portal);return 0;
    }
    inside=1;enter_zero();
    uint32_t hit=guest(cpu,0x8002D654u,actor,PLAYER);
    context[2]=hit;STATE_UPDATE(restore_portal,context);
    uint32_t result=0;
    if(hit) {
        result=guest(cpu,address,actor,cpu->gpr[5]);
        context[3]=result;STATE_UPDATE(restore_portal,context);
        /* Native contact owns action2/+84. Shared locks and transition flags
         * are still untouched until later original portal updates write them. */
        if(psx_mod_read_byte(actor+5)==2 && !psx_mod_read_byte(actor+6))
            scene_begin(1,address);
        leave_zero_context(1);
    } else leave_zero();
    inside=0;scene_call=0;STATE_POP(restore_portal);
    if(!hit)return 0;
    cpu->gpr[2]=result;
    return 1;
}
/* F147: let an already voluntary outgoing beam finish before the original
 * portal commits its new section. EC880 dispatches this void phase callback
 * through F3928 and ignores v0. At counter28, EC8F8's next call increments
 * to29, requests the native fade, writes PLAY+0F=41 and advances phase2.
 * Defer only that final call. Do not replay a prefix, alter its timer, move
 * a body or create an arrival: scene_tick phase0 already runs original3674C
 * during the primary's native lock. Native state3 alone completes departure;
 * the ordinary callback then resumes and commits its own original writes. */
static int recycle_portal_departure_wait(CPUState *cpu,uint32_t address) {
    if(address!=0x800EC8F8u || cpu->gpr[31]!=0x800EC8ACu ||
       inside || scene_call || zero_world || zero_projected || private_draw || view_call ||
       !stage_call || !ready || !enrolled || failed || scene_owner!=1 || scene_phase ||
       life.status[0]!=MMX6_COOP_ALIVE || life.status[1]!=MMX6_COOP_LEAVING ||
       psx_mod_read_byte(PLAY)!=10 || psx_mod_read_byte(PLAY+1) ||
       psx_mod_read_byte(PLAY+12)!=4 || psx_mod_read_byte(PLAY+13) ||
       psx_mod_read_byte(PLAY+0x0F) || psx_mod_read_byte(PLAY+0x10)!=2 ||
       !(psx_mod_read_byte(PLAYER)&1u) || !psx_mod_read_byte(PLAYER+0x5C) ||
       (psx_mod_read_byte(PLAYER+0x5C)&0x80u) ||
       !(p2.body[0]&1u) || p2.body[4]!=1 || !p2.body[0x5C] || (p2.body[0x5C]&0x80u))return 0;
    uint32_t actor=cpu->gpr[4];
    if(actor<0x8008EF48u || actor>=0x80090C88u || (actor-0x8008EF48u)%0x9Cu ||
       !(psx_mod_read_byte(actor)&1u) || psx_mod_read_byte(actor+1)!=0x1C ||
       psx_mod_read_byte(actor+2)!=1 || psx_mod_read_byte(actor+4)!=1 ||
       psx_mod_read_byte(actor+5)!=2 || psx_mod_read_byte(actor+6)!=1 ||
       psx_mod_read_half(actor+0x7C)!=28 || psx_mod_read_word(actor+0x10)!=0x800F2B0Cu ||
       psx_mod_read_half(actor+10)!=1552 || psx_mod_read_half(actor+14)!=1584 ||
       psx_mod_read_word(actor+0x50)!=0x800F38BCu ||
       psx_mod_read_word(actor+0x54)!=0x800F38C0u ||
       psx_mod_read_word(actor+0x68)!=0x800F38B8u || !recycle_portal_source())return 0;
    return 1; /* Void callback deferred; preserve CPU and every native byte. */
}
