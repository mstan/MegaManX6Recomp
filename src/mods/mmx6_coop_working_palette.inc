/* Native stage/section type5 WORKING palettes differ from type9 SOURCE
 * palettes. 800140B4..14124 chooses live native tables; 800154D0..15520
 * installs type5 at SCRATCH+28 and type9 at SCRATCH+24. Stage13 can rewrite
 * its selector from auxiliary8006DB40 (records52..72). All payload caches
 * here are immutable mounted resources; live selectors remain native RAM. */
enum { WORKING_STAGE_COUNT=23,WORKING_SECTION_COUNT=2,
       WORKING_RECORD_COUNT=72 };
static uint8_t native_working_palettes[WORKING_RECORD_COUNT+1][MMX6_COOP_WORKING_PALETTE_BYTES];
static uint8_t working_palette_lengths[(WORKING_RECORD_COUNT+1)*2];
static int working_palette_assets_ready;
static uint32_t working_palette_code_hash(uint32_t at,uint32_t end) {
    uint32_t h=2166136261u;
    for(;at<end;++at)h=(h^psx_mod_read_byte(at))*16777619u;
    return h;
}
static int working_palette_source_guards(void) {
    /* Do NOT freeze/hash the mutable stage selector tables as asset data. */
    return working_palette_code_hash(0x800140B4u,0x80014124u)==0x451A419Au &&
        working_palette_code_hash(0x800154D0u,0x80015520u)==0x0B42F851u &&
        working_palette_code_hash(0x8003C4ECu,0x8003C6A4u)==0xDEAEEA14u &&
        working_palette_code_hash(0x8006DB40u,0x8006DB6Au)==0x552CE9B5u;
}
static unsigned working_palette_record(unsigned character,unsigned index) {
    return psx_mod_read_half(0x8006DA88u+character*92u+index*2u);
}
static int working_palette_prepare(const uint8_t *dat,size_t bytes,unsigned records) {
    working_palette_assets_ready=0;
    memset(native_working_palettes,0,sizeof native_working_palettes);
    memset(working_palette_lengths,0,sizeof working_palette_lengths);
    if(!records || records>WORKING_RECORD_COUNT)return 0;
    for(unsigned record=1;record<=records;++record) {
        Mmx6AssetView v;
        if(!mmx6_coop_dat_asset(dat,bytes,record,0,&v) || v.type!=5 ||
            (v.size!=0x3C00 && v.size!=MMX6_COOP_WORKING_PALETTE_BYTES))return 0;
        memcpy(native_working_palettes[record],v.data,v.size);
        working_palette_lengths[record*2]=(uint8_t)v.size;
        working_palette_lengths[record*2+1]=(uint8_t)(v.size>>8);
    }
    working_palette_assets_ready=1;
    return 1;
}
static int working_palette_index(unsigned *index) {
    unsigned stage=psx_mod_read_byte(PLAY+0x0C),section=psx_mod_read_byte(PLAY+0x0D);
    if(stage>=WORKING_STAGE_COUNT || section>=WORKING_SECTION_COUNT)return 0;
    *index=stage*WORKING_SECTION_COUNT+section;
    return 1;
}
/* 0=invalid,1=no native type5 preserve,2=authored payload seed. Records
 *25..29/52..72 provide3C00 bytes; preserve the existing extra window tail. */
static int working_palette_seed(unsigned require_payload) {
    unsigned index;
    if(!working_palette_assets_ready || !working_palette_index(&index))return 0;
    unsigned record=working_palette_record(1,index);
    if(!record)return require_payload?0:1;
    if(record>WORKING_RECORD_COUNT)return 0;
    unsigned bytes=working_palette_lengths[record*2]|(unsigned)working_palette_lengths[record*2+1]<<8;
    if(bytes!=0x3C00 && bytes!=MMX6_COOP_WORKING_PALETTE_BYTES)return 0;
    project(active_palette,native_working_palettes[record],bytes);
    return 2;
}
static void enter_zero(void);
static void leave_zero(void);
static int working_palette_native_load(CPUState *cpu,uint32_t address) {
    (void)address;
    if(!ready || !working_palette_assets_ready || failed || (inside && !zero_projected))return 0;
    /* Only the original character's exact stage-palette request. Return0
     * leaves primary loading/CD scheduling native and executes it once. */
    if(cpu->gpr[31]!=0x800140F0u && cpu->gpr[31]!=0x80014124u)return 0;
    unsigned index,character=psx_mod_read_byte(PLAY+0x38);
    if(character>1 || character!=(unsigned)!!zero_projected ||
        cpu->gpr[31]!=(character?0x80014124u:0x800140F0u) ||
        !working_palette_index(&index) ||
        cpu->gpr[4]!=working_palette_record(character,index) || cpu->gpr[5]!=1 || cpu->gpr[6]) {
        failed=1;return 0;
    }
    int seeded=working_palette_seed(0);
    if(!seeded){failed=1;return 0;}
    if(seeded==2 && enrolled && psx_mod_read_byte(PLAY)==0x0A) {
        /* A section refresh is not actor birth. Reapply only native current
         * body/variant palette rows; do not initialize HP/ammo/action. */
        if(zero_projected) {
            /* The native loader can already have changed resident palette
             * pointers inside a Zero-owned world. Reapply private rows with
             * private pointers, restoring the exact shared/native resources. */
            uint32_t restore[3]={psx_mod_read_word(SCRATCH+0x24),
                psx_mod_read_word(SCRATCH+0x28),psx_mod_read_byte(0x800C4560u)};
            STATE_WORDS(restore_palette,58,restore,3);
            psx_mod_write_word(SCRATCH+0x24,palette_source);
            psx_mod_write_word(SCRATCH+0x28,active_palette);
            guest(cpu,0x8003C4ECu,PLAYER,0);
            psx_mod_write_word(SCRATCH+0x24,restore[0]);
            psx_mod_write_word(SCRATCH+0x28,restore[1]);
            psx_mod_write_byte(0x800C4560u,(uint8_t)restore[2]);
            STATE_POP(restore_palette);
        } else {
            inside=1;
            enter_zero();
            guest(cpu,0x8003C4ECu,PLAYER,0);
            leave_zero();
            inside=0;
        }
    }
    return 0;
}
