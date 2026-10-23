#ifndef PSX_EXECUTION_PROFILE_CONFIG
#define PSX_EXECUTION_PROFILE_CONFIG "mmx6_host_lab_test_profile.h"
#endif
#include "../src/mods/mmx6_coop_host_lab.c"
#include <stdio.h>
#include <stdlib.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1);}}while(0)
#if defined(PSX_MOD_NETPLAY_HOST_CATALOG_API) && PSX_MOD_NETPLAY_HOST_CATALOG_API >= 2
#ifndef MMX6_HOST_LAB_EXPECT_OFFER
#error Explicit expected eligibility is required; do not infer a passing positive from implementation macros.
#endif
static PSXModNetplayProfile title;
static uint8_t artifact[32]={1};
static uint32_t digest(void){return 1;}
const PSXModNetplayProfile *psx_mod_netplay_profile(void){return &title;}
static PSXModNetplayHostStartup valid(void){
    PSXModNetplayHostStartup c={0};
    c.cpu=(PSXHostCPU){PSX_HOST_ARCH_X64,1,0x7f};
    c.compiled_backends=c.available_backends=PSX_HOST_BACKEND_ENHANCED;
    c.fp_contract=2;c.interpreted_overlays_sealed=c.builtin_linked_bios=c.direct_loopback_scope=1;
    c.actual_executable_sha256=artifact;
    c.declared_build_manifest_sha256="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
    c.declared_build_manifest_schema=1;c.builtin_bios_image_id="OPENBIOS";
    c.builtin_bios_image_wordsum=0xc4daeb88u;c.slot_count=c.player_count=2;c.occupied_mask=3;
    c.loading_enabled=1;c.renderer=1;c.retained_texture_banks=1;c.aspect_index=0;
    title=(PSXModNetplayProfile){.plugin_id="mmx6.local-coop.prototype",.compatibility_id="mmx6-x-zero-delay-v18",
        .skip_bios_intro=1,.state_digest=digest,.requires_retained_texture_banks=1,
        .loading_package_id="mmx6.enhancement.seamless-loading",.loading_feature_id="seamless-loading",
        .loading_plugin_id="mmx6.seamless"};
    return c;
}
static void refused(const PSXModNetplayHostStartup *c){
    CHECK(!lab_context_eligible(c,MMX6_HOST_LAB_EXECUTION_ID));
    PSXHostProfileCatalog cat={(const PSXHostProfileRule *)(uintptr_t)1,9};
    CHECK(!mmx6_coop_lab_host_profiles(c,&cat)&&!cat.rules&&!cat.count);
}
#define REJECT(field,value) do{PSXModNetplayHostStartup c=valid();c.field=(value);refused(&c);}while(0)
int main(void){
    PSXModNetplayHostStartup c=valid();CHECK(lab_context_eligible(&c,MMX6_HOST_LAB_EXECUTION_ID));
    CHECK(lab_title_eligible(&title));
    PSXHostProfileCatalog cat={0};
    CHECK(mmx6_coop_lab_host_profiles(&c,&cat)==MMX6_HOST_LAB_EXPECT_OFFER);
    if(MMX6_HOST_LAB_EXPECT_OFFER){
        CHECK(cat.count==1&&cat.rules&&cat.rules->flags==PSX_HOST_PROFILE_DIRECT_LOOPBACK);
        CHECK(!strcmp(cat.rules->profile,"mmx6.win64-clang22.loopback"));
        CHECK(cat.rules->revision==2&&cat.rules->implementation_count==1);
        PSXHostCapabilities caps;CHECK(psx_host_caps_init(&caps,&c.cpu,2,2,artifact));
        CHECK(psx_host_caps_offer(&caps,cat.rules,2)&&psx_host_caps_validate(&caps,&cat));
        CHECK(!psx_host_caps_offer(&caps,cat.rules,1));
    }else CHECK(!cat.count&&!cat.rules);
    refused(NULL);CHECK(!mmx6_coop_lab_host_profiles(&c,NULL));
    REJECT(cpu.architecture,PSX_HOST_ARCH_ARM64);REJECT(cpu.features_known,0);
    for(unsigned bit=0;bit<7;++bit)REJECT(cpu.features,0x7fu&~(1u<<bit));
    REJECT(cpu.features,0xff);REJECT(compiled_backends,1);REJECT(compiled_backends,3);
    REJECT(available_backends,0);REJECT(available_backends,1);REJECT(fp_contract,1);
    REJECT(interpreted_overlays_sealed,0);REJECT(builtin_linked_bios,0);
    REJECT(builtin_bios_image_id,"SCPH-1001");REJECT(builtin_bios_image_id,NULL);
    REJECT(builtin_bios_image_wordsum,0xc4daeb89u);REJECT(direct_loopback_scope,0);
    REJECT(slot_count,3);REJECT(slot_count,1);REJECT(player_count,1);REJECT(occupied_mask,1);
    REJECT(occupied_mask,7);REJECT(rollback,1);REJECT(loading_enabled,0);
    REJECT(renderer,0);REJECT(renderer,2);REJECT(retained_texture_banks,0);REJECT(aspect_index,1);
    REJECT(declared_build_manifest_schema,0);REJECT(declared_build_manifest_schema,2);
    REJECT(declared_build_manifest_sha256,NULL);REJECT(declared_build_manifest_sha256,"");
    REJECT(declared_build_manifest_sha256,"not-a-sha256");
    REJECT(declared_build_manifest_sha256,"0000000000000000000000000000000000000000000000000000000000000000");
    REJECT(declared_build_manifest_sha256,"z123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef");
    REJECT(actual_executable_sha256,NULL);uint8_t zero[32]={0};REJECT(actual_executable_sha256,zero);
    c=valid();CHECK(!lab_context_eligible(&c,"bad-contract"));CHECK(!lab_context_eligible(&c,NULL));
    c.player_count=0;c.occupied_mask=0;CHECK(lab_context_eligible(&c,MMX6_HOST_LAB_EXECUTION_ID));
    c=valid();title.compatibility_id="mmx6-x-zero-delay-v14";CHECK(!lab_title_eligible(&title));
    CHECK(!mmx6_coop_lab_host_profiles(&c,&cat));
    c=valid();title.compatibility_id="mmx6-x-zero-delay-v15";CHECK(!lab_title_eligible(&title));
    CHECK(!mmx6_coop_lab_host_profiles(&c,&cat));
    c=valid();title.rollback_supported=1;CHECK(!lab_title_eligible(&title));
    c=valid();title.savestates_supported=1;CHECK(!lab_title_eligible(&title));
    c=valid();title.state_digest=NULL;CHECK(!lab_title_eligible(&title));
    c=valid();title.requires_retained_texture_banks=0;CHECK(!lab_title_eligible(&title));
    c=valid();title.loading_plugin_id="other-loader";CHECK(!lab_title_eligible(&title));
    printf("lab eligibility: PASS (actual offer=%d; no native qualification)\n",MMX6_HOST_LAB_EXPECT_OFFER);
    return 0;
}
#else
int main(void){puts("old SDK: catalog unavailable; compilation remains supported");return 0;}
#endif
