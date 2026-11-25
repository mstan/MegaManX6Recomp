/* Exercise the actual policy with the existing native-startup contract fixture.
 * This supplies no native LAN, rendering or performance qualification. */
#define main legacy_host_lab_fixture_main
#include "test_mmx6_coop_host_lab.c"
#undef main
#if defined(PSX_MOD_NETPLAY_HOST_CATALOG_API) && PSX_MOD_NETPLAY_HOST_CATALOG_API >= 2
#include "psx_sha256.h"
#ifndef MMX6_RELEASE_HOST_EXPECT_OFFER
#error Explicit expected release eligibility is required.
#endif
static void release_refused(PSXModNetplayHostStartup c){
    PSXHostProfileCatalog cat={(const PSXHostProfileRule *)(uintptr_t)1,9};
    CHECK(!mmx6_coop_release_host_profiles(&c,&cat)&&!cat.rules&&!cat.count);
}
#define RELEASE_REJECT(field,value) do{PSXModNetplayHostStartup c=valid();c.direct_loopback_scope=0;c.field=(value);release_refused(c);}while(0)
int main(void){
    PSXModNetplayHostStartup c=valid();c.direct_loopback_scope=0;c.cpu.features=0x3f;
    const uint8_t identity[32]=MMX6_RELEASE_HOST_QUALIFICATION_BYTES;
    const uint8_t old_identity[32]=MMX6_PORTABLE_CPU_HOST_LAB_QUALIFICATION_BYTES;
    uint8_t actual[32];
    psx_sha256_compute((const uint8_t *)MMX6_RELEASE_HOST_POLICY,strlen(MMX6_RELEASE_HOST_POLICY),actual);
    CHECK(!memcmp(identity,actual,32)&&memcmp(identity,old_identity,32));
    CHECK(strcmp(MMX6_RELEASE_HOST_PROFILE,MMX6_HOST_LAB_PROFILE));
    CHECK(strcmp(MMX6_RELEASE_HOST_PROFILE,MMX6_PORTABLE_CPU_HOST_LAB_PROFILE));
    PSXHostSelection fixture={0};strcpy(fixture.profile,MMX6_RELEASE_HOST_PROFILE);
    fixture.revision=MMX6_RELEASE_HOST_REVISION;fixture.flags=PSX_HOST_PROFILE_PORTABLE;
    memcpy(fixture.qualification,identity,32);
    /* A normal profile can never authorize agreed LAB checkpoint mutations. */
    CHECK(!mmx6_coop_lab_selection_matches(&fixture));
    PSXHostProfileCatalog cat={0};
    CHECK(mmx6_coop_release_host_profiles(&c,&cat)==MMX6_RELEASE_HOST_EXPECT_OFFER);
    CHECK(mmx6_coop_host_profiles(&c,&cat)==MMX6_RELEASE_HOST_EXPECT_OFFER);
    if(MMX6_RELEASE_HOST_EXPECT_OFFER){
        CHECK(cat.count==1&&cat.rules);
        CHECK(!strcmp(cat.rules->profile,MMX6_RELEASE_HOST_PROFILE));
        CHECK(cat.rules->revision==2&&cat.rules->flags==PSX_HOST_PROFILE_PORTABLE);
        CHECK(cat.rules->implementation_count==1&&!memcmp(cat.rules->qualification,identity,32));
        CHECK(cat.rules->implementations[0].backend==PSX_HOST_BACKEND_ENHANCED);
        CHECK(cat.rules->implementations[0].architectures==(1u<<PSX_HOST_ARCH_X64));
        CHECK(cat.rules->implementations[0].required_features==0);
        /* Distinct real CPU masks agree without hiding their capabilities. */
        PSXHostCapabilities peers[2];
        for(unsigned i=0;i<2;++i){
            PSXHostCPU cpu={PSX_HOST_ARCH_X64,1,i?0x3fu:0x7fu};
            CHECK(psx_host_caps_init(peers+i,&cpu,2,2,artifact));
            CHECK(psx_host_caps_offer(peers+i,cat.rules,2));
            CHECK(psx_host_caps_validate(peers+i,&cat));
        }
        uint8_t session[32]={2};PSXHostMatch match;
        psx_host_match_init(&match);
        CHECK(psx_host_match_select(&match,peers,2,&cat,session)==PSX_HOST_OK);
        CHECK(!strcmp(match.selected.profile,MMX6_RELEASE_HOST_PROFILE));
        CHECK(match.selected.flags==PSX_HOST_PROFILE_PORTABLE);
        CHECK(!mmx6_coop_lab_selection_matches(&match.selected));
        peers[1].build[0]^=2;psx_host_match_init(&match);
        CHECK(psx_host_match_select(&match,peers,2,&cat,session)==PSX_HOST_BUILD_MISMATCH);
        peers[1].build[0]^=2;peers[1].offers[0].revision++;
        CHECK(!psx_host_caps_validate(peers+1,&cat));
        peers[1].offers[0].revision--;peers[1].offers[0].qualification[0]^=1;
        CHECK(!psx_host_caps_validate(peers+1,&cat));
        c.cpu.features=0;CHECK(mmx6_coop_host_profiles(&c,&cat)&&cat.count==1);
        c.cpu.features=0x7f;c.direct_loopback_scope=1;
        CHECK(mmx6_coop_host_profiles(&c,&cat)&&cat.count==1);
        c.player_count=0;c.occupied_mask=0;CHECK(mmx6_coop_host_profiles(&c,&cat));
    }
    CHECK(!mmx6_coop_release_host_profiles(NULL,&cat)&&!cat.rules&&!cat.count);
    CHECK(!mmx6_coop_release_host_profiles(&c,NULL));
    RELEASE_REJECT(cpu.architecture,PSX_HOST_ARCH_ARM64);
    RELEASE_REJECT(cpu.features_known,0);RELEASE_REJECT(cpu.features,0x80);
    RELEASE_REJECT(compiled_backends,PSX_HOST_BACKEND_REFERENCE);
    RELEASE_REJECT(compiled_backends,3);RELEASE_REJECT(available_backends,0);
    RELEASE_REJECT(available_backends,3);RELEASE_REJECT(fp_contract,1);
    RELEASE_REJECT(interpreted_overlays_sealed,0);RELEASE_REJECT(builtin_linked_bios,0);
    RELEASE_REJECT(builtin_bios_image_id,"SCPH-1001");RELEASE_REJECT(builtin_bios_image_id,NULL);
    RELEASE_REJECT(builtin_bios_image_wordsum,0xc4daeb89u);RELEASE_REJECT(direct_loopback_scope,2);
    RELEASE_REJECT(slot_count,1);RELEASE_REJECT(slot_count,3);
    RELEASE_REJECT(player_count,1);RELEASE_REJECT(occupied_mask,1);RELEASE_REJECT(occupied_mask,7);
    RELEASE_REJECT(rollback,1);RELEASE_REJECT(loading_enabled,0);
    RELEASE_REJECT(renderer,0);RELEASE_REJECT(renderer,2);RELEASE_REJECT(retained_texture_banks,0);
    RELEASE_REJECT(aspect_index,1);RELEASE_REJECT(actual_executable_sha256,NULL);
    uint8_t zero[32]={0};RELEASE_REJECT(actual_executable_sha256,zero);
    RELEASE_REJECT(declared_build_manifest_schema,0);RELEASE_REJECT(declared_build_manifest_schema,2);
    RELEASE_REJECT(declared_build_manifest_sha256,NULL);RELEASE_REJECT(declared_build_manifest_sha256,"bad");
    RELEASE_REJECT(declared_build_manifest_sha256,"0000000000000000000000000000000000000000000000000000000000000000");
    c=valid();title.compatibility_id="other";release_refused(c);
    c=valid();title.rollback_supported=1;release_refused(c);
    c=valid();title.savestates_supported=1;release_refused(c);
    c=valid();title.state_digest=NULL;release_refused(c);
    c=valid();title.skip_bios_intro=0;release_refused(c);
    c=valid();title.requires_retained_texture_banks=0;release_refused(c);
    c=valid();title.loading_plugin_id="other";release_refused(c);
#if defined(PSX_MOD_NETPLAY_SETTINGS_LOADING_API) && PSX_MOD_NETPLAY_SETTINGS_LOADING_API >= 1
    c=valid();title.settings_package_id="other";release_refused(c);
    c=valid();title.settings_feature_id="other";release_refused(c);
#endif
    puts("normal host policy and separate LAB authority checked; native LAN qualification remains required");
    return 0;
}
#else
int main(void){puts("old SDK: normal catalog unavailable; offline compilation remains supported");return 0;}
#endif
