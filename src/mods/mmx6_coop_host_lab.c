/* Development-only candidate. See COOP_HOST_LAB_CONTRACT; no broad policy. */
#include "mmx6_coop_host_lab.h"
#if defined(PSX_MOD_NETPLAY_HOST_CATALOG_API) && PSX_MOD_NETPLAY_HOST_CATALOG_API >= 2
#include "execution_profile.h"
#include "mmx6_coop_host_lab_contract.h"
#include <string.h>
#ifndef MMX6_ENABLE_LOOPBACK_HOST_LAB
#define MMX6_ENABLE_LOOPBACK_HOST_LAB 0
#endif
#if defined(_WIN32) && defined(_WIN64) && defined(__MINGW64__) && defined(__x86_64__) && defined(__clang__) && __clang_major__ == 22 && __clang_minor__ == 1 && __clang_patchlevel__ == 8
#define MMX6_HOST_LAB_COMPILER 1
#else
#define MMX6_HOST_LAB_COMPILER 0
#endif
#if defined(PSX_PGXP) && PSX_PGXP
#define MMX6_HOST_LAB_VARIANT 0
#else
#define MMX6_HOST_LAB_VARIANT 1
#endif
static int lab_sha256(const char *text){
    unsigned nonzero=0;
    if(!text||strlen(text)!=64)return 0;
    for(unsigned i=0;i<64;++i){unsigned c=(unsigned char)text[i];
        if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))return 0;
        nonzero|=c!='0';}
    return nonzero!=0;
}
static int lab_context_eligible(const PSXModNetplayHostStartup *c,const char *execution){
    if(!c||!execution||strcmp(execution,MMX6_HOST_LAB_EXECUTION_ID))return 0;
    unsigned image_nonzero=0;
    if(!c->actual_executable_sha256)return 0;
    for(unsigned i=0;i<32;++i)image_nonzero|=c->actual_executable_sha256[i];
    /* API2 documents zero players/mask as all configured slots. */
    int players=c->player_count?c->player_count:c->slot_count;
    uint32_t mask=c->occupied_mask?c->occupied_mask:3u;
    return image_nonzero&&c->cpu.architecture==PSX_HOST_ARCH_X64&&c->cpu.features_known==1&&
        c->cpu.features==MMX6_HOST_LAB_FEATURES&&
        c->compiled_backends==PSX_HOST_BACKEND_ENHANCED&&c->available_backends==PSX_HOST_BACKEND_ENHANCED&&
        c->fp_contract==2&&c->interpreted_overlays_sealed==1&&c->builtin_linked_bios==1&&
        c->builtin_bios_image_id&&!strcmp(c->builtin_bios_image_id,MMX6_HOST_LAB_BIOS_ID)&&
        c->builtin_bios_image_wordsum==MMX6_HOST_LAB_BIOS_WORDSUM&&
        c->direct_loopback_scope==1&&c->slot_count==2&&players==2&&mask==3&&c->rollback==0&&
        c->loading_enabled==1&&c->renderer==1&&c->retained_texture_banks==1&&c->aspect_index==0&&
        c->declared_build_manifest_schema==1&&lab_sha256(c->declared_build_manifest_sha256);
}
static int lab_title_eligible(const PSXModNetplayProfile *p){
    return p&&p->plugin_id&&!strcmp(p->plugin_id,"mmx6.local-coop.prototype")&&
        p->compatibility_id&&!strcmp(p->compatibility_id,MMX6_HOST_LAB_TITLE_COMPATIBILITY)&&
        !p->rollback_supported&&!p->savestates_supported&&p->skip_bios_intro==1&&
        p->requires_retained_texture_banks==1&&p->state_digest&&
        p->loading_package_id&&!strcmp(p->loading_package_id,"mmx6.enhancement.seamless-loading")&&
        p->loading_feature_id&&!strcmp(p->loading_feature_id,"seamless-loading")&&
        p->loading_plugin_id&&!strcmp(p->loading_plugin_id,"mmx6.seamless");
}
int mmx6_coop_lab_host_profiles(const PSXModNetplayHostStartup *context,PSXHostProfileCatalog *out){
    if(!out)return 0;
    out->rules=NULL;out->count=0;
    if(!MMX6_ENABLE_LOOPBACK_HOST_LAB||!MMX6_HOST_LAB_COMPILER||!MMX6_HOST_LAB_VARIANT||!PSX_EXECUTION_ENHANCED||
       !lab_context_eligible(context,PSX_EXECUTION_ID)||!lab_title_eligible(psx_mod_netplay_profile()))return 0;
    static const PSXHostProfileRule rule={
        .profile=MMX6_HOST_LAB_PROFILE,.revision=MMX6_HOST_LAB_REVISION,.priority=1,
        .flags=PSX_HOST_PROFILE_DIRECT_LOOPBACK,.implementation_count=1,
        .qualification=MMX6_HOST_LAB_QUALIFICATION_BYTES,
        .implementations={{PSX_HOST_BACKEND_ENHANCED,1u<<PSX_HOST_ARCH_X64,MMX6_HOST_LAB_FEATURES}}
    };
    out->rules=&rule;out->count=1;return 1;
}
#endif
